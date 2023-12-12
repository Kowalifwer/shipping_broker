from typing import Dict, Tuple, Callable, Coroutine, Any, Literal, List
import asyncio

from pymongo import MongoClient
from pymongo.errors import ConnectionFailure

from setup import email_client, openai, db
from realtime_status_logger import live_logger
from mail import EmailMessageAdapted
from db import MongoEmail

async def mailbox_read_producer(stoppage_event: asyncio.Event, queue: asyncio.Queue):
    # 1. Read all UNSEEN emails from the mailbox, every 5 seconds, or if email queue is processed.

    attempt_interval = 5 # seconds

    while not stoppage_event.is_set():

        email_generator = email_client.endless_email_read_generator(
            n=9999,
            batch_size=50,

            most_recent_first=True,
            unseen_only=False,
            set_to_read=False,
            remove_undelivered=True
        )

        async for email_batch in email_generator:
            emails = email_batch
            batch_processed = False # This flag will indicate when it is time to fetch the next batch of emails

            while not batch_processed: # Will continuosuly try to add emails to the queue, until the batch is processed.

                if isinstance(emails, str):
                    live_logger.report_to_channel("error", f"Error reading emails from mailbox. {emails}. Closing producer.")
                    break

                if isinstance(emails, list) and not emails:
                    live_logger.report_to_channel("info", f"No emails found in mailbox.")
                    break
                
                email_iterator = iter(emails) # needed as a way to track exhaustion of iterator and thus the emails, and to add remaining emails to the start of the list, to be processed in the next iteration

                for count, email in enumerate(email_iterator, start=1):
                    try:
                        if stoppage_event.is_set(): # if producer got stopped in the middle of processing emails, then we must unset the read flag for the remaining emails
                            ##for remaining emails, unset the read flag
                            # email_ids = [email.id] + [email.id for email in email_iterator]
                            # asyncio.create_task(email_client.set_email_seen_status(email_ids, False))
                            live_logger.report_to_channel("warning", f"Failed to add whole email batch to queue. Producer closing before more space free'd up. Cleanup in progress.")
                            live_logger.report_to_channel("info", f"Producer closed verified.")
                            return

                        queue.put_nowait(email)
                        live_logger.report_to_channel("info", f"Email {count} placed in queue.")

                    except asyncio.QueueFull:
                        emails = [email] + emails[count:] # add the remaining emails to the start of the list, to be processed in the next iteration
                        live_logger.report_to_channel("warning", f"{queue.qsize()}/{queue.maxsize} emails in messenger queue - waiting for queue to free up space. Emails waiting to be added by producer: {len(emails)}")
                        await asyncio.sleep(attempt_interval)
                        break

                # If emails got exhausted (also cover the edge case process getting stopped, on the very LAST email, causing exhaustion but not success of whole operation)
                if len(list(email_iterator)) == 0 and not stoppage_event.is_set():
                    live_logger.report_to_channel("info", f"Full email batch added to MQ succesfully.")
                    batch_processed = True

                    await asyncio.sleep(0.2)

    live_logger.report_to_channel("info", f"Producer closed verified.")


async def mailbox_read_consumer(stoppage_event: asyncio.Event, queue: asyncio.Queue):
    # 2. Process all emails in the queue, every 10 seconds, or if email queue is processed.
    while not stoppage_event.is_set():
        try:
            email = queue.get_nowait() # get email from queue
        except asyncio.QueueEmpty:
            await asyncio.sleep(1)
            continue

        email_added = await add_email_to_db(email)

        if not email_added:
            live_logger.report_to_channel("warning", f"Email with id {email.id} already in database. Ignoring.")
            continue
        else:
            live_logger.report_to_channel("info", f"Email with id {email.id} added to database.")
    
    live_logger.report_to_channel("info", f"Consumer closed verified.")

async def queue_capacity_producer(stoppage_event: asyncio.Event, queue: asyncio.Queue):
    # 3. Check the queue capacity every 5 seconds, and report to the live logger
    from uuid import uuid4
    q_id = uuid4()
    while not stoppage_event.is_set():
        await asyncio.sleep(0.2)
        live_logger.report_to_channel("capacities", f"{queue.qsize()},{queue.maxsize},{q_id}", False)
    
    live_logger.report_to_channel("info", f"Queue capacity producer closed verified.")

async def flush_queue(stoppage_event: asyncio.Event, queue: asyncio.Queue):

    ##remove all items from queue
    while not queue.empty() and not stoppage_event.is_set():
        queue.get_nowait()
        await asyncio.sleep(0.1)
    
    live_logger.report_to_channel("info", f"Queue flushed.")

async def db_listens_for_new_emails_producer(stoppage_event: asyncio.Event, queue: asyncio.Queue):
    attempt_interval = 5 # seconds

    # 4. Listen for new emails being added to the database, and add them to the queue
    collection = db["emails"]
    async with collection.watch() as stream:
        async for change in stream:
            retry = True
            while retry:
                if change["operationType"] == "insert":
                    db_object = change["fullDocument"]
                    email = MongoEmail(**db_object)
                    try:
                        queue.put_nowait(email)
                        live_logger.report_to_channel("info", f"Email with id {email.id} added to queue.")
                        break # break out of the while loop
                    except asyncio.QueueFull:
                        live_logger.report_to_channel("warning", f"{queue.qsize()}/{queue.maxsize} emails in messenger queue - waiting for queue to free up space.")
                        await asyncio.sleep(attempt_interval)
                    finally:
                        if stoppage_event.is_set():
                            live_logger.report_to_channel("info", f"Producer closed verified.")
                            return

MQ_MAILBOX: asyncio.Queue[EmailMessageAdapted] = asyncio.Queue(maxsize=500) # A maximum buffer of 10 emails
MQ_GPT_EMAIL_TO_DB = asyncio.Queue(maxsize=150) # A maximum buffer of 10 emails

# Please respect the complex signature of this dictionary. You have to create your async functions with the specified signature, and add them to the dictionary below.
MQ_HANDLER: Dict[str, Tuple[
        Callable[[asyncio.Event, asyncio.Queue], Coroutine[Any, Any, None]], 
        asyncio.Event,
        asyncio.Queue]
    ] = {
    "mailbox_read_producer": (mailbox_read_producer, asyncio.Event(), MQ_MAILBOX),   
    "mailbox_read_consumer": (mailbox_read_consumer, asyncio.Event(), MQ_MAILBOX),

    "db_listens_for_new_emails_producer": (db_listens_for_new_emails_producer, asyncio.Event(), MQ_GPT_EMAIL_TO_DB),


    # "gpt_email_producer": (gpt_email_producer, asyncio.Event(), MQ_GPT_EMAIL_TO_DB),
    # "gpt_email_consumer": (gpt_email_consumer, asyncio.Event(), MQ_GPT_EMAIL_TO_DB),


    # temporary helper methods for testing.
    "queue_capacity_producer": (queue_capacity_producer, asyncio.Event(), MQ_MAILBOX),
    "flush_queue_producer": (flush_queue, asyncio.Event(), MQ_MAILBOX),
}
"""
This dictionary (MQ_HANDLER) stores the callables for different message queue handlers, along with the event and queue objects that they will be using.
The functionality should be handled by adding new methods in process_manager.py, and then adding them to this dictionary, following the correct format.
"""

def setup_to_frontend_template_data() -> List[Dict[str, str]]:
    """A helper function to convert the MQ_HANDLER dictionary into a format that can be used by the frontend template."""

    buttons = []
    for key in MQ_HANDLER:
        title_words = key.split("_")
        task_type = title_words[-1]
        title = " ".join(title_words).capitalize()

        buttons.append({
            "name": title,
            "start_url": f"/start/{task_type}/{key}",
            "end_url": f"/end/{task_type}/{key}"
        })
    return buttons

async def add_email_to_db(email_message: EmailMessageAdapted) -> bool:
    """Add email to database, if it doesn't already exist. Return True if added, False if already exists."""

    try:
        email_in_db = await db["emails"].find_one({
            "$or": [
                {"id": email_message.id},
                {"body": email_message.body}
                # {"subject": email_message.subject, "sender": email_message.sender},
            ]
        })
    except Exception as e:
        live_logger.report_to_channel("error", f"Error finding email in database. {e}")
        return False

    if email_in_db:
        # TODO: consider updating the fields on the duplicate object, such as date_recieved or store a counter of duplicates, if this into will be useful later.
        return False

    await db["emails"].insert_one(email_message.mongo_db_object.model_dump())

    return True
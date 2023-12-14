from typing import Dict, Tuple, Callable, Coroutine, Any, Literal, List, Union, Optional
import asyncio

from pymongo import MongoClient
from pymongo.errors import ConnectionFailure

from setup import email_client, openai, db
from realtime_status_logger import live_logger
from mail import EmailMessageAdapted
from db import MongoEmail
from gpt_prompts import prompt
import json

async def mailbox_read_producer(stoppage_event: asyncio.Event, queue: asyncio.Queue[EmailMessageAdapted]):
    # 1. Read all UNSEEN emails from the mailbox, every 5 seconds, or if email queue is processed.

    attempt_interval = 5 # seconds

    while not stoppage_event.is_set():

        email_generator = email_client.endless_email_read_generator(
            n=9999,
            batch_size=50,

            most_recent_first=True,
            unseen_only=True,
            set_to_read=False,
            remove_undelivered=True
        )

        async for email_batch in email_generator:
            batch_processed = False # This flag will indicate when it is time to fetch the next batch of emails

            while not batch_processed: # Will continuosuly try to add emails to the queue, until the batch is processed.

                if isinstance(email_batch, str):
                    live_logger.report_to_channel("error", f"Error reading emails from mailbox. Closing producer.")
                    break

                if isinstance(email_batch, list) and not email_batch:
                    live_logger.report_to_channel("info", f"No emails found in mailbox.")
                    break
                
                for count, email in enumerate(email_batch, start=1):

                    while True: # Will continuously try to add emails to the queue, until the queue has space. Make sure to break out of this loop when the email is added to the queue.
                        try:
                            if stoppage_event.is_set(): # if producer got stopped in the middle of processing emails, then we must unset the read flag for the remaining emails
                                ##for remaining emails, unset the read flag
                                # email_ids = [email.id] + [email.id for email in emails[count:]]
                                # asyncio.create_task(email_client.set_email_seen_status(email_ids, False))
                                live_logger.report_to_channel("warning", f"Failed to add whole email batch to queue. Producer closing before more space free'd up. Cleanup in progress.")
                                live_logger.report_to_channel("info", f"Producer closed verified.")
                                return

                            queue.put_nowait(email)
                            live_logger.report_to_channel("info", f"Email {count} placed in queue.")
                            break # break out of the while loop

                        except asyncio.QueueFull:
                            live_logger.report_to_channel("warning", f"{queue.qsize()}/{queue.maxsize} emails in messenger queue - waiting for queue to free up space. Emails waiting to be added by producer: {len(emails)}")
                            await asyncio.sleep(attempt_interval)

                # If full email batch was added to queue, then break out of the while loop
                if stoppage_event.is_set():
                    live_logger.report_to_channel("warning", f"producer closed verified (after adding a full batch of emails to queue)")
                    return

                live_logger.report_to_channel("info", f"Full email batch added to MQ succesfully.")
                batch_processed = True

                await asyncio.sleep(0.2)

    live_logger.report_to_channel("info", f"Producer closed verified.")

async def mailbox_read_consumer(stoppage_event: asyncio.Event, queue_to_fetch_from: asyncio.Queue[EmailMessageAdapted], queue_to_add_to: asyncio.Queue[str]):
    # 2. Process all emails in the queue, every 10 seconds, or if email queue is processed.
    while not stoppage_event.is_set():
        try:
            email = queue_to_fetch_from.get_nowait() # get email from queue
        except asyncio.QueueEmpty:
            await asyncio.sleep(1)
            continue

        email_added = await add_email_to_db(email)
        if email_added == False:
            continue
        
        # TODO: This currently also acts as a producer (until it is decided what the final approach will be) which can cause bottlenecks. 
        # Refer to: https://github.com/Kowalifwer/shipping_broker/issues/2
        while True:
            try:
                queue_to_add_to.put_nowait(str(email_added))
                live_logger.report_to_channel("info", f"Email with id {email.id} added to queue.")
                break # break out of the while loop
            except asyncio.QueueFull:
                live_logger.report_to_channel("warning", f"{queue_to_add_to.qsize()}/{queue_to_add_to.maxsize} email id's in messenger queue - waiting for queue to free up space.")
                await asyncio.sleep(5)
                continue

    live_logger.report_to_channel("info", f"Consumer closed verified.")

async def gpt_email_consumer(stoppage_event: asyncio.Event, queue: asyncio.Queue[str], n_tasks: int = 1):
    # Summon n consumers to run concurrently, and turn emails from queue into entities using GPT-3 (THIS IS ALMOST FULLY A I/O BOUND TASK, so should not be too CPU intensive)
    for i in range(n_tasks):
        asyncio.create_task(_gpt_email_consumer(stoppage_event, queue))
    
    live_logger.report_to_channel("gpt", f"Summoned {n_tasks} GPT-3 email consumers.")

async def _gpt_email_consumer(stoppage_event: asyncio.Event, queue: asyncio.Queue[str]):
    # 5. Consume emails from the queue, and generate a response using GPT-3
    live_logger.report_to_channel("gpt", f"Starting GPT-3 email consumer.")
    while not stoppage_event.is_set():
        try:
            email_id = queue.get_nowait() # get email from queue
            await email_to_entities_via_openai(email_id)

        except asyncio.QueueEmpty:
            await asyncio.sleep(1)
            continue

        except Exception as e:
            live_logger.report_to_channel("gpt", f"Error converting email to entities via OpenAI. {e}")
            continue

async def queue_capacity_producer(stoppage_event: asyncio.Event, *queues: asyncio.Queue):
    # 3. Check the queue capacity every 5 seconds, and report to the live logger
    from uuid import uuid4
    q_ids = [str(uuid4()) for _ in queues]

    while not stoppage_event.is_set():
        for i, queue in enumerate(queues):
            live_logger.report_to_channel("capacities", f"{queue.qsize()},{queue.maxsize},{q_ids[i]}", False)

        await asyncio.sleep(0.2)
    
    live_logger.report_to_channel("info", f"Queue capacity producer closed verified.")

async def flush_queue(stoppage_event: asyncio.Event, queue: asyncio.Queue):

    ##remove all items from queue
    while not queue.empty() and not stoppage_event.is_set():
        queue.get_nowait()
        await asyncio.sleep(0.1)
    
    live_logger.report_to_channel("info", f"Queue flushed.")

MQ_MAILBOX: asyncio.Queue[EmailMessageAdapted] = asyncio.Queue(maxsize=500) # A maximum buffer of 10 emails
MQ_GPT_EMAIL_TO_DB = asyncio.Queue(maxsize=500) # A maximum buffer of 10 emails

# Please respect the complex signature of this dictionary. You have to create your async functions with the specified signature, and add them to the dictionary below.
MQ_HANDLER: Dict[str, Tuple[
        Callable[[asyncio.Event, asyncio.Queue], Coroutine[Any, Any, None]], 
        asyncio.Event,
        asyncio.Queue]
    ] = {
    "mailbox_read_producer": (mailbox_read_producer, asyncio.Event(), MQ_MAILBOX),   
    "mailbox_read_consumer": (mailbox_read_consumer, asyncio.Event(), MQ_MAILBOX, MQ_GPT_EMAIL_TO_DB), # type: ignore - temporary due to https://github.com/Kowalifwer/shipping_broker/issues/2


    "3_gpt_email_consumer": (gpt_email_consumer, asyncio.Event(), MQ_GPT_EMAIL_TO_DB), #temporarily, declare number of tasks in the function name

    # "db_listens_for_new_emails_producer": (db_listens_for_new_emails_producer, asyncio.Event(), MQ_GPT_EMAIL_TO_DB),
    # "gpt_email_producer": (gpt_email_producer, asyncio.Event(), MQ_GPT_EMAIL_TO_DB),


    # temporary helper methods for testing.
    "queue_capacity_producer": (queue_capacity_producer, asyncio.Event(), MQ_MAILBOX, MQ_GPT_EMAIL_TO_DB),
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

async def add_email_to_db(email_message: EmailMessageAdapted) -> Union[str, bool]:
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

    inserted_result = await db["emails"].insert_one(email_message.mongo_db_object.model_dump())

    if not inserted_result.acknowledged:
        live_logger.report_to_channel("error", f"Error adding email to database.")
        return False

    live_logger.report_to_channel("info", f"Email with id {email_message.id} added to database.")

    return str(inserted_result.inserted_id)

async def email_to_entities_via_openai(email_message: Union[EmailMessageAdapted, str]) -> dict:
    
    #https://github.com/openai/openai-cookbook/blob/main/examples/api_request_parallel_processor.py -> parallel processing example
    """
    Convert an email message to JSON using OpenAI ChatCompletion.

    Parameters:
    - email_message: The email message to be converted. Can be either an EmailMessageAdapted object, or a string representing the email id in the database.

    Returns:
    Union[str, dict]: The JSON representation of the email message, or an error message.

    Raises:
    - OpenAIError: If there is an error in the OpenAI API request.
    - json.JSONDecodeError: If there is an error decoding the JSON response.
    """
    if isinstance(email_message, str):
        found_email = await db["emails"].find_one({"_id": email_message})
        if not found_email:
            return {"error": f"Email with id {email_message} not found in database."}

        email_message = MongoEmail(**found_email) # type: ignore

    response = await openai.ChatCompletion.acreate(
        model="gpt-3.5-turbo-1106",
        temperature=0.2,
        # top_p=1,
        response_format={ "type": "json_object" },
        messages=[
            {"role": "system", "content": prompt.system},
            {"role": "user", "content": email_message.body} # type: ignore
        ]
    )
    json_response = response.choices[0].message.content # type: ignore

    final = json.loads(json_response)
    return final


async def db_listens_for_new_emails_producer(stoppage_event: asyncio.Event, queue: asyncio.Queue):
    """Deprecated. Until it is decided what approach to take with issue #2, this function will not be used."""

    attempt_interval = 5 # seconds

    # 4. Listen for new emails being added to the database, and add them to the queue
    collection = db["emails"]
    async with collection.watch() as stream:
        print("Listening for new emails in database.")
        async for change in stream:
            print(type(change))
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
from typing import Dict, Tuple, Callable, Coroutine, Any, Literal, List, Union, Optional
import asyncio
from openai import OpenAIError

from pydantic import ValidationError
from db import MongoShip, MongoCargo

from setup import email_client, openai_client, db
from realtime_status_logger import live_logger
from mail import EmailMessageAdapted
from db import MongoEmail, create_calculated_fields_for_ship, create_calculated_fields_for_cargo
from gpt_prompts import prompt
import json

async def mailbox_read_producer(stoppage_event: asyncio.Event, queue: asyncio.Queue[EmailMessageAdapted]):
    live_logger.report_to_channel("extra", f"Starting MULTI mailbox read producer.")
    asyncio.create_task(_mailbox_read_producer(stoppage_event, queue, False))
    # asyncio.create_task(_mailbox_read_producer(stoppage_event, queue, True))

async def _mailbox_read_producer(stoppage_event: asyncio.Event, queue: asyncio.Queue[EmailMessageAdapted], reverse=False):
    # 1. Read all UNSEEN emails from the mailbox, every 5 seconds, or if email queue is processed.

    attempt_interval = 5 # seconds

    while not stoppage_event.is_set():

        email_generator = email_client.endless_email_read_generator(
            n=9999,
            batch_size=50,

            most_recent_first=reverse,
            unseen_only=True,
            set_to_read=False,
            remove_undelivered=True,
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
                            live_logger.report_to_channel("warning", f"{queue.qsize()}/{queue.maxsize} emails in messenger queue - waiting for queue to free up space.")
                            await asyncio.sleep(attempt_interval)

                # If full email batch was added to queue, then break out of the while loop
                if stoppage_event.is_set():
                    live_logger.report_to_channel("warning", f"producer closed verified (after adding a full batch of emails to queue)")
                    return

                live_logger.report_to_channel("info", f"Full email batch added to MQ succesfully.")
                batch_processed = True

                await asyncio.sleep(0.2)
        
        # If we are here - that means the generator has been exhaused! meaning all emails have been read OR n limit has been reached.
        # Therefore, it would be a good idea to wait a bit before starting a new cycle.
        live_logger.report_to_channel("info", f"Email generator exhausted. Waiting 10 seconds before starting a new cycle.")
        await asyncio.sleep(10)

    live_logger.report_to_channel("info", f"Producer closed verified.")

async def mailbox_read_consumer(stoppage_event: asyncio.Event, queue_to_fetch_from: asyncio.Queue[EmailMessageAdapted], queue_to_add_to: asyncio.Queue[EmailMessageAdapted]):
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
                queue_to_add_to.put_nowait(email)
                live_logger.report_to_channel("info", f"Email with id {email.id} added to queue.")
                break # break out of the while loop
            except asyncio.QueueFull:
                live_logger.report_to_channel("warning", f"{queue_to_add_to.qsize()}/{queue_to_add_to.maxsize} email id's in messenger queue - waiting for queue to free up space.")
                await asyncio.sleep(5)
                continue

    live_logger.report_to_channel("info", f"Consumer closed verified.")

async def gpt_email_consumer(stoppage_event: asyncio.Event, queue: asyncio.Queue[EmailMessageAdapted], n_tasks: int = 1):
    # Summon n consumers to run concurrently, and turn emails from queue into entities using GPT-3 (THIS IS ALMOST FULLY A I/O BOUND TASK, so should not be too CPU intensive)
    for _ in range(n_tasks):
        asyncio.create_task(_gpt_email_consumer(stoppage_event, queue))
    
    live_logger.report_to_channel("gpt", f"Summoned {n_tasks} GPT-3 email consumers.")

async def _gpt_email_consumer(stoppage_event: asyncio.Event, queue: asyncio.Queue[EmailMessageAdapted]):
    # 5. Consume emails from the queue, and generate a response using GPT-3
    live_logger.report_to_channel("gpt", f"Starting GPT-3 email consumer.")
    while not stoppage_event.is_set():
        try:
            email = queue.get_nowait() # get email from queue
            gpt_response = await email_to_entities_via_openai(email)

            entries = gpt_response.get("entries", [])
            if not entries:
                live_logger.report_to_channel("error", f"Error in processing email - No entries returned from GPT-3.5.")
                return
            
            await insert_gpt_entries_into_db(entries, email)

            live_logger.report_to_channel("gpt", f"Email with id {email.id} processed by GPT-3.5. Entities added to database. Sleeping for 5 seconds.")
            await asyncio.sleep(5)

        except asyncio.QueueEmpty:
            await asyncio.sleep(2)

        except OpenAIError as e:
            live_logger.report_to_channel("gpt", f"Error converting email to entities via OpenAI. {e}")
        
        except json.JSONDecodeError as e:
            live_logger.report_to_channel("gpt", f"Error decoding JSON response from OpenAI. {e}")
        
        except Exception as e:
            live_logger.report_to_channel("gpt", f"Unhandled error in processing email. {e}")

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

# Message Queue for stage 1 - Mailbox read and add to database
MQ_MAILBOX: asyncio.Queue[EmailMessageAdapted] = asyncio.Queue(maxsize=2000)

# Message Queue for stage 2 - GPT-3.5 email processing
MQ_GPT_EMAIL_TO_DB: asyncio.Queue[EmailMessageAdapted] = asyncio.Queue(maxsize=500)

# Please respect the complex signature of this dictionary. You have to create your async functions with the specified signature, and add them to the dictionary below.
MQ_HANDLER: Dict[str, Tuple[
        Callable[[asyncio.Event, asyncio.Queue], Coroutine[Any, Any, None]], 
        asyncio.Event,
        asyncio.Queue]
    ] = {
    "mailbox_read_producer": (mailbox_read_producer, asyncio.Event(), MQ_MAILBOX),   
    "mailbox_read_consumer": (mailbox_read_consumer, asyncio.Event(), MQ_MAILBOX, MQ_GPT_EMAIL_TO_DB), # type: ignore - temporary due to https://github.com/Kowalifwer/shipping_broker/issues/2


    "1_gpt_email_consumer": (gpt_email_consumer, asyncio.Event(), MQ_GPT_EMAIL_TO_DB), #temporarily, declare number of tasks in the function name

    # "db_listens_for_new_emails_producer": (db_listens_for_new_emails_producer, asyncio.Event(), MQ_GPT_EMAIL_TO_DB),
    # "gpt_email_producer": (gpt_email_producer, asyncio.Event(), MQ_GPT_EMAIL_TO_DB),


    # temporary helper methods for testing.
    "queue_capacity_producer": (queue_capacity_producer, asyncio.Event(), MQ_MAILBOX, MQ_GPT_EMAIL_TO_DB),
    # "flush_queue_producer": (flush_queue, asyncio.Event(), MQ_MAILBOX),
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

async def email_to_entities_via_openai(email_message: EmailMessageAdapted) -> dict:
    
    #https://github.com/openai/openai-cookbook/blob/main/examples/api_request_parallel_processor.py -> parallel processing example
    """
    Convert an email message to JSON using OpenAI ChatCompletion.

    Parameters:
    - email_message: The email message to convert to JSON. An instance of EmailMessageAdapted.

    Returns:
    Union[str, dict]: The JSON representation of the email message, or an error message.

    Raises:
    - OpenAIError: If there is an error in the OpenAI API request.
    - json.JSONDecodeError: If there is an error decoding the JSON response.
    """

    response = await openai_client.chat.completions.create(
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
    if not json_response:
        raise OpenAIError("No JSON response from OpenAI.")

    final = json.loads(json_response)
    return final

async def insert_gpt_entries_into_db(entries: List[dict], email: EmailMessageAdapted) -> None:
    """Insert GPT-3.5 entries into database."""

    ignored_entries = []
    ships = []
    cargos = []
    mongo_email = email.mongo_db_object

    for entry in entries:

        entry_type = entry.get("type")
        if entry_type not in ["ship", "cargo"]:
            ignored_entries.append(entry)
            continue

        entry["email"] = mongo_email

        if entry_type == "ship":
            try:
                # Add calculated fields to ship
                ship_calculated_fields = create_calculated_fields_for_ship(entry)
                entry.update(ship_calculated_fields)

                ship = MongoShip(**entry)

                ships.append(ship.model_dump())
            except ValidationError as e:
                ignored_entries.append(entry)
                print("Error validating ship. skipping addition", e)
        
        elif entry_type == "cargo":
            try:
                # Add calculated fields to cargo
                cargo_calculated_fields = create_calculated_fields_for_cargo(entry)
                entry.update(cargo_calculated_fields)

                cargo = MongoCargo(**entry)

                cargos.append(cargo.model_dump())
            except ValidationError as e:
                ignored_entries.append(entry)
                print("Error validating cargo. skipping addition", e)


    # Insert email into MongoDB
    await db["emails"].insert_one(mongo_email.model_dump())

    if ships:
        # Insert ships into MongoDB
        await db["ships"].insert_many(ships)

    if cargos:
        # Insert cargos into MongoDB
        await db["cargos"].insert_many(cargos)
    
    live_logger.report_to_channel("gpt", f"Inserted {len(ships)} ships and {len(cargos)} cargos into database.")
    if ignored_entries:
        live_logger.report_to_channel("extra", f"Additionally, ignored {len(ignored_entries)} entries from GPT-3.5. {ignored_entries}")



async def db_listens_for_new_emails_producer(stoppage_event: asyncio.Event, queue: asyncio.Queue):
    """Deprecated. Until it is decided what approach to take with issue #2, this function will not be used."""

    attempt_interval = 5 # seconds

    # 4. Listen for new emails being added to the database, and add them to the queue
    # Note this only works if MongoDB Node is running in replica set mode, and the database is configured to use Change Streams.
    # This can be done locally by running the following command in the mongo shell:
    # rs.initiate()
    # But only if the initialized node had the proper config that allows for replica sets. Check mongo-setup mongod.conf for commented out example how I did it locally.
    # More info: https://docs.mongodb.com/manual/changeStreams/

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
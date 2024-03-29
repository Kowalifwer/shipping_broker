from typing import Dict, Tuple, Callable, Coroutine, Any, Literal, List, Union, Optional
import asyncio
from openai import OpenAIError

from pydantic import ValidationError
from db import MongoShip, MongoCargo
from jinja2 import Template, Environment, FileSystemLoader
import json
from datetime import datetime, timedelta
from bson import ObjectId

from setup import email_client, openai_client, db_client
from realtime_status_logger import live_logger
from mail import EmailMessageAdapted
from db import MongoEmail, update_ship_entry_with_calculated_fields, update_cargo_entry_with_calculated_fields, FailedEntry, MongoEmailAndExtractedEntities
from mq import scoring
from gpt_prompts import prompt_geocode_optimized as prompt
from geocoding import geocode_location_with_retry

async def mailbox_read_producer(stoppage_event: asyncio.Event, queue: asyncio.Queue[EmailMessageAdapted]):
    live_logger.report_to_channel("extra", f"Starting MULTI mailbox read producer.")
    asyncio.create_task(_mailbox_read_producer(stoppage_event, queue, True))
    # asyncio.create_task(_mailbox_read_producer(stoppage_event, queue, False))

async def _mailbox_read_producer(stoppage_event: asyncio.Event, queue: asyncio.Queue[EmailMessageAdapted], reverse=True):
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

async def mailbox_read_consumer(stoppage_event: asyncio.Event, queue_to_fetch_from: asyncio.Queue[EmailMessageAdapted], queue_to_add_to: asyncio.Queue[EmailMessageAdapted], default=True):
    # 2. Process all emails in the queue, every 10 seconds, or if email queue is processed.
    
    # create a fake queue, by pulling most recent emails from the database

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
    live_logger.report_to_channel("gpt", f"Summoned {n_tasks} GPT-3 email consumers.")
    # Summon n consumers to run concurrently, and turn emails from queue into entities using GPT-3 (THIS IS ALMOST FULLY A I/O BOUND TASK, so should not be too CPU intensive)

    semaphore = asyncio.Semaphore(n_tasks) # limit the number of concurrent tasks to n_tasks * 10
    while not stoppage_event.is_set():
        tasks = [asyncio.create_task(_gpt_email_consumer(stoppage_event, queue, semaphore)) for _ in range(n_tasks * 10)]

        await asyncio.gather(*tasks, return_exceptions=True)


    live_logger.report_to_channel("gpt", f"Consumer closed verified.")

async def _gpt_email_consumer(stoppage_event: asyncio.Event, queue: asyncio.Queue[EmailMessageAdapted], semaphore: asyncio.Semaphore):
    async with semaphore:
        # 5. Consume emails from the queue, and generate a response using GPT-3
        if stoppage_event.is_set():
            return

        try:
            email = queue.get_nowait() # get email from queue
            gpt_response = await email_to_entities_via_openai(email)

            entries = gpt_response.get("entries", [])
            if not entries:
                live_logger.report_to_channel("error", f"Error in processing email - No entries returned from GPT-3.5.")
                return
            
            await insert_gpt_entries_into_db(entries, email)

            live_logger.report_to_channel("gpt", f"Email with id {email.id} processed by GPT-3.5. Entities added to database. Sleeping for 5 seconds.")
            await asyncio.sleep(1)

        except asyncio.QueueEmpty:
            await asyncio.sleep(2)

        except OpenAIError as e:
            live_logger.report_to_channel("gpt", f"Error converting email to entities via OpenAI. {e}")
        
        except json.JSONDecodeError as e:
            live_logger.report_to_channel("gpt", f"Error decoding JSON response from OpenAI. {e}")
        
        except Exception as e:
            live_logger.report_to_channel("gpt", f"Unhandled error in processing email. {e}")

async def item_matching_producer(stoppage_event: asyncio.Event, queue: asyncio.Queue[MongoShip]):

    while not stoppage_event.is_set():

        # Fetch emails from DB, about SHIPS, from most RECENT to least recent, and add them to the queue
        # Make sure the ships "pairs_with" is an empty list, and that the ship has not been processed yet.
        date_from = datetime.utcnow() - timedelta(days=21)

        # Fields that will be counted to prioritize ships with more filled-in fields
        fields_to_count = ["name", "status", "month", "capacity", "location_geocoded"] #name, status, keyword_data - ignored for now since they will compete with more important fields

        # Create the aggregation pipeline
        pipeline = [
            # Your existing $match stage
            {
                "$match": {
                    "pairs_with": [],
                    "timestamp_created": {"$gte": date_from},
                    "location_geocoded.location.coordinates": {"$type": "array", "$size": 2},
                }
            },
            # Your existing logic to add a count of non-empty fields
            {
                "$addFields": {
                    "nonEmptyFields": {
                        "$size": {
                            "$filter": {
                                "input": {"$objectToArray": "$$ROOT"},
                                "as": "item",
                                "cond": {
                                    "$and": [
                                        {"$ne": ["$$item.v", ""]},
                                        {"$in": ["$$item.k", fields_to_count]}
                                    ]
                                }
                            }
                        }
                    }
                }
            },
            {
                "$sort": {"nonEmptyFields": -1}  # Sort before grouping to make the first document the highest priority
            },
            # Group by your specified fields to eliminate duplicates, retaining the document with the most nonEmptyFields
            {
                "$group": {
                    "_id": {
                        "name": "$name",
                        "status": "$status",
                        "capacity_int": "$capacity_int",
                        "month_int": "$month_int",
                        "location": "$location",
                        # "location_geocoded.name": "$location_geocoded.name",
                    },
                    "document": {"$first": "$$ROOT"}  # Retain the first document in each group
                }
            },
            # Replace the root with the document retained above, to get back to the original document structure
            {
                "$replaceRoot": {"newRoot": "$document"}
            },
            # Your existing sort, if necessary, applied again on the de-duplicated list
            {
                "$sort": {"nonEmptyFields": -1, "timestamp_created": -1}
            }
        ]
    
        db_cursor = db_client["ships"].aggregate(pipeline)

        async for ship in db_cursor:
            ship = MongoShip(**ship)
            print(f"Ship added to queue: {ship.name}, {ship.location_geocoded.address}, {ship.month}, {ship.capacity_int} - {ship.timestamp_created}") # type: ignore (will have an address guaranteed, based on queries above)
            await queue.put(ship)
            if stoppage_event.is_set():
                live_logger.report_to_channel("info", f"Producer closed verified.")
                return
        else:
            print("Ship cursor exchausted. Will go again in 3 seconds.")

            # Temorarily, avoid another run of the cursor, by setting the stoppage event.
            stoppage_event.set()

            await asyncio.sleep(3)

async def item_matching_consumer(stoppage_event: asyncio.Event, queue_from: asyncio.Queue[MongoShip], queue_to: asyncio.Queue[MongoShip]):
    # 6. Consume emails from the queue, and match them with other entities in the database
    while not stoppage_event.is_set():
        try:
            ship = queue_from.get_nowait() # get ship from queue
            # TODO: Check this ship was not already recently processed (i.e. timestamp_pairs_updated is None or > 1 day ago)
            # To enable idempotency basically, such that if in case we get a duplicate ship in the queue, we can just ignore it.
            matching_cargos = await match_cargos_to_ship(ship, 5)

            if not matching_cargos:
                live_logger.report_to_channel("warning", f"No matching cargos found for ship with id {str(ship.id)}.")
                continue
            
            filename = "example_matches.json"
            try:
                with open(filename, "r") as file:
                    existing_data = json.load(file)
            except FileNotFoundError:
                existing_data = []

            existing_data.append({
                "ship": ship.name,
                "ship_location": ship.location,
                "ship_location_geocoded": ship.location_geocoded,
                "ship_month": ship.month,
                "ship_email_contents": ship.email.body,
                "ship_capacity": ship.capacity_int,
                "matching_cargos": matching_cargos
            })

            with open(filename, "w") as file:
                json.dump(existing_data, file, indent=4, default=str)
                
            ship.pairs_with = [ObjectId(cargo["id"]) for cargo in matching_cargos]

            # Update ship in database
            # res = await db_client["ships"].update_one({"_id": ObjectId(ship.id)}, {"$set": {"pairs_with": ship.pairs_with, "timestamp_pairs_updated": datetime.now()}})
            # if not res.acknowledged:
            #     live_logger.report_to_channel("error", f"Error updating ship with id {str(ship.id)} in database.")
            #     continue

            while True:
                try:
                    queue_to.put_nowait(ship)
                    break
                except asyncio.QueueFull:
                    if stoppage_event.is_set():
                        live_logger.report_to_channel("info", f"Consumer closed verified.")
                        return

                    live_logger.report_to_channel("warning", f"{queue_to.qsize()}/{queue_to.maxsize} ships in matching queue - waiting for queue to free up space.")
                    await asyncio.sleep(5)
        
        except asyncio.QueueEmpty:
            await asyncio.sleep(2)
    
    live_logger.report_to_channel("info", f"Consumer closed verified.")

async def email_send_producer(stoppage_event: asyncio.Event, queue: asyncio.Queue[MongoShip]):
    # 7. Consume emails from the queue, and send emails to the relevant recipients
    while not stoppage_event.is_set():
        try:
            ship = queue.get_nowait() # get ship from queue
            if not ship.pairs_with:
                live_logger.report_to_channel("warning", f"Ship with id {str(ship.id)} has no matching cargos. CRITICAL ERROR SHOULD NOT HAPPEN!!")
                continue

            # At this point, we have a MongoShip object, with a list of id's of matching cargos.
            # That is enough to send our emails.

            # Fetch the cargoes from the database
            db_cargos = await db_client["cargos"].find({"_id": {"$in": ship.pairs_with}}).to_list(None)
            cargos = [MongoCargo(**cargo) for cargo in db_cargos]

            body = render_email_body_text({
                "cargos": cargos,
                "ship": ship,
                "email": ship.email,
            }, template_path= "email/to_ship_verbose.html")

            success = await email_client.send_email(
                to_email="shipperinho123@gmail.com",
                subject="Cargo Matching TEST",
                body=body,
            )

            if not success:
                live_logger.report_to_channel("error", f"Error sending email to {ship.email.sender}.")
                continue
        
        except asyncio.QueueEmpty:
            await asyncio.sleep(2)
    
    live_logger.report_to_channel("info", f"Producer closed verified.")

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

async def endless_trash_email_cleaner(stoppage_event: asyncio.Event):
    """This function will run until told to stop, scanning the mailbox for emails and deleting all the trash."""
    batch_size = 50

    while not stoppage_event.is_set():
        async for emails in email_client.endless_email_read_generator(n=99999, batch_size=batch_size, unseen_only=False, most_recent_first=True, remove_undelivered=True, set_to_read=False):
            live_logger.report_to_channel("trash_emails", f"{len(emails)} emails processed. Deleting {batch_size - len(emails)}/{batch_size} this round.")

            # If process stopped - break out of the infinite generator
            if stoppage_event.is_set():
                break

        # If the process finished on its own (i.e all the emails have been read OR n limit has been reached), then wait 20 seconds before starting a new cycle.
        else:
            live_logger.report_to_channel("trash_emails", f"Email generator exhausted. Waiting 20 seconds before starting a new cycle.")
            await asyncio.sleep(20)

    live_logger.report_to_channel("info", f"Consumer closed verified.")

# Message Queue for stage 1 - Mailbox read and add to database
MQ_MAILBOX: asyncio.Queue[EmailMessageAdapted] = asyncio.Queue(maxsize=2000)

# Message Queue for stage 2 - GPT-3.5 email processing
MQ_GPT_EMAIL_TO_DB: asyncio.Queue[EmailMessageAdapted] = asyncio.Queue(maxsize=500)

# Message Queue for stage 3 - Item matching
MQ_ITEM_MATCHING: asyncio.Queue[MongoShip] = asyncio.Queue(maxsize=1500)

# Message Queue for stage 4 - Email send for Ships with matched cargos
MQ_EMAIL_SEND: asyncio.Queue[MongoShip] = asyncio.Queue(maxsize=20)

# Please respect the complex signature of this dictionary. You have to create your async functions with the specified signature, and add them to the dictionary below.
MQ_HANDLER: Dict[str, Tuple[
        Callable[[asyncio.Event, asyncio.Queue], Coroutine[Any, Any, None]], 
        asyncio.Event,
        asyncio.Queue]
    ] = {
    "mailbox_read_producer": (mailbox_read_producer, asyncio.Event(), MQ_MAILBOX),   
    "mailbox_read_consumer": (mailbox_read_consumer, asyncio.Event(), MQ_MAILBOX, MQ_GPT_EMAIL_TO_DB), # type: ignore - temporary due to https://github.com/Kowalifwer/shipping_broker/issues/2


    "6_gpt_email_consumer": (gpt_email_consumer, asyncio.Event(), MQ_GPT_EMAIL_TO_DB), #temporarily, declare number of tasks in the function name

    "item_matching_producer": (item_matching_producer, asyncio.Event(), MQ_ITEM_MATCHING),
    "item_matching_consumer": (item_matching_consumer, asyncio.Event(), MQ_ITEM_MATCHING, MQ_EMAIL_SEND), # type: ignore - temporary due to

    "email_send_producer": (email_send_producer, asyncio.Event(), MQ_EMAIL_SEND), # type: ignore - temporary due to "item_matching_consumer


    # "db_listens_for_new_emails_producer": (db_listens_for_new_emails_producer, asyncio.Event(), MQ_GPT_EMAIL_TO_DB),
    # "gpt_email_producer": (gpt_email_producer, asyncio.Event(), MQ_GPT_EMAIL_TO_DB),


    # temporary helper methods for testing.
    "queue_capacity_producer": (queue_capacity_producer, asyncio.Event(), MQ_MAILBOX, MQ_GPT_EMAIL_TO_DB, MQ_ITEM_MATCHING, MQ_EMAIL_SEND),
    "endless_trash_email_cleaner_producer": (endless_trash_email_cleaner, asyncio.Event()),
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
        email_in_db = await db_client["emails"].find_one({
            "$or": [
                {"id": email_message.id},
                {"body": email_message.body}
                # {"subject": email_message.subject, "sender": email_message.sender},

                # Date recieved - within a day or so is common ?
                # 
            ]
        })
    except Exception as e:
        live_logger.report_to_channel("error", f"Error finding email in database. {e}")
        return False

    if email_in_db:
        # TODO: consider updating the fields on the duplicate object, such as date_recieved or store a counter of duplicates, if this into will be useful later.
        return False

    mongo_email = email_message.mongo_db_object
    mongo_email.timestamp_added_to_db = datetime.now()

    inserted_result = await db_client["emails"].insert_one(mongo_email.model_dump())

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
        temperature=0.22,
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

    validation_failed_entries: List[FailedEntry] = []
    ships: List[MongoShip] = []
    cargos: List[MongoCargo] = []
    mongo_email = email.mongo_db_object
    # Entity extraction timestamp must be set.
    mongo_email.timestamp_entities_extracted = datetime.now()

    for entry in entries:
        entry["email"] = mongo_email.model_dump()

        entry_type = entry.pop("type", None)
        if entry_type is None:
            entry["type"] = "unknown"
            entry["reason"] = "No entry type specified"
            validation_failed_entries.append(FailedEntry(**entry))

        entry_type = entry_type.lower()
        # Validate entity is Ship or Cargo. Otherwise, add to validation_failed_entries
        if entry_type not in ["ship", "cargo"]:
            entry["type"] = entry_type
            entry["reason"] = "Invalid entry type (must be 'ship' or 'cargo')"
            validation_failed_entries.append(FailedEntry(**entry))
            continue

        if entry_type == "ship":
            # Add calculated fields to ship
            update_ship_entry_with_calculated_fields(entry)

            try:
                ship = MongoShip(**entry)

                ship.location_geocoded = await geocode_location_with_retry(ship.location)

                ships.append(ship)

            except ValidationError as e:
                entry["type"] = entry_type
                entry["reason"] = str(e)
                validation_failed_entries.append(FailedEntry(**entry))
            
            except Exception as e:
                entry["type"] = entry_type
                entry["reason"] = str(e)
                validation_failed_entries.append(FailedEntry(**entry))
        
        elif entry_type == "cargo":
            # Add calculated fields to cargo
            update_cargo_entry_with_calculated_fields(entry)

            try:
                cargo = MongoCargo(**entry)

                cargo.location_from_geocoded = await geocode_location_with_retry(cargo.location_from)
                cargo.location_to_geocoded = await geocode_location_with_retry(cargo.location_to)

                cargos.append(cargo)

            except ValidationError as e:
                entry["type"] = entry_type
                entry["reason"] = str(e)
                validation_failed_entries.append(FailedEntry(**entry))
            
            except Exception as e:
                entry["type"] = entry_type
                entry["reason"] = str(e)
                validation_failed_entries.append(FailedEntry(**entry))

    if ships:
        # Insert ships into MongoDB
        await db_client["ships"].insert_many([ship.model_dump() for ship in ships])

    if cargos:
        # Insert cargos into MongoDB
        await db_client["cargos"].insert_many([cargo.model_dump() for cargo in cargos])

    live_logger.report_to_channel("gpt", f"Inserted {len(ships)} ships and {len(cargos)} cargos into database.")
    if validation_failed_entries:
        live_logger.report_to_channel("extra", f"Additionally, ignored {len(validation_failed_entries)} entries from GPT-3.5.")
        # Add all validation_failed entries to "failed_entries" collection in database
        await db_client["failed_entries"].insert_many([entry.model_dump() for entry in validation_failed_entries])
    
    await db_client["extractions"].insert_one(
        MongoEmailAndExtractedEntities(
            email=mongo_email,
            entities=ships + cargos,
            failed_entries=validation_failed_entries,
        ).model_dump()
    )
    
async def match_cargos_to_ship(ship: MongoShip, max_n: int = 5) -> List[Any]:
    """Match cargos to a ship, based on the extracted fields."""

    # Try to consider the following:
    # 1. capacity_int (if specified) - both ship and cargo have a value. make it a match IF capacities are within 10% of each other.
    # 2. month_int (if specified) - both ship and cargo have a value. make it a match IF months are the same or within 1 month of each other.
    # 3. port (if specified) - both ship and cargo have a value. cargo has port_from port_to, whilst ship only has port. make it a match IF port is the same as either port_from or port_to.
    # 4. sea (if specified) - both ship and cargo have a value. cargo has sea_from sea_to, whilst ship only has sea. make it a match IF sea is the same as either sea_from or sea_to.

    # STAGE 1 - HARD FILTERS (DB QUERY) - stuff that will completely disqualify a cargo from being matched with a ship (can be done fully via DB query)
    # TBD... (for now we retrieve all cargos, since we don't have enough data to filter them out)

    if ship.location_geocoded is None:
        raise ValueError("Ship location is not geocoded.")

    ship_coordinates = ship.location_geocoded.location.coordinates

    #fetch cargos from past 3 days only
    date_from = datetime.now() - timedelta(days=31)

    query_cargos: Dict[str, Dict] = {
        "timestamp_created": {"$gte": date_from},
    }

    if ship.capacity_int: # Capacity must be within 20% of the bounds
        query_cargos["capacity_max_int"] = {"$gte": ship.capacity_int * 0.80}
        query_cargos["capacity_min_int"] = {"$lte": ship.capacity_int * 1.20}

    if ship.month_int: # Month must be within 1 month of the bounds
        query_cargos["month_int"] = {"$gte": ship.month_int - 1, "$lte": ship.month_int + 1}
    
    query_cargos["commission_float"] = {"$lte": 5.00} # Comission must be less than 3.75%

    # Locations must be non-empty!
    query_cargos["location_from_geocoded"] = {"$exists": True, "$ne": None}
    query_cargos["location_to_geocoded"] = {"$exists": True, "$ne": None}

    # Assuming `location_from_geocoded.location` is the field storing the Point object
    query_cargos["location_from_geocoded.location"] = {
        "$near": {
            "$geometry": {
                "type": "Point",
                "coordinates": ship_coordinates  # Replace with your actual coordinates
            },
            "$maxDistance": 1_500_000  # Replace with your desired max distance in meters (1,500 km)
        }
    }

    seen_combinations = set()
    result = []
    expected_unique_fields = ["name", "capacity_min_int", "capacity_max_int", "month_int", "commission_float"]
    async for cargo in db_client["cargos"].find(query_cargos):
        # Construct a unique key for each cargo based on specified fields
        cargo_key = tuple(cargo[field] for field in expected_unique_fields)

        if cargo_key not in seen_combinations:
            # This cargo is unique; process and add it to the results
            seen_combinations.add(cargo_key)
            
            # Formulate cargo details (modify this part as needed to include relevant information)
            cargo_details = {
                "id": str(cargo["_id"]),
                "cargo_capacity_max": cargo.get("capacity_max_int"),
                "cargo_capacity_min": cargo.get("capacity_min_int"),
                "cargo_month": cargo["month"],
                "cargo_commission": cargo["commission"],

                "cargo_location_from": cargo["location_from"],
                "cargo_location_to": cargo["location_to"],

                "cargo_location_from_geocoded": cargo["location_from_geocoded"],
                "cargo_location_to_geocoded": cargo["location_to_geocoded"],

                "email_body": cargo["email"]["body"],
            }
            
            result.append(cargo_details)
                    
            # Stop processing if we've reached the desired number of results
            if len(result) == max_n:
                break
    
    return result

    return [
        {
            "id": str(cargo["_id"]),

            "cargo_capacity_max": cargo["capacity_max_int"],
            "cargo_capacity_min": cargo["capacity_min_int"],
            "cargo_month": cargo["month"],
            "cargo_commission": cargo["commission"],

            "cargo_location_from": cargo["location_from"],
            "cargo_location_to": cargo["location_to"],

            "cargo_location_from_geocoded": cargo["location_from_geocoded"],
            "cargo_location_to_geocoded": cargo["location_to_geocoded"],

            "email_body": cargo["email"]["body"],
        } for cargo in db_cargos if cargo["location_from_geocoded"] and cargo["location_to_geocoded"]
        # TODO: The hack above is to filter out cargos that don't have full locations. Likely only if the geocoding failed OR even worse- the field has wrongly been classified as cargo, and does not even have a location_to (validation check fail)
        # https://github.com/Kowalifwer/shipping_broker/issues/3
    ]

    # hard filter subset to be ordered by &near to the ship's location. this is one ranked list of cargos.
    # second ranked list of cargos is based on the simple scores, and then the two rankings combined to get the final ranking.

    cargos = [MongoCargo(**cargo) for cargo in db_cargos]
    simple_scores = []
    
    for cargo in cargos:

        score = 0
        # STAGE 2 - BASIC DB FIELDS SCORE -> CALCULATE SCORE from simple fields, such as capacity_int, month_int, comission_float...

        # 1. Handle Ship Capacity vs Cargo Quantity logic
        score += scoring.capacity_modifier(ship, cargo)

        # 2. Handle Ship Month vs Cargo Month logic
        score += scoring.month_modifier(ship, cargo)

        # 3. Handle Cargo comission scoring
        score += scoring.comission_modifier(ship, cargo)

        # 4. Handle date created scoring
        # score += scoring.timestamp_created_modifier(ship, cargo)

        simple_scores.append(score)

    # STAGE 3 - EMBEDDINGS SCORE -> CALCULATE SCORE from embeddings, such as port_embedding, sea_embedding, general_embedding...
    from sklearn.metrics.pairwise import cosine_similarity

    # Normalize simple scores based on max and min values in the list

    simple_scores = scoring.min_max_scale_robust(simple_scores, -0.1, 1) # Normalized to be between -0.1 and 1.0

    # STAGE 4 - FINAL SCORE -> COMBINE THE SCORES FROM STAGE 2 AND STAGE 3, AND SORT THE CARGOS BY SCORE
    # Mean rank? Weighted Sum (normalize scores first)? TBD...
    final_scores = [
        {
            "id": str(cargos[i].id),
            "cargo_capacity_max": cargos[i].capacity_max_int,
            "cargo_capacity_min": cargos[i].capacity_min_int,
            "cargo_month": cargos[i].month,
            "cargo_port_from": cargos[i].port_from,
            "cargo_port_to": cargos[i].port_to,
            "cargo_sea_from": cargos[i].sea_from,
            "cargo_sea_to": cargos[i].sea_to,
            "cargo_commission": cargos[i].commission,

            "total_score": sum(scores),
            "email_body": cargos[i].email.body,
        } for i, scores in enumerate(zip(
            simple_scores,  # Simple score (db scores) are important - hence should be multiplied
        ))
    ]
    final_scores.sort(key=lambda x: x["total_score"], reverse=True)

    return final_scores[:max_n]

def render_email_body_text(data, template_path: str = "email/to_ship.html"):
    template_loader = FileSystemLoader(searchpath="templates")
    env = Environment(loader=template_loader)

    template = env.get_template(template_path)
    rendered_content = template.render(data)
    return rendered_content

async def db_listens_for_new_emails_producer(stoppage_event: asyncio.Event, queue: asyncio.Queue):
    """Deprecated. Until it is decided what approach to take with issue #2, this function will not be used."""

    attempt_interval = 5 # seconds

    # 4. Listen for new emails being added to the database, and add them to the queue
    # Note this only works if MongoDB Node is running in replica set mode, and the database is configured to use Change Streams.
    # This can be done locally by running the following command in the mongo shell:
    # rs.initiate()
    # But only if the initialized node had the proper config that allows for replica sets. Check mongo-setup mongod.conf for commented out example how I did it locally.
    # More info: https://docs.mongodb.com/manual/changeStreams/

    collection = db_client["emails"]
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
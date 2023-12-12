from fastapi import FastAPI, Depends, HTTPException, Query, Request, BackgroundTasks
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
from mail import EmailClientIMAP, EmailClientAzure
import asyncio
import configparser
from typing import Any, List, Optional, Union, Literal, Coroutine, Dict, Tuple, Callable
from datetime import datetime
from db import MongoEmail, MongoShip, MongoCargo
from pydantic import ValidationError
from gpt_prompts import prompt
import json
from motor.motor_asyncio import AsyncIOMotorClient
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from mail import EmailMessageAdapted
from fastapi.templating import Jinja2Templates

import openai
import mail_init

#uvicorn main:app --reload
#https://admin.exchange.microsoft.com/#/settings
#https://admin.microsoft.com/#/users/:/UserDetails/6943c12b-f238-483e-af43-8e4cf25ba599/Mail

# Get credentials from config.cfg
config = configparser.ConfigParser()
config.read('config.cfg')

app = FastAPI()

# Serve static files from the "static" directory
app.mount("/static", StaticFiles(directory="static"), name="static")

# Create a Jinja2Templates instance and point it to the "templates" folder
templates = Jinja2Templates(directory="templates")

from realtime_status_logger import router, live_logger

# Add the router to the app, to also serve endpoints from the files below
app.include_router(router)

# Set your Outlook email and password (or App Password if 2FA is enabled)
email_address = config['imap']['email']
email_password = config['imap']['pw']

azure_client = mail_init.connect_to_azure(config["azure1"])
if isinstance(azure_client, str):
    print(azure_client)
    exit()

email_client = EmailClientAzure(azure_client)

# Imap details
# imap_server = "outlook.office365.com"
# imap_port = 993

# imap_client = EmailClientIMAP(imap_server, imap_port, email_address, email_password)
# imap_client.connect()

# Connect to MongoDB
db_hanlder = AsyncIOMotorClient("mongodb://localhost:27017/")
db = db_hanlder["broker"]

# Load your API key from an environment variable or secret management service
openai.api_key = config['openai']['api_key']

# chat_completion = openai.ChatCompletion.create(model="gpt-3.5-turbo", messages=[{"role": "user", "content": "Hello world"}])
# print(chat_completion.choices[0].message.content)

## All routes for FastAPI below

# Route for the root endpoint
@app.get("/")
async def read_root():
    live_logger.report_to_channel("info", "Hello from the root endpoint")
    return {"message": "Welcome to your FastAPI app!"}

@app.get("/info", response_class=HTMLResponse)
async def live_log(request: Request):
    # Provide data to be rendered in the template
    data = {
        "title": "Live Event Logging",
        "message": "Hello, FastAPI!",
        "user_id": live_logger.user_id,
        "channels": live_logger.channels,
        "buttons": mq_setup_to_frontend_template_data()
    }

    # Render the template with the provided data
    return templates.TemplateResponse("live_logger.html", {"request": request, **data})

@app.get("/gpt")
async def gpt_prompt():
    example = """Iskenderun => 1 Italy Adriatic
Abt 4387 Cbm/937 mts Pipes
LENGHT OF PIPE: 20M
Total 83 pieces pipes
11 Nov/Onwards
4 ttl days sshex eiu
3.75%
+++

Batumi => Split 
5.000 mt urea in bb, sf'51 1000ex / 1500ex 
01-10 November 
3.75% 
+++
Saint Petersburg, Russia => Koper, Slovenia    
Abt 10'000 mts +10% in OO, SF abt 1.2 wog , 2 grades to be fully segregated 
15-20.11.2023
8000 mts SSHINC / 3500 mts SSHEX
EIU PWWD OF 24CONSECUTIVE HOURS  BENDS
CHABE
SDBC MAX 25 Y.O.
3.75%
+
"""

    response = await openai.ChatCompletion.acreate(
        model="gpt-3.5-turbo-1106",
        # temperature=0.01,
        top_p=0.5,
        response_format={ "type": "json_object" },
        messages=[
            {"role": "system", "content": prompt.system},
            {"role": "user", "content": example}
        ]
    )
    json_response = response.choices[0].message.content

    try:
        final = json.loads(json_response)
    except Exception as e:
        print("Error parsing JSON response from GPT-3", e)
        return {"message": "Error parsing JSON response from GPT-3", "original": json_response}

    return final

# Create an async FIFO queue for processing emails (acts as a simple MQ pipeline, simple alternative to Celery, for now)

mail_queue = asyncio.Queue(maxsize=10) # A maximum buffer of 1,000 emails

shutdown_background_processes = asyncio.Event()

@app.on_event("shutdown") # on shutdown, shut all background processes too.
async def shutdown_event_handler():
    shutdown_background_processes.set()

@app.on_event("startup") # handle on startup background process setup
async def startup_event_handler():
    ...

@app.get("/shutdown")
async def shutdown():
    print("setting shutdown event")
    shutdown_background_processes.set()
    await live_logger.close_session()
    return {"message": "Shutdown event set"}

@app.get("/{action}/{task_type}/{name}")
async def launch_backgrond_task(background_tasks: BackgroundTasks, action: Literal["start", "end"], task_type: Literal["consumer", "producer"], name: str):
    if action not in ["start", "end"]:
        live_logger.report_to_channel("error", f"Invalid action {action}. Must be either 'start' or 'end'")
        return {"error": f"Invalid action {action}. Must be either 'start' or 'end'"}

    if task_type not in ["consumer", "producer"]:
        live_logger.report_to_channel("error", f"Invalid task type {task_type}. Must be either 'consumer' or 'producer'")
        return {"error": f"Invalid task type {task_type}. Must be either 'consumer' or 'producer'"}

    if name not in MQ_HANDLER:
        live_logger.report_to_channel("error", f"Invalid task name {name}. Must be one of {MQ_HANDLER.keys()}")
        return {"error": f"Invalid task name {name}. Must be one of {MQ_HANDLER.keys()}"}

    task_function = MQ_HANDLER[name][0]
    task_event = MQ_HANDLER[name][1]
    message_queue = MQ_HANDLER[name][2]

    if action == "start":
        task_event.clear()

        background_tasks.add_task(task_function, task_event, message_queue)
    elif action == "end":
        task_event.set()

    live_logger.report_to_channel("info", f"{task_type.capitalize()} task - {name} {action}ed")

    return {"message": f"{task_type.capitalize()} task - {name} {action}ed"}


from typing import Iterator
async def mailbox_read_producer(stoppage_event: asyncio.Event, queue: asyncio.Queue):
    # 1. Read all UNSEEN emails from the mailbox, every 5 seconds, or if email queue is processed.

    attempt_interval = 5 # seconds

    while not stoppage_event.is_set():

        email_generator = email_client.endless_email_read_generator(
            n=9999,
            batch_size=4,

            most_recent_first=True,
            unseen_only=False,
            set_to_read=False,
            remove_undelivered=True
        )

        end_email_fetching: bool = False # This flag will be checked at the end of processing the email_batch, to decide if the generator should be broken out of.

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
                            end_email_fetching = True # Prevent the next batch from being fetched from the generator for loop
                            batch_processed = True # Prevent the next batch from being processed
                            break

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

                    await asyncio.sleep(2)

            if end_email_fetching: # if producer got stopped - we must break out of the generator for loop
                print("breaking out of generator for loop - producer stop command received")
                break      

    print("producer task ended completely")


async def mailbox_read_consumer(stoppage_event: asyncio.Event, queue: asyncio.Queue):
    # 2. Process all emails in the queue, every 10 seconds, or if email queue is processed.
    while not stoppage_event.is_set():
        email = await queue.get() # get email from queue
        print("consumer fetched email from queue")
        await process_email_dummy(email)

MQ_MAILBOX: asyncio.Queue[EmailMessageAdapted] = asyncio.Queue(maxsize=10) # A maximum buffer of 10 emails
MQ_GPT_EMAIL_TO_DB = asyncio.Queue(maxsize=10) # A maximum buffer of 10 emails

# Please respect the complex signature of this dictionary. You have to create your async functions with the specified signature, and add them to the dictionary below.
MQ_HANDLER: Dict[str, Tuple[
        Callable[[asyncio.Event, asyncio.Queue], Coroutine[Any, Any, None]], 
        asyncio.Event, 
        asyncio.Queue]
    ] = {
    "mailbox_read_producer": (mailbox_read_producer, asyncio.Event(), MQ_MAILBOX),   
    "mailbox_read_consumer": (mailbox_read_consumer, asyncio.Event(), MQ_MAILBOX),

    # "gpt_email_producer": (gpt_email_producer, asyncio.Event(), MQ_GPT_EMAIL_TO_DB),
    # "gpt_email_consumer": (gpt_email_consumer, asyncio.Event(), MQ_GPT_EMAIL_TO_DB),
}

def mq_setup_to_frontend_template_data():
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

async def match_ship_to_cargos(ship: MongoShip):
    #query all cargos, first in a quantity_int +- 20% range
    
    quantity_int = ship.capacity_int
    if quantity_int:
        percent_difference = 0.2
        min_quantity_int = int(quantity_int * (1 - percent_difference))
        max_quantity_int = int(quantity_int * (1 + percent_difference))

        cargos_by_quantity = await db["cargos"].find({
            "quantity_int": {
                "$gte": min_quantity_int,
                "$lte": max_quantity_int
            }
        }).to_list(100)

        print(f"Found {len(cargos_by_quantity)} cargos for ship {ship.name}, in quantity range {min_quantity_int} - {max_quantity_int}")
    
    #query all cargos where sea_from or sea_to, matches the ships sea
    if ship.sea:
        cargos_by_sea = await db["cargos"].find({
            "$or": [
                {"sea_from": ship.sea},
                {"sea_to": ship.sea}
            ]
        }).to_list(100)

        print(f"Found {len(cargos_by_sea)} cargos for ship {ship.name}, in sea {ship.sea}")

    #query all cargos where port_from or port_to, matches the ships port
    if ship.port:
        cargos_by_port = await db["cargos"].find({
            "$or": [
                {"port_from": ship.port},
                {"port_to": ship.port}
            ]
        }).to_list(100)

        print(f"Found {len(cargos_by_port)} cargos for ship {ship.name}, in port {ship.port}")
    
    #query all cargos where month matches the ships month, with a +- 1 month range
    if ship.month_int:
        cargos_by_month = await db["cargos"].find({
            "month_int": {
                "$gte": ship.month_int - 1,
                "$lte": ship.month_int + 1
            }
        }).to_list(100)

        print(f"Found {len(cargos_by_month)} cargos for ship {ship.name}, in month range {ship.month_int - 1} - {ship.month_int + 1}")

async def endless_cargo_ship_matcher():
    # 1. Endless query for all ships with no cargo pairs
    # 2. For each ship, find all cargoes that match the ship's criteria (for now via simple querying)
    # 3. set the ship's matched_cargo_ids
    # 4. append to the cargo's matched_ship_ids

    # query for all ships with no cargo pairs
    cursor = db["ships"].find({"pairs_with": []}).batch_size(100)
    async for ship in cursor:
        matches = await match_ship_to_cargos(MongoShip(**ship))

async def process_email_dummy(email_message: EmailMessageAdapted) -> Union[bool, str]:
    print("processing email")
    await asyncio.sleep(5) # simulate the gpt api call time
    return True
    
@app.get("/read_emails_azure")
async def read_emails_azure():
    
    emails = await email_client.get_emails(
        n=50,
        most_recent_first=True,
        unseen_only=False,
        set_to_read=False
    )

    if isinstance(emails, str):
        return {"error": emails}
    

    for i, email in enumerate(emails, start=1):
        print(f"msg {i}: {email.date_received}, subject: {email.subject}")


        output = await process_email(email)
        if output != True:
            return {"message": output}


    return {"emails": len(emails)}

# Test view
@app.get("/delete_spam_emails_azure")
async def delete_spam_emails_azure():
    start_time = datetime.now()
    remaining_emails = await email_client.read_emails_and_delete_spam(500, unseen_only=False)
    print(f"Time taken to fetch emails and create objects, whilst launching background tasks: {datetime.now() - start_time}")

    if isinstance(remaining_emails, str):
        return {"error": remaining_emails}

    print(f"Number of remaining emails: {len(remaining_emails)}")

# Test view
@app.get("/list_mail_folders")
async def list_mail_folders():
    folders = await email_client.client.me.mail_folders.get()
    for folder in folders.value:
        messages = await email_client.client.me.mail_folders.by_mail_folder_id(folder.id).messages.get()
        print(f"{folder.display_name} has {len(messages.value)} messages")
        

    return {"message": folders}

async def email_to_json_via_openai(email_message: EmailMessageAdapted) -> dict:
    
    #https://github.com/openai/openai-cookbook/blob/main/examples/api_request_parallel_processor.py -> parallel processing example
    """
    Convert an email message to JSON using OpenAI ChatCompletion.

    Parameters:
    - email_message (EmailMessageAdapted): The email message to be converted.

    Returns:
    Union[str, dict]: The JSON representation of the email message, or an error message.

    Raises:
    - OpenAIError: If there is an error in the OpenAI API request.
    - json.JSONDecodeError: If there is an error decoding the JSON response.
    """

    response = await openai.ChatCompletion.acreate(
        model="gpt-3.5-turbo-1106",
        temperature=0.2,
        # top_p=1,
        response_format={ "type": "json_object" },
        messages=[
            {"role": "system", "content": prompt.system},
            {"role": "user", "content": email_message.body}
        ]
    )
    json_response = response.choices[0].message.content # type: ignore

    final = json.loads(json_response)
    return final
    
async def add_email_to_db(email_message: EmailMessageAdapted) -> bool:
    """Add email to database, if it doesn't already exist. Return True if added, False if already exists."""

    email_in_db = await db["emails"].find_one({
        "$or": [
            {"id": email_message.id},
            {"body": email_message.body}
            # {"subject": email_message.subject, "sender": email_message.sender},
        ]
    })

    if email_in_db:
        # TODO: consider updating the fields on the duplicate object, such as date_recieved or store a counter of duplicates, if this into will be useful later.
        print("Email already in database. ignoring")
        return False

    print("Email not in database. inserting")
    await db["emails"].insert_one(email_message.mongo_db_object.model_dump())

    return True

async def insert_gpt_entries_into_db(entries: List[dict], email: MongoEmail) -> None:
    """Insert GPT-3.5 entries into database."""

    ignored_entries = []
    ships = []
    cargos = []

    for entry in entries:

        entry_type = entry.get("type")
        if entry_type not in ["ship", "cargo"]:
            ignored_entries.append(entry)
            continue

        entry["email"] = email

        if entry_type == "ship":
            try:
                ship = MongoShip(**entry)

                ships.append(ship.model_dump())
            except ValidationError as e:
                ignored_entries.append(entry)
                print("Error validating ship. skipping addition", e)
        
        elif entry_type == "cargo":
            try:
                cargo = MongoCargo(**entry)

                cargos.append(cargo.model_dump())
            except ValidationError as e:
                ignored_entries.append(entry)
                print("Error validating cargo. skipping addition", e)
    
    # Insert email into MongoDB
    await db["emails"].insert_one(email.model_dump())

    if ships:
        # Insert ships into MongoDB
        await db["ships"].insert_many(ships)

    if cargos:
        # Insert cargos into MongoDB
        await db["cargos"].insert_many(cargos)
    
    live_logger.report_to_channel("info", f"Inserted {len(ships)} ships and {len(cargos)} cargos into database.")
    if ignored_entries:
        live_logger.report_to_channel("warning", f"Additionally, ignored {len(ignored_entries)} entries from GPT-3.5. {ignored_entries}")

async def process_email(email_message: EmailMessageAdapted) -> None:

    email_added = await add_email_to_db(email_message)

    if not email_added:
        live_logger.report_to_channel("warning", f"Email with id {email_message.id} already in database. Ignoring.")
        return

    # Converting email to JSON via GPT-3.5
    try:
        gpt_response = await email_to_json_via_openai(email_message)
    except Exception as e:
        live_logger.report_to_channel("error", f"Error converting email to JSON via GPT-3.5. {e}")
        return

    entries = gpt_response.get("entries", [])
    if not entries:
        live_logger.report_to_channel("error", f"Error in processing email - No entries returned from GPT-3.5.")
        return

    email: MongoEmail = email_message.mongo_db_object
    
    # For simplicity, the function below will handle logging to the live_logger
    await insert_gpt_entries_into_db(entries, email)

global_task_dict = {} # to track which endless tasks are running

async def endless_task(n: int):
    while global_task_dict.get(n, False): # while task is running. If task not initialized, return False
        print(f"Hello from the endless task {n}")
        await asyncio.sleep(3)

def start_endless_task(background_tasks: BackgroundTasks, n: int = 1):
    if not global_task_dict.get(n, False): # if task not initialized, initialize it
        global_task_dict[n] = True
        background_tasks.add_task(endless_task, n)

def stop_endless_task(n: int):
    global_task_dict[n] = False

@app.get("/start/{n}")
async def start_task(n: int, background_tasks: BackgroundTasks):
    start_endless_task(background_tasks, n)
    return {"message": f"Endless task {n} started."}

@app.get("/stop/{n}")
async def stop_tasks(n: int):
    stop_endless_task(n)
    return {"message": f"Endless task {n} stopped."}

@app.get("/stop_all")
async def stop_all_tasks():
    for key in global_task_dict:
        stop_endless_task(key)
    return {"message": "All tasks stopped."}

@app.get("/read_emails")
async def read_emails():
    emails = mail_handler.read_emails(
        #all emails search criteria
        search_criteria="ALL",
        num_emails=1,
        # search_keyword="MAP TA PHUT"
    )
    output = "no emails"
    if emails:
        print(emails[0].body)
        output = await process_email(emails[0])
        print(output)

        # for email_message in emails:
        #     # Process or display email details as needed
        #     db_entries.append(email_message.mongo_db_object.model_dump())
        
        # # Insert emails into MongoDB
        # await db["emails"].insert_many(db_entries)

        # #return html of last email
    return JSONResponse(content=output)

@app.get("/regex")
async def regex():
    import re
    cargo_email_text = """
    6912/232 mts
    8000/15000 PWWD SHINC BENDS
    END OCT/EARLY NOV 2023
    2.5% PUS
    """

    # Define the regex pattern
    pattern = re.compile(r"(\d+(?:,\d{3})*(?:\.\d+)?)\s*mts?\b", re.IGNORECASE)

    # Find all matches in the text
    matches = pattern.findall(cargo_email_text)

    print(matches)

    return {"message": matches}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
from fastapi import FastAPI, Depends, HTTPException, Query, Request, BackgroundTasks
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
from mail import EmailClientSMTP, EmailClientAzure
import asyncio
import configparser
from typing import Any, List, Optional, Union
from datetime import datetime
from db import MongoEmail, MongoShip, MongoCargo
from pydantic import ValidationError
from gpt_prompts import prompt
import json
from motor.motor_asyncio import AsyncIOMotorClient

from mail import EmailMessageAdapted

import openai
import mail_init

app = FastAPI()

#uvicorn main:app --reload
#https://admin.exchange.microsoft.com/#/settings
#https://admin.microsoft.com/#/users/:/UserDetails/6943c12b-f238-483e-af43-8e4cf25ba599/Mail

# Get credentials from config.cfg
config = configparser.ConfigParser()
config.read('config.cfg')

# Set your Outlook email and password (or App Password if 2FA is enabled)
email_address = config['imap']['email']
email_password = config['imap']['pw']

azure_client = mail_init.connect_to_azure(config["azure"])
if isinstance(azure_client, str):
    print(azure_client)
    exit()

email_client = EmailClientAzure(azure_client)

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
    return {"message": "Welcome to your FastAPI app!"}

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

@app.get("/start_producer")
async def start_producer(background_tasks: BackgroundTasks):
    background_tasks.add_task(endless_mailbox_producer)
    return {"message": "Mailbox reader producer started"}

@app.get("/start_consumer")
async def start_consumer(background_tasks: BackgroundTasks):
    background_tasks.add_task(endless_mailbox_consumer)
    return {"message": "Mailbox reader consumer started"}

async def endless_mailbox_producer():
    # 1. Read all UNSEEN emails from the mailbox, every 5 seconds, or if email queue is processed.

    while not shutdown_background_processes.is_set():
        emails = await mail_handler.read_emails_dummy(
            #all emails search criteria
            search_criteria="UNSEEN",
            num_emails=1,
            # search_keyword="MAP TA PHUT"
        )
        total = len(emails)
        print(f"Fetched {total} emails from smtp server")

        for i, email in enumerate(emails):
            print(f"putting email {i}/{total} in queue")
            await mail_queue.put(email)

async def endless_mailbox_consumer():
    # 2. Process all emails in the queue, every 10 seconds, or if email queue is processed.
    while not shutdown_background_processes.is_set():
        email = await mail_queue.get() # get email from queue
        print("consumer fetched email from queue")
        await process_email_dummy(email)

async def match_ship_to_cargos(ship: MongoShip):
    #query all cargos, first in a quantity_int +- 20% range
    
    quantity_int = ship.capacity_int
    percent_difference = 0.2
    min_quantity_int = int(quantity_int * (1 - percent_difference))
    max_quantity_int = int(quantity_int * (1 + percent_difference))

    cargos_by_quantity = await db["cargos"].find({
        "quantity_int": {
            "$gte": min_quantity_int,
            "$lte": max_quantity_int
        }
    }).to_list()

    print(f"Found {len(cargos_by_quantity)} cargos for ship {ship.name}, in quantity range {min_quantity_int} - {max_quantity_int}")

    #query all cargos where sea_from or sea_to, matches the ships sea
    cargos_by_sea = await db["cargos"].find({
        "$or": [
            {"sea_from": ship.sea},
            {"sea_to": ship.sea}
        ]
    }).to_list()

    print(f"Found {len(cargos_by_sea)} cargos for ship {ship.name}, in sea {ship.sea}")

    #query all cargos where port_from or port_to, matches the ships port
    cargos_by_port = await db["cargos"].find({
        "$or": [
            {"port_from": ship.port},
            {"port_to": ship.port}
        ]
    }).to_list()

    print(f"Found {len(cargos_by_port)} cargos for ship {ship.name}, in port {ship.port}")

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

async def email_to_json_via_openai(email_message: EmailMessageAdapted) -> Union[str, dict]:
    try:
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

    except Exception as e:
        return f"Error in email_to_json_via_openai - {e}"
    
@app.get("/read_emails_azure")
async def read_emails_azure():
    
    # check if client is connected to Azure

    messages = await email_client.get_emails(
        top=100,
        most_recent_first=True
    )

    if isinstance(messages, str):
        return {"error": messages}
    

    for i, message in enumerate(messages, start=1):
        print(f"msg {i}: {message.date_received}")

        output = await process_email(message)
        if output != True:
            return {"message": output}


    return {"message": messages}

async def process_email(email_message: EmailMessageAdapted) -> Union[bool, str]:
    
    #https://github.com/openai/openai-cookbook/blob/main/examples/api_request_parallel_processor.py -> parallel processing example

    # run some checks on email, to make sure it is worthy of processing
    # check if email is already in db
    email_in_db = await db["emails"].find_one({"id": email_message.id})
    if email_in_db:
        print("Email already in database. ignoring")
    else:
        print("Email not in database. inserting")
        await db["emails"].insert_one(email_message.mongo_db_object.dict())

    return True

    # Converting email to JSON via GPT-3.5
    gpt_response = await email_to_json_via_openai(email_message)
    if isinstance(gpt_response, str):
        return gpt_response

    entries = gpt_response.get("entries", [])
    if not entries:
        return "No entries returned from GPT-3"



    email: MongoEmail = email_message.mongo_db_object
    ignored_entries = []
    ships = []
    cargos = []

    for entry in entries:
        print(entry)

        entry_type = entry.get("type")
        if entry_type not in ["ship", "cargo"]:
            ignored_entries.append(entry)
            continue

        entry["email"] = email

        if entry_type == "ship":
            try:
                ship = MongoShip(**entry)

                ships.append(ship.dict())
            except ValidationError as e:
                ignored_entries.append(entry)
                print("Error validating ship. skipping addition", e)
        
        elif entry_type == "cargo":
            try:
                cargo = MongoCargo(**entry)

                cargos.append(cargo.dict())
            except ValidationError as e:
                ignored_entries.append(entry)
                print("Error validating cargo. skipping addition", e)

    if ignored_entries:
        print("ignored entries", ignored_entries)
    
    # Insert email into MongoDB
    await db["emails"].insert_one(email.dict())

    if ships:
        # Insert ships into MongoDB
        await db["ships"].insert_many(ships)

    if cargos:
        # Insert cargos into MongoDB
        await db["cargos"].insert_many(cargos)

    return True

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
        #     db_entries.append(email_message.mongo_db_object.dict())
        
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
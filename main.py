from fastapi import FastAPI, Depends, HTTPException, Query, Request, BackgroundTasks
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
from mail import EmailClient
import asyncio
import configparser
import imaplib
from typing import Any, List, Optional, Union
from datetime import datetime
from db import MongoEmail, MongoShip, MongoCargo
from pydantic import ValidationError
from gpt_prompts import prompt
import json
from motor.motor_asyncio import AsyncIOMotorClient
from email.message import EmailMessage

app = FastAPI()

#uvicorn main:app --reload

# Get credentials from config.cfg
config = configparser.ConfigParser()
config.read('config.cfg')

# Set your Outlook email and password (or App Password if 2FA is enabled)
email_address = config['imap']['email']
imap_password = config['imap']['pw']

# Outlook IMAP settings
imap_server = "outlook.office365.com"  # Use "outlook.office.com" for Outlook.com accounts
imap_port = 993  # IMAPS port (secure)

# Connect to the Outlook IMAP server
try:
    imap_connection = imaplib.IMAP4_SSL(imap_server, imap_port)
    imap_connection.login(email_address, imap_password)
except Exception as e:
    print(f"Error: Could not connect to the server - {e}")
    exit()

# Initialize the EmailClient

mail_handler = EmailClient(
    imap_server=imap_server,
    imap_port=imap_port,
    email_address=email_address,
    password=imap_password,
    mailbox_name="INBOX",
)

mail_handler.connect()

# Connect to MongoDB
db_hanlder = AsyncIOMotorClient("mongodb://localhost:27017/")
db = db_hanlder["broker"]

import openai
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
mail_queue = asyncio.Queue(maxsize=1000) # A maximum buffer of 1,000 emails

shutdown_background_processes = asyncio.Event()

@app.on_event("shutdown") # on shutdown, shut all background processes too.
async def shutdown_event_handler():
    shutdown_background_processes.set()

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

async def process_email_dummy(email_message: EmailMessage) -> Union[True, str]:
    print("processing email")
    await asyncio.sleep(5) # simulate the gpt api call time
    return True

async def process_email(email_message: EmailMessage) -> Union[True, str]:
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
    json_response = response.choices[0].message.content

    try:
        final = json.loads(json_response)
    except Exception as e:
        return "Error parsing JSON response from GPT-3"

    entries = final.get("entries", [])
    if not entries:
        return "No entries returned from GPT-3"

    email: MongoEmail = email_message.get_db_object() # Email object will be the same for all entries
    ignored_entries = []
    ships = []
    cargos = []

    for entry in entries:
        entry_type = entry.get("type")
        if entry_type not in ["ship", "cargo"]:
            ignored_entries.append(entry)
            continue
    
        if entry_type == "ship":
            try:
                ship = MongoShip.parse_obj(entry, validate=False)
                ship.email = email

                ships.append(ship.dict())
            except ValidationError as e:
                ignored_entries.append(entry)
                print("Error validating ship. skipping addition", e)
        
        elif entry_type == "cargo":
            try:
                cargo = MongoCargo.parse_obj(entry, validate=False)
                cargo.email = email

                cargos.append(cargo.dict())
            except ValidationError as e:
                ignored_entries.append(entry)
                print("Error validating cargo. skipping addition", e)

    if ignored_entries:
        print("ignored entries", ignored_entries)
    
    # Insert email into MongoDB
    await db["emails"].insert_one(email.dict())

    # Insert ships into MongoDB
    await db["ships"].insert_many(ships)
    # Insert cargos into MongoDB
    await db["cargos"].insert_many(cargos)

    return True
        

from typing import Union
# def gpt_response_to_db_objects(gpt_response: dict) -> List[Union[Ship, Cargo]]:

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
        #     db_entries.append(email_message.get_db_object().dict())
        
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
from fastapi import FastAPI, Depends, HTTPException, Query, Request, BackgroundTasks
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
from mail import EmailClient
import asyncio
import configparser
import imaplib
from typing import Any, List
from datetime import datetime
from db import MongoEmail, MongoShip, MongoCargo
from pydantic import ValidationError
from gpt_prompts import prompt
import json
from motor.motor_asyncio import AsyncIOMotorClient

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

endless_task_running = False


def process_email():
    pass

from email.message import EmailMessage

@app.get("/gpt")
async def gpt_prompt():
    example = """pls offer yr firm / rated cgo for mv A z a r a open Nemrut 01-02 dec

we hv interest for cgo ex odessa area

mvAZARA
IMO  9132492 Blt 1997
Palau Flag Shipping Register of Ukraine
DWT 13898 / Drft 8,214 mtr
BC,SID,grab disch,steel floored,
Grt/Nrt 10220/5123
LOA/Bm 142,14/22,2
4 HO / 4 HA,CO2 Fitted
Hatch open dims 1/2/3/4 15,75 x 14

        L      B      H      Grain/Bale

Hold 1  22,5   22,2   11,42  140804,90 / 137202,66
Hold 2  22,5   22,2   11,42  163901,55 / 156647,65
Hold 3  22,5   22,2   11,42  164537,24 / 156721,81
Hold 4  21,8   22,2   11,42  160546,54 / 156732,41

             total Grain/bale 629790,22 / 607304,53


Gears 4 crane,SWL 12.5 mts,positioned btwn holds - Considered as GearLess
PANDI: British Marine, Lux"""

    response = openai.ChatCompletion.create(
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

async def email_processor(email_message: EmailMessage):
    # 1. Read all UNSEEN emails from the mailbox, every 5 seconds
    # 2. Process each email
    # 2.1 Extract the cargo or ship details from the email body
    # 2.2 Create a Cargo or Ship object with the extracted details
    # 2.3 Create an Email object with the email details
    # 3. Insert the processed email into MongoDB
    # 4. Repeat
    response = openai.ChatCompletion.create(
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
        print("Error parsing JSON response from GPT-3", e)
        return {"message": "Error parsing JSON response from GPT-3"}

    return final

    entries = final.get("entries", [])
    if entries:
        email: MongoEmail = email_message.get_db_object() # Email object will be the same for all entries
        ignored_entries = []
        ships = []
        cargos = []

        for entry in entries:
            entry_type = entry.get("type")
            if entry_type not in ["ship", "cargo"]:
                print("Invalid entry type", entry_type)
                ignored_entries.append(entry)
                continue
        
            if entry_type == "ship":
                try:
                    ship = MongoShip(
                        **entry,
                        email = email,
                        timestamp_created = datetime.now()
                    )
                    ships.append(ship.dict())
                except ValidationError as e:
                    ignored_entries.append(entry)
                    print("Error validating ship. skipping addition", e)
            
            elif entry_type == "cargo":
                try:
                    cargo = MongoCargo(
                        **entry,
                        email = email,
                        timestamp_created = datetime.now()
                    )
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

    else:
        print("No entries returned from GPT-3")
    return final

from typing import Union
# def gpt_response_to_db_objects(gpt_response: dict) -> List[Union[Ship, Cargo]]:


async def endless_task():
    global endless_task_running
    while endless_task_running:
        print("Hello from the endless task")
        await asyncio.sleep(3)

def start_endless_task(background_tasks: BackgroundTasks):
    global endless_task_running
    if not endless_task_running:
        endless_task_running = True
        background_tasks.add_task(endless_task)

def stop_endless_task():
    global endless_task_running
    endless_task_running = False

@app.get("/start")
async def start_task(background_tasks: BackgroundTasks):
    start_endless_task(background_tasks)
    return {"message": "Endless task started in the background."}

@app.get("/stop")
async def stop_task():
    stop_endless_task()
    return {"message": "Endless task stopped."}

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
        output = await email_processor(emails[0])
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
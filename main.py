from fastapi import FastAPI, Depends, HTTPException, Query, Request, BackgroundTasks
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
from mail import EmailClient
import asyncio
import configparser
import imaplib
from typing import Any, List
from datetime import datetime

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

def email_processor(email_message: EmailMessage):
    # 1. Read all UNSEEN emails from the mailbox, every 5 seconds
    # 2. Process each email
    # 2.1 Extract the cargo or ship details from the email body
    # 2.2 Create a Cargo or Ship object with the extracted details
    # 2.3 Create an Email object with the email details
    # 3. Insert the processed email into MongoDB
    # 4. Repeat
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        # response_format={ "type": "json_object" },
        messages=[
            {"role": "system", "content": """
            You are an intelligent email processor, that can read emails which will include either cargoes or ships (or neither, eg. SPAM). You must return a Json object to summarize the email. First field should be "type", which can be "ship", "cargo", or "unknown", depending on what the email contains. The second field should be a list name "entries", which will be a list of objects, representing either the Ships or the Cargos.

A CARGO object should contain the following fields:
1.  name
2. quantity i.e The quantity of cargo (in metric tons, CBFT, or other appropriate units) for cargoes.

A SHIP object should contain the following fields:
1. name
2. capacity i.e  how much weight the ship can carry, (in Deadweight Tonnage (DWT), Gross Tonnage (GT), Net Tonnage (NT) or other appropriate units)

!Important - make sure that capacity and quantity are always numbers, not strings. For example, if the email says "The ship can carry 37000 tons", then the capacity should be 37000, not "37000".
Example output:

{
    "type": "ship",
    "entries": [
        {
            "name": "M/V AFRICAN BEE",
            "capacity": "37000",
        }
    ]
}"""},
            {"role": "user", "content": email_message.body}
        ]
    )
    json_response = response.choices[0].message.content
    import json
    final = json.loads(json_response)
    return final
    

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
        # search_criteria="ALL",
        num_emails=5,
        # search_keyword="MAP TA PHUT"
    )
    print(emails[0].body)

    output = email_processor(emails[0])
    print(output)

    # for email_message in emails:
    #     # Process or display email details as needed
    #     db_entries.append(email_message.get_db_object().dict())
    
    # # Insert emails into MongoDB
    # await db["emails"].insert_many(db_entries)

    # #return html of last email
    return JSONResponse(content=output)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
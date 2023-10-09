from fastapi import FastAPI, Depends, HTTPException, Query, Request, BackgroundTasks
from fastapi.responses import RedirectResponse, HTMLResponse
from mail import EmailClient
import asyncio
import configparser
import imaplib
from typing import Any, List
from datetime import datetime

from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, EmailStr, Field

class Email(BaseModel):
    id: str = Field(..., description="Unique identifier for the email")
    subject: str = Field(..., description="Subject of the email")
    sender: EmailStr = Field(..., description="Email address of the sender")
    recipients: List[EmailStr] = Field(..., description="List of email addresses of the recipients")
    timestamp: datetime = Field(..., description="Timestamp of when the email was sent")

app = FastAPI()

#uvicorn main:app --port 8000 --reload

# Get credentials from config.cfg
config = configparser.ConfigParser()
config.read('config.cfg')
config = config['imap']

# Set your Outlook email and password (or App Password if 2FA is enabled)
email_address = config['email']
imap_password = config['pw']

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

# Connect to MongoDB

mongodb = AsyncIOMotorClient("mongodb://localhost:27017/")
db = mongodb["broker"]
db_emails = db["emails"]

# Route for the root endpoint
@app.get("/")
async def read_root():
    return {"message": "Welcome to your FastAPI app!"}

# The rest of your email processing code goes here

client = EmailClient(
    imap_server=imap_server,
    imap_port=imap_port,
    email_address=email_address,
    password=imap_password,
    mailbox_name="INBOX",
)

client.connect()

endless_task_running = False

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
    emails = client.read_emails(
        #all emails search criteria
        search_criteria="ALL",
        num_emails=3,
        search_keyword="MAP TA PHUT"
    )
    for email_message in emails:
        # Process or display email details as needed
        print("Subject:", email_message["Subject"])
        print("-" * 40)
        print(email_message.body)
        # print(decode_email_body(email_message))

    #return html of last email
    return HTMLResponse(email_message.body)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

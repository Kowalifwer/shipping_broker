import configparser
from motor.motor_asyncio import AsyncIOMotorClient
import openai

from mail import EmailClientAzure
import mail_init

# Get credentials from config.cfg
config = configparser.ConfigParser()
config.read('config.cfg')

# Set your Outlook email and password (or App Password if 2FA is enabled)
email_address = config['imap']['email']
email_password = config['imap']['pw']

azure_connection = mail_init.connect_to_azure(config["azure1"])
if isinstance(azure_connection, str):
    # If the connection is a string, it is an error message. Print it and exit.
    print(azure_connection)
    exit()

email_client = EmailClientAzure(azure_connection)

# Connect to MongoDB
db_hanlder = AsyncIOMotorClient("mongodb://localhost:27017/")
db = db_hanlder["broker"]

# Load your API key from an environment variable or secret management service
openai.api_key = config['openai']['api_key']
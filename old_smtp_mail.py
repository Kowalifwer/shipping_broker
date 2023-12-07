import configparser
import imaplib
import smtplib
from typing import Optional
from email.message import EmailMessage
from mail import EmailClient

config = configparser.ConfigParser()
config.read('config.cfg')

# Set your Outlook email and password (or App Password if 2FA is enabled)
email_address = config['imap']['email']
imap_password = config['imap']['pw']

# SMTP settings
smtp_server = 'smtp-mail.outlook.com'
smtp_port = 587
smtp_user = config['imap']['email']
smtp_password = config['imap']['pw']

# Connect to the SMTP server and send the email with OAuth 2.0 token
with smtplib.SMTP(smtp_server, smtp_port) as server:
    server.starttls()  # Use TLS encryption
    server.login(smtp_user, smtp_password)
    server.ehlo_or_helo_if_needed()

    # see if connection was successful
    print("Connection successful")

# Create an SMTP session
try:
    smtp_session = smtplib.SMTP(smtp_server, smtp_port)
    smtp_session.starttls()  # Use STARTTLS for encryption
    smtp_session.ehlo() # identify ourselves to smtp server
    smtp_session.login(smtp_user, smtp_password)
except Exception as e:
    print(f"Error: Could not connect to the SMTP server. Reason: {e}")
    # exit()

imap_server = "outlook.office365.com"  # Use "outlook.office.com" for Outlook.com accounts
imap_port = 993  # IMAPS port (secure)

# Connect to the Outlook IMAP server
try:
    imap_connection = imaplib.IMAP4_SSL(imap_server, imap_port)
    imap_connection.login(email_address, imap_password)
except Exception as e:
    print(f"Error: Could not connect to the IMAPLIB server - {e}")
    # exit()

# Initialize the EmailClient

mail_handler = EmailClient(
    imap_server=imap_server,
    imap_port=imap_port,
    email_address=email_address,
    password=imap_password,
    mailbox_name="INBOX",
)

mail_handler.connect()
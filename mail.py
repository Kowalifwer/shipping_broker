import imaplib
import email
from typing import List, Optional, Literal, Union
from email.message import EmailMessage
from email.policy import SMTPUTF8, default
from db import MongoEmail
from datetime import datetime
import random
from faker import Faker
from training.dummy_emails import examples
from msgraph import GraphServiceClient

## Additional methods for EmailMessage class
@property
def body(self):
    body = self.get_body(preferencelist=('plain', 'html'))
    if body:
        charset = body.get_charset()
        if charset:
            return body.get_content().decode(charset)
        else:
            return body.get_content()
    else:
        return ""

def get_db_object(self) -> MongoEmail:
    return MongoEmail(
        id=self["Message-ID"],
        subject=self["Subject"],
        sender=self["From"],
        recipients=self["To"],
        date_received=self["Date"],
        timestamp_processed=datetime.now(),
        body=self.body
    )

EmailMessage.body = body
EmailMessage.get_db_object = get_db_object

## End of additional methods for EmailMessage class

class EmailClientSMTP:
    """
    A Python class for handling email-related tasks using imaplib.
    
    Attributes:
        imap_server (str): The IMAP server address.
        imap_port (int): The port for IMAPS (secure IMAP) communication.
        email_address (str): The email address for authentication.
        password (str): The email account password.
        mailbox_name (str): The name of the mailbox to work with (e.g., "INBOX").
    """

    def __init__(self, imap_server: str, imap_port: int, email_address: str, password: str, mailbox_name: str = "INBOX") -> None:
        """
        Initializes the EmailClient with IMAP settings and login credentials.

        Args:
            imap_server (str): The IMAP server address.
            imap_port (int): The port for IMAPS (secure IMAP) communication.
            email_address (str): The email address for authentication.
            password (str): The email account password.
            mailbox_name (str, optional): The name of the mailbox to work with. Default is "INBOX".
        """
        self.imap_server = imap_server
        self.imap_port = imap_port
        self.email_address = email_address
        self.password = password
        self.mailbox_name = mailbox_name
        self.imap_connection: Optional[imaplib.IMAP4_SSL] = None

    def connect(self) -> None:
        """
        Connects to the IMAP server and logs in to the email account.
        """
        try:
            self.imap_connection = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
            self.imap_connection.login(self.email_address, self.password)
            print("Connected to the IMAP server")
        except Exception as e:
            raise Exception(f"Error: Could not connect to the server - {e}")

    def disconnect(self) -> None:
        """
        Disconnects from the IMAP server.
        """
        if self.imap_connection:
            self.imap_connection.logout()

    async def read_emails(self, search_criteria: Literal["UNSEEN", "ALL"] = "UNSEEN", num_emails: int = 10, search_keyword: str = "") -> Union[List[EmailMessage], str]:
        """
        Reads email messages from the mailbox.

        Args:
            search_criteria (str, optional): The search criteria for emails. Default is "UNSEEN" (unread emails).
            num_emails (int, optional): The maximum number of emails to retrieve. Default is 10.

        Returns:
            List[EmailMessage]: A list of email message objects.
        """
        if not self.imap_connection:
            return "Error: Not connected to the IMAP server"

        try:
            self.imap_connection.select(self.mailbox_name)
            search_str: str = f"{search_criteria}"
            if search_keyword:
                search_str = f'({search_str} OR SUBJECT "{search_keyword}" BODY "{search_keyword}")'

            status, email_ids = self.imap_connection.search(None, search_str)
            email_id_list = email_ids[0].split()
            num_emails_to_fetch = min(num_emails, len(email_id_list))
            email_messages: List[EmailMessage] = []
            
            for i in range(-1, -1*num_emails_to_fetch-1, -1): # Fetch emails in reverse order
                status, email_data = self.imap_connection.fetch(email_id_list[i], "(RFC822)")

                email_data = email_data[0]
                if isinstance(email_data, tuple):
                    raw_email = email_data[1]
                    email_message = email.message_from_bytes(raw_email, _class=EmailMessage, policy=SMTPUTF8)
                    email_messages.append(email_message) # type: ignore - we specified the _class argument to EmailMessage


            return email_messages

        except Exception as e:
            return f"Error: Could not read emails - {e}"
    
    async def read_emails_dummy(self, *args, **kwargs):
        #return list with 0-10 dummy random emails
        fake = Faker()
        email_messages = []
        for _ in range(random.randint(0,10)):
            email_message = EmailMessage()
            email_message["Subject"] = fake.sentence()
            email_message["From"] = fake.email()
            email_message["To"] = fake.email()
            email_message["Date"] = fake.date_time()
            email_message.set_content(random.choice(examples)) #randomly choose one of the dummy emails
            email_messages.append(email_message)
        
        return email_messages

from mail_init import CustomGraphServiceClient
from typing import Union, List
from msgraph.generated.models.message import Message
from msgraph.generated.users.item.messages.messages_request_builder import MessagesRequestBuilder

class EmailClientAzure:
    """
    A class that encapsulates email-related operations using the Microsoft Graph SDK.

    Args:
        client (GraphServiceClient): An instance of the Microsoft Graph Service Client.

    Attributes:
        client (GraphServiceClient): An instance of the Microsoft Graph Service Client.
    """

    def __init__(self, client: CustomGraphServiceClient) -> None:
        """
        Initializes the EmailService with the Microsoft Graph client.

        Args:
            client (GraphServiceClient): An instance of the Microsoft Graph Service Client.
        """
        self.client = client

    async def send_email(self, subject: str, body: str, to_email: str) -> str:
        """
        Sends an email.

        Args:
            subject (str): The subject of the email.
            body (str): The content of the email.
            to_email (str): The recipient's email address.

        Returns:
            str: A message indicating the result of the operation.

        Raises:
            Exception: If an error occurs during the operation.
        """
        # new_email = Message(
        #     subject=subject,
        #     body=ItemBody(content=body),
        #     to_recipients=[Recipient(email_address=EmailAddress(address=to_email))]
        # )


        try:
            self.client.me.send_mail(message=new_email)
            return "Email sent successfully"
        except Exception as e:
            return str(e)

    async def get_email_folders(self) -> Union[List, str]:
        """
        Retrieves a list of email folders in the user's mailbox.

        Returns:
            list: A list of email folders.

        Raises:
            Exception: If an error occurs during the operation.
        """
        try:
            folders = self.client.me.mail_folders.get()
            return folders
        except Exception as e:
            return str(e)
    
    async def get_emails(self, sender_email: str = "") -> Union[list, str]:
        """
        Retrieves a list of email messages from the user's mailbox.

        Args:
            sender_email (str, optional): The email address of the sender. Defaults to None.

        Returns:
            list: A list of email messages.

        Raises:
            Exception: If an error occurs during the operation.
        """

        try:
            query_params = None
            if sender_email:
                query_params = MessagesRequestBuilder.MessagesRequestBuilderGetQueryParameters(
                    # filter=f'from/emailAddress/address eq \'{sender_email}\'',
                    search='MAP TA PHUT',
                )

            config = MessagesRequestBuilder.MessagesRequestBuilderGetRequestConfiguration(
                query_parameters=query_params,
            )
            
            messages = await self.client.me.messages.get(config)

            return messages.value
        except Exception as e:
            return str(e)

    async def get_email_attachments(self, message_id: str) -> Union[list, str]:
        """
        Retrieves email attachments for a specific email message.

        Args:
            message_id (str): The ID of the email message.

        Returns:
            list: A list of email attachments.

        Raises:
            Exception: If an error occurs during the operation.
        """
        try:
            attachments = self.client.me.messages[message_id].attachments.get()
            return attachments
        except Exception as e:
            return str(e)

    async def reply_to_email(self, message_id: str) -> str:
        """
        Replies to an email message.

        Args:
            message_id (str): The ID of the email message to reply to.

        Returns:
            str: A message indicating the result of the operation.

        Raises:
            Exception: If an error occurs during the operation.
        """
        try:
            self.client.me.messages[message_id].reply()
            return "Email replied successfully"
        except Exception as e:
            return str(e)

    async def forward_email(self, message_id: str) -> str:
        """
        Forwards an email message.

        Args:
            message_id (str): The ID of the email message to forward.

        Returns:
            str: A message indicating the result of the operation.

        Raises:
            Exception: If an error occurs during the operation.
        """
        try:
            self.client.me.messages[message_id].forward()
            return "Email forwarded successfully"
        except Exception as e:
            return str(e)

    async def move_email(self, message_id: str, folder_id: str) -> str:
        """
        Moves an email message to a specified folder.

        Args:
            message_id (str): The ID of the email message to move.
            folder_id (str): The ID of the target folder.

        Returns:
            str: A message indicating the result of the operation.

        Raises:
            Exception: If an error occurs during the operation.
        """
        try:
            self.client.me.messages[message_id].move(destination_id=folder_id)
            return "Email moved successfully"
        except Exception as e:
            return str(e)

    async def delete_email(self, message_id: str) -> str:
        """
        Deletes an email message.

        Args:
            message_id (str): The ID of the email message to delete.

        Returns:
            str: A message indicating the result of the operation.

        Raises:
            Exception: If an error occurs during the operation.
        """
        try:
            self.client.me.messages[message_id].delete()
            return "Email deleted successfully"
        except Exception as e:
            return str(e)

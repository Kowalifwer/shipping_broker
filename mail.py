import imaplib
import email
from typing import List, Optional, Literal, Union, Type, Any

from email.message import EmailMessage as BaseEmailMessage
from msgraph.generated.models.message import Message as AzureEmailMessage

from mail_init import CustomGraphServiceClient
from msgraph.generated.models.message import Message
from msgraph.generated.users.item.messages.messages_request_builder import MessagesRequestBuilder

from email.policy import SMTPUTF8, default
from db import MongoEmail
from datetime import datetime
import random
from faker import Faker
from training.dummy_emails import examples
import requests
import asyncio

def subject_reveals_email_is_failed(text: str) -> bool:
    """Returns True if the subject reveals that the email is an undeliverable email, False otherwise."""

    word_list = ["undeliverable", "not read", "rejected", "failure", "spam", "couldn't be delivered"] # maybe notification? 
    
    lowercase_text = text.lower()
    for word in word_list:
        if word in lowercase_text:
            return True
    return False

def optional_chain(obj, return_if_fails, *attrs) -> Any:
    """Returns the last value in the chain of attributes, or {return_if_fails} upon the first failure"""
    for attr in attrs:
        if not hasattr(obj, attr):
            return return_if_fails

        obj = getattr(obj, attr)
        if obj is None:
            return return_if_fails

    return obj

def optional_chain_return_empty_str(obj, *attrs):
    """Returns the value of the first attribute in attrs that is not None, or "" if all attributes are None."""
    return optional_chain(obj, "", *attrs)

class EmailMessageAdapted:
    
    def __init__(self, base: Union[BaseEmailMessage, AzureEmailMessage]):
        if not isinstance(base, (BaseEmailMessage, AzureEmailMessage)):
            raise TypeError("base must be an instance of BaseEmailMessage or AzureEmailMessage.")
        # Store a reference to the base object
        self._base = base    

    ## Start of additional methods for EmailMessageAdapted class
    @property
    def id(self) -> str:
        if isinstance(self._base, AzureEmailMessage):
            return optional_chain_return_empty_str(self._base, "id")

        elif isinstance(self._base, BaseEmailMessage):
            return self._base["Message-ID"]

        return ""

    @property
    def subject(self) -> str:
        if isinstance(self._base, AzureEmailMessage):
            return optional_chain_return_empty_str(self._base, "subject")

        elif isinstance(self._base, BaseEmailMessage):
            return self._base["Subject"]
        
        return ""
    
    @property
    def sender(self) -> str:
        if isinstance(self._base, AzureEmailMessage):
            return optional_chain_return_empty_str(self._base, "sender", "email_address", "address")

        elif isinstance(self._base, BaseEmailMessage):
            return self._base["From"]
        
        return ""
    
    @property
    def recipients(self) -> str:
        if isinstance(self._base, AzureEmailMessage):
            #First 50 recipients, from list to string
            if self._base.to_recipients is None:
                return ""

            recipient_emails: List[str] = [recipient.email_address.address for recipient in self._base.to_recipients] # type: ignore - to_recipients is Optional
            if recipient_emails:
                return ",".join(recipient_emails[:50])

            return ""

        elif isinstance(self._base, BaseEmailMessage):
            return self._base["To"]

        return ""
    
    @property
    def date_received(self) -> str:
        if isinstance(self._base, AzureEmailMessage):
            return str(optional_chain_return_empty_str(self._base, "received_date_time"))

        elif isinstance(self._base, BaseEmailMessage):
            return self._base["Date"]

        return ""
    
    @property
    def is_read(self) -> bool:
        if isinstance(self._base, AzureEmailMessage):
            return optional_chain(self._base, False, "is_read")

        elif isinstance(self._base, BaseEmailMessage):
            return True

        return False
    
    @property
    def body(self) -> str:
        if isinstance(self._base, AzureEmailMessage):
            return optional_chain_return_empty_str(self._base, "unique_body", "content")

        elif isinstance(self._base, BaseEmailMessage):
            body = self._base.get_body(preferencelist=('plain', 'html'))
            if body:
                charset = body.get_charset()
                if charset:
                    return body.get_content().decode(charset) # type: ignore - get_content() returns bytes, but decode() expects str
                else:
                    return body.get_content() # type: ignore - get_content() returns bytes, but decode() expects str
            else:
                return ""

        else:
            raise TypeError("base must be an instance of BaseEmailMessage or AzureEmailMessage.")
    
    @property
    def mongo_db_object(self) -> MongoEmail:
        return MongoEmail(
                id=self.id,
                subject=self.subject,
                sender=self.sender,
                recipients=self.recipients,
                date_received=self.date_received,
                timestamp_processed=datetime.now(),
                body=self.body,
            )

## End of additional methods for EmailMessageAdapted class

class EmailClientIMAP:
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

    async def read_emails(self, search_criteria: Literal["UNSEEN", "ALL"] = "UNSEEN", num_emails: int = 10, search_keyword: str = "") -> Union[List[EmailMessageAdapted], str]:
        """
        Reads email messages from the mailbox.

        Args:
            search_criteria (str, optional): The search criteria for emails. Default is "UNSEEN" (unread emails).
            num_emails (int, optional): The maximum number of emails to retrieve. Default is 10.

        Returns:
            List[EmailMessageAdapted]: A list of email message objects.
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
            email_messages: List[EmailMessageAdapted] = []
            
            for i in range(-1, -1*num_emails_to_fetch-1, -1): # Fetch emails in reverse order
                status, email_data = self.imap_connection.fetch(email_id_list[i], "(RFC822)")

                email_data = email_data[0]
                if isinstance(email_data, tuple):
                    raw_email = email_data[1]
                    email_message = email.message_from_bytes(raw_email, _class=BaseEmailMessage, policy=SMTPUTF8)
                    email_messages.append(EmailMessageAdapted(email_message)) # type: ignore - we specified the _class argument to EmailMessageAdapted

            return email_messages

        except Exception as e:
            return f"Error: Could not read emails - {e}"
    
    async def read_emails_dummy(self, *args, **kwargs) -> List[EmailMessageAdapted]:
        #return list with 0-10 dummy random emails
        fake = Faker()
        email_messages: List[EmailMessageAdapted] = []
        for _ in range(random.randint(0,10)):
            email_message = BaseEmailMessage()
            email_message["Subject"] = fake.sentence()
            email_message["From"] = fake.email()
            email_message["To"] = fake.email()
            email_message["Date"] = fake.date_time()
            email_message.set_content(random.choice(examples)) #randomly choose one of the dummy emails
            email_messages.append(EmailMessageAdapted(email_message))

        return email_messages

class EmailClientAzure:
    """
    A class that encapsulates email-related operations using the Microsoft Graph SDK.

    Args:
        client (CustomGraphServiceClient): An instance of the Microsoft Graph Service Client.
    """

    def __init__(self, client: CustomGraphServiceClient) -> None:
        """
        Initializes the EmailService with the Microsoft Graph client.

        Args:
            client (CustomGraphServiceClient): An instance of the Microsoft Graph Service Client.
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

    async def set_emails_to_read(self, email_ids: List[str]) -> bool:

        batch_requests = []

        for i, email_id in enumerate(email_ids):

            # Add the PATCH request to the batch
            batch_requests.append({
                "method": "PATCH",
                "id": i,
                "url": f"{self.client.me_url_without_base}/messages/{email_id}",  # Construct the URL for the specific email
                "headers": {
                    "Content-Type": "application/json",
                },
                "body": {
                    "isRead": "true"  # Sets the email to read
                },
            })

        await self.client.post_batch_request(batch_requests)

        return True

    async def delete_emails(self, email_ids: List[str]) -> bool:

        batch_requests = []

        for i, email_id in enumerate(email_ids):

            # Add the DELETE request to the batch
            batch_requests.append({
                "method": "DELETE",
                "id": i,
                "url": f"{self.client.me_url_without_base}/messages/{email_id}",  # Construct the URL for the specific email
            })

        await self.client.post_batch_request(batch_requests)

        return True
    
    async def read_emails_and_delete_spam(self, n:int, most_recent_first: bool = True, unseen_only: bool = False):
        return await self.get_emails(n=n, unseen_only=unseen_only, most_recent_first=most_recent_first, remove_undelivered=True, set_to_read=False)

    # Note: cannot sort by date recieved AND filter by name. Only one or the other.
    async def get_emails(self, 
        # Below are the parameters for the api call
        # sender_email: Optional[str] = None,
        n: int = 5,
        unseen_only: bool = True,
        most_recent_first: bool = True,

        folders: Optional[List[str]] = [], # List of folders to search in. If empty, search in all folders.

        # Below are the parameters for post-processing
        remove_undelivered: bool = True,
        set_to_read: bool = True,
    ) -> Union[List[EmailMessageAdapted], str]:
        """
        Retrieves a list of email messages from the user's mailbox.

        IF remove_undelivered is True, then those emails will be deleted and not included in the return list.

        Args:
            search (str, optional): The search criteria for emails.
            n (int, optional): The maximum number of emails to retrieve. Default is 5.
            unseen_only (bool, optional): Whether to retrieve only unseen emails. Default is True.
            most_recent_first (bool, optional): Whether to sort the emails by most recent first. Default is True.



        Returns:
            list: A list of EmailMessageAdapted objects, that can be used throughout the application.

        Raises:
            Exception: If an error occurs during the operation.

        API Reference: https://learn.microsoft.com/en-us/graph/api/message-get?view=graph-rest-1.0&tabs=python
        and: https://learn.microsoft.com/en-us/graph/query-parameters?tabs=http
        """
        try:
            MAX_MSG_PER_REQUEST = 50

            query_params = {
                "top": min(n, MAX_MSG_PER_REQUEST),  # The maximum number of messages to return
                "select": ['id', 'subject', 'sender', 'toRecipients', 'receivedDateTime', 'uniqueBody', 'isRead'],  # uniqueBody is the body of the email without any reply/forward history
            }

            # if sender_email:
            #     query_params["filter"] = f'from/emailAddress/address eq \'{sender_email}\''

            # if remove_undelivered:
            #     if query_params["filter"]:
            #         query_params["filter"] += ' and '

            #     # check if subject contains 'Undeliverable:'
            #     query_params["filter"] += 'not startswith(subject, \'Undeliverable:\')'

            # Using filter and orderby in the same query
            # When using $filter and $orderby in the same query to get messages, make sure to specify properties in the following ways:

            # Properties that appear in $orderby must also appear in $filter.
            # Properties that appear in $orderby are in the same order as in $filter.
            # Properties that are present in $orderby appear in $filter before any properties that aren't.
            # Failing to do this results in the following error:

            # Error code: InefficientFilter
            # Error message: The restriction or sort order is too complex for this operation.

            if most_recent_first:
                query_params["orderby"] = ['receivedDateTime desc']
            else:
                query_params["orderby"] = ['receivedDateTime asc']

            # Take care if chaining filters in the future!
            if unseen_only:
                query_params["filter"] = 'isRead eq false'

            config = MessagesRequestBuilder.MessagesRequestBuilderGetRequestConfiguration(
                query_parameters = MessagesRequestBuilder.MessagesRequestBuilderGetQueryParameters(**query_params),
                headers={
                    "Prefer": "outlook.body-content-type=\"text\"",
                },
            )
            message_list = []

            # Do the first call with our config. Further pages will be retrieved in the loop below.
            messages = await self.client.me.messages.get(config)
            if messages:
                if messages.value:
                    print(f"Retrieved {len(messages.value)} emails from the server")
                    message_list.extend(messages.value)

                    next_link = messages.odata_next_link

                    if next_link: # If Azure API returns a link to the next page of results - means there are more emails to retrieve.
                        # Create a safe loop for the next n//MAX_MSG_PER_REQUEST requests. This will also handle the case if there are no more emails to retrieve (n_loops will be 0)
                        n_loops = (n-len(message_list))//MAX_MSG_PER_REQUEST
                        print(f"Will retrieve {n_loops} more batches of {MAX_MSG_PER_REQUEST} emails")
                        
                        for _ in range(n_loops):
                            messages = await self.client.me.messages.with_url(next_link).get()  # Fetch the next page of results using the url provided in the previous response.
                            if messages:
                                if messages.value:
                                    message_list.extend(messages.value)
                                    next_link = messages.odata_next_link

                                    if not next_link:
                                        print(f"Retrieval cut short as all emails have been read. Total of {len(message_list)} emails retrieved, even though {n} were requested.")
                                        break

            if message_list is not None:

                # To assemble the final list of messages
                final_message_list: List[EmailMessageAdapted] = []

                # To store id's of emails to delete and mark as read
                to_delete, to_mark_as_read = [], []

                for message in message_list:
                    
                    # Handles the case of frequent exchange underliverable emails.
                    if remove_undelivered:
                        if message.subject:
                            # Delete message if subject reveals it is an undeliverable email OR mark as read otherwise
                            if subject_reveals_email_is_failed(message.subject):
                                to_delete.append(message.id)
                            else:
                                final_message_list.append(EmailMessageAdapted(message))
                                if set_to_read:
                                    to_mark_as_read.append(message.id)

                    else:
                        final_message_list.append(EmailMessageAdapted(message))
                        if set_to_read:
                            to_mark_as_read.append(message.id)

                if remove_undelivered:
                    print(f"Excluded and deleted {len(to_delete)} undeliverable emails")

                print(f"Returning a total of {len(final_message_list)}/{len(message_list)} emails that were fetched from the server.")

                # Launch a background task to delete and mark emails as read, if necessary
                if set_to_read:
                    asyncio.create_task(self.set_emails_to_read(to_mark_as_read))
                if remove_undelivered:
                    asyncio.create_task(self.delete_emails(to_delete))

                return final_message_list
        
            print("no messages found")
            return []

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

import imaplib
import email
from typing import List, Optional, Literal
from email.message import EmailMessage
from email.policy import SMTPUTF8, default
from db import Email

## Additional methods for EmailMessage class
@property
def body(self):
    body = self.get_body(preferencelist=('plain', 'html'))
    if body:
        charset = body.get_charset()
        print(charset)
        if charset:
            return body.get_content().decode(charset)
        else:
            return body.get_content()
    else:
        return ""

def get_db_object(self) -> Email:
    return Email(
        id=self["Message-ID"],
        subject=self["Subject"],
        sender=self["From"],
        recipients=self["To"],
        timestamp=self["Date"],
        body=self.body
    )

EmailMessage.body = body
EmailMessage.get_db_object = get_db_object

## End of additional methods for EmailMessage class

class EmailClient:
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

    def read_emails(self, search_criteria: Literal["UNSEEN", "ALL"] = "UNSEEN", num_emails: int = 10, search_keyword: str = "") -> List[EmailMessage]:
        """
        Reads email messages from the mailbox.

        Args:
            search_criteria (str, optional): The search criteria for emails. Default is "UNSEEN" (unread emails).
            num_emails (int, optional): The maximum number of emails to retrieve. Default is 10.

        Returns:
            List[EmailMessage]: A list of email message objects.
        """
        if not self.imap_connection:
            raise Exception("Error: Not connected to the IMAP server.")

        try:
            self.imap_connection.select(self.mailbox_name)
            search_criteria = f"{search_criteria}"
            if search_keyword:
                search_criteria = f'({search_criteria} OR SUBJECT "{search_keyword}" BODY "{search_keyword}")'
            
            print(f"Searching for emails with criteria: {search_criteria}")

            status, email_ids = self.imap_connection.search(None, search_criteria)
            email_id_list = email_ids[0].split()
            num_emails_to_fetch = min(num_emails, len(email_id_list))
            email_messages: List[EmailMessage] = []
            
            for i in range(-1, -1*num_emails_to_fetch - 1, -1): # Fetch emails in reverse order
                status, email_data = self.imap_connection.fetch(email_id_list[i], "(RFC822)")
                raw_email = email_data[0][1]
                email_message = email.message_from_bytes(raw_email, _class=EmailMessage, policy=SMTPUTF8)
                email_messages.append(email_message)


            return email_messages

        except Exception as e:
            raise Exception(f"Error: Could not fetch emails - {e}")
from msgraph import GraphServiceClient
from typing import Union, List
from msgraph.generated.models.message import Message
from msgraph.generated.users.item.messages.messages_request_builder import MessagesRequestBuilder

class EmailService:
    """
    A class that encapsulates email-related operations using the Microsoft Graph SDK.

    Args:
        client (GraphServiceClient): An instance of the Microsoft Graph Service Client.

    Attributes:
        client (GraphServiceClient): An instance of the Microsoft Graph Service Client.
    """

    def __init__(self, client: 'GraphServiceClient') -> None:
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
    
    async def get_emails(self, sender_email: str = None) -> Union[list, str]:
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

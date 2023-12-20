import asyncio
import mail_init
import configparser
from typing import List, AsyncGenerator
from msgraph.generated.users.item.messages.messages_request_builder import MessagesRequestBuilder
import traceback

# Constants
MAX_MSG_PER_REQUEST = 250 # Controls the number of messages requested from the Azure Api, per request. Not recommended to go over 100.

async def main():
    events = []
    try:
        config = configparser.ConfigParser()
        config.read('config.cfg')

        azure_keys = ["azure2", "azure1"]
        tasks = []

        for key in azure_keys:
            azure_graph_client = mail_init.connect_to_azure(config[key])
            if isinstance(azure_graph_client, str):
                # If the connection is a string, it is an error message. Print it and exit.
                print(azure_graph_client)
                exit()

            # Create a task for each azure client
            event = asyncio.Event()
            events.append(event)
            print(f"Starting mail cleaner process for {config[key]['name']} inbox.")
            tasks.append(asyncio.create_task(mail_cleaner_process(azure_graph_client, config[key]["name"], event)))

        # Wait for all tasks to finish
        await asyncio.gather(*tasks)

        print("-----------------------------------------------")
        print("All tasks complete. You may now restart the program.")

    except Exception as e:
        print(f"Exception in main: {e}. Stopping all mail cleaner processes.")

        for event in events:
            event.set()

        await asyncio.sleep(5)
        asyncio.get_running_loop().stop()

async def mail_cleaner_process(azure_graph_client, inbox_name, stop_event: asyncio.Event):
    try:
        async for n_deleted in endless_email_deletion_generator(azure_graph_client, inbox_name):
            print(f"{inbox_name} UPDATE: {n_deleted} emails DELETED.")
            if stop_event.is_set():
                return

            await asyncio.sleep(1)

    except Exception as e:
        if not str(e):
            print(repr(e))
        else:
            print(f"Exception in mail_cleaner_process: {e}. Stopping mail cleaner process for {inbox_name} inbox.")

        return

def launch_delete_emails_task(azure_client, email_ids: List[str]):
    if not email_ids:
        return True

    batch_requests = []

    for i, email_id in enumerate(email_ids, start=1):

        # Add the DELETE request to the batch
        batch_requests.append({
            "method": "DELETE",
            "id": i,
            "url": f"{azure_client.me_url_without_base}/messages/{email_id}",  # Construct the URL for the specific email
        })

    azure_client.post_batch_request_no_answer(batch_requests)

# Helper functions
def subject_reveals_email_is_failed(text: str) -> bool:
    """Returns True if the subject reveals that the email is an undeliverable email, False otherwise."""

    word_list = ["undeliver", "not read", "rejected", "failure", "couldn't be delivered"] # maybe notification?

    lowercase_text = text.lower()
    for word in word_list:
        if word in lowercase_text:
            return True
    return False

async def endless_email_deletion_generator(azure_client,
    mailbox_name,
    # Below are the parameters for the api call
    # sender_email: Optional[str] = None,
    n: int = 9999,
    batch_size: int = MAX_MSG_PER_REQUEST,
    unseen_only: bool = False,
    most_recent_first: bool = True,

    folders: List[str] = ["inbox", "junkemail"], # List of folders to search in. For all shortcuts: # https://learn.microsoft.com/en-us/graph/api/resources/mailfolder?view=graph-rest-1.0 for all mail folder access shortcuts
) -> AsyncGenerator[int, None]:
    """
    Endlessly generates batches(lists) of size {batch-size} of email messages from the user's mailbox.

    IF remove_undelivered is True, then those emails will be deleted and not included in the return list.

    Args:
        n: The maximum number of emails to retrieve. Generator will stop yielding either when n emails have been retrieved, or when there are no more emails to retrieve.
        batch_size: The number of emails to retrieve per request. Default is MAX_MSG_PER_REQUEST.

        unseen_only: If True, only unseen/unread emails will be retrieved. Default is True.
        most_recent_first: If True, the most recent emails will be retrieved first. set to False for oldest first. Default is True.
        folders: A list of folders to be searched in. Default is ["inbox", "junkemail"].

        remove_undelivered: If True, emails with subject that reveals they are undeliverable, will be deleted. Default is True. Look at subject_reveals_email_is_failed() for the list of keywords that are used to detect undeliverable emails.
        set_to_read: If True, emails will be marked as read during post-processing. Default is True.

    Returns:
        list: A list of EmailMessageAdapted objects, that can be used throughout the application.

    Raises:
        Exception: If an error occurs during the operation.

    API Reference: https://learn.microsoft.com/en-us/graph/api/message-get?view=graph-rest-1.0&tabs=python
    and: https://learn.microsoft.com/en-us/graph/query-parameters?tabs=http
    """

    folder_filters = [f"parentFolderId eq '{folder_name}'" for folder_name in folders]
    folder_filter_string = " or ".join(folder_filters)

    query_params = {
        "top": min(n, batch_size),  # The maximum number of messages to return
        "select": ['id', 'subject'],
        "filter": folder_filter_string,
    }

    if most_recent_first:
        query_params["orderby"] = ['receivedDateTime desc']
    else:
        query_params["orderby"] = ['receivedDateTime asc']

    # Take care if chaining filters in the future!
    if unseen_only:
        query_params["filter"] += ' and isRead eq false'

    config = MessagesRequestBuilder.MessagesRequestBuilderGetRequestConfiguration(
        query_parameters = MessagesRequestBuilder.MessagesRequestBuilderGetQueryParameters(**query_params),
        headers={
            "Prefer": "outlook.body-content-type=\"text\"",
        },
    )

    # Do the first call with our config. Further pages will be retrieved in the loop below.
    messages = await azure_client.me.messages.get(config)
    yielded_messages_count = 0
    total_deleted_count = 0
    if messages:
        if messages.value:
            next_link = messages.odata_next_link

            msg_ids_to_delete = [msg.id for msg in messages.value if msg.subject and subject_reveals_email_is_failed(msg.subject)]

            launch_delete_emails_task(azure_client, msg_ids_to_delete)

            yielded_messages_count += len(messages.value)
            total_deleted_count += len(msg_ids_to_delete)

            if not next_link:
                print(f"{mailbox_name} mailbox cleaned! {total_deleted_count}/{yielded_messages_count} EMAILS CLEANED.")
                yield len(msg_ids_to_delete)
                return

            yield len(msg_ids_to_delete)

            if next_link: # If Azure API returns a link to the next page of results - means there are more emails to retrieve.
                # Create a safe loop for the next n//batch_size requests. This will also handle the case if there are no more emails to retrieve (n_loops will be 0)
                n_loops = (n-yielded_messages_count)//batch_size

                for i in range(n_loops):
                    messages = await azure_client.me.messages.with_url(next_link).get()  # Fetch the next page of results using the url provided in the previous response.
                    if messages:
                        if messages.value:

                            msg_ids_to_delete = [msg.id for msg in messages.value if msg.subject and subject_reveals_email_is_failed(msg.subject)]

                            launch_delete_emails_task(azure_client, msg_ids_to_delete)

                            next_link = messages.odata_next_link
                            yielded_messages_count += len(messages.value)

                            yield len(msg_ids_to_delete)

                            if not next_link:
                                print(f"{mailbox_name} mailbox cleaned! {total_deleted_count}/{yielded_messages_count} EMAILS CLEANED.")
                                return

if __name__ == "__main__":

    asyncio.run(main())
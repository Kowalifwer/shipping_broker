from requests_oauthlib import OAuth2Session
from oauthlib.oauth2 import BackendApplicationClient
from requests.auth import HTTPBasicAuth
import requests
from msgraph import GraphServiceClient
from azure.mail import EmailService
from azure.core.credentials_async import AsyncTokenCredential
from azure.core.credentials import AccessToken
from typing import Any, Union, List, Optional
from msgraph import GraphServiceClient
import httpx

BATCH_REQUEST_LIMIT = 20

class TokenAdaptor(AsyncTokenCredential):
    
    """Acts as an adaptor for the string access token to be compatible with the Azure SDK GraphServiceClient class."""

    def __init__(self, access_token):
        self.access_token: str = access_token

    async def get_token(
        self,
        *args: Any,
        **kwargs: Any,
    ) -> AccessToken:

        return AccessToken(self.access_token, 3600)

class CustomGraphServiceClient(GraphServiceClient):
    """Intended to have all the functionality of the GraphServiceClient class, but with additional custom behavior."""


    def __init__(self, access_token: str, scopes: List[str], client_id: str, user_id: Optional[str]):
        self.access_token_str = access_token
        self.client_id = client_id
        self.user_id = user_id
        super().__init__(
            credentials=TokenAdaptor(access_token),
            scopes=scopes,
        )
    
    @property
    def base_url(self) -> str:
        """Returns the base URL of the Graph API, e.g. https://graph.microsoft.com/v1.0"""
        return "https://graph.microsoft.com/v1.0"
    
    @property
    def me(self):
        """Overrides the existing me property, to reroute to self.users.by_user_id if user_id is provided."""
        if self.user_id:
            return self.users.by_user_id(self.user_id)

        return super().me
    
    @property
    def me_url_with_base(self):
        """Returns the base URL of the Graph API with the access point, e.g. https://graph.microsoft.com/v1.0/me or https://graph.microsoft.com/v1.0/users/{{user-id}}"""
        base_url = self.base_url
        if self.user_id:
            return f"{base_url}/users/{self.user_id}"

        return f"{base_url}/me"

    @property
    def me_url_without_base(self):
        """Returns the access point AFTER the base URL.
           returns /me if no user id is provided. 
           returns /users/{{user-id}} if user id is provided."""
        if self.user_id:
            return f"/users/{self.user_id}"

        return "/me"
    
    async def post_batch_request(self, batch_requests: List[dict]) -> dict:
        """
        Sends a batch request to the Graph API. Returns the response if successful, dict with status code and error message if not.
        This function will automatically split the batch request into multiple sub-batches if the number of requests exceeds the Azure limit.
        
        args:
            batch_requests: a list of dicts, each dict representing a request to be included in the batch.
        """
        total = 0
        operation_name = ""
        batches = [batch_requests[i:i + BATCH_REQUEST_LIMIT] for i in range(0, len(batch_requests), BATCH_REQUEST_LIMIT)]
        if batches:
            if batches[0]:
                operation_name = batches[0][0]["method"]
                print(f"Will attemtpt to send {len(batches)} batches of batch requests. Method: {batches[0][0]['method']}")

        for i, batch in enumerate(batches, start=1):
            total += len(batch)
            print(f"Sending sub-batch request {i}/{len(batches)} with {len(batch)} requests.")
            batch_response = await self._post_batch_request(batch)
            if batch_response["status"] != 200:
                return batch_response
        
        print(f"Batch operation ({operation_name}) completed successfully. Total number of requests: {total}")

        return {"status": 200, "body": "Batch request completed."}
    
    async def _post_batch_request(self, batch_requests: List[dict]) -> dict:
        """A helper function for post_batch_request, which sends a single batch request of up to BATCH_REQUEST_LIMIT requests."""

        # Send the batch request (async, since it might take some time)
        async with httpx.AsyncClient() as client:
            batch_response = await client.post(
                url=f"{self.base_url}/$batch",
                json={"requests": batch_requests},
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.access_token_str}",
                },
            )

            # Check if the batch request was successful
            if batch_response.status_code != 200:
                print(f"Error: Batch request failed - {batch_response.text}")
                return {"status": batch_response.status_code, "body": batch_response.text}
            
            return {"status": batch_response.status_code, "body": batch_response.json()}
    
    async def set_emails_to_read(self, email_ids: List[str]) -> bool:
        #split email ids into batches based on BATCH_REQUEST_LIMIT
        batches = [email_ids[i:i + BATCH_REQUEST_LIMIT] for i in range(0, len(email_ids), BATCH_REQUEST_LIMIT)]

        print(f"Will set {len(email_ids)} emails to read in {len(batches)} batches")
        for batch in batches:
            status = await self._set_emails_to_read(batch)
            if not status:
                return False
            print(f"Batch completed")

        return True
    
    async def _set_emails_to_read(self, email_ids: List[str]) -> bool:

        batch_requests = []

        for i, email_id in enumerate(email_ids, start=1):

            # Construct the URL for the specific email
            request_url = f"{self.client.me_url_without_base}/messages/{email_id}"

            # Construct the request body to update the 'isRead' property
            request_body = {
                "isRead": "true"
            }

            # Add the PATCH request to the batch
            batch_requests.append({
                "method": "PATCH",
                "url": request_url,
                "id": i,
                "headers": {
                    "Content-Type": "application/json",
                },
                "body": request_body,
            })

        # Send the batch request (async, since it might take some time)
        async with httpx.AsyncClient() as client:
            batch_response = await client.post(
                url="https://graph.microsoft.com/v1.0/$batch",
                json={"requests": batch_requests},
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.client.access_token_str}",
                },
            )

            # Check if the batch request was successful
            if batch_response.status_code != 200:
                print(f"Error: Could not update emails to read - {batch_response.text}")
                return False
            
            for response in batch_response.json()["responses"]:
                if response["status"] != 200:
                    print(f"Error: Could not update email {response['id']} to read - {response['body']['error']['message']}")

        return True

def connect_to_azure(azure_conf) -> Union[CustomGraphServiceClient, str]:
    
    scope = ["https://graph.microsoft.com/.default"]
    endpoint = "https://graph.microsoft.com/v1.0/users"

    client_id = azure_conf['client_id']
    client_secret = azure_conf['client_secret_value']
    tenant_id = azure_conf['tenant_id']
    user_id = azure_conf['user_id']

    # azure_app = msal.ConfidentialClientApplication(
    #     client_id, authority=f"https://login.microsoftonline.com/{tenant_id}",
    #     client_credential=client_secret
    # )

    client = BackendApplicationClient(client_id=client_id, scope=scope)
    oauth = OAuth2Session(client=client)
    result = oauth.fetch_token(token_url=f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token",
                            auth=HTTPBasicAuth(client_id, client_secret),
                            scope=scope)

    # result = azure_app.acquire_token_silent(scope, account=None)

    # if not result:
    #     print("No suitable token exists in cache. Let's get a new one from AAD.")
    #     result = azure_app.acquire_token_for_client(scopes=scope)

    if not result:
        return "Failed to acquire a token from Azure AD."

    access_token = result.get("access_token", None)

    if access_token is None:
        print(result.get("error"))
        print(result.get("error_description"))
        print(result.get("correlation_id"))  # You might need this when reporting a bug.
        return "Failed to acquire a token from Azure AD."

    response = requests.get(endpoint, headers={'Authorization': 'Bearer ' + access_token})

    if response.status_code == 200:
        print("Connected to Azure services.")
    else:
        return f"Failed to connect to Azure services. - api call failed. {response.status_code} - {response.text}"

    client = CustomGraphServiceClient(
        access_token=access_token,
        scopes=scope,
        client_id=client_id,
        user_id=user_id
    )

    return client


# Obtain an access token using OAuth2
# client = BackendApplicationClient(client_id=client_id, scope=scope)
# oauth = OAuth2Session(client=client)
# result = oauth.fetch_token(token_url=f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token",
#                           auth=HTTPBasicAuth(client_id, client_secret),
#                           scope=scope)
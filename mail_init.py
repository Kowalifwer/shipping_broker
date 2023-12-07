from requests_oauthlib import OAuth2Session
from oauthlib.oauth2 import BackendApplicationClient
from requests.auth import HTTPBasicAuth
import requests
import msal
from msgraph import GraphServiceClient
from azure.mail import EmailService
from azure.core.credentials_async import AsyncTokenCredential
from azure.core.credentials import AccessToken
from typing import Any, Union, List, Optional
from msgraph import GraphServiceClient

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
    def me(self):
        """If a user id is provided, this will reroute from /me to /users/{{user-id}}. Otherwise, it will return the default .me property."""
        if self.user_id:
            return self.users.by_user_id(self.user_id)

        return super().me

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
    # print(response.json())

    if response.status_code == 200:
        print("Connected to Azure services.")
    else:
        return "Failed to connect to Azure services. - api call failed"

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
from fastapi import FastAPI, Depends, HTTPException, Query, Request, BackgroundTasks
from fastapi.responses import RedirectResponse
import requests
import msal
import configparser
from azure.core.credentials_async import AsyncTokenCredential
from azure.core.credentials import AccessToken
from typing import Any
from msgraph import GraphServiceClient
from azure.mail import EmailService

# OAuth2 configuration
# Get credentials from config.cfg
config = configparser.ConfigParser()
config.read('config.cfg')
config = config['azure']
client_id = config['client_id']
client_secret = config['client_secret']
tenant_id = config['tenant_id']
redirect_uri = config['redirect_uri']

authority = "https://login.microsoftonline.com/common"  # common, to allow any microsoft account to authenticate
SCOPES = ["User.Read", "Mail.Read", "Mail.Send"] # You can list the scopes you want to access

# Create a MSAL PublicClientApplication
client = msal.PublicClientApplication(
    client_id,
    authority=authority,
)

# Route for the root endpoint
@app.get("/")
async def read_root():
    return {"message": "Welcome to your FastAPI app!"}

access_token = None

# Route for login and redirection to the Microsoft login page
@app.get("/login")
async def login():
    try:
        auth_url = client.get_authorization_request_url(
            scopes=SCOPES,
            redirect_uri=redirect_uri
        )

        # redirect to Microsoft login page
        return RedirectResponse(auth_url)
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Authorization error - {e}")

# Route for handling the redirect from Microsoft login, and verifying the access token, so it can be used to make requests to the Microsoft Graph API
@app.get("/auth")
async def verified(code: str = Query(...)):
    global access_token

    try:
        # Build the request
        headers = {
            "Content-Type": "application/x-www-form-urlencoded"
        }
        data = {
            "grant_type": "authorization_code",   
            "client_id": client_id,
            "scope": SCOPES,
            "code": code,
            "redirect_uri": redirect_uri,
            "client_secret": client_secret
        }

        # Send the request
        response = requests.post(
            f"https://login.microsoftonline.com/common/oauth2/v2.0/token",
            headers=headers,
            data=data
        )

        if response.status_code == 200:
            access_token = response.json()["access_token"]
            return RedirectResponse(url="/search_emails")
            return {"message": "You have successfully logged in"}
        else:
            raise HTTPException(status_code=401, detail="Authorization error")

    except Exception as e:
        print(e)
        raise HTTPException(status_code=401, detail="Authorization error")

class Token(AsyncTokenCredential):

    def __init__(self, access_token):
        self.access_token: str = access_token

    async def get_token(
        *args: Any,
        **kwargs: Any,
        # self, *scopes: str, claims: Optional[str] = None, tenant_id: Optional[str] = None, **kwargs: Any
    ) -> AccessToken:
        return AccessToken(access_token, 3600)

# Route to read emails
@app.get("/read_emails")
async def read_emails():

    if access_token is None:
        return RedirectResponse(url="/login")
    
    token = Token(access_token)
    client = GraphServiceClient(
        credentials=token,
        scopes=SCOPES
    )

    messages = await EmailService(client).get_emails("circular@unimarservice.ltd")
    print(messages)
    subjects = [message.subject for message in messages]

    return subjects


from msgraph.generated.search.query.query_post_request_body import QueryPostRequestBody
from msgraph.generated.models.search_request import SearchRequest
from msgraph.generated.models.entity_type import EntityType
from msgraph.generated.models.search_query import SearchQuery


# Route to search emails
@app.get("/search_emails")
async def search_emails(query: str = Query(...)):
    if access_token is None:
        return RedirectResponse(url="/login")
    token = Token(access_token)
    client = GraphServiceClient(
        credentials=token,
        scopes=SCOPES
    )

    request_body = QueryPostRequestBody(
        requests = [
            SearchRequest(
                entity_types = [
                    EntityType.Message,
                ],
                query = SearchQuery(
                    query_string = "TTL 9,735MTS",
                    # query_template = "{searchTerms} CreatedBy:Bob",
                ),
                # size = 25,
            )
        ],
    )

    query_response = await client.search.query.post(body = request_body)
    print(query_response.value)
from fastapi import FastAPI, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
import requests
import msal
import configparser

app = FastAPI()

#uvicorn main:app --port 8000 --reload

# OAuth2 configuration
# Get credentials from config.cfg
config = configparser.ConfigParser()
config.read('config.cfg')
client_id = config['DEFAULT']['client_id']
client_secret = config['DEFAULT']['client_secret']
tenant_id = config['DEFAULT']['tenant_id']
redirect_uri = config['DEFAULT']['redirect_uri']

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
async def login(request: Request):
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
@app.get("/verified")
async def verified(request: Request, code: str = Query(...)):
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
            return {"message": "You have successfully logged in"}
        else:
            raise HTTPException(status_code=401, detail="Authorization error")

    except Exception as e:
        print(e)
        raise HTTPException(status_code=401, detail="Authorization error")

# Route to read emails
@app.get("/read_emails")
async def read_emails():
    if access_token is None:
        return RedirectResponse(url="/login")

    headers = {"Authorization": "Bearer " + access_token}

    # Get emails from Microsoft Graph API
    graph_api_url = "https://graph.microsoft.com/v1.0/me/messages"
    response = requests.get(graph_api_url, headers=headers)

    print(response.json())

    if response.status_code == 200:
        emails = response.json()
        return emails
    else:
        raise HTTPException(status_code=500, detail="Error reading emails")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
import requests
import os
from dotenv import load_dotenv
import random
import json
from fastapi.middleware.cors import CORSMiddleware


# Load environment variables
load_dotenv()

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
APP_URL = os.getenv("APP_URL")
API_URL = os.getenv("API_URL")

REDIRECT_URI = f"{API_URL}/callback"
ERROR_URI = f"{APP_URL}/auth/error"
LOGIN_URI = f"{APP_URL}/auth/login"
API_BASE_URL = "https://discord.com/api"

OAUTH_URL = f"{API_BASE_URL}/oauth2/authorize"
TOKEN_URL = f"{API_BASE_URL}/oauth2/token"
USER_URL = f"{API_BASE_URL}/users/@me"


# FastAPI app
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Root Route: Login page
@app.get("/", response_class=HTMLResponse)
async def root():
    return """
    <html>
        <body>
            <a href="/login">Login with Discord</a>
        </body>
    </html>
    """


# Login route: Return redirect url to Discord for authentication
@app.post("/login")
async def login(request: Request):

    TOKEN = request.query_params.get("token")

    if TOKEN is None:
        return JSONResponse(content=f"{ERROR_URI}?error=GET_TOKEN_FAILED")

    state = random.randbytes(7).hex()

    with open("data.json", "r") as f:
        data = json.load(f)
        data["states"][state] = TOKEN
    with open("data.json", "w") as f:
        json.dump(data, f, indent=2)

    return JSONResponse(
        f"{OAUTH_URL}?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&response_type=code&scope=identify+email&state={state}"
    )


# Callback route: Discord redirects here after successful login
@app.get("/callback")
async def callback(request: Request):
    """
    validate the state from the callback
    """
    code = request.query_params.get("code")
    state = request.query_params.get("state")

    # Error : state not found
    if state is None:
        return RedirectResponse(f"{ERROR_URI}?error=STATE_NOT_FOUND")

    with open("data.json", "r") as f:
        data: dict = json.load(f)

    # Error : state is not valid
    if state not in data["states"]:
        return RedirectResponse(f"{ERROR_URI}?error=INVALID_STATE")

    """
    get the access token from discord
    """
    TOKEN = data["states"].pop(state)

    with open("data.json", "w") as f:
        json.dump(data, f, indent=2)

    # Exchange the code for an access token
    try:
        response = requests.post(
            TOKEN_URL,
            data={
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": REDIRECT_URI,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    except Exception:
        return RedirectResponse(f"{ERROR_URI}?error=REQUEST_ERROR")

    # Error : cannot get token
    if not response.ok:
        return RedirectResponse(f"{ERROR_URI}?error=CANNOT_GET_TOKEN")

    """
    get the user discord id
    """

    access_token = response.json().get("access_token")
    refresh_token = response.json().get("refresh_token")

    # Get user data using the access token
    try:
        response = requests.get(
            USER_URL, headers={"Authorization": f"Bearer {access_token}"}
        )
    except Exception:
        return RedirectResponse(f"{ERROR_URI}?error=REQUEST_ERROR")

    # Error : cannot get user
    if not response.ok:
        return RedirectResponse(f"{ERROR_URI}?error=CANNOT_GET_USER")

    """
    store access token, request token, discord id, and refrsh token in database
    """
    with open("data.json", "r") as f:
        data = json.load(f)

    data["tokens"][TOKEN] = {
        "id": response.json().get("id"),
        "access_token": access_token,
        "refresh_token": refresh_token,
    }

    with open("data.json", "w") as f:
        json.dump(data, f, indent=2)

    # Error : cannot store token
    if not response.ok:
        return RedirectResponse(f"{ERROR_URI}?error=CANNOT_STORE_TOKEN")

    return RedirectResponse(APP_URL)

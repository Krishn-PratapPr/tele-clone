from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from telethon import TelegramClient
from telethon.sessions import SQLiteSession
from telethon.errors import SessionPasswordNeededError
import os
import asyncio

app = FastAPI()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")

clients = {}  # phone -> TelegramClient
os.makedirs("sessions", exist_ok=True)

templates = Jinja2Templates(directory="templates")


async def load_sessions():
    for filename in os.listdir("sessions"):
        if filename.endswith(".db"):
            phone = filename.replace(".db", "")
            client = TelegramClient(SQLiteSession(f"sessions/{phone}.db"), API_ID, API_HASH)
            await client.connect()
            if await client.is_user_authorized():
                clients[phone] = client


@app.on_event("startup")
async def startup_event():
    asyncio.create_task(load_sessions())


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "accounts": list(clients.keys())})


@app.get("/login", response_class=HTMLResponse)
async def login_get(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login", response_class=HTMLResponse)
async def login_post(request: Request, phone: str = Form(...)):
    session_path = f"sessions/{phone}.db"
    client = TelegramClient(SQLiteSession(session_path), API_ID, API_HASH)
    clients[phone] = client

    await client.connect()
    try:
        await client.send_code_request(phone)
    except Exception as e:
        return HTMLResponse(content=f"Error sending code: {e}", status_code=400)

    return templates.TemplateResponse("code.html", {"request": request, "phone": phone})


@app.post("/verify")
async def verify(request: Request, phone: str = Form(...), code: str = Form(...), password: str = Form(None)):
    client = clients.get(phone)
    if not client:
        return HTMLResponse(content="No client found!", status_code=400)

    try:
        await client.sign_in(phone, code)
    except Exception as e:
        if "PASSWORD" in str(e).upper():
            if not password:
                return HTMLResponse(content="Password required for 2FA!", status_code=400)
            try:
                await client.sign_in(password=password)
            except Exception as e2:
                return HTMLResponse(content=f"Error verifying password: {e2}", status_code=400)
        else:
            return HTMLResponse(content=f"Error verifying code: {e}", status_code=400)

    return RedirectResponse(url="/", status_code=303)


@app.post("/send")
async def send(request: Request, phone: str = Form(...), target: str = Form(...), message: str = Form(...)):
    client = clients.get(phone)
    if not client:
        return HTMLResponse(content="No client found!", status_code=400)

    try:
        await client.send_message(target, message)
    except Exception as e:
        return HTMLResponse(content=f"Error sending message: {e}", status_code=400)

    return RedirectResponse(url="/", status_code=303)


@app.get("/logout/{phone}")
async def logout(phone: str):
    client = clients.pop(phone, None)
    if client:
        try:
            await client.log_out()
        except Exception as e:
            return HTMLResponse(content=f"Error logging out: {e}", status_code=400)

    return RedirectResponse(url="/", status_code=303)

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from telethon import TelegramClient
from telethon.sessions import SQLiteSession
import os
import asyncio

app = FastAPI()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")

clients = {}  # phone -> TelegramClient
active_account = None  # Track current active account

os.makedirs("sessions", exist_ok=True)
templates = Jinja2Templates(directory="templates")


# ---------- Load Existing Sessions on Startup ----------
async def load_sessions():
    global clients
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


# ---------- Home ----------
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "accounts": list(clients.keys()), "active": active_account},
    )


# ---------- Login ----------
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


# ---------- Verify ----------
@app.post("/verify")
async def verify(request: Request, phone: str = Form(...), code: str = Form(...), password: str = Form(None)):
    global active_account
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

    # set as active after login
    active_account = phone

    return RedirectResponse(url="/", status_code=303)


# ---------- Send Message ----------
@app.post("/send")
async def send(request: Request, target: str = Form(...), message: str = Form(...)):
    global active_account
    if not active_account or active_account not in clients:
        return HTMLResponse(content="No active account!", status_code=400)

    client = clients[active_account]
    try:
        await client.send_message(target, message)
    except Exception as e:
        return HTMLResponse(content=f"Error sending message: {e}", status_code=400)

    return RedirectResponse(url="/", status_code=303)


# ---------- Logout ----------
@app.get("/logout/{phone}")
async def logout(phone: str):
    client = clients.pop(phone, None)
    if client:
        try:
            await client.log_out()
        except Exception as e:
            return HTMLResponse(content=f"Error logging out: {e}", status_code=400)

    global active_account
    if active_account == phone:
        active_account = None

    return RedirectResponse(url="/", status_code=303)


# ---------- Account Management ----------
@app.get("/accounts")
async def get_accounts():
    return {"accounts": list(clients.keys()), "active": active_account}


@app.get("/switch/{phone}")
async def switch_account(phone: str):
    global active_account
    if phone not in clients:
        return JSONResponse({"error": "Account not found"}, status_code=400)
    active_account = phone
    return {"message": f"Switched to {phone}"}


# ---------- Messages ----------
@app.get("/messages/{phone}")
async def get_messages(phone: str):
    if phone not in clients:
        return JSONResponse({"error": "Account not found"}, status_code=400)

    client = clients[phone]
    if not client.is_connected():
        await client.connect()

    dialogs = await client.get_dialogs(limit=10)
    chats = []
    for d in dialogs:
        messages = []
        async for m in client.iter_messages(d.id, limit=5):
            sender_name = None
            try:
                if m.sender:
                    sender_name = m.sender.first_name or m.sender.username or str(m.sender_id)
            except:
                sender_name = str(m.sender_id)

            messages.append({
                "id": m.id,
                "sender": sender_name,
                "text": m.text
            })
        chats.append({
            "chat_id": d.id,
            "title": d.name or "Unknown",
            "messages": messages
        })

    return {"phone": phone, "chats": chats}

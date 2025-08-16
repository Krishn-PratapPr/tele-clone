from flask import Flask, render_template, request, redirect, url_for
from telethon import TelegramClient
from telethon.sessions import SQLiteSession
import os, asyncio

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "super-secret-key")

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH"))

clients = {}  # phone -> TelegramClient
os.makedirs("sessions", exist_ok=True)


async def load_sessions():
    for filename in os.listdir("sessions"):
        if filename.endswith(".db"):
            phone = filename.replace(".db", "")
            client = TelegramClient(SQLiteSession(f"sessions/{phone}.db"), API_ID, API_HASH)
            await client.connect()
            clients[phone] = client

# Schedule session loading on first request
@app.before_first_request
def before_first_request_func():
    asyncio.create_task(load_sessions())


@app.route("/")
async def home():
    return render_template("index.html", accounts=list(clients.keys()))


@app.route("/login", methods=["GET", "POST"])
async def login():
    if request.method == "POST":
        phone = request.form["phone"]
        session_path = f"sessions/{phone}.db"
        client = TelegramClient(SQLiteSession(session_path), API_ID, API_HASH)
        clients[phone] = client

        await client.connect()
        try:
            await client.send_code_request(phone)
        except Exception as e:
            return f"Error sending code: {e}", 400

        return render_template("code.html", phone=phone)

    return render_template("login.html")


@app.route("/verify", methods=["POST"])
async def verify():
    phone = request.form["phone"]
    code = request.form["code"]
    client = clients.get(phone)
    if not client:
        return "No client found!", 400
    try:
        await client.sign_in(phone, code)
    except Exception as e:
        return f"Error verifying code: {e}", 400
    return redirect(url_for("home"))


@app.route("/send", methods=["POST"])
async def send():
    phone = request.form["phone"]
    target = request.form["target"]
    message = request.form["message"]

    client = clients.get(phone)
    if not client:
        return "No client found!", 400

    try:
        await client.send_message(target, message)
    except Exception as e:
        return f"Error sending message: {e}", 400

    return redirect(url_for("home"))


@app.route("/logout/<phone>")
async def logout(phone):
    client = clients.pop(phone, None)
    if client:
        try:
            await client.log_out()
        except Exception as e:
            return f"Error logging out: {e}", 400
    return redirect(url_for("home"))

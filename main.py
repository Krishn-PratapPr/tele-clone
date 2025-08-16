from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from telethon import TelegramClient
import os, asyncio

app = Flask(__name__)
app.secret_key = "super-secret-key"  # change this in production

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")

# Store all clients (phone -> client object)
clients = {}
loop = asyncio.get_event_loop()

# Dashboard home
@app.route("/")
def home():
    return render_template("index.html", accounts=list(clients.keys()))

# Login page (enter phone number)
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        phone = request.form["phone"]
        client = TelegramClient(f"sessions/{phone}", API_ID, API_HASH, loop=loop)
        clients[phone] = client
        loop.create_task(client.connect())
        session["phone"] = phone
        loop.create_task(client.send_code_request(phone))
        return render_template("code.html", phone=phone)
    return render_template("login.html")

# Verify code
@app.route("/verify", methods=["POST"])
def verify():
    phone = request.form["phone"]
    code = request.form["code"]
    client = clients.get(phone)
    if not client:
        return "No client found!", 400

    async def do_login():
        await client.sign_in(phone, code)

    loop.run_until_complete(do_login())
    return redirect(url_for("home"))

# Send message
@app.route("/send", methods=["POST"])
def send():
    phone = request.form["phone"]
    target = request.form["target"]
    message = request.form["message"]

    client = clients.get(phone)
    if not client:
        return "No client found!", 400

    async def do_send():
        await client.send_message(target, message)

    loop.run_until_complete(do_send())
    return redirect(url_for("home"))

# Logout
@app.route("/logout/<phone>")
def logout(phone):
    client = clients.pop(phone, None)
    if client:
        loop.run_until_complete(client.log_out())
    return redirect(url_for("home"))

if __name__ == "__main__":
    os.makedirs("sessions", exist_ok=True)
    app.run(host="0.0.0.0", port=10000)

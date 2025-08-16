from flask import Flask, render_template, request, redirect, url_for
from telethon import TelegramClient
import os, asyncio

app = Flask(__name__)
app.secret_key = "super-secret-key"

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")

# Store clients
clients = {}
loop = asyncio.get_event_loop()


@app.route("/")
def home():
    return render_template("index.html", accounts=list(clients.keys()))


# Step 1: enter phone
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        phone = request.form["phone"]

        # create client
        client = TelegramClient(f"sessions/{phone}", API_ID, API_HASH, loop=loop)
        clients[phone] = client

        async def send_code():
            await client.connect()
            await client.send_code_request(phone)

        loop.run_until_complete(send_code())
        return render_template("code.html", phone=phone)

    return render_template("login.html")


# Step 2: enter code
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
        async def do_logout():
            await client.log_out()
        loop.run_until_complete(do_logout())
    return redirect(url_for("home"))


if __name__ == "__main__":
    os.makedirs("sessions", exist_ok=True)
    app.run(host="0.0.0.0", port=10000)

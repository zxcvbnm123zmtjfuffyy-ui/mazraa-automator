#!/usr/bin/env python3
"""
Mazraat Credits Automator v3.0 - with Discord Control Bot
Author: Dark & f5r
"""

import os
import json
import time
import random
import threading
import requests
from datetime import datetime, timedelta
from flask import Flask, request, jsonify

# ========== CONFIGURATION FROM ENVIRONMENT ==========
TOKENS_LIST = os.environ.get("TOKENS_LIST", "")
GUILD_ID = os.environ.get("GUILD_ID", "")
CHANNEL_ID = os.environ.get("CHANNEL_ID", "")
CONTROL_API_KEY = os.environ.get("CONTROL_API_KEY", "default_key_change_me")
DISCORD_BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "")
COMMAND_CHANNEL_ID = os.environ.get("COMMAND_CHANNEL_ID", "")
PORT = int(os.environ.get("PORT", 5000))

if not TOKENS_LIST:
    raise ValueError("❌ TOKENS_LIST not set!")
if not GUILD_ID or not CHANNEL_ID:
    raise ValueError("❌ GUILD_ID and CHANNEL_ID must be set!")

TOKENS = [t.strip() for t in TOKENS_LIST.split(",") if t.strip()]
DATA_FILE = "schedule_data.json"

# ========== LOGGING ==========
def log(msg, level="INFO"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {msg}")

# ========== DISCORD API HELPERS (Self-bot for credits) ==========
def send_message(token, channel_id, content):
    url = f"https://discord.com/api/v9/channels/{channel_id}/messages"
    headers = {
        "Authorization": token,
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0"
    }
    payload = {"content": content}
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=15)
        return r.status_code == 200, None
    except:
        return False, None

def execute_daily(token, channel_id, account_name):
    for cmd in ["d", "D", "/daily"]:
        ok, _ = send_message(token, channel_id, cmd)
        if ok:
            log(f"{account_name} -> DAILY: '{cmd}'")
            return True
    return False

def execute_profile(token, channel_id, account_name):
    for cmd in ["p", "P", "/profile"]:
        ok, _ = send_message(token, channel_id, cmd)
        if ok:
            log(f"{account_name} -> PROFILE")
            return True
    return False

def execute_credits(token, channel_id, account_name):
    for cmd in ["c", "C", "/credits"]:
        ok, _ = send_message(token, channel_id, cmd)
        if ok:
            log(f"{account_name} -> CREDITS")
            return True
    return False

def execute_say(token, channel_id, message):
    ok, _ = send_message(token, channel_id, message)
    return ok

def get_account_name(token, idx):
    url = "https://discord.com/api/v9/users/@me"
    headers = {"Authorization": token}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            data = r.json()
            return f"{data['username']}#{data.get('discriminator', '0')}"
    except:
        pass
    return f"Account_{idx+1}"

# ========== PERSISTENT SCHEDULE ==========
def load_schedule():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {}

def save_schedule(schedule):
    with open(DATA_FILE, "w") as f:
        json.dump(schedule, f, indent=2)

def init_schedule():
    schedule = load_schedule()
    changed = False
    now = datetime.now()
    for idx, token in enumerate(TOKENS):
        if token not in schedule:
            delay_hours = random.uniform(0, 2)
            next_run = now + timedelta(hours=delay_hours)
            schedule[token] = {
                "last_run": None,
                "next_run": next_run.isoformat(),
                "account_name": get_account_name(token, idx)
            }
            changed = True
    if changed:
        save_schedule(schedule)
    return schedule

# ========== DAILY SCHEDULER THREAD ==========
scheduler_running = True

def scheduler_loop():
    global scheduler_running
    log("🕒 Scheduler thread started")
    schedule = init_schedule()
    while scheduler_running:
        now = datetime.now()
        updated = False
        for token in TOKENS:
            entry = schedule.get(token)
            if not entry:
                continue
            next_run = datetime.fromisoformat(entry["next_run"])
            account_name = entry["account_name"]
            if now >= next_run:
                log(f"⏰ Executing daily for {account_name}")
                success = execute_daily(token, CHANNEL_ID, account_name)
                next_hours = random.uniform(23, 25)
                next_run_time = now + timedelta(hours=next_hours)
                entry["last_run"] = now.isoformat()
                entry["next_run"] = next_run_time.isoformat()
                entry["last_success"] = success
                updated = True
                log(f"{account_name} -> next daily in {next_hours:.1f}h")
        if updated:
            save_schedule(schedule)
        time.sleep(60)

# ========== FLASK API ==========
app = Flask(__name__)

def authorize():
    key = request.args.get("api_key") or request.headers.get("X-API-Key")
    return key == CONTROL_API_KEY

@app.route("/")
def index():
    return jsonify({"status": "running", "accounts": len(TOKENS)})

@app.route("/control", methods=["GET", "POST"])
def control():
    if not authorize():
        return jsonify({"error": "Unauthorized"}), 401
    cmd = request.args.get("cmd") or (request.form.get("cmd") if request.method == "POST" else None)
    if not cmd:
        return jsonify({"error": "Missing cmd"}), 400

    import re
    match = re.match(r'^(\d+)(!?)([a-zA-Z]+)(?:\s+(.*))?$', cmd.strip())
    if not match:
        return jsonify({"error": "Invalid format"}), 400

    acc_num = int(match.group(1))
    has_bang = match.group(2) == "!"
    cmd_name = match.group(3).lower()
    arg = match.group(4) or ""

    if acc_num < 1 or acc_num > len(TOKENS):
        return jsonify({"error": "Account out of range"}), 400

    token = TOKENS[acc_num - 1]
    acc_name = f"Account_{acc_num}"

    if cmd_name == "d":
        success = execute_daily(token, CHANNEL_ID, acc_name)
        return jsonify({"success": success, "command": "daily"})
    elif cmd_name == "p":
        success = execute_profile(token, CHANNEL_ID, acc_name)
        return jsonify({"success": success, "command": "profile"})
    elif cmd_name == "c":
        success = execute_credits(token, CHANNEL_ID, acc_name)
        return jsonify({"success": success, "command": "credits"})
    elif cmd_name == "say" and has_bang and arg:
        success = execute_say(token, CHANNEL_ID, arg)
        return jsonify({"success": success, "command": "say", "message": arg})
    else:
        return jsonify({"error": "Unknown command"}), 400

def start_flask():
    app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False)

# ========== DISCORD CONTROL BOT (RELAY) ==========
def start_discord_bot():
    if not DISCORD_BOT_TOKEN or not COMMAND_CHANNEL_ID:
        log("Discord bot not configured. Skipping.", "WARNING")
        return

    import discord
    from discord.ext import commands

    intents = discord.Intents.default()
    intents.message_content = True
    bot = commands.Bot(command_prefix="!", intents=intents)

    @bot.event
    async def on_ready():
        log(f"🤖 Control bot online: {bot.user}")

    @bot.event
    async def on_message(message):
        if message.channel.id != int(COMMAND_CHANNEL_ID) or message.author == bot.user:
            return
        if message.content and message.content[0].isdigit() and '!' in message.content:
            api_url = f"http://localhost:{PORT}/control"
            params = {"api_key": CONTROL_API_KEY, "cmd": message.content}
            try:
                resp = requests.get(api_url, params=params, timeout=10)
                if resp.status_code == 200:
                    await message.add_reaction("✅")
                    log(f"Command '{message.content}' executed")
                else:
                    await message.add_reaction("❌")
                    log(f"Command failed: {resp.text}")
            except Exception as e:
                await message.add_reaction("⚠️")
                log(f"Error: {e}")
        await bot.process_commands(message)

    try:
        bot.run(DISCORD_BOT_TOKEN, log_handler=None)
    except Exception as e:
        log(f"Bot error: {e}", "ERROR")

# ========== MAIN ==========
if __name__ == "__main__":
    log("🚀 Mazraat Automator v3.0 starting...")
    log(f"📡 Target channel: {CHANNEL_ID}")
    log(f"👥 Loaded {len(TOKENS)} tokens")

    threading.Thread(target=scheduler_loop, daemon=True).start()

    if DISCORD_BOT_TOKEN and COMMAND_CHANNEL_ID:
        threading.Thread(target=start_discord_bot, daemon=True).start()
    else:
        log("⚠️ Discord bot not configured. Only API control available.", "WARNING")

    log(f"🔌 API listening on port {PORT}")
    start_flask()
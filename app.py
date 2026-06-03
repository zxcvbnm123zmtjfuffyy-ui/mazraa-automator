#!/usr/bin/env python3
"""
Mazraat Credits Automator v4.0 - Stable Edition
Author: Dark & f5r
Fully working with Python 3.12 on Render
"""

import os
import json
import time
import random
import threading
import asyncio
import requests
from datetime import datetime, timedelta
from flask import Flask, request, jsonify

# ========== CONFIGURATION ==========
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

# ========== DISCORD SELF-BOT HELPERS (Credits Collection) ==========
def send_message(token, channel_id, content):
    url = f"https://discord.com/api/v9/channels/{channel_id}/messages"
    headers = {
        "Authorization": token,
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    payload = {"content": content}
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=15)
        if r.status_code == 200:
            return True, r.json().get("id")
        else:
            return False, None
    except Exception as e:
        log(f"Send error: {e}", "ERROR")
        return False, None

def execute_daily(token, channel_id, account_name):
    for cmd in ["d", "D", "/daily", "!daily"]:
        ok, _ = send_message(token, channel_id, cmd)
        if ok:
            log(f"{account_name} -> DAILY: '{cmd}'")
            return True
        time.sleep(1)
    log(f"{account_name} -> DAILY: All shortcuts failed", "WARNING")
    return False

def execute_profile(token, channel_id, account_name):
    for cmd in ["p", "P", "/profile", "!profile"]:
        ok, _ = send_message(token, channel_id, cmd)
        if ok:
            log(f"{account_name} -> PROFILE")
            return True
        time.sleep(0.5)
    return False

def execute_credits(token, channel_id, account_name):
    for cmd in ["c", "C", "/credits", "!credits"]:
        ok, _ = send_message(token, channel_id, cmd)
        if ok:
            log(f"{account_name} -> CREDITS")
            return True
        time.sleep(0.5)
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
            delay_hours = random.uniform(0, 2)  # Spread initial runs
            next_run = now + timedelta(hours=delay_hours)
            schedule[token] = {
                "last_run": None,
                "next_run": next_run.isoformat(),
                "account_name": get_account_name(token, idx)
            }
            changed = True
            log(f"Initialized {schedule[token]['account_name']}: first daily at {next_run}")
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
        try:
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
        except Exception as e:
            log(f"Scheduler error: {e}", "ERROR")
        time.sleep(60)  # Check every minute

# ========== FLASK API ==========
app = Flask(__name__)

def authorize():
    key = request.args.get("api_key") or request.headers.get("X-API-Key")
    return key == CONTROL_API_KEY

@app.route("/")
def index():
    return jsonify({
        "status": "running",
        "accounts": len(TOKENS),
        "version": "4.0",
        "bot_status": "configured" if DISCORD_BOT_TOKEN else "not configured"
    })

@app.route("/control", methods=["GET", "POST"])
def control():
    if not authorize():
        return jsonify({"error": "Unauthorized"}), 401
    
    cmd = request.args.get("cmd") or (request.form.get("cmd") if request.method == "POST" else None)
    if not cmd:
        return jsonify({"error": "Missing cmd parameter"}), 400

    import re
    match = re.match(r'^(\d+)(!?)([a-zA-Z]+)(?:\s+(.*))?$', cmd.strip())
    if not match:
        return jsonify({"error": "Invalid command format. Use: <num>d or <num>!say text"}), 400

    acc_num = int(match.group(1))
    has_bang = match.group(2) == "!"
    cmd_name = match.group(3).lower()
    arg = match.group(4) or ""

    if acc_num < 1 or acc_num > len(TOKENS):
        return jsonify({"error": f"Account index out of range (1-{len(TOKENS)})"}), 400

    token = TOKENS[acc_num - 1]
    acc_name = f"Account_{acc_num}"

    if cmd_name == "d":
        success = execute_daily(token, CHANNEL_ID, acc_name)
        return jsonify({"success": success, "command": "daily", "account": acc_num})
    elif cmd_name == "p":
        success = execute_profile(token, CHANNEL_ID, acc_name)
        return jsonify({"success": success, "command": "profile", "account": acc_num})
    elif cmd_name == "c":
        success = execute_credits(token, CHANNEL_ID, acc_name)
        return jsonify({"success": success, "command": "credits", "account": acc_num})
    elif cmd_name == "say" and has_bang and arg:
        success = execute_say(token, CHANNEL_ID, arg)
        return jsonify({"success": success, "command": "say", "account": acc_num, "message": arg})
    else:
        return jsonify({"error": "Unknown command. Available: d, p, c, !say"}), 400

def start_flask():
    app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False)

# ========== DISCORD CONTROL BOT ==========
def start_discord_bot():
    if not DISCORD_BOT_TOKEN or not COMMAND_CHANNEL_ID:
        log("Discord bot not configured. Only API control available.", "WARNING")
        return

    # Ensure event loop for this thread
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    except Exception as e:
        log(f"Failed to create event loop: {e}", "ERROR")
        return

    try:
        import discord
        from discord.ext import commands
    except ImportError as e:
        log(f"Failed to import discord.py: {e}", "ERROR")
        return

    intents = discord.Intents.default()
    intents.message_content = True
    bot = commands.Bot(command_prefix="!", intents=intents)

    @bot.event
    async def on_ready():
        log(f"🤖 Control bot online: {bot.user} (ID: {bot.user.id})")

    @bot.event
    async def on_message(message):
        # Ignore messages from self or wrong channel
        if message.author == bot.user:
            return
        if str(message.channel.id) != str(COMMAND_CHANNEL_ID):
            return
        
        # Check for command format: number!command or numbercommand
        content = message.content.strip()
        if content and content[0].isdigit() and ('!' in content or content[1:].isalpha()):
            api_url = f"http://localhost:{PORT}/control"
            params = {"api_key": CONTROL_API_KEY, "cmd": content}
            try:
                resp = requests.get(api_url, params=params, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("success"):
                        await message.add_reaction("✅")
                        log(f"Command '{content}' executed successfully")
                    else:
                        await message.add_reaction("❌")
                        log(f"Command '{content}' failed: {data}")
                else:
                    await message.add_reaction("❌")
                    log(f"Command '{content}' HTTP {resp.status_code}")
            except Exception as e:
                await message.add_reaction("⚠️")
                log(f"Command '{content}' error: {e}", "ERROR")
        await bot.process_commands(message)

    try:
        bot.run(DISCORD_BOT_TOKEN, log_handler=None)
    except Exception as e:
        log(f"Bot fatal error: {e}", "ERROR")

# ========== MAIN ENTRY POINT ==========
if __name__ == "__main__":
    log("🚀 Mazraat Automator v4.0 (Stable) starting...")
    log(f"📡 Target channel: {CHANNEL_ID}")
    log(f"👥 Loaded {len(TOKENS)} tokens")
    log(f"🔌 API listening on port {PORT}")

    # Start daily scheduler thread
    scheduler_thread = threading.Thread(target=scheduler_loop, daemon=True)
    scheduler_thread.start()

    # Start Discord control bot thread (if configured)
    if DISCORD_BOT_TOKEN and COMMAND_CHANNEL_ID:
        bot_thread = threading.Thread(target=start_discord_bot, daemon=True)
        bot_thread.start()
        # Give bot time to initialize
        time.sleep(2)
    else:
        log("⚠️ Discord bot not configured. Only API control available.", "WARNING")

    # Start Flask (blocking, runs in main thread)
    start_flask()
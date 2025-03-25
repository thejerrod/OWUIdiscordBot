import discord
from discord.ext import commands
from discord.ext.commands import cooldown, BucketType
import aiohttp
import logging
import time
import json
import os
from dotenv import load_dotenv

# load .env variables
load_dotenv()

OPEN_WEBUI_API_TOKEN = os.getenv("OPEN_WEBUI_API_TOKEN")
OPEN_WEBUI_API_URL = os.getenv("OPEN_WEBUI_API_URL")
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DEBUG_MODE = os.getenv("DEBUG_MODE", "False").lower() == "true"

# ──────────────────────────────────────────────────────────────
# Logging configuration
# ──────────────────────────────────────────────────────────────
if DEBUG_MODE:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler("botlog.log", encoding="utf-8"),
            logging.StreamHandler()
        ]
    )
else:
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler()]
    )

logging.info("🔍 Debug logging is enabled and writing to botlog.log.")

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

user_sessions = {}      # {user_id: [chat history]}
user_personas = {}      # {user_id: system prompt}
stats_data = {
    "total_requests": 0,
    "total_tokens": 0,
    "total_prompt_tokens": 0,
    "total_completion_tokens": 0,
    "total_duration_ns": 0,
    "avg_response_speed": [],
}

# helpers
def split_message(text, max_length=2000):
    lines = text.splitlines(keepends=True)
    chunks = []
    current = ""
    for line in lines:
        if len(current) + len(line) <= max_length:
            current += line
        else:
            chunks.append(current)
            current = line
    if current:
        chunks.append(current)
    return chunks

def log_debug(header, content):
    if DEBUG_MODE:
        logging.info(f"\n--- DEBUG: {header} ---")
        if isinstance(content, (dict, list)):
            logging.info(json.dumps(content, indent=2))
        else:
            logging.info(str(content))

def log_request_summary(user_id, username, model, usage):
    prompt_tokens = usage.get("prompt_tokens", 0)
    completion_tokens = usage.get("completion_tokens", 0)
    total_tokens = usage.get("total_tokens", 0)
    duration_ns = usage.get("total_duration", 0)
    latency = duration_ns / 1e9 if duration_ns else 0

    logging.info(
        f"🧾 Request by {username} (ID: {user_id}) | Model: {model} | "
        f"Tokens — Prompt: {prompt_tokens}, Completion: {completion_tokens}, Total: {total_tokens} | "
        f"Latency: {latency:.2f}s"
    )

def update_stats(usage):
    stats_data["total_requests"] += 1
    stats_data["total_tokens"] += usage.get("total_tokens", 0)
    stats_data["total_prompt_tokens"] += usage.get("prompt_tokens", 0)
    stats_data["total_completion_tokens"] += usage.get("completion_tokens", 0)
    stats_data["total_duration_ns"] += usage.get("total_duration", 0)

    if "response_token/s" in usage:
        stats_data["avg_response_speed"].append(usage["response_token/s"])

async def send_request_to_model(model_name, messages, user_id, username):
    payload = {
        "model": model_name,
        "messages": messages
    }

    headers = {
        "Authorization": f"Bearer {OPEN_WEBUI_API_TOKEN}",
        "Content-Type": "application/json"
    }

    log_debug(f"REQUEST from {username} ({user_id})", {
        "model": model_name,
        "messages": messages
    })

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(OPEN_WEBUI_API_URL, headers=headers, json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    log_debug("RESPONSE", data)

                    usage = data.get("usage", {})
                    log_request_summary(user_id, username, model_name, usage)
                    update_stats(usage)

                    return data.get("choices", [{}])[0].get("message", {}).get("content", "No response received.")
                else:
                    error = await resp.text()
                    logging.warning(f"HTTP {resp.status}: {error}")
                    return f"⚠️ API error: HTTP {resp.status}"
        except Exception as e:
            logging.error(f"Exception during request: {e}", exc_info=True)
            return f"❌ Exception occurred: {str(e)}"

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user.name}")


# bot commands
@bot.command()
@cooldown(rate=1, per=5.0, type=BucketType.user)
async def ask(ctx, *, prompt: str):
    user_id = str(ctx.author.id)
    username = ctx.author.name
    messages = user_sessions.get(user_id)

    if messages is None:
        messages = []
        if user_id in user_personas:
            messages.append({
                "role": "system",
                "content": user_personas[user_id]
            })

    messages.append({"role": "user", "content": prompt})
    user_sessions[user_id] = messages

    async with ctx.typing():
        response = await send_request_to_model("discord", messages, user_id, username)
        messages.append({"role": "assistant", "content": response})
        user_sessions[user_id] = messages

    for chunk in split_message(response):
        await ctx.send(chunk)

@ask.error
async def ask_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"⏳ You're on cooldown. Try again in {error.retry_after:.1f} seconds.")
    else:
        logging.error(f"Unexpected error: {error}", exc_info=True)
        await ctx.send("⚠️ Something went wrong.")

@bot.command()
@cooldown(rate=1, per=5.0, type=BucketType.user)
async def summarize(ctx, *, text: str):
    user_id = str(ctx.author.id)
    username = ctx.author.name
    messages = [{"role": "user", "content": text}]

    async with ctx.typing():
        response = await send_request_to_model("summarizer", messages, user_id, username)

    for chunk in split_message(response):
        await ctx.send(chunk)

@bot.command()
async def setpersona(ctx, *, persona: str):
    user_id = str(ctx.author.id)
    user_personas[user_id] = persona
    await ctx.send(f"✅ Persona set! Future replies will reflect: *{persona}*")

@bot.command()
async def reset(ctx):
    user_id = str(ctx.author.id)
    user_sessions.pop(user_id, None)
    await ctx.send("🗑️ Your conversation history has been reset.")

@bot.command()
async def debug(ctx):
    global DEBUG_MODE
    DEBUG_MODE = not DEBUG_MODE
    await ctx.send(f"🐞 Debug mode is now {'ON' if DEBUG_MODE else 'OFF'}")

@bot.command()
async def stats(ctx):
    num_users = len(user_sessions)
    num_personas = len(user_personas)
    total_messages = sum(len(history) for history in user_sessions.values())
    avg_speed = sum(stats_data["avg_response_speed"]) / len(stats_data["avg_response_speed"]) if stats_data["avg_response_speed"] else 0
    readable_duration = time.strftime('%Hh%Mm%Ss', time.gmtime(stats_data["total_duration_ns"] / 1e9))

    await ctx.send(
        f"📊 **Bot Stats:**\n"
        f"- Active conversations: {num_users}\n"
        f"- Custom personas set: {num_personas}\n"
        f"- Total messages tracked: {total_messages}\n"
        f"\n"
        f"🧠 **Model Usage Stats:**\n"
        f"- Requests made: {stats_data['total_requests']}\n"
        f"- Total tokens used: {stats_data['total_tokens']}\n"
        f"  - Prompt: {stats_data['total_prompt_tokens']}\n"
        f"  - Completion: {stats_data['total_completion_tokens']}\n"
        f"- Total runtime: {readable_duration}\n"
        f"- Avg response speed: {avg_speed:.2f} tokens/sec"
    )

@bot.command(name="commands")
async def custom_help(ctx):
    help_text = (
        "**🤖 Available Commands:**\n"
        "`!ask [message]` — Send a message to the model and get a response.\n"
        "`!summarize [text]` — Summarize input using a dedicated model.\n"
        "`!setpersona [description]` — Define how the assistant should behave for you.\n"
        "`!reset` — Clear your personal conversation history.\n"
        "`!stats` — View overall bot and usage stats.\n"
        "`!debug` — Toggle debug mode (logs full requests/responses).\n"
        "`!commands` — Show this help message."
    )
    await ctx.send(help_text)

# Lets go!!
bot.run(DISCORD_BOT_TOKEN)

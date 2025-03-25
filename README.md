
# Discord Chatbot Powered by Open WebUI

This is a modular and customizable Discord chatbot that connects to your **local LLM** using [Open WebUI](https://github.com/open-webui/open-webui) via REST API.

It supports conversational memory, system personas, summarization, logging, and stat tracking — all configurable through a `.env` file.

---

## Features

- `!ask` — Send a prompt to your local LLM and get a response
- `!summarize` — Send text to a separate summarization model
- `!setpersona` — Define how the assistant should behave for your user session
- `!reset` — Clear your session memory
- `!stats` — View global usage stats (token count, requests, latency)
- `!debug` — Toggle debug mode (enables file logging)
- `!commands` — List all available commands

---

## How It Works

This bot connects to **Open WebUI** using its REST API:
- Each command (`!ask`, `!summarize`, etc.) sends messages to the `/api/chat/completions` endpoint
- You can specify different `model` values in the request payload (e.g. `"discord"`, `"summarizer"`)
- User history and personas are tracked in memory per Discord user

---

## Requirements

- Python 3.8+
- A local or network-accessible instance of [Open WebUI](https://github.com/open-webui/open-webui)
- A Discord bot token

---

## Setup

1. Clone the repo
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Create a `.env` file in the root directory:

```env
DISCORD_BOT_TOKEN=your_discord_bot_token
OPEN_WEBUI_API_TOKEN=your_open_webui_token
OPEN_WEBUI_API_URL=http://localhost:3000/api/chat/completions
DEBUG_MODE=True
```

4. Run the bot:

```bash
python bot.py
```

---

## Notes

- Debug mode logs all requests/responses and usage metrics to `botlog.log`
- User history is stored in-memory (non-persistent)
- You can customize model names, persona behavior, and command cooldowns easily in the code

---

## License

MIT — use freely, but attribution is appreciated.

---

## Contributions Welcome

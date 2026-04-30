# NEAR Bridge Status Bot

A Telegram bot that provides real-time status updates for the NEAR Protocol bridge ecosystem. Monitor bridge health, Aurora compatibility, recent transactions, and wallet balances — all without leaving Telegram.

---

## Prerequisites

- Python 3.9+
- A Telegram bot token from [@BotFather](https://t.me/BotFather)

---

## Installation

Clone the repository and install dependencies:

git clone https://github.com/your-username/near-bridge-bot.git
cd near-bridge-bot
pip install -r requirements.txt

---

## Configuration

1. Open Telegram and start a chat with [@BotFather](https://t.me/BotFather)
2. Send `/newbot` and follow the prompts to create your bot
3. Copy the token BotFather provides
4. Set it as an environment variable:

export BOT_TOKEN=your_token_here

Or create a `.env` file in the project root:

BOT_TOKEN=your_token_here

---

## Running

python bot.py

---

## Available Commands

| Command | Description |
|---------|-------------|
| `/start` | Start the bot and see a welcome message |
| `/help` | Display all available commands and usage |
| `/status` | Check current NEAR network status |
| `/bridge` | View NEAR bridge health and metrics |
| `/aurora` | Get Aurora EVM compatibility status |
| `/recent` | Show recent bridge transactions |
| `/balance` | Look up a NEAR wallet balance |

---

## Deploy

**Railway** (recommended): Push to GitHub, connect your repo at [railway.app](https://railway.app), and add `BOT_TOKEN` as an environment variable. Railway auto-detects the `Procfile`.

**Heroku**: 
heroku create
heroku config:set BOT_TOKEN=your_token_here
git push heroku main

The included `Procfile` contains:
worker: python bot.py

---

## Project Structure

near-bridge-bot/
├── bot.py
├── requirements.txt
├── Procfile
└── .env.example

---

## License

MIT
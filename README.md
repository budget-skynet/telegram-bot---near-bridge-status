# NEAR Bridge Status Bot

A Telegram bot that provides real-time status updates for the NEAR Protocol bridge. Monitor bridge activity, gas prices, and validator information directly from Telegram. Designed to keep users connected to the NEAR ecosystem with instant, well-formatted data.

---

## Prerequisites

- Python 3.9+
- A Telegram bot token from [@BotFather](https://t.me/BotFather)

---

## Installation

git clone https://github.com/your-username/near-bridge-bot.git
cd near-bridge-bot
pip install -r requirements.txt

---

## Configuration

1. Open Telegram and start a chat with [@BotFather](https://t.me/BotFather)
2. Send `/newbot` and follow the prompts to create your bot
3. Copy the token provided by BotFather
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
|---|---|
| `/start` | Start the bot and see a welcome message |
| `/help` | Display all available commands |
| `/status` | Get current NEAR bridge status |
| `/bridge` | View bridge transaction activity |
| `/gas` | Check current gas prices on NEAR |
| `/validators` | List active NEAR validators |

---

## Deployment

Deploy instantly to [Railway](https://railway.app) or [Heroku](https://heroku.com) using the included `Procfile`:

worker: python bot.py

Push to your platform of choice and set the `BOT_TOKEN` environment variable in the dashboard. The bot will start automatically.

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
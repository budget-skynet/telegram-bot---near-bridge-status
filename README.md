# NEAR Bridge Status Bot

A Telegram bot that provides real-time NEAR Protocol network and bridge status information. Users can monitor block height, gas prices, validator activity, and cross-chain bridge health directly from Telegram. Designed to keep the NEAR community informed and engaged with the ecosystem.

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
3. Copy the token BotFather provides
4. Set it as an environment variable:

export BOT_TOKEN=your_telegram_bot_token_here

Or create a `.env` file in the project root:

BOT_TOKEN=your_telegram_bot_token_here

---

## Running

python bot.py

---

## Available Commands

| Command | Description |
|---|---|
| `/start` | Start the bot and see a welcome message |
| `/help` | Show all available commands and usage info |
| `/status` | Get current NEAR network status |
| `/block` | View the latest block height and details |
| `/gas` | Check current gas prices on NEAR |
| `/bridge` | View Rainbow Bridge status and health |
| `/validators` | List active validators and their stats |

---

## Deployment

Deploy instantly to [Railway](https://railway.app) or [Heroku](https://heroku.com) using the included `Procfile`:

worker: python bot.py

Push your code, set the `BOT_TOKEN` environment variable in your platform's dashboard, and your bot will run continuously in the cloud.

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
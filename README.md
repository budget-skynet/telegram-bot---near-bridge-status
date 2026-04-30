# NEAR Bridge Status Bot

A Telegram bot that provides real-time NEAR Protocol network and bridge status updates. Users can monitor block height, gas prices, and bridge activity directly from Telegram. Designed to keep the NEAR ecosystem community informed and engaged.

## Prerequisites

- Python 3.9+
- A Telegram bot token from [@BotFather](https://t.me/BotFather)

## Installation

git clone https://github.com/yourname/near-bridge-bot.git
cd near-bridge-bot
pip install -r requirements.txt

## Configuration

1. Open Telegram and start a chat with [@BotFather](https://t.me/BotFather)
2. Send `/newbot` and follow the prompts to create your bot
3. Copy the token BotFather provides
4. Set it as an environment variable:

export BOT_TOKEN=your_token_here

Or create a `.env` file in the project root:

BOT_TOKEN=your_token_here

## Running

python bot.py

## Available Commands

| Command | Description |
|------------|------------------------------------------|
| `/start` | Start the bot and see a welcome message |
| `/help` | Show all available commands |
| `/status` | Current NEAR network status |
| `/block` | Latest block height and timestamp |
| `/gas` | Current gas price on NEAR |
| `/bridge` | NEAR bridge activity and status |
| `/summary` | Full summary of all network metrics |

## Deploy

Deploy to Railway or Heroku in one step — add a `Procfile` with `worker: python bot.py` and push to your connected repo.

worker: python bot.py

**Railway (recommended):**

railway up

**Heroku:**

heroku create
git push heroku main

## Project Structure

near-bridge-bot/
├── bot.py
├── requirements.txt
├── Procfile
└── .env

## Requirements

python-telegram-bot
requests
python-dotenv

## License

MIT
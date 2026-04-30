# NEAR Bridge Status Bot

A Telegram bot that provides real-time NEAR Protocol bridge and network status updates. Users can monitor block activity, bridge transactions, Aurora EVM stats, and gas prices directly from Telegram. Designed to keep the NEAR ecosystem community informed and engaged.

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

The bot will start polling for updates. You should see a confirmation message in the terminal.

## Available Commands

| Command | Description |
|---------|-------------|
| `/start` | Start the bot and see a welcome message |
| `/help` | List all available commands |
| `/status` | Get current NEAR network status |
| `/block` | Show the latest block height and details |
| `/bridge` | Display Rainbow Bridge transaction activity |
| `/aurora` | Fetch Aurora EVM network stats |
| `/gas` | Check current gas prices on NEAR |

## Deployment

**Railway (recommended):**

Add a `Procfile` to your project root:

worker: python bot.py

Then push to Railway:

railway up

**Heroku:**

heroku create your-app-name
heroku config:set BOT_TOKEN=your_token_here
git push heroku main

Both platforms will keep the bot running continuously without any manual restarts.

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `BOT_TOKEN` | Yes | Telegram bot token from BotFather |

## License

MIT
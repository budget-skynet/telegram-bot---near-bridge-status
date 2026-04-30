# NEAR Bridge Status Bot

A Telegram bot that provides real-time status updates for the NEAR Protocol bridge and ecosystem. Monitor block production, validator activity, wNEAR metrics, and bridge health — all from within Telegram.

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
3. Copy the token provided and set it as an environment variable:

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
| `/start` | Start the bot and see the welcome message |
| `/help` | Display help and usage information |
| `/status` | Show current NEAR network status |
| `/bridge` | Display NEAR bridge health and activity |
| `/wnear` | Show wNEAR token metrics and stats |
| `/blocks` | View latest block production data |
| `/validators` | List active validators and their status |
| `/cmd_status` | Alias for `/status` |
| `/cmd_bridge` | Alias for `/bridge` |
| `/cmd_wnear` | Alias for `/wnear` |
| `/cmd_blocks` | Alias for `/blocks` |
| `/cmd_validators` | Alias for `/validators` |

---

## Deployment

Deploy instantly to [Railway](https://railway.app) or [Heroku](https://heroku.com) using the included `Procfile`:

worker: python bot.py

Push to your platform of choice and set the `BOT_TOKEN` environment variable in the dashboard. The bot will start automatically.

---

## License

MIT
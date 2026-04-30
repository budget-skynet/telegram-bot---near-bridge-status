# NEAR Bridge Status Bot

A Telegram bot that provides real-time NEAR Protocol network and bridge status information. Monitor block height, gas prices, token data, and cross-chain bridge activity directly from Telegram. Designed to keep users connected to the NEAR ecosystem at a glance.

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
|-----------|-------------|
| `/start` | Start the bot and see a welcome message |
| `/help` | Display all available commands |
| `/status` | Get current NEAR network status |
| `/block` | Show the latest block height and details |
| `/gas` | Check current gas prices on NEAR |
| `/bridge` | View cross-chain bridge status and activity |
| `/tokens` | List token prices and bridge balances |

---

## Deployment

Deploy instantly to [Railway](https://railway.app) or [Heroku](https://heroku.com) using the included `Procfile`:

worker: python bot.py

Set your `BOT_TOKEN` environment variable in the platform dashboard and your bot will be live in minutes.

---

## Project Structure

near-bridge-bot/
├── bot.py
├── requirements.txt
├── Procfile
└── .env.example

---

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

---

## License

[MIT](LICENSE)
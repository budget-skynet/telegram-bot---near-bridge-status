import os
import logging
import aiohttp
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ── NEAR RPC endpoint ─────────────────────────────────────────────────────────
NEAR_RPC = "https://rpc.mainnet.near.org"

# ── Rainbow Bridge contract addresses ────────────────────────────────────────
ETH_CUSTODIAN = "factory.bridge.near"
AURORA_ACCOUNT = "aurora"
BRIDGE_TOKEN_FACTORY = "factory.bridge.near"
WORMHOLE_ACCOUNT = "wormhole.near"

# ── Generic RPC helper ────────────────────────────────────────────────────────
async def _rpc(method: str, params: dict) -> dict:
    """Send a JSON-RPC request to the NEAR mainnet endpoint."""
    payload = {
        "jsonrpc": "2.0",
        "id": "bridge-bot",
        "method": method,
        "params": params,
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(NEAR_RPC, json=payload, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            data = await resp.json()
            if "error" in data:
                raise RuntimeError(data["error"].get("message", "RPC error"))
            return data.get("result", {})


# ── NEAR helper functions ─────────────────────────────────────────────────────

async def get_network_status() -> dict:
    """Fetch current NEAR network / node status."""
    return await _rpc("status", [None])


async def get_bridge_account_info(account_id: str) -> dict:
    """Fetch on-chain account info for a bridge-related account."""
    return await _rpc(
        "query",
        {
            "request_type": "view_account",
            "finality": "final",
            "account_id": account_id,
        },
    )


async def get_latest_block() -> dict:
    """Return the most-recent finalized block details."""
    return await _rpc("block", {"finality": "final"})


async def get_bridge_token_balance(account_id: str, token_contract: str) -> str:
    """
    Call ft_balance_of on a bridged-token contract for a given account.
    Returns the raw u128 balance string.
    """
    import json as _json
    args_bytes = _json.dumps({"account_id": account_id}).encode()
    import base64 as _b64
    args_b64 = _b64.b64encode(args_bytes).decode()

    result = await _rpc(
        "query",
        {
            "request_type": "call_function",
            "finality": "final",
            "account_id": token_contract,
            "method_name": "ft_balance_of",
            "args_base64": args_b64,
        },
    )
    raw = bytes(result["result"])
    balance = _json.loads(raw.decode())
    return balance


async def get_recent_bridge_transactions(account_id: str, limit: int = 5) -> list:
    """
    Query the NEAR indexer API for recent transactions involving a bridge account.
    Falls back gracefully if the indexer is unreachable.
    """
    url = f"https://api.nearblocks.io/v1/account/{account_id}/txns?limit={limit}&order=desc"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("txns", [])
    except Exception as exc:
        logger.warning("Indexer fetch failed: %s", exc)
    return []


# ── /start & /help ────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Welcome message."""
    text = (
        "🌉 *NEAR Bridge Status Bot*\n\n"
        "Monitor the Rainbow Bridge and NEAR network in real-time.\n\n"
        "*Available commands:*\n"
        "• /status — NEAR network health & latest block\n"
        "• /bridge — Rainbow Bridge contract overview\n"
        "• /aurora — Aurora EVM account info\n"
        "• /recent — Recent Rainbow Bridge transactions\n"
        "• /balance `<account> <token_contract>` — Bridged token balance\n"
        "• /help — Show this menu\n\n"
        "🔗 Powered by [NEAR Protocol](https://near.org)"
    )
    await update.message.reply_text(text, parse_mode="Markdown", disable_web_page_preview=True)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Mirror of start — always reachable via /help."""
    await start(update, context)


# ── Command handlers ──────────────────────────────────────────────────────────

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/status — NEAR network health and latest finalized block."""
    await update.message.reply_text("⏳ Fetching network status…")
    try:
        net = await get_network_status()
        block = await get_latest_block()

        chain_id = net.get("chain_id", "N/A")
        version = net.get("version", {}).get("version", "N/A")
        protocol = net.get("protocol_version", "N/A")
        node_count = len(net.get("validators", []))
        sync = net.get("sync_info", {})
        latest_height = sync.get("latest_block_height", "N/A")
        syncing = "✅ Synced" if not sync.get("syncing") else "🔄 Syncing"

        b_height = block.get("header", {}).get("height", "N/A")
        b_hash = block.get("header", {}).get("hash", "N/A")[:12] + "…"
        b_time = block.get("header", {}).get("timestamp_nanosec", 0)
        import datetime
        b_dt = datetime.datetime.utcfromtimestamp(int(b_time) / 1e9).strftime("%Y-%m-%d %H:%M:%S UTC") if b_time else "N/A"

        text = (
            "📡 *NEAR Network Status*\n"
            "──────────────────────\n"
            f"🔗 Chain ID:         `{chain_id}`\n"
            f"🛠 Node version:     `{version}`\n"
            f"📜 Protocol ver.:   `{protocol}`\n"
            f"👥 Active validators:`{node_count}`\n"
            f"🔄 Sync state:       {syncing}\n"
            f"📦 Latest height:   `{latest_height}`\n\n"
            "🧱 *Latest Finalized Block*\n"
            "──────────────────────\n"
            f"📏 Height:  `{b_height}`\n"
            f"🔑 Hash:    `{b_hash}`\n"
            f"🕐 Time:    `{b_dt}`\n"
        )
    except Exception as exc:
        logger.exception("status_command failed")
        text = f"❌ Error fetching status:\n`{exc}`"

    await update.message.reply_text(text, parse_mode="Markdown")


async def bridge_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/bridge — Rainbow Bridge token-factory contract overview."""
    await update.message.reply_text("⏳ Fetching Rainbow Bridge info…")
    try:
        info = await get_bridge_account_info(BRIDGE_TOKEN_FACTORY)

        amount_near = int(info.get("amount", 0)) / 1e24
        locked = int(info.get("locked", 0)) / 1e24
        storage = info.get("storage_usage", 0)
        code_hash = info.get("code_hash", "N/A")

        text = (
            "🌉 *Rainbow Bridge — Token Factory*\n"
            "──────────────────────────────────\n"
            f"📋 Account:     `{BRIDGE_TOKEN_FACTORY}`\n"
            f"💰 Balance:     `{amount_near:,.4f} NEAR`\n"
            f"🔒 Locked:      `{locked:,.4f} NEAR`\n"
            f"💾 Storage:     `{storage:,} bytes`\n"
            f"🔑 Code hash:   `{code_hash[:16]}…`\n\n"
            "ℹ️ The token factory deploys bridged ERC-20 contracts on NEAR.\n"
            "🔗 [Explorer](https://nearblocks.io/address/factory.bridge.near)"
        )
    except Exception as exc:
        logger.exception("bridge_command failed")
        text = f"❌ Error fetching bridge info:\n`{exc}`"

    await update.message.reply_text(text, parse_mode="Markdown", disable_web_page_preview=True)


async def aurora_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/aurora — Aurora EVM account info on NEAR."""
    await update.message.reply_text("⏳ Fetching Aurora account info…")
    try:
        info = await get_bridge_account_info(AURORA_ACCOUNT)

        amount_near = int(info.get("amount", 0)) / 1e24
        locked = int(info.get("locked", 0)) / 1e24
        storage = info.get("storage_usage", 0)
        code_hash = info.get("code_hash", "N/A")

        text = (
            "🌅 *Aurora EVM on NEAR*\n"
            "───────────────────────\n"
            f"📋 Account:   `aurora`\n"
            f"💰 Balance:   `{amount_near:,.4f} NEAR`\n"
            f"🔒 Locked:    `{locked:,.4f} NEAR`\n"
            f"💾 Storage:   `{storage:,} bytes`\n"
            f"🔑 Code hash: `{code_hash[:16]}…`\n\n"
            "ℹ️ Aurora is an EVM environment running as a NEAR smart contract, "
            "enabling Ethereum apps to run on NEAR with near-zero gas fees.\n"
            "🔗 [aurora.dev](https://aurora.dev)"
        )
    except Exception as exc:
        logger.exception("aurora_command failed")
        text = f"❌ Error fetching Aurora info:\n`{exc}`"

    await update.message.reply_text(text, parse_mode="Markdown", disable_web_page_preview=True)


async def recent_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/recent — Show recent Rainbow Bridge transactions."""
    await update.message.reply_text("⏳ Fetching recent bridge transactions…")
    try:
        txns = await get_recent_bridge_transactions(BRIDGE_TOKEN_FACTORY, limit=5)

        if not txns:
            await update.message.reply_text(
                "ℹ️ No recent transactions found (indexer may be rate-limited).\n"
                f"Check manually: https://nearblocks.io/address/{BRIDGE_TOKEN_FACTORY}"
            )
            return

        lines = ["🔄 *Recent Rainbow Bridge Txns*\n──────────────────────────────"]
        for i, tx in enumerate(txns[:5], 1):
            tx_hash = tx.get("transaction_hash", "N/A")
            short_hash = tx_hash[:10] + "…" if len(tx_hash) > 10 else tx_hash
            signer = tx.get("signer_account_id", "N/A")
            receiver = tx.get("receiver_account_id", "N/A")
            status = "✅" if tx.get("outcomes", {}).get("status") != "FAILURE" else "❌"
            block_ts = tx.get("block_timestamp", 0)
            import datetime
            ts = datetime.datetime.utcfromtimestamp(int(block_ts) / 1e9).strftime("%m-%d %H:%M") if block_ts else "N/A"

            lines.append(
                f"\n*#{i}* {status} `{short_hash}`\n"
                f"  👤 From:  `{signer}`\n"
                f"  📨 To:    `{receiver}`\n"
                f"  🕐 Time:  `{ts} UTC`"
            )

        lines.append(
            f"\n🔗 [View all on NearBlocks]"
            f"(https://nearblocks.io/address/{BRIDGE_TOKEN_FACTORY})"
        )
        text = "\n".join(lines)

    except Exception as exc:
        logger.exception("recent_command failed")
        text = f"❌ Error fetching transactions:\n`{exc}`"

    await update.message.reply_text(text, parse_mode="Markdown", disable_web_page_preview=True)


async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/balance <account_id> <token_contract> — Bridged token balance."""
    if len(context.args) < 2:
        await update.message.reply_text(
            "⚠️ Usage: `/balance <account_id> <token_contract>`\n\n"
            "Example:\n"
            "`/balance alice.near dac17f958d2ee523a2206206994597c13d831ec7.factory.bridge.near`",
            parse_mode="Markdown",
        )
        return

    account_id = context.args[0]
    token_contract = context.args[1]
    await update.message.reply_text(f"⏳ Fetching balance for `{account_id}`…", parse_mode="Markdown")

    try:
        raw_balance = await get_bridge_token_balance(account_id, token_contract)
        # Most bridged tokens use 18 decimals (ERC-20 standard via Rainbow Bridge)
        decimals = 18
        try:
            human = int(raw_balance) / (10 ** decimals)
            human_str = f"{human:,.6f}"
        except Exception:
            human_str = raw_balance

        text = (
            "💰 *Bridged Token Balance*\n"
            "──────────────────────────\n"
            f"👤 Account:  `{account_id}`\n"
            f"📜 Contract: `{token_contract}`\n"
            f"💵 Balance:  `{human_str}` _(18 dec assumed)_\n"
            f"🔢 Raw:      `{raw_balance}`\n\n"
            f"🔗 [View on NearBlocks](https://nearblocks.io/address/{account_id})"
        )
    except Exception as exc:
        logger.exception("balance_command failed")
        text = (
            f"❌ Could not fetch balance.\n"
            f"Error: `{exc}`\n\n"
            "Make sure the account exists and the token contract is valid."
        )

    await update.message.reply_text(text, parse_mode="Markdown", disable_web_page_preview=True)


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    logging.basicConfig(level=logging.INFO)
    token = os.environ.get("BOT_TOKEN", "")
    application = ApplicationBuilder().token(token).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("bridge", bridge_command))
    application.add_handler(CommandHandler("aurora", aurora_command))
    application.add_handler(CommandHandler("recent", recent_command))
    application.add_handler(CommandHandler("balance", balance_command))
    application.run_polling()

if __name__ == "__main__":
    main()

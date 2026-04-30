import os
import logging
import aiohttp
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

NEAR_RPC = 'https://rpc.mainnet.near.org'

# ─────────────────────────────────────────────
# RPC HELPER
# ─────────────────────────────────────────────

async def _rpc(method: str, params: dict) -> dict:
    """Generic async NEAR RPC helper."""
    payload = {
        "jsonrpc": "2.0",
        "id": "bridge-bot",
        "method": method,
        "params": params,
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                NEAR_RPC,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                data = await resp.json()
                return data.get("result", {})
    except aiohttp.ClientError as e:
        logger.error("RPC request failed: %s", e)
        return {}

# ─────────────────────────────────────────────
# NEAR HELPER FUNCTIONS
# ─────────────────────────────────────────────

async def get_network_status() -> dict:
    """Fetch overall NEAR network / node status."""
    return await _rpc("status", [None])


async def get_latest_block() -> dict:
    """Fetch the most recent finalized block."""
    return await _rpc("block", {"finality": "final"})


async def get_bridge_account_info(account_id: str) -> dict:
    """
    Fetch on-chain account details for a bridge-related contract
    (Rainbow Bridge locker / factory).
    """
    return await _rpc("query", {
        "request_type": "view_account",
        "finality": "final",
        "account_id": account_id,
    })


async def get_gas_price() -> dict:
    """Fetch current gas price on NEAR mainnet."""
    return await _rpc("gas_price", [None])


async def get_recent_transactions(account_id: str) -> dict:
    """
    Query recent changes / access keys for a bridge contract account
    as a lightweight proxy for recent activity.
    """
    return await _rpc("query", {
        "request_type": "view_access_key_list",
        "finality": "final",
        "account_id": account_id,
    })

# ─────────────────────────────────────────────
# KNOWN RAINBOW BRIDGE CONTRACTS
# ─────────────────────────────────────────────
ETH_LOCKER     = "factory.bridge.near"
AURORA_ENGINE  = "aurora"
BRIDGE_TOKEN   = "token.bridge.near"

# ─────────────────────────────────────────────
# /start  &  /help
# ─────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Welcome message."""
    text = (
        "🌉 *NEAR Rainbow Bridge Status Bot*\n\n"
        "Stay up-to-date with the NEAR ↔ Ethereum bridge in real time.\n\n"
        "📋 *Available Commands*\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🔵 /status   — NEAR network health\n"
        "🧱 /block    — Latest finalized block\n"
        "⛽ /gas      — Current gas price\n"
        "🔗 /bridge   — Bridge contract info\n"
        "📊 /summary  — Full bridge dashboard\n\n"
        "Type /help for more details.\n\n"
        "🚀 _Powered by NEAR Protocol_"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Detailed help text."""
    text = (
        "🆘 *Help — NEAR Bridge Status Bot*\n\n"
        "This bot queries the NEAR mainnet RPC directly — "
        "no third-party APIs, always fresh data.\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "*/status*\n"
        "  Shows node version, chain-id, syncing state & peer count.\n\n"
        "*/block*\n"
        "  Latest finalized block height, timestamp & hash.\n\n"
        "*/gas*\n"
        "  Current gas price in yoctoNEAR.\n\n"
        "*/bridge*\n"
        "  On-chain info for the Rainbow Bridge locker contract "
        f"(`{ETH_LOCKER}`): balance, storage usage.\n\n"
        "*/summary*\n"
        "  All of the above in one handy dashboard.\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "📡 Data source: `https://rpc.mainnet.near.org`\n"
        "🔄 Every command fetches live data on demand."
    )
    await update.message.reply_text(text, parse_mode="Markdown")

# ─────────────────────────────────────────────
# COMMAND HANDLERS
# ─────────────────────────────────────────────

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/status — NEAR network health."""
    await update.message.reply_text("⏳ Fetching network status…")
    data = await get_network_status()

    if not data:
        await update.message.reply_text("❌ Could not reach NEAR RPC. Try again shortly.")
        return

    chain_id   = data.get("chain_id", "N/A")
    version    = data.get("version", {}).get("version", "N/A")
    build      = data.get("version", {}).get("build", "N/A")
    sync_info  = data.get("sync_info", {})
    syncing    = "🔄 Syncing" if data.get("sync_info", {}).get("syncing") else "✅ Synced"
    latest_h   = sync_info.get("latest_block_height", "N/A")
    latest_t   = sync_info.get("latest_block_time", "N/A")[:19].replace("T", " ") if sync_info.get("latest_block_time") else "N/A"
    peers      = len(data.get("active_connections", []))  # may be 0 on public RPC

    text = (
        "🌐 *NEAR Network Status*\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🔗 Chain ID:      `{chain_id}`\n"
        f"🏷  Version:       `{version}` (`{build}`)\n"
        f"🔄 Sync State:    {syncing}\n"
        f"🧱 Block Height:  `{latest_h:,}` \n"
        f"🕐 Block Time:    `{latest_t} UTC`\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🟢 *NEAR Mainnet is operational*"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def block_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/block — Latest finalized block."""
    await update.message.reply_text("⏳ Fetching latest block…")
    data = await get_latest_block()

    if not data:
        await update.message.reply_text("❌ Could not fetch block data. Try again shortly.")
        return

    header        = data.get("header", {})
    height        = header.get("height", "N/A")
    block_hash    = header.get("hash", "N/A")
    timestamp_ns  = header.get("timestamp", 0)
    timestamp_s   = timestamp_ns // 1_000_000_000 if timestamp_ns else 0
    from datetime import datetime, timezone
    dt = datetime.fromtimestamp(timestamp_s, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S") if timestamp_s else "N/A"
    prev_hash     = header.get("prev_hash", "N/A")
    chunks        = len(data.get("chunks", []))
    gas_used      = sum(c.get("gas_used", 0) for c in data.get("chunks", []))
    gas_limit     = sum(c.get("gas_limit", 0) for c in data.get("chunks", []))
    gas_pct       = f"{gas_used / gas_limit * 100:.1f}%" if gas_limit else "N/A"

    text = (
        "🧱 *Latest Finalized Block*\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"📏 Height:     `{height:,}`\n"
        f"🕐 Timestamp:  `{dt} UTC`\n"
        f"#️⃣  Hash:       `{block_hash[:20]}…`\n"
        f"⬅️  Prev Hash:  `{prev_hash[:20]}…`\n"
        f"📦 Shards:     `{chunks}`\n"
        f"⛽ Gas Used:   `{gas_pct}`\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🔍 [View on Explorer](https://explorer.near.org/blocks/{block_hash})"
    )
    await update.message.reply_text(text, parse_mode="Markdown", disable_web_page_preview=True)


async def gas_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/gas — Current NEAR gas price."""
    await update.message.reply_text("⏳ Fetching gas price…")
    data = await get_gas_price()

    if not data:
        await update.message.reply_text("❌ Could not fetch gas price. Try again shortly.")
        return

    gas_price_yocto = int(data.get("gas_price", 0))
    gas_price_tera  = gas_price_yocto / 1e12          # TGas price
    near_per_tgas   = gas_price_tera  / 1e12           # NEAR per TGas (yocto → NEAR)

    # Estimate simple transfer cost (~2.4 TGas)
    transfer_cost_near = near_per_tgas * 2.4

    text = (
        "⛽ *NEAR Gas Price*\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 Price (yocto):  `{gas_price_yocto:,}` yN\n"
        f"📐 Price (Tgas):   `{gas_price_tera:.4f}` yN/gas\n"
        f"🔁 Transfer ~cost: `{transfer_cost_near:.8f}` NEAR\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "💡 _Bridge txns typically use 10–300 TGas_"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def bridge_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/bridge — Rainbow Bridge contract on-chain info."""
    await update.message.reply_text("⏳ Querying bridge contracts…")

    locker = await get_bridge_account_info(ETH_LOCKER)
    aurora = await get_bridge_account_info(AURORA_ENGINE)

    def fmt_near(yocto_str) -> str:
        try:
            return f"{int(yocto_str) / 1e24:.4f} NEAR"
        except Exception:
            return "N/A"

    def fmt_storage(bytes_val) -> str:
        try:
            kb = int(bytes_val) / 1024
            return f"{kb:,.1f} KB"
        except Exception:
            return "N/A"

    locker_bal  = fmt_near(locker.get("amount", "0"))
    locker_stor = fmt_storage(locker.get("storage_usage", "0"))
    locker_ok   = "✅" if locker else "❌"

    aurora_bal  = fmt_near(aurora.get("amount", "0"))
    aurora_stor = fmt_storage(aurora.get("storage_usage", "0"))
    aurora_ok   = "✅" if aurora else "❌"

    text = (
        "🌉 *Rainbow Bridge Contracts*\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"{locker_ok} *ETH Locker* (`{ETH_LOCKER}`)\n"
        f"   💵 Balance:  `{locker_bal}`\n"
        f"   🗄  Storage:  `{locker_stor}`\n\n"
        f"{aurora_ok} *Aurora Engine* (`{AURORA_ENGINE}`)\n"
        f"   💵 Balance:  `{aurora_bal}`\n"
        f"   🗄  Storage:  `{aurora_stor}`\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🔍 [Rainbow Bridge Docs](https://rainbowbridge.app)\n"
        "🔍 [Aurora Explorer](https://explorer.aurora.dev)"
    )
    await update.message.reply_text(text, parse_mode="Markdown", disable_web_page_preview=True)


async def summary_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/summary — Full bridge dashboard combining all data."""
    await update.message.reply_text("⏳ Building bridge dashboard… (fetching all data)")

    # Fetch all concurrently
    import asyncio
    network, block, gas_data, locker = await asyncio.gather(
        get_network_status(),
        get_latest_block(),
        get_gas_price(),
        get_bridge_account_info(ETH_LOCKER),
    )

    # Network
    sync_info   = network.get("sync_info", {})
    syncing     = "🔄 Syncing" if network.get("sync_info", {}).get("syncing") else "✅ Synced"
    net_height  = sync_info.get("latest_block_height", "N/A")

    # Block
    header      = block.get("header", {})
    blk_height  = header.get("height", "N/A")
    ts_ns       = header.get("timestamp", 0)
    ts_s        = ts_ns // 1_000_000_000 if ts_ns else 0
    from datetime import datetime, timezone
    blk_time    = datetime.fromtimestamp(ts_s, tz=timezone.utc).strftime("%H:%M:%S UTC") if ts_s else "N/A"

    # Gas
    gp_yocto    = int(gas_data.get("gas_price", 0))
    gp_near     = gp_yocto / 1e12 / 1e12

    # Locker
    locker_ok   = "✅ Active" if locker else "❌ Unreachable"
    locker_bal  = f"{int(locker.get('amount', 0)) / 1e24:.2f} NEAR" if locker else "N/A"

    text = (
        "📊 *NEAR Bridge Dashboard*\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🌐 *Network*\n"
        f"   Status:   {syncing}\n"
        f"   Height:   `{net_height:,}`\n\n"
        "🧱 *Latest Block*\n"
        f"   Height:   `{blk_height:,}`\n"
        f"   Time:     `{blk_time}`\n\n"
        "⛽ *Gas*\n"
        f"   Price:    `{gp_near:.8f}` NEAR/TGas\n\n"
        "🌉 *Bridge Locker* (`factory.bridge.near`)\n"
        f"   State:    {locker_ok}\n"
        f"   Balance:  `{locker_bal}`\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🔗 [NEAR Explorer](https://explorer.near.org) | "
        "[Rainbow Bridge](https://rainbowbridge.app) | "
        "[Aurora](https://aurora.dev)\n\n"
        "🔄 _Data is live from NEAR mainnet RPC_"
    )
    await update.message.reply_text(text, parse_mode="Markdown", disable_web_page_preview=True)

def main() -> None:
    logging.basicConfig(level=logging.INFO)
    token = os.environ.get("BOT_TOKEN", "")
    application = ApplicationBuilder().token(token).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("block", block_command))
    application.add_handler(CommandHandler("gas", gas_command))
    application.add_handler(CommandHandler("bridge", bridge_command))
    application.add_handler(CommandHandler("summary", summary_command))
    application.run_polling()

if __name__ == "__main__":
    main()

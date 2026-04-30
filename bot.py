import os
import logging
import aiohttp
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ── NEAR RPC endpoint ─────────────────────────────────────────────────────────
NEAR_RPC = "https://rpc.mainnet.near.org"

# Known Rainbow Bridge contract addresses on NEAR mainnet
BRIDGE_CONTRACT = "factory.bridge.near"
ETH_CONNECTOR   = "aurora"          # ETH↔NEAR connector lives inside Aurora
BRIDGE_TOKEN_FACTORY = "factory.bridge.near"

# ── Low-level RPC helper ──────────────────────────────────────────────────────
async def _rpc(method: str, params: dict) -> dict:
    """
    Fire a JSON-RPC request at the NEAR mainnet RPC and return the result dict.
    Raises RuntimeError when the response contains an error key.
    """
    payload = {
        "jsonrpc": "2.0",
        "id":      "bridge-bot",
        "method":  method,
        "params":  params,
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(
            NEAR_RPC,
            json=payload,
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            resp.raise_for_status()
            data = await resp.json(content_type=None)
    if "error" in data:
        raise RuntimeError(data["error"].get("message", str(data["error"])))
    return data.get("result", {})


# ── NEAR helper functions ─────────────────────────────────────────────────────

async def get_network_status() -> dict:
    """
    Return high-level network / node status from the RPC.
    Uses the `status` method (no params needed).
    """
    return await _rpc("status", [])


async def get_latest_block() -> dict:
    """Fetch the latest finalised block header."""
    return await _rpc("block", {"finality": "final"})


async def get_bridge_account_info() -> dict:
    """
    Query the on-chain state of the Rainbow Bridge token-factory account.
    Returns account details such as balance and storage usage.
    """
    return await _rpc(
        "query",
        {
            "request_type": "view_account",
            "finality":     "final",
            "account_id":   BRIDGE_CONTRACT,
        },
    )


async def get_aurora_account_info() -> dict:
    """
    Query Aurora's account — the EVM layer that hosts the ETH connector,
    giving an indirect health signal for the ETH↔NEAR bridge leg.
    """
    return await _rpc(
        "query",
        {
            "request_type": "view_account",
            "finality":     "final",
            "account_id":   ETH_CONNECTOR,
        },
    )


async def get_gas_price() -> dict:
    """Return the current network gas price (yoctoNEAR per gas unit)."""
    return await _rpc("gas_price", [None])


# ── /start ────────────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    text = (
        f"👋 *Welcome, {user.first_name}!*\n\n"
        "🌉 I'm the *NEAR Bridge Status Bot* — your real-time window into\n"
        "the [Rainbow Bridge](https://rainbowbridge.app) that connects\n"
        "*NEAR Protocol ↔ Ethereum ↔ Aurora*.\n\n"
        "📡 *Available commands:*\n"
        "  /status   — Network & RPC health\n"
        "  /block    — Latest finalised block\n"
        "  /bridge   — Bridge contract state\n"
        "  /aurora   — Aurora (ETH connector) state\n"
        "  /gas      — Current gas price\n"
        "  /help     — Show this menu again\n\n"
        "🚀 Built to keep the NEAR ecosystem connected — enjoy!"
    )
    await update.message.reply_text(text, parse_mode="Markdown", disable_web_page_preview=True)


# ── /help ─────────────────────────────────────────────────────────────────────
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "🗺️ *NEAR Bridge Status Bot — Command Reference*\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "*/status*  — RPC node info, chain ID, protocol version\n"
        "*/block*   — Latest finalised block height, hash & timestamp\n"
        "*/bridge*  — Rainbow Bridge token-factory account balance & storage\n"
        "*/aurora*  — Aurora EVM account balance & code hash\n"
        "*/gas*     — Real-time gas price in yoctoNEAR & Tgas cost estimate\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        "All data is fetched *live* from `rpc.mainnet.near.org`.\n"
        "Tip: the Rainbow Bridge UI lives at https://rainbowbridge.app 🌈"
    )
    await update.message.reply_text(text, parse_mode="Markdown", disable_web_page_preview=True)


# ── /status ───────────────────────────────────────────────────────────────────
async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show live NEAR network / RPC-node status."""
    await update.message.reply_text("⏳ Fetching network status…")
    try:
        result = await get_network_status()

        chain_id   = result.get("chain_id", "—")
        version    = result.get("version", {})
        rpc_ver    = version.get("version", "—")
        build      = version.get("build",   "—")
        protocol   = result.get("protocol_version", "—")
        node_key   = result.get("node_key", "—")[:20] + "…"
        validators = result.get("num_active_validators",
                     result.get("validator_account_id", "—"))

        sync = result.get("sync_info", {})
        syncing      = sync.get("syncing", False)
        latest_hash  = sync.get("latest_block_hash",   "—")
        latest_height= sync.get("latest_block_height", "—")

        sync_icon = "✅ Synced" if not syncing else "🔄 Syncing…"

        text = (
            "📡 *NEAR Network Status*\n\n"
            f"🔗 Chain ID        : `{chain_id}`\n"
            f"📦 Protocol ver.   : `{protocol}`\n"
            f"🛠️ Node version     : `{rpc_ver}` (build `{build}`)\n"
            f"🔑 Node key prefix  : `{node_key}`\n"
            f"👥 Active validators: `{validators}`\n\n"
            f"📏 Latest block     : `{latest_height}`\n"
            f"🔐 Latest hash      : `{latest_hash[:20]}…`\n"
            f"🌐 Sync state       : {sync_icon}\n\n"
            "_Data: rpc.mainnet.near.org_"
        )
        await update.message.reply_text(text, parse_mode="Markdown")

    except Exception as exc:
        logger.exception("status_command failed")
        await update.message.reply_text(f"❌ Error fetching status:\n`{exc}`", parse_mode="Markdown")


# ── /block ────────────────────────────────────────────────────────────────────
async def block_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the latest finalised NEAR block."""
    await update.message.reply_text("⏳ Fetching latest block…")
    try:
        result = await get_latest_block()
        header = result.get("header", {})

        height        = header.get("height",           "—")
        block_hash    = header.get("hash",             "—")
        prev_hash     = header.get("prev_hash",        "—")
        timestamp_ns  = header.get("timestamp",        0)
        gas_limit     = header.get("gas_limit",        "—")
        gas_used      = header.get("gas_burnt",        "—")
        num_chunks    = len(result.get("chunks", []))
        validator     = header.get("validator_proposals", [])

        # Convert nanosecond timestamp → human readable
        import datetime
        ts_sec = int(timestamp_ns) / 1_000_000_000
        dt     = datetime.datetime.utcfromtimestamp(ts_sec).strftime("%Y-%m-%d %H:%M:%S UTC")

        # Format gas numbers
        def fmt_gas(g):
            try:
                return f"{int(g)/1e12:.2f} Tgas"
            except Exception:
                return str(g)

        text = (
            "📦 *Latest Finalised Block*\n\n"
            f"🔢 Height     : `{height}`\n"
            f"🕐 Timestamp  : `{dt}`\n"
            f"🔐 Hash       : `{block_hash[:24]}…`\n"
            f"⬅️  Prev hash  : `{prev_hash[:24]}…`\n"
            f"🧩 Chunks     : `{num_chunks}`\n"
            f"⛽ Gas limit  : `{fmt_gas(gas_limit)}`\n"
            f"🔥 Gas burnt  : `{fmt_gas(gas_used)}`\n\n"
            f"🔍 [View on Explorer](https://nearblocks.io/blocks/{block_hash})"
        )
        await update.message.reply_text(text, parse_mode="Markdown", disable_web_page_preview=True)

    except Exception as exc:
        logger.exception("block_command failed")
        await update.message.reply_text(f"❌ Error fetching block:\n`{exc}`", parse_mode="Markdown")


# ── /bridge ───────────────────────────────────────────────────────────────────
async def bridge_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show Rainbow Bridge token-factory contract health."""
    await update.message.reply_text("⏳ Querying bridge contract…")
    try:
        result = await get_bridge_account_info()

        amount_yocto = int(result.get("amount", 0))
        amount_near  = amount_yocto / 1e24
        locked       = int(result.get("locked",         0)) / 1e24
        storage_used = result.get("storage_usage",      "—")
        code_hash    = result.get("code_hash",          "—")
        storage_paid = int(result.get("storage_paid_at", 0))

        # Rough health assessment
        health = "🟢 Healthy" if amount_near > 0 else "🔴 Low balance — investigate!"

        text = (
            "🌉 *Rainbow Bridge — Token Factory*\n"
            f"`{BRIDGE_CONTRACT}`\n\n"
            f"💰 Balance     : `{amount_near:,.4f} NEAR`\n"
            f"🔒 Locked      : `{locked:,.4f} NEAR`\n"
            f"💾 Storage used: `{storage_used:,} bytes`\n"
            f"🔐 Code hash   : `{code_hash[:20]}…`\n\n"
            f"🩺 Status: {health}\n\n"
            f"🔍 [Explorer](https://nearblocks.io/address/{BRIDGE_CONTRACT}) | "
            f"[Rainbow Bridge](https://rainbowbridge.app)"
        )
        await update.message.reply_text(text, parse_mode="Markdown", disable_web_page_preview=True)

    except Exception as exc:
        logger.exception("bridge_command failed")
        await update.message.reply_text(f"❌ Error querying bridge:\n`{exc}`", parse_mode="Markdown")


# ── /aurora ───────────────────────────────────────────────────────────────────
async def aurora_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show Aurora EVM account state (ETH↔NEAR connector)."""
    await update.message.reply_text("⏳ Querying Aurora account…")
    try:
        result = await get_aurora_account_info()

        amount_yocto = int(result.get("amount", 0))
        amount_near  = amount_yocto / 1e24
        storage_used = result.get("storage_usage", "—")
        code_hash    = result.get("code_hash",     "—")

        # Aurora holds enormous balances; flag if suspiciously low
        health = "🟢 Operational" if amount_near > 1 else "🟡 Low balance — monitor"

        text = (
            "🔷 *Aurora EVM — ETH ↔ NEAR Connector*\n"
            f"`{ETH_CONNECTOR}`\n\n"
            f"💰 Balance     : `{amount_near:,.2f} NEAR`\n"
            f"💾 Storage used: `{storage_used:,} bytes`\n"
            f"🔐 Code hash   : `{code_hash[:20]}…`\n\n"
            f"🩺 Status : {health}\n\n"
            "📖 Aurora is the EVM-compatible layer on NEAR that powers\n"
            "the ETH side of the Rainbow Bridge.\n\n"
            f"🔍 [Explorer](https://nearblocks.io/address/{ETH_CONNECTOR}) | "
            "[Aurora.dev](https://aurora.dev)"
        )
        await update.message.reply_text(text, parse_mode="Markdown", disable_web_page_preview=True)

    except Exception as exc:
        logger.exception("aurora_command failed")
        await update.message.reply_text(f"❌ Error querying Aurora:\n`{exc}`", parse_mode="Markdown")


# ── /gas ──────────────────────────────────────────────────────────────────────
async def gas_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the current NEAR network gas price."""
    await update.message.reply_text("⏳ Fetching gas price…")
    try:
        result     = await get_gas_price()
        price_yocto = int(result.get("gas_price", 0))

        # Common conversions
        price_tera = price_yocto / 1e12          # yoctoNEAR per gas → cost per Tgas
        tgas_near  = price_tera / 1e12           # cost of 1 Tgas in NEAR
        tgas_near_milli = tgas_near * 1000        # milliNEAR

        # Typical bridge tx uses ~200 Tgas
        bridge_cost = 200 * tgas_near

        text = (
            "⛽ *NEAR Gas Price (Live)*\n\n"
            f"💲 Price/gas unit : `{price_yocto:,} yoctoNEAR`\n"
            f"📐 Price/Tgas     : `{price_tera:,.0f} yoctoNEAR`\n"
            f"💎 1 Tgas cost    : `{tgas_near_milli:.4f} mNEAR`\n\n"
            "🌉 *Bridge cost estimate (≈200 Tgas):*\n"
            f"   `{bridge_cost:.6f} NEAR`\n\n"
            "ℹ️  Gas on NEAR is extremely cheap by design.\n"
            "Unused gas is automatically refunded to the caller."
        )
        await update.message.reply_text(text, parse_mode="Markdown")

    except Exception as exc:
        logger.exception("gas_command failed")
        await update.message.reply_text(f"❌ Error fetching gas price:\n`{exc}`", parse_mode="Markdown")

def main() -> None:
    logging.basicConfig(level=logging.INFO)
    token = os.environ.get("BOT_TOKEN", "")
    application = ApplicationBuilder().token(token).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("block", block_command))
    application.add_handler(CommandHandler("bridge", bridge_command))
    application.add_handler(CommandHandler("aurora", aurora_command))
    application.add_handler(CommandHandler("gas", gas_command))
    application.run_polling()

if __name__ == "__main__":
    main()

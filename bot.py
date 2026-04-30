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

# ── Constants ─────────────────────────────────────────────────────────────────
NEAR_RPC = "https://rpc.mainnet.near.org"
RAINBOW_BRIDGE_ETH_CONNECTOR = "aurora"          # aurora == ETH↔NEAR bridge engine
BRIDGE_ACCOUNT = "bridge.near"
AURORA_ACCOUNT = "aurora"
WRAP_NEAR_ACCOUNT = "wrap.near"
TOKEN_FACTORY = "factory.bridge.near"

# ── Low-level RPC helper ──────────────────────────────────────────────────────
async def _rpc(method: str, params: dict) -> dict:
    """
    Send a JSON-RPC request to the NEAR mainnet RPC endpoint.
    Returns the 'result' field on success, raises RuntimeError on failure.
    """
    payload = {
        "jsonrpc": "2.0",
        "id": "nearbridge-bot",
        "method": method,
        "params": params,
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(
            NEAR_RPC,
            json=payload,
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            resp.raise_for_status()
            data = await resp.json()
    if "error" in data:
        raise RuntimeError(data["error"].get("message", "Unknown RPC error"))
    return data.get("result", {})


# ── NEAR helper functions ─────────────────────────────────────────────────────

async def get_network_status() -> dict:
    """
    Fetch high-level network info: latest block height, chain-id, node version,
    validator count, and epoch info — all from a single status call.
    """
    result = await _rpc("status", {})
    sync = result.get("sync_info", {})
    validators = result.get("validators", [])
    return {
        "chain_id": result.get("chain_id", "N/A"),
        "latest_block_height": sync.get("latest_block_height", "N/A"),
        "latest_block_hash": sync.get("latest_block_hash", "N/A"),
        "syncing": sync.get("syncing", False),
        "validator_count": len(validators),
        "node_version": result.get("version", {}).get("version", "N/A"),
        "rpc_addr": result.get("rpc_addr", "N/A"),
    }


async def get_aurora_bridge_account_info() -> dict:
    """
    Fetch the Aurora (ETH↔NEAR) engine account state, which represents
    the primary Rainbow Bridge entry-point on NEAR.
    """
    result = await _rpc(
        "query",
        {
            "request_type": "view_account",
            "finality": "final",
            "account_id": AURORA_ACCOUNT,
        },
    )
    return {
        "account_id": AURORA_ACCOUNT,
        "amount_near": int(result.get("amount", 0)) / 1e24,
        "storage_usage_kb": result.get("storage_usage", 0) / 1024,
        "code_hash": result.get("code_hash", "N/A"),
        "block_height": result.get("block_height", "N/A"),
    }


async def get_wrap_near_supply() -> dict:
    """
    Call the wNEAR (wrap.near) contract to get the total circulating supply.
    wNEAR is the wrapped NEAR token used heavily in bridge flows.
    """
    result = await _rpc(
        "query",
        {
            "request_type": "call_function",
            "finality": "final",
            "account_id": WRAP_NEAR_ACCOUNT,
            "method_name": "ft_total_supply",
            "args_base64": "e30=",   # base64("{}")
        },
    )
    raw_bytes = result.get("result", [])
    raw_str = "".join(chr(b) for b in raw_bytes).strip('"')
    try:
        supply_near = int(raw_str) / 1e24
    except (ValueError, TypeError):
        supply_near = None
    return {
        "account_id": WRAP_NEAR_ACCOUNT,
        "total_supply_near": supply_near,
        "block_height": result.get("block_height", "N/A"),
    }


async def get_recent_bridge_blocks(num_blocks: int = 5) -> list[dict]:
    """
    Retrieve the last `num_blocks` final block headers, which can be inspected
    to see bridge-related transaction counts per block.
    """
    # Get latest block
    status = await _rpc("status", {})
    latest_height = status["sync_info"]["latest_block_height"]

    blocks = []
    for height in range(latest_height, latest_height - num_blocks, -1):
        try:
            block = await _rpc(
                "block",
                {"block_id": height},
            )
            header = block.get("header", {})
            chunks = block.get("chunks", [])
            tx_count = sum(c.get("tx_root", "") != "11111111111111111111111111111111" for c in chunks)
            blocks.append(
                {
                    "height": header.get("height", height),
                    "timestamp_ms": header.get("timestamp", 0) // 1_000_000,
                    "chunk_count": len(chunks),
                    "active_chunks": tx_count,
                    "gas_price": int(header.get("gas_price", 0)) / 1e12,  # TGas
                }
            )
        except Exception as exc:
            logger.warning("Could not fetch block %s: %s", height, exc)
    return blocks


async def get_validators_brief() -> dict:
    """
    Fetch the current epoch validators to show overall network health,
    which directly affects bridge security and finality.
    """
    result = await _rpc("validators", {"latest_block": None})
    current = result.get("current_validators", [])
    next_v = result.get("next_validators", [])
    epoch_start = result.get("epoch_start_height", "N/A")
    total_stake = sum(int(v.get("stake", 0)) for v in current) / 1e24

    # Top 5 by stake
    top5 = sorted(current, key=lambda v: int(v.get("stake", 0)), reverse=True)[:5]
    top5_info = [
        {
            "account_id": v["account_id"],
            "stake_near": int(v["stake"]) / 1e24,
            "slashed": v.get("is_slashed", False),
        }
        for v in top5
    ]
    return {
        "epoch_start_height": epoch_start,
        "current_validator_count": len(current),
        "next_validator_count": len(next_v),
        "total_stake_near": total_stake,
        "top5": top5_info,
    }


# ── /start and /help ──────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Welcome message with a quick overview of the bot."""
    text = (
        "🌉 *NEAR Bridge Status Bot*\n\n"
        "Stay up-to-date with the *Rainbow Bridge* (ETH↔NEAR) and the broader "
        "NEAR ecosystem in real time.\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "📡 *Available Commands*\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "/status   — Network & sync status\n"
        "/bridge   — Aurora bridge engine info\n"
        "/wnear    — Wrapped NEAR total supply\n"
        "/blocks   — Latest 5 block summaries\n"
        "/validators — Validator set overview\n"
        "/help     — Show this help message\n\n"
        "💡 _Powered by NEAR Protocol RPC_"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Detailed help message."""
    text = (
        "🆘 *NEAR Bridge Status Bot — Help*\n\n"
        "This bot fetches live data directly from the *NEAR mainnet RPC*.\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🔹 `/status`\n"
        "   Chain ID, block height, sync state, and validator count.\n\n"
        "🔹 `/bridge`\n"
        "   Aurora engine account state — the heart of the Rainbow Bridge.\n\n"
        "🔹 `/wnear`\n"
        "   Total circulating wNEAR supply (wrap.near contract).\n\n"
        "🔹 `/blocks`\n"
        "   Last 5 finalized blocks: height, gas price, chunk activity.\n\n"
        "🔹 `/validators`\n"
        "   Current epoch validators, total stake, and top-5 by stake.\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "📣 *About Rainbow Bridge*\n"
        "The Rainbow Bridge lets you move assets between Ethereum and NEAR "
        "trustlessly. Aurora (EVM on NEAR) provides the on-chain engine.\n\n"
        "🌐 https://rainbowbridge.app"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


# ── Command handlers ──────────────────────────────────────────────────────────

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show NEAR network status."""
    await update.message.reply_text("⏳ Fetching network status…")
    try:
        s = await get_network_status()
        sync_icon = "🔄 Syncing…" if s["syncing"] else "✅ Fully synced"
        text = (
            "📡 *NEAR Network Status*\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"🔗 Chain ID:          `{s['chain_id']}`\n"
            f"📦 Latest Block:      `{s['latest_block_height']:,}`\n"
            f"#️⃣  Block Hash:        `{s['latest_block_hash'][:16]}…`\n"
            f"🔄 Sync Status:      {sync_icon}\n"
            f"🏛️  Validators:        `{s['validator_count']}`\n"
            f"🖥️  Node Version:      `{s['node_version']}`\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "_Data: NEAR Mainnet RPC_"
        )
    except Exception as exc:
        logger.exception("cmd_status failed")
        text = f"❌ Error fetching status:\n`{exc}`"
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_bridge(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show Aurora (Rainbow Bridge engine) account info."""
    await update.message.reply_text("⏳ Querying Aurora bridge engine…")
    try:
        info = await get_aurora_bridge_account_info()
        text = (
            "🌉 *Rainbow Bridge — Aurora Engine*\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"📋 Account:           `{info['account_id']}`\n"
            f"💰 Balance:           `{info['amount_near']:,.4f} NEAR`\n"
            f"🗄️  Storage Used:      `{info['storage_usage_kb']:,.2f} KB`\n"
            f"🔑 Code Hash:         `{info['code_hash'][:16]}…`\n"
            f"📦 At Block:          `{info['block_height']:,}`\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "ℹ️  Aurora is the EVM engine powering ETH↔NEAR transfers.\n"
            "🌐 https://aurora.dev"
        )
    except Exception as exc:
        logger.exception("cmd_bridge failed")
        text = f"❌ Error fetching bridge info:\n`{exc}`"
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_wnear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show wNEAR (wrap.near) total supply."""
    await update.message.reply_text("⏳ Querying wNEAR contract…")
    try:
        info = await get_wrap_near_supply()
        supply_str = (
            f"`{info['total_supply_near']:,.2f} wNEAR`"
            if info["total_supply_near"] is not None
            else "_unavailable_"
        )
        text = (
            "🔄 *Wrapped NEAR (wNEAR) Supply*\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"📋 Contract:          `{info['account_id']}`\n"
            f"💎 Total Supply:      {supply_str}\n"
            f"📦 At Block:          `{info['block_height']:,}`\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "ℹ️  wNEAR is used in DeFi and cross-chain bridge flows.\n"
            "_1 wNEAR = 1 NEAR, always redeemable_"
        )
    except Exception as exc:
        logger.exception("cmd_wnear failed")
        text = f"❌ Error fetching wNEAR supply:\n`{exc}`"
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_blocks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the last 5 finalized block summaries."""
    await update.message.reply_text("⏳ Loading latest blocks…")
    try:
        blocks = await get_recent_bridge_blocks(5)
        lines = [
            "📦 *Recent Finalized Blocks*\n"
            "━━━━━━━━━━━━━━━━━━━━"
        ]
        for b in blocks:
            chunk_bar = "▓" * b["active_chunks"] + "░" * (b["chunk_count"] - b["active_chunks"])
            lines.append(
                f"\n🔢 Height: `{b['height']:,}`\n"
                f"   ⛽ Gas Price: `{b['gas_price']:.4f} TGas`\n"
                f"   🧱 Chunks:    `{chunk_bar}` ({b['active_chunks']}/{b['chunk_count']} active)"
            )
        lines.append("\n━━━━━━━━━━━━━━━━━━━━\n_Live from NEAR Mainnet_")
        text = "\n".join(lines)
    except Exception as exc:
        logger.exception("cmd_blocks failed")
        text = f"❌ Error fetching blocks:\n`{exc}`"
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_validators(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show validator set overview and top-5 validators by stake."""
    await update.message.reply_text("⏳ Querying validator set…")
    try:
        v = await get_validators_brief()
        top5_lines = "\n".join(
            f"   {'🔴' if vv['slashed'] else '🟢'} `{vv['account_id'][:28]}`\n"
            f"       Stake: `{vv['stake_near']:,.0f} NEAR`"
            for vv in v["top5"]
        )
        text = (
            "🏛️  *NEAR Validator Overview*\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"🗓️  Epoch Start Block: `{v['epoch_start_height']:,}`\n"
            f"✅ Active Validators: `{v['current_validator_count']}`\n"
            f"🔜 Next Epoch Validators: `{v['next_validator_count']}`\n"
            f"💎 Total Staked:      `{v['total_stake_near']:,.0f} NEAR`\n\n"
            "🏆 *Top 5 Validators by Stake*\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"{top5_lines}\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "ℹ️  Validators secure the NEAR chain and bridge finality.\n"
            "🌐 https://nearblocks.io/nodes/validators"
        )
    except Exception as exc:
        logger.exception("cmd_validators failed")
        text = f"❌ Error fetching validators:\n`{exc}`"
    await update.message.reply_text(text, parse_mode="Markdown")


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]

    app = (
        ApplicationBuilder()
        .token(TOKEN)
        .build()
    )

    app.add_handler(CommandHandler("start",       start))
    app.add_handler(CommandHandler("help",        help_command))
    app.add_handler(CommandHandler("status",      cmd_status))
    app.add_handler(CommandHandler("bridge",      cmd_bridge))
    app.add_handler(CommandHandler("wnear",       cmd_wnear))
    app.add_handler(CommandHandler("blocks",      cmd_blocks))
    app.add_handler(CommandHandler("validators",  cmd_validators))

    logger.info("🌉 NEAR Bridge Status Bot is running…")

def main() -> None:
    logging.basicConfig(level=logging.INFO)
    token = os.environ.get("BOT_TOKEN", "")
    application = ApplicationBuilder().token(token).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("cmd_status", cmd_status))
    application.add_handler(CommandHandler("cmd_bridge", cmd_bridge))
    application.add_handler(CommandHandler("cmd_wnear", cmd_wnear))
    application.add_handler(CommandHandler("cmd_blocks", cmd_blocks))
    application.add_handler(CommandHandler("cmd_validators", cmd_validators))
    application.run_polling()

if __name__ == "__main__":
    main()

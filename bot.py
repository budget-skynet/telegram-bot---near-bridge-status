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
# 1. RPC HELPER
# ─────────────────────────────────────────────

async def _rpc(method: str, params: dict) -> dict:
    """Generic NEAR RPC call helper."""
    payload = {
        "jsonrpc": "2.0",
        "id": "bridge-bot",
        "method": method,
        "params": params,
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(
            NEAR_RPC,
            json=payload,
            timeout=aiohttp.ClientTimeout(total=15)
        ) as resp:
            data = await resp.json()
            if "error" in data:
                raise ValueError(f"RPC error: {data['error']}")
            return data.get("result", {})


# ─────────────────────────────────────────────
# 2. NEAR HELPER FUNCTIONS
# ─────────────────────────────────────────────

async def get_network_status() -> dict:
    """Fetch overall NEAR network status."""
    return await _rpc("status", [None])


async def get_block_info() -> dict:
    """Fetch the latest finalized block."""
    return await _rpc("block", {"finality": "final"})


async def get_bridge_account_info(account_id: str) -> dict:
    """Fetch account info for a bridge-related contract."""
    return await _rpc("query", {
        "request_type": "view_account",
        "finality": "final",
        "account_id": account_id,
    })


async def get_gas_price() -> dict:
    """Fetch current NEAR gas price."""
    return await _rpc("gas_price", [None])


async def get_validators() -> dict:
    """Fetch current epoch validator info."""
    return await _rpc("validators", [None])


# ─────────────────────────────────────────────
# 3. /start AND /help
# ─────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Welcome message with command overview."""
    user = update.effective_user
    text = (
        f"👋 Welcome, <b>{user.first_name}</b>!\n\n"
        "🌉 <b>NEAR Bridge Status Bot</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Monitor the Rainbow Bridge and NEAR network "
        "in real time, right here in Telegram.\n\n"
        "📋 <b>Available Commands</b>\n"
        "  /status   — Network & bridge health\n"
        "  /block    — Latest finalized block\n"
        "  /gas      — Current gas price\n"
        "  /bridge   — Rainbow Bridge contract info\n"
        "  /validators — Active validator set\n"
        "  /help     — Show this message\n\n"
        "🔗 Powered by <b>NEAR Protocol</b> mainnet RPC"
    )
    await update.message.reply_text(text, parse_mode="HTML")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Detailed help message."""
    text = (
        "🆘 <b>NEAR Bridge Bot — Help</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "<b>/status</b>\n"
        "  Shows NEAR network health, sync info,\n"
        "  and Rainbow Bridge contract status.\n\n"
        "<b>/block</b>\n"
        "  Displays the latest finalized block:\n"
        "  height, hash, timestamp, and gas used.\n\n"
        "<b>/gas</b>\n"
        "  Reports the current gas price in yoctoNEAR\n"
        "  and an approximate USD equivalent.\n\n"
        "<b>/bridge</b>\n"
        "  Queries the official Rainbow Bridge\n"
        "  locker contract on NEAR mainnet.\n\n"
        "<b>/validators</b>\n"
        "  Lists active validators, their stake,\n"
        "  and the current epoch information.\n\n"
        "📡 All data is fetched live from\n"
        "   <code>rpc.mainnet.near.org</code>"
    )
    await update.message.reply_text(text, parse_mode="HTML")


# ─────────────────────────────────────────────
# 4. COMMAND HANDLERS
# ─────────────────────────────────────────────

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show NEAR network status + bridge contract reachability."""
    await update.message.reply_text("🔄 Fetching network status…")
    try:
        net = await get_network_status()
        chain_id   = net.get("chain_id", "unknown")
        node_ver   = net.get("version", {}).get("version", "?")
        latest_blk = net.get("sync_info", {}).get("latest_block_height", "?")
        syncing    = net.get("sync_info", {}).get("syncing", False)
        sync_emoji = "✅" if not syncing else "⏳"

        # Quick-check bridge locker contract
        bridge_ok = True
        bridge_note = "✅ Reachable"
        try:
            await get_bridge_account_info("factory.bridge.near")
        except Exception:
            bridge_ok = False
            bridge_note = "⚠️ Unreachable"

        text = (
            "🌐 <b>NEAR Network Status</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🔗 Chain ID        : <code>{chain_id}</code>\n"
            f"📦 Latest Block    : <code>{latest_blk:,}</code>\n"
            f"🖥️ Node Version    : <code>{node_ver}</code>\n"
            f"{sync_emoji} Syncing         : <b>{'Yes' if syncing else 'No'}</b>\n\n"
            "🌉 <b>Rainbow Bridge</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"factory.bridge.near : {bridge_note}\n"
        )
        await update.message.reply_text(text, parse_mode="HTML")

    except Exception as exc:
        logger.error("status_command error: %s", exc)
        await update.message.reply_text(f"❌ Error fetching status:\n<code>{exc}</code>", parse_mode="HTML")


async def block_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show latest finalized block details."""
    await update.message.reply_text("🔄 Fetching latest block…")
    try:
        blk    = await get_block_info()
        header = blk.get("header", {})
        height    = header.get("height", "?")
        blk_hash  = header.get("hash", "?")
        timestamp = header.get("timestamp", 0)
        gas_used  = header.get("gas_used", 0)
        gas_limit = header.get("gas_limit", 1)

        # Convert nanosecond timestamp → human-readable
        import datetime
        ts_sec = int(timestamp) // 1_000_000_000
        dt_str = datetime.datetime.utcfromtimestamp(ts_sec).strftime("%Y-%m-%d %H:%M:%S UTC")

        # Gas utilization
        gas_pct = (int(gas_used) / int(gas_limit) * 100) if gas_limit else 0

        short_hash = f"{blk_hash[:8]}…{blk_hash[-6:]}" if len(blk_hash) > 16 else blk_hash

        text = (
            "📦 <b>Latest Finalized Block</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🔢 Height     : <code>{int(height):,}</code>\n"
            f"#️⃣  Hash       : <code>{short_hash}</code>\n"
            f"🕐 Timestamp  : <code>{dt_str}</code>\n"
            f"⛽ Gas Used   : <code>{int(gas_used):,}</code>\n"
            f"📊 Gas Limit  : <code>{int(gas_limit):,}</code>\n"
            f"💹 Gas Fill   : <b>{gas_pct:.2f}%</b>\n\n"
            f"🔍 <a href='https://explorer.near.org/blocks/{blk_hash}'>View on Explorer</a>"
        )
        await update.message.reply_text(text, parse_mode="HTML", disable_web_page_preview=True)

    except Exception as exc:
        logger.error("block_command error: %s", exc)
        await update.message.reply_text(f"❌ Error fetching block:\n<code>{exc}</code>", parse_mode="HTML")


async def gas_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show current NEAR gas price."""
    await update.message.reply_text("🔄 Fetching gas price…")
    try:
        result    = await get_gas_price()
        gas_price = int(result.get("gas_price", 0))

        # Convert yoctoNEAR/gas → TGas cost (1 TGas = 1e12 gas units)
        tgas_cost_yocto = gas_price * 1_000_000_000_000          # yoctoNEAR per TGas
        tgas_cost_near  = tgas_cost_yocto / 1e24                  # NEAR per TGas

        # Approximate USD (rough peg — bot shows disclaimer)
        near_usd_approx = 5.0
        tgas_cost_usd   = tgas_cost_near * near_usd_approx

        text = (
            "⛽ <b>NEAR Gas Price</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💎 Gas Price        : <code>{gas_price:,}</code> yoctoNEAR/gas\n"
            f"🔥 Cost per TGas    : <code>{tgas_cost_near:.6f}</code> NEAR\n"
            f"💵 ≈ Cost per TGas  : <code>${tgas_cost_usd:.4f}</code> USD*\n\n"
            "<i>* USD estimate uses ~$5/NEAR for illustration.</i>\n\n"
            "🌉 <b>Bridge Tip:</b> A cross-chain transfer\n"
            "   typically costs 10–30 TGas on NEAR."
        )
        await update.message.reply_text(text, parse_mode="HTML")

    except Exception as exc:
        logger.error("gas_command error: %s", exc)
        await update.message.reply_text(f"❌ Error fetching gas price:\n<code>{exc}</code>", parse_mode="HTML")


async def bridge_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show Rainbow Bridge contract details on NEAR mainnet."""
    await update.message.reply_text("🔄 Querying Rainbow Bridge contracts…")

    BRIDGE_CONTRACTS = {
        "factory.bridge.near":       "ERC-20 Token Factory",
        "aurora":                    "Aurora EVM Engine",
        "wrap.near":                 "Wrapped NEAR (wNEAR)",
    }

    lines = [
        "🌉 <b>Rainbow Bridge Contracts</b>",
        "━━━━━━━━━━━━━━━━━━━━━━━",
    ]

    for contract, label in BRIDGE_CONTRACTS.items():
        try:
            info   = await get_bridge_account_info(contract)
            amount = int(info.get("amount", 0)) / 1e24        # yoctoNEAR → NEAR
            code   = "📜 Has Code" if info.get("code_hash", "11111") != "11111111111111111111111111111111" else "📄 No Code"
            lines.append(
                f"\n🔹 <b>{label}</b>\n"
                f"   Account : <code>{contract}</code>\n"
                f"   Balance : <code>{amount:,.4f} NEAR</code>\n"
                f"   Contract: {code}\n"
                f"   Status  : ✅ Active"
            )
        except Exception as exc:
            lines.append(
                f"\n🔸 <b>{label}</b>\n"
                f"   Account : <code>{contract}</code>\n"
                f"   Status  : ⚠️ {str(exc)[:60]}"
            )

    lines.append(
        "\n🔗 <a href='https://rainbowbridge.app'>rainbowbridge.app</a>"
    )
    await update.message.reply_text("\n".join(lines), parse_mode="HTML", disable_web_page_preview=True)


async def validators_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show current NEAR validator set summary."""
    await update.message.reply_text("🔄 Fetching validator info…")
    try:
        val_data   = await get_validators()
        current    = val_data.get("current_validators", [])
        epoch_height = val_data.get("epoch_height", "?")
        epoch_start  = val_data.get("epoch_start_height", "?")

        total_stake = sum(int(v.get("stake", 0)) for v in current) / 1e24
        num_vals    = len(current)

        # Top 5 by stake
        top5 = sorted(current, key=lambda v: int(v.get("stake", 0)), reverse=True)[:5]

        lines = [
            "🏛️ <b>NEAR Validator Set</b>",
            "━━━━━━━━━━━━━━━━━━━━━━━",
            f"📅 Epoch Height  : <code>{epoch_height}</code>",
            f"🚀 Epoch Start   : <code>{epoch_start:,}</code>",
            f"👥 Active Vals   : <code>{num_vals}</code>",
            f"💰 Total Stake   : <code>{total_stake:,.0f} NEAR</code>",
            "",
            "🏆 <b>Top 5 Validators by Stake</b>",
            "━━━━━━━━━━━━━━━━━━━━━━━",
        ]

        for i, v in enumerate(top5, 1):
            stake_near = int(v.get("stake", 0)) / 1e24
            share      = stake_near / total_stake * 100 if total_stake else 0
            acc        = v.get("account_id", "unknown")
            # Shorten long account names
            display    = acc if len(acc) <= 24 else f"{acc[:20]}…"
            lines.append(
                f"{i}. <code>{display}</code>\n"
                f"   Stake: <b>{stake_near:,.0f} NEAR</b> ({share:.1f}%)"
            )

        lines.append(
            "\n🔍 <a href='https://explorer.near.org/nodes/validators'>Full list on Explorer</a>"
        )
        await update.message.reply_text("\n".join(lines), parse_mode="HTML", disable_web_page_preview=True)

    except Exception as exc:
        logger.error("validators_command error: %s", exc)
        await update.message.reply_text(f"❌ Error fetching validators:\n<code>{exc}</code>", parse_mode="HTML")

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
    application.add_handler(CommandHandler("validators", validators_command))
    application.run_polling()

if __name__ == "__main__":
    main()

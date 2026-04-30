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
# 1. Core RPC helper
# ─────────────────────────────────────────────

async def _rpc(method: str, params: dict) -> dict:
    """Send a JSON-RPC request to the NEAR mainnet RPC endpoint."""
    payload = {
        "jsonrpc": "2.0",
        "id": "dontcare",
        "method": method,
        "params": params,
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(NEAR_RPC, json=payload, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            resp.raise_for_status()
            data = await resp.json()
            if "error" in data:
                raise ValueError(f"RPC error: {data['error']}")
            return data.get("result", {})

# ─────────────────────────────────────────────
# 2. NEAR Helper Functions
# ─────────────────────────────────────────────

async def get_latest_block() -> dict:
    """Fetch the latest finalized block from NEAR."""
    result = await _rpc("block", {"finality": "final"})
    header = result.get("header", {})
    return {
        "height": header.get("height"),
        "hash": header.get("hash"),
        "timestamp_ns": header.get("timestamp"),
        "validator": header.get("challenges_result"),
        "gas_price": header.get("gas_price"),
        "total_supply": header.get("total_supply"),
    }


async def get_network_info() -> dict:
    """Fetch NEAR network status including peer count and sync info."""
    result = await _rpc("status", [None])
    sync = result.get("sync_info", {})
    return {
        "chain_id": result.get("chain_id"),
        "latest_block_height": sync.get("latest_block_height"),
        "latest_block_hash": sync.get("latest_block_hash"),
        "latest_block_time": sync.get("latest_block_time"),
        "syncing": sync.get("syncing"),
        "node_version": result.get("version", {}).get("version"),
    }


async def get_bridge_account_state(account_id: str) -> dict:
    """
    Fetch on-chain state for a known Rainbow Bridge contract account.
    Default: eth-connector.bridge.near (the ETH↔NEAR connector).
    """
    result = await _rpc("query", {
        "request_type": "view_account",
        "finality": "final",
        "account_id": account_id,
    })
    return {
        "account_id": account_id,
        "amount": result.get("amount"),
        "locked": result.get("locked"),
        "code_hash": result.get("code_hash"),
        "storage_usage": result.get("storage_usage"),
    }


async def get_validators_summary() -> dict:
    """Fetch current epoch validator information."""
    result = await _rpc("validators", [None])
    current = result.get("current_validators", [])
    next_v = result.get("next_validators", [])
    return {
        "epoch_start_height": result.get("epoch_start_height"),
        "current_count": len(current),
        "next_count": len(next_v),
        "top_validators": [
            {
                "account_id": v.get("account_id"),
                "stake": v.get("stake"),
                "num_produced_blocks": v.get("num_produced_blocks"),
                "num_expected_blocks": v.get("num_expected_blocks"),
            }
            for v in sorted(current, key=lambda x: int(x.get("stake", 0)), reverse=True)[:5]
        ],
    }


async def get_gas_price_info() -> dict:
    """Fetch current NEAR gas price."""
    result = await _rpc("gas_price", [None])
    gas_price_yocto = int(result.get("gas_price", 0))
    # 1 NEAR = 10^24 yoctoNEAR
    gas_price_near = gas_price_yocto / 1e24
    return {
        "gas_price_yocto": gas_price_yocto,
        "gas_price_near": gas_price_near,
        # Cost of 300 TGas (typical cross-contract call)
        "typical_tx_cost_near": gas_price_near * 300_000_000_000_000,
    }

# ─────────────────────────────────────────────
# 3. Bot Command Handlers — /start & /help
# ─────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Welcome message with command overview."""
    text = (
        "🌉 *NEAR Bridge Status Bot*\n\n"
        "Monitor the NEAR Rainbow Bridge and network health in real time.\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "📡 *Available Commands*\n\n"
        "🔷 /status — Network & latest block\n"
        "🌉 /bridge — Rainbow Bridge contract state\n"
        "⛽ /gas — Current gas price\n"
        "🗳 /validators — Top validators this epoch\n"
        "❓ /help — Show this menu\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "Built with ❤️ for the NEAR ecosystem.\n"
        "_Data sourced directly from NEAR RPC mainnet._"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Detailed help message."""
    text = (
        "📖 *NEAR Bridge Bot — Help*\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "*Commands:*\n\n"
        "🔷 `/status`\n"
        "  → Live NEAR network info: block height, hash, sync status, node version.\n\n"
        "🌉 `/bridge`\n"
        "  → Rainbow Bridge ETH connector contract state: locked NEAR, storage usage, code hash.\n\n"
        "⛽ `/gas`\n"
        "  → Current gas price in yoctoNEAR and estimated cost for a typical transaction.\n\n"
        "🗳 `/validators`\n"
        "  → Top 5 validators by stake, block production rate, and epoch info.\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "*What is the Rainbow Bridge?*\n"
        "The Rainbow Bridge connects NEAR Protocol and Ethereum, enabling trustless asset transfers between the two chains.\n\n"
        "_All data is live from `rpc.mainnet.near.org`_"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

# ─────────────────────────────────────────────
# 4. Feature Command Handlers
# ─────────────────────────────────────────────

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show live NEAR network status."""
    await update.message.reply_text("⏳ Fetching NEAR network status…")
    try:
        net = await get_network_info()
        block = await get_latest_block()

        # Convert nanosecond timestamp to readable
        ts_ns = block.get("timestamp_ns", 0)
        ts_s = int(ts_ns) / 1e9 if ts_ns else 0
        from datetime import datetime, timezone
        dt = datetime.fromtimestamp(ts_s, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC") if ts_s else "N/A"

        # Format gas price
        gas_raw = block.get("gas_price", "0")
        gas_near = int(gas_raw) / 1e24 if gas_raw else 0

        # Total supply
        supply_raw = block.get("total_supply", "0")
        supply_near = int(supply_raw) / 1e24 if supply_raw else 0

        text = (
            "🔷 *NEAR Network Status*\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"🌐 *Chain ID:* `{net['chain_id']}`\n"
            f"📦 *Block Height:* `{block['height']:,}`\n"
            f"#️⃣ *Block Hash:* `{str(block['hash'])[:20]}…`\n"
            f"🕐 *Block Time:* `{dt}`\n"
            f"⛽ *Gas Price:* `{gas_near:.2e} NEAR/gas`\n"
            f"💰 *Total Supply:* `{supply_near:,.0f} NEAR`\n"
            f"🔄 *Syncing:* `{'Yes ⚠️' if net['syncing'] else 'No ✅'}`\n"
            f"🖥 *Node Version:* `{net['node_version']}`\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "_Live data from NEAR mainnet RPC_"
        )
        await update.message.reply_text(text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"status_command error: {e}")
        await update.message.reply_text(f"❌ Failed to fetch network status.\n`{e}`", parse_mode="Markdown")


async def bridge_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show Rainbow Bridge contract state."""
    # Key Rainbow Bridge contracts on NEAR mainnet
    BRIDGE_CONTRACTS = [
        "eth-connector.bridge.near",
        "factory.bridge.near",
    ]
    await update.message.reply_text("⏳ Querying Rainbow Bridge contracts…")
    try:
        lines = [
            "🌉 *Rainbow Bridge Status*\n",
            "━━━━━━━━━━━━━━━━━━━━",
        ]
        for account_id in BRIDGE_CONTRACTS:
            try:
                state = await get_bridge_account_state(account_id)
                amount_near = int(state["amount"]) / 1e24 if state.get("amount") else 0
                locked_near = int(state["locked"]) / 1e24 if state.get("locked") else 0
                storage_kb = (state.get("storage_usage") or 0) / 1024

                lines.append(f"\n📋 *Contract:* `{account_id}`")
                lines.append(f"  💵 Balance: `{amount_near:,.4f} NEAR`")
                lines.append(f"  🔒 Locked:  `{locked_near:,.4f} NEAR`")
                lines.append(f"  💾 Storage: `{storage_kb:,.2f} KB`")
                lines.append(f"  🔑 Code Hash: `{str(state['code_hash'])[:16]}…`")
            except Exception as ce:
                lines.append(f"\n⚠️ `{account_id}`: Could not fetch (`{ce}`)")

        lines += [
            "\n━━━━━━━━━━━━━━━━━━━━",
            "_Source: NEAR mainnet RPC_",
        ]
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
    except Exception as e:
        logger.error(f"bridge_command error: {e}")
        await update.message.reply_text(f"❌ Failed to fetch bridge data.\n`{e}`", parse_mode="Markdown")


async def gas_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show current NEAR gas price."""
    await update.message.reply_text("⏳ Fetching gas price…")
    try:
        info = await get_gas_price_info()
        yocto = info["gas_price_yocto"]
        near_per_gas = info["gas_price_near"]
        typical_cost = info["typical_tx_cost_near"]

        text = (
            "⛽ *NEAR Gas Price*\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"💱 *Gas Price:*\n"
            f"  `{yocto:,}` yoctoNEAR/gas\n"
            f"  `{near_per_gas:.6e}` NEAR/gas\n\n"
            f"📊 *Typical Transaction Costs:*\n"
            f"  🔹 Simple transfer (450 Tgas):\n"
            f"     `{near_per_gas * 450_000_000_000_000:.6f} NEAR`\n"
            f"  🔹 Cross-contract call (300 Tgas):\n"
            f"     `{typical_cost:.6f} NEAR`\n"
            f"  🔹 Bridge deposit (~2.5 Tgas):\n"
            f"     `{near_per_gas * 2_500_000_000_000:.8f} NEAR`\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "_1 NEAR = 10²⁴ yoctoNEAR_"
        )
        await update.message.reply_text(text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"gas_command error: {e}")
        await update.message.reply_text(f"❌ Failed to fetch gas price.\n`{e}`", parse_mode="Markdown")


async def validators_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show top validators and epoch info."""
    await update.message.reply_text("⏳ Fetching validator data…")
    try:
        data = await get_validators_summary()
        top = data["top_validators"]

        lines = [
            "🗳 *NEAR Validators — Current Epoch*\n",
            "━━━━━━━━━━━━━━━━━━━━",
            f"📅 *Epoch Start Block:* `{data['epoch_start_height']:,}`",
            f"✅ *Active Validators:* `{data['current_count']}`",
            f"🔜 *Next Epoch Validators:* `{data['next_count']}`\n",
            "🏆 *Top 5 Validators by Stake:*\n",
        ]

        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
        for i, v in enumerate(top):
            stake_near = int(v["stake"]) / 1e24 if v.get("stake") else 0
            produced = v.get("num_produced_blocks", 0)
            expected = v.get("num_expected_blocks", 1) or 1
            uptime = (produced / expected) * 100 if expected else 0
            medal = medals[i] if i < len(medals) else f"{i+1}."
            lines.append(
                f"{medal} `{v['account_id']}`\n"
                f"   Stake: `{stake_near:,.0f} NEAR`\n"
                f"   Uptime: `{uptime:.1f}%` ({produced}/{expected} blocks)\n"
            )

        lines += [
            "━━━━━━━━━━━━━━━━━━━━",
            "_Data from NEAR mainnet RPC_",
        ]
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
    except Exception as e:
        logger.error(f"validators_command error: {e}")
        await update.message.reply_text(f"❌ Failed to fetch validator data.\n`{e}`", parse_mode="Markdown")

def main() -> None:
    logging.basicConfig(level=logging.INFO)
    token = os.environ.get("BOT_TOKEN", "")
    application = ApplicationBuilder().token(token).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("bridge", bridge_command))
    application.add_handler(CommandHandler("gas", gas_command))
    application.add_handler(CommandHandler("validators", validators_command))
    application.run_polling()

if __name__ == "__main__":
    main()

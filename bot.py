import os
import logging
import aiohttp
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────
NEAR_RPC = "https://rpc.mainnet.near.org"

# Rainbow Bridge contracts (NEAR side)
BRIDGE_CONTRACT = "factory.bridge.near"
ETH_CUSTODIAN   = "aurora"                     # ETH→NEAR entry point on NEAR
AURORA_CONTRACT = "aurora"

# ── Core RPC helper ───────────────────────────────────────────────────────────
async def _rpc(method: str, params: dict) -> dict:
    """
    Fire a JSON-RPC request at the NEAR mainnet endpoint.
    Returns the 'result' key on success, raises RuntimeError on failure.
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
            data = await resp.json(content_type=None)

    if "error" in data:
        raise RuntimeError(data["error"].get("message", "RPC error"))
    return data.get("result", {})


# ── NEAR helper functions ─────────────────────────────────────────────────────
async def get_network_status() -> dict:
    """
    Fetch general NEAR network / node status.
    Returns a dict with chain_id, latest_block_height, sync_info, etc.
    """
    result = await _rpc("status", {})
    return {
        "chain_id":     result.get("chain_id", "unknown"),
        "node_version": result.get("version", {}).get("version", "?"),
        "protocol":     result.get("protocol_version", "?"),
        "block_height": result.get("sync_info", {}).get("latest_block_height", "?"),
        "block_hash":   result.get("sync_info", {}).get("latest_block_hash", "?"),
        "syncing":      result.get("sync_info", {}).get("syncing", False),
    }


async def get_bridge_account_info(account_id: str) -> dict:
    """
    Return balance + storage usage for any NEAR account (bridge contracts).
    """
    result = await _rpc("query", {
        "request_type": "view_account",
        "finality":     "final",
        "account_id":   account_id,
    })
    raw_balance = int(result.get("amount", 0))
    near_balance = raw_balance / 1e24          # yoctoNEAR → NEAR
    return {
        "account_id":    account_id,
        "balance_near":  round(near_balance, 4),
        "storage_bytes": result.get("storage_usage", 0),
        "block_height":  result.get("block_height", "?"),
    }


async def get_latest_block() -> dict:
    """
    Fetch the most recently finalised NEAR block.
    """
    result = await _rpc("block", {"finality": "final"})
    header = result.get("header", {})
    return {
        "height":        header.get("height", "?"),
        "hash":          header.get("hash", "?"),
        "timestamp_ns":  header.get("timestamp", 0),
        "gas_price":     header.get("gas_price", "?"),
        "validator":     header.get("block_ordinal", "?"),
        "chunk_count":   len(result.get("chunks", [])),
    }


async def get_gas_price() -> dict:
    """
    Return the current NEAR gas price (in yoctoNEAR per gas unit).
    """
    result = await _rpc("gas_price", [None])   # None → latest block
    gp_raw = int(result.get("gas_price", 0))
    return {
        "yocto_per_gas": gp_raw,
        "tgas_cost_near": round(gp_raw * 1e12 / 1e24, 6),   # cost of 1 TGas
    }


async def get_bridge_token_list() -> list[dict]:
    """
    Call the bridge factory contract to list the first page of bridged tokens.
    Falls back gracefully if the contract view call fails.
    """
    try:
        import json, base64
        args_b64 = base64.b64encode(
            json.dumps({"from_index": 0, "limit": 10}).encode()
        ).decode()
        result = await _rpc("query", {
            "request_type": "call_function",
            "finality":     "final",
            "account_id":   BRIDGE_CONTRACT,
            "method_name":  "get_tokens",
            "args_base64":  args_b64,
        })
        raw = bytes(result.get("result", []))
        tokens = json.loads(raw.decode()) if raw else []
        return tokens
    except Exception as exc:
        logger.warning("Token list fetch failed: %s", exc)
        return []


# ── /start and /help ──────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "🌉 *NEAR Bridge Status Bot*\n\n"
        "Monitor the Rainbow Bridge (NEAR ↔ Ethereum) in real time.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "📋 *Commands*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "/status   — Network & bridge health\n"
        "/block    — Latest finalised block\n"
        "/gas      — Current gas price\n"
        "/bridge   — Bridge contract balances\n"
        "/tokens   — Bridged ERC-20 tokens\n"
        "/help     — Show this menu\n\n"
        "Built on the [NEAR Rainbow Bridge](https://rainbowbridge.app) 🌈"
    )
    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        disable_web_page_preview=True,
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await start(update, context)


# ── Command handlers ──────────────────────────────────────────────────────────
async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /status — Show overall NEAR network health plus bridge account state.
    """
    await update.message.reply_text("⏳ Fetching network status…")
    try:
        net   = await get_network_status()
        sync  = "✅ Synced" if not net["syncing"] else "⚠️ Syncing"
        text  = (
            "🌐 *NEAR Network Status*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🔗 Chain ID       : `{net['chain_id']}`\n"
            f"📦 Block Height   : `{net['block_height']:,}`\n"
            f"🔑 Block Hash     : `{str(net['block_hash'])[:12]}…`\n"
            f"⚙️  Protocol ver  : `{net['protocol']}`\n"
            f"🖥  Node version  : `{net['node_version']}`\n"
            f"🔄 Sync status   : {sync}\n\n"
            "🌉 *Bridge Contracts*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"• `factory.bridge.near`\n"
            f"• `aurora` (ETH custodian)\n\n"
            "_Use /bridge for contract balances_"
        )
        await update.message.reply_text(text, parse_mode="Markdown")
    except Exception as exc:
        logger.error("status_command: %s", exc)
        await update.message.reply_text(f"❌ Error fetching status:\n`{exc}`", parse_mode="Markdown")


async def block_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /block — Display the latest finalised block details.
    """
    await update.message.reply_text("⏳ Fetching latest block…")
    try:
        blk = await get_latest_block()
        ts_s = int(blk["timestamp_ns"]) // 1_000_000_000
        from datetime import datetime, timezone
        dt = datetime.fromtimestamp(ts_s, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        text = (
            "📦 *Latest Finalised Block*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🔢 Height      : `{int(blk['height']):,}`\n"
            f"#️⃣  Hash        : `{str(blk['hash'])[:16]}…`\n"
            f"🕐 Time        : `{dt}`\n"
            f"⛽ Gas Price   : `{blk['gas_price']}`\n"
            f"🧩 Chunks      : `{blk['chunk_count']}`\n\n"
            "_NEAR produces blocks roughly every second_ ⚡"
        )
        await update.message.reply_text(text, parse_mode="Markdown")
    except Exception as exc:
        logger.error("block_command: %s", exc)
        await update.message.reply_text(f"❌ Error:\n`{exc}`", parse_mode="Markdown")


async def gas_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /gas — Show current NEAR gas price.
    """
    await update.message.reply_text("⏳ Fetching gas price…")
    try:
        gp = await get_gas_price()
        text = (
            "⛽ *NEAR Gas Price*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 Per gas unit  : `{gp['yocto_per_gas']:,}` yoctoNEAR\n"
            f"💸 1 TGas cost   : `{gp['tgas_cost_near']}` NEAR\n\n"
            "📝 *Bridge Tx Estimates*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"  ETH→NEAR lock  : ~300 TGas "
            f"≈ `{round(gp['tgas_cost_near']*300,4)}` NEAR\n"
            f"  NEAR→ETH burn  : ~100 TGas "
            f"≈ `{round(gp['tgas_cost_near']*100,4)}` NEAR\n\n"
            "_Gas prices on NEAR are extremely stable_ ✅"
        )
        await update.message.reply_text(text, parse_mode="Markdown")
    except Exception as exc:
        logger.error("gas_command: %s", exc)
        await update.message.reply_text(f"❌ Error:\n`{exc}`", parse_mode="Markdown")


async def bridge_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /bridge — Show balances & storage for key Rainbow Bridge contracts.
    """
    await update.message.reply_text("⏳ Querying bridge contracts…")
    contracts = [BRIDGE_CONTRACT, AURORA_CONTRACT]
    lines = ["🌉 *Rainbow Bridge Contract Status*\n━━━━━━━━━━━━━━━━━━━━━━"]
    for acct in contracts:
        try:
            info = await get_bridge_account_info(acct)
            storage_kb = round(info["storage_bytes"] / 1024, 2)
            lines.append(
                f"\n📄 `{info['account_id']}`\n"
                f"   💰 Balance : `{info['balance_near']:,}` NEAR\n"
                f"   🗄  Storage : `{storage_kb:,}` KB\n"
                f"   📦 At block: `{info['block_height']:,}`"
            )
        except Exception as exc:
            lines.append(f"\n⚠️ `{acct}` — fetch failed: {exc}")

    lines.append(
        "\n━━━━━━━━━━━━━━━━━━━━━━\n"
        "🔗 [Rainbow Bridge App](https://rainbowbridge.app)"
    )
    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="Markdown",
        disable_web_page_preview=True,
    )


async def tokens_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /tokens — List bridged ERC-20 tokens registered on factory.bridge.near.
    """
    await update.message.reply_text("⏳ Fetching bridged token list…")
    try:
        tokens = await get_bridge_token_list()
        if tokens:
            lines = ["🪙 *Bridged ERC-20 Tokens (first 10)*\n━━━━━━━━━━━━━━━━━━━━━━"]
            for i, token in enumerate(tokens, 1):
                if isinstance(token, str):
                    lines.append(f"{i}. `{token}`")
                elif isinstance(token, dict):
                    name = token.get("name") or token.get("symbol") or str(token)
                    lines.append(f"{i}. `{name}`")
            lines.append(
                "\n━━━━━━━━━━━━━━━━━━━━━━\n"
                "🔍 Full list: [NEAR Explorer](https://nearblocks.io/address/factory.bridge.near)"
            )
            text = "\n".join(lines)
        else:
            # Provide curated list as fallback
            text = (
                "🪙 *Well-Known Rainbow Bridge Tokens*\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "1. `wETH` — Wrapped Ether\n"
                "2. `USDC` — USD Coin\n"
                "3. `USDT` — Tether USD\n"
                "4. `DAI`  — Dai Stablecoin\n"
                "5. `WBTC` — Wrapped Bitcoin\n"
                "6. `LINK` — Chainlink\n"
                "7. `UNI`  — Uniswap\n"
                "8. `AAVE` — Aave\n\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "🔍 [View all tokens](https://nearblocks.io/address/factory.bridge.near)"
            )
        await update.message.reply_text(
            text,
            parse_mode="Markdown",
            disable_web_page_preview=True,
        )
    except Exception as exc:
        logger.error("tokens_command: %s", exc)
        await update.message.reply_text(f"❌ Error:\n`{exc}`", parse_mode="Markdown")

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
    application.add_handler(CommandHandler("tokens", tokens_command))
    application.run_polling()

if __name__ == "__main__":
    main()

"""
bot_interactive.py - Interactive Telegram bot
Run this separately to enable on-demand commands

Commands:
  /search [make] [model] [year] - Search both yards right now
  /price [make] [model] [part]  - Look up eBay average sold price
  /targets                      - Show your current watchlist
  /status                       - Show last run info
  /help                         - Show all commands
"""

import os
import json
import logging
import concurrent.futures
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")


def load_targets():
    path = os.path.join(os.path.dirname(__file__), "targets.json")
    with open(path) as f:
        return json.load(f)


# ── /help ─────────────────────────────────────────────────────────────────────
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🤖 <b>Junkyard Bot Commands</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "/search [make] [model] [year]\n"
        "  Example: /search Mitsubishi Lancer 2010\n\n"
        "/price [make] [model] [part]\n"
        "  Example: /price Mitsubishi Lancer tail light\n\n"
        "/targets — Show your watchlist\n\n"
        "/status — Show bot stats\n\n"
        "/help — Show this message"
    )
    await update.message.reply_text(msg, parse_mode="HTML")


# ── /targets ──────────────────────────────────────────────────────────────────
async def targets_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        targets = load_targets()
        lines = ["🎯 <b>Your Watchlist</b>", "━━━━━━━━━━━━━━━━━━━━━━━━"]
        for t in targets:
            years = f"{min(t['years'])}–{max(t['years'])}"
            parts = ", ".join(t["parts_to_pull"])
            priority = t.get("priority", "medium").upper()
            lines.append(
                f"\n🚗 <b>{t['make']} {t['model']}</b> ({years})\n"
                f"   Priority: {priority}\n"
                f"   Parts: {parts}"
            )
        await update.message.reply_text("\n".join(lines), parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"Error loading targets: {e}")


# ── /status ───────────────────────────────────────────────────────────────────
async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        from database import get_conn
        conn = get_conn()
        total   = conn.execute("SELECT COUNT(*) FROM inventory").fetchone()[0]
        targets = conn.execute("SELECT COUNT(*) FROM inventory WHERE is_target=1").fetchone()[0]
        last    = conn.execute("SELECT MAX(last_seen) FROM inventory").fetchone()[0]
        alerts  = conn.execute("SELECT COUNT(*) FROM alert_log").fetchone()[0]
        conn.close()

        msg = (
            f"📊 <b>Bot Status</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🚗 Total vehicles tracked: {total}\n"
            f"🎯 Target matches found: {targets}\n"
            f"🔔 Total alerts sent: {alerts}\n"
            f"🕐 Last seen: {last[:16] if last else 'Never'}\n"
            f"⏰ Next run: Today at 5:00 PM"
        )
        await update.message.reply_text(msg, parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"Error getting status: {e}")


# ── /search ───────────────────────────────────────────────────────────────────
async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 3:
        await update.message.reply_text(
            "Usage: /search [make] [model] [year]\n"
            "Example: /search Mitsubishi Lancer 2010"
        )
        return

    year  = args[-1]
    make  = args[0]
    model = " ".join(args[1:-1])

    if not year.isdigit():
        await update.message.reply_text("Year must be a number. Example: /search Mitsubishi Lancer 2010")
        return

    await update.message.reply_text(
        f"🔍 Searching both yards for {year} {make} {model}...\nThis may take a few minutes."
    )

    try:
        target = [{
            "make": make,
            "model": model,
            "years": [int(year)],
            "parts_to_pull": ["driver mirror", "passenger mirror", "tail light", "head light", "BCM module"],
            "priority": "high"
        }]

        from scrapers.jalopy import scrape_all as jalopy_scrape
        from scrapers.trusty import scrape_all as trusty_scrape

        with concurrent.futures.ThreadPoolExecutor() as executor:
            f1 = executor.submit(jalopy_scrape, target)
            f2 = executor.submit(trusty_scrape, target)
            jalopy_results = f1.result()
            trusty_results = f2.result()

        all_results = jalopy_results + trusty_results

        if not all_results:
            await update.message.reply_text(
                f"❌ No {year} {make} {model} found at either yard right now."
            )
            return

        lines = [f"✅ <b>Found {len(all_results)} result(s) for {year} {make} {model}</b>", ""]
        for v in all_results:
            row = f"Row {v['row']}" if v.get("row") else "Row unknown"
            lines.append(f"🏭 {v['yard']} — {v['location']}\n📍 {row}")

        await update.message.reply_text("\n".join(lines), parse_mode="HTML")

    except Exception as e:
        await update.message.reply_text(f"Search error: {e}")


# ── /price ────────────────────────────────────────────────────────────────────
async def price_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 3:
        await update.message.reply_text(
            "Usage: /price [make] [model] [part]\n"
            "Example: /price Mitsubishi Lancer tail light\n\n"
            "Parts: driver mirror, passenger mirror, tail light, head light, BCM module"
        )
        return

    make  = args[0]
    model = args[1]
    part  = " ".join(args[2:])

    await update.message.reply_text(f"💰 Looking up eBay prices for {make} {model} — {part}...")

    try:
        import base64, requests, time

        app_id  = os.getenv("EBAY_APP_ID")
        cert_id = os.getenv("EBAY_CERT_ID")

        # Get token
        credentials = base64.b64encode(f"{app_id}:{cert_id}".encode()).decode()
        r = requests.post(
            "https://api.ebay.com/identity/v1/oauth2/token",
            headers={"Authorization": f"Basic {credentials}", "Content-Type": "application/x-www-form-urlencoded"},
            data="grant_type=client_credentials&scope=https://api.ebay.com/oauth/api_scope"
        )
        token = r.json()["access_token"]

        # Search eBay
        query = f"{make} {model} {part} OEM"
        r = requests.get(
            "https://api.ebay.com/buy/browse/v1/item_summary/search",
            headers={"Authorization": f"Bearer {token}", "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"},
            params={"q": query, "limit": 50, "filter": "buyingOptions:{FIXED_PRICE}"},
            timeout=15
        )

        items = r.json().get("itemSummaries", [])
        prices = []
        for item in items:
            val = item.get("price", {}).get("value")
            if val:
                try:
                    prices.append(float(val))
                except ValueError:
                    pass

        if not prices:
            await update.message.reply_text(f"No eBay listings found for {make} {model} {part}.")
            return

        avg = round(sum(prices) / len(prices), 2)
        low = round(min(prices), 2)
        high = round(max(prices), 2)

        msg = (
            f"💰 <b>eBay Price Data</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🚗 {make} {model}\n"
            f"🔧 {part.title()}\n\n"
            f"Avg:      ${avg:.2f}\n"
            f"Lowest:   ${low:.2f}\n"
            f"Highest:  ${high:.2f}\n"
            f"Listings: {len(prices)}"
        )
        await update.message.reply_text(msg, parse_mode="HTML")

    except Exception as e:
        await update.message.reply_text(f"Price lookup error: {e}")


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    if TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("ERROR: Set your TELEGRAM_BOT_TOKEN environment variable first")
        return

    print("Starting interactive Junkyard Bot...")
    print("Send /help in Telegram to see available commands")

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("help",    help_command))
    app.add_handler(CommandHandler("targets", targets_command))
    app.add_handler(CommandHandler("status",  status_command))
    app.add_handler(CommandHandler("search",  search_command))
    app.add_handler(CommandHandler("price",   price_command))

    app.run_polling()


if __name__ == "__main__":
    main()

"""
telegram_bot.py - Telegram notification system for junkyard bot
Handles all alert types: new arrivals, daily digest, weekly trends
"""

import os
import requests
from datetime import datetime

# ─── Configuration ────────────────────────────────────────────────────────────
# Get your bot token from @BotFather on Telegram
# Get your chat ID by messaging @userinfobot on Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID",   "YOUR_CHAT_ID_HERE")

PRIORITY_EMOJI = {
    "high":   "🔴",
    "medium": "🟡",
    "low":    "🟢"
}

YARD_EMOJI = {
    "Jalopy Jungle":    "🏚️",
    "Trusty Auto Parts": "🔧"
}


def send_message(text: str) -> bool:
    """Send a message via Telegram bot."""
    if TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print(f"[Telegram] Bot not configured. Would send:\n{text}\n")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id":    TELEGRAM_CHAT_ID,
        "text":       text,
        "parse_mode": "HTML"
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            return True
        else:
            print(f"[Telegram] Failed: {response.status_code} {response.text}")
            return False
    except Exception as e:
        print(f"[Telegram] Error: {e}")
        return False


def build_new_arrival_message(vehicle: dict, target: dict, price_block: str) -> str:
    """
    Build alert message for a new vehicle matching your target list.
    
    Example output:
    🔴 TARGET FOUND - High Priority
    ━━━━━━━━━━━━━━━━━━━━━━━━
    🏚️ Jalopy Jungle — Boise
    📍 Row 14
    🚗 2018 Ford F-150

    💰 Parts Worth Pulling:
      ✅ Driver Mirror
         Avg: $92.00 | Min: $45.00 | Max: $145.00 | 38 sold
      ✅ Tail Light
         Avg: $67.00 | Min: $30.00 | Max: $110.00 | 24 sold

    ⏰ Just arrived — go soon!
    """
    priority = target.get("priority", "medium")
    emoji = PRIORITY_EMOJI.get(priority, "🟡")
    yard_emoji = YARD_EMOJI.get(vehicle["yard"], "🏭")

    row_line = f"📍 Row {vehicle['row']}" if vehicle.get("row") else "📍 Row: check yard"

    msg = (
        f"{emoji} <b>TARGET FOUND — {priority.upper()} PRIORITY</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{yard_emoji} <b>{vehicle['yard']}</b> — {vehicle['location']}\n"
        f"{row_line}\n"
        f"🚗 <b>{vehicle['year']} {vehicle['make']} {vehicle['model']}</b>\n"
        f"\n"
        f"💰 <b>Parts Worth Pulling:</b>\n"
        f"{price_block}\n"
        f"\n"
        f"⏰ Just arrived — go soon!"
    )
    return msg


def build_any_new_vehicle_message(vehicle: dict) -> str:
    """
    Shorter alert for any new vehicle (not on target list).
    
    Example output:
    🆕 New Vehicle — Trusty Auto Parts (Meridian)
    📍 Row 7
    🚗 2015 Subaru Outback
    Not on target list — check if worth pulling
    """
    yard_emoji = YARD_EMOJI.get(vehicle["yard"], "🏭")
    row_line = f"📍 Row {vehicle['row']}" if vehicle.get("row") else ""

    msg = (
        f"🆕 <b>New Vehicle</b> — {yard_emoji} {vehicle['yard']} ({vehicle['location']})\n"
        f"{row_line}\n"
        f"🚗 {vehicle['year']} {vehicle['make']} {vehicle['model']}\n"
        f"<i>Not on target list — worth a look?</i>"
    )
    return msg


def send_new_arrival_alert(vehicle: dict, target: dict, price_block: str):
    """Send alert for a target vehicle."""
    msg = build_new_arrival_message(vehicle, target, price_block)
    sent = send_message(msg)
    if sent:
        try:
            from database import log_alert, mark_notified
            log_alert("new_target", msg)
            mark_notified(vehicle["id"])
        except Exception:
            pass
    return sent


def send_any_vehicle_alert(vehicle: dict):
    """Send alert for any new vehicle."""
    msg = build_any_new_vehicle_message(vehicle)
    sent = send_message(msg)
    if sent:
        try:
            from database import log_alert, mark_notified
            log_alert("new_vehicle", msg)
            mark_notified(vehicle["id"])
        except Exception:
            pass
    return sent


def send_daily_digest(vehicles_today: list):
    """
    Send morning summary of everything at the yards today.
    Groups by yard and location.
    """
    if not vehicles_today:
        msg = (
            f"☀️ <b>Daily Digest — {datetime.now().strftime('%B %d, %Y')}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"No new vehicles found at either yard today."
        )
    else:
        targets   = [v for v in vehicles_today if v.get("is_target")]
        non_targets = [v for v in vehicles_today if not v.get("is_target")]

        lines = [
            f"☀️ <b>Daily Digest — {datetime.now().strftime('%B %d, %Y')}</b>",
            f"━━━━━━━━━━━━━━━━━━━━━━━━",
            f"📊 {len(vehicles_today)} new vehicles found today",
            f"🎯 {len(targets)} match your target list",
            ""
        ]

        if targets:
            lines.append("🔴 <b>TARGET MATCHES:</b>")
            for v in targets:
                row = f" — Row {v['row']}" if v.get("row") else ""
                yard_emoji = YARD_EMOJI.get(v["yard"], "🏭")
                lines.append(
                    f"  {yard_emoji} {v['yard']} ({v['location']}){row}\n"
                    f"     🚗 {v['year']} {v['make']} {v['model']}"
                )
            lines.append("")

        if non_targets:
            lines.append("🆕 <b>OTHER NEW ARRIVALS:</b>")
            for v in non_targets[:10]:  # cap at 10 to avoid giant message
                yard_emoji = YARD_EMOJI.get(v["yard"], "🏭")
                lines.append(f"  {yard_emoji} {v['yard']} ({v['location']}) — {v['year']} {v['make']} {v['model']}")
            if len(non_targets) > 10:
                lines.append(f"  ... and {len(non_targets) - 10} more")

        msg = "\n".join(lines)

    sent = send_message(msg)
    if sent:
        try:
            from database import log_alert
            log_alert("daily_digest", msg)
        except Exception:
            pass
    return sent


def send_weekly_trend_report(trend_data: list):
    """
    Send weekly eBay price trend summary.
    Shows top parts by average sold price.
    """
    if not trend_data:
        msg = (
            f"📈 <b>Weekly Price Trends</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"No pricing data available yet.\n"
            f"Run the bot for a few days to build up data."
        )
    else:
        # Group by make/model and find top earners
        summary = {}
        for row in trend_data:
            key = f"{row['year']} {row['make']} {row['model']}"
            if key not in summary:
                summary[key] = []
            if row["avg_price"]:
                summary[key].append((row["part"], row["avg_price"], row["sold_count"]))

        lines = [
            f"📈 <b>Weekly Price Trends — {datetime.now().strftime('%B %d, %Y')}</b>",
            f"━━━━━━━━━━━━━━━━━━━━━━━━",
            ""
        ]

        for vehicle, parts in sorted(summary.items()):
            if not parts:
                continue
            lines.append(f"🚗 <b>{vehicle}</b>")
            for part, avg, count in sorted(parts, key=lambda x: x[1], reverse=True):
                lines.append(f"  • {part.title()}: avg ${avg:.2f} ({count} sold)")
            lines.append("")

        msg = "\n".join(lines)

    sent = send_message(msg)
    if sent:
        try:
            from database import log_alert
            log_alert("weekly_trends", msg)
        except Exception:
            pass
    return sent


if __name__ == "__main__":
    # Test your Telegram connection
    print("[Telegram] Sending test message...")
    result = send_message(
        "🤖 <b>Junkyard Bot Online</b>\n"
        "Your car parts tracker is running!\n"
        "You'll get alerts here when target vehicles arrive at the yards."
    )
    print(f"[Telegram] {'Sent successfully!' if result else 'Failed - check your token and chat ID'}")

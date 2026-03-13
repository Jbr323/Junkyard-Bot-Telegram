"""
main.py - Main orchestrator for the Junkyard Bot
Runs the full pipeline: scrape → compare → alert

Schedule: Runs daily at 5pm via cron (see setup instructions in README)
"""

import json
import os
import sys
import logging
from datetime import datetime, time

# ─── Logging Setup ────────────────────────────────────────────────────────────
log_dir = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(log_dir, f"bot_{datetime.now().strftime('%Y%m%d')}.log")),
        logging.StreamHandler(sys.stdout)
    ]
)
log = logging.getLogger(__name__)


def load_targets():
    path = os.path.join(os.path.dirname(__file__), "targets.json")
    with open(path) as f:
        return json.load(f)


def is_target(vehicle: dict, targets: list):
    """Check if a vehicle matches any target. Returns (bool, target dict or None)."""
    v_make  = vehicle["make"].strip().lower()
    v_model = vehicle["model"].strip().lower()
    v_year  = int(vehicle["year"])

    for t in targets:
        if (t["make"].lower() == v_make and
            t["model"].lower() == v_model and
            v_year in t["years"]):
            return True, t
    return False, None


def run_pipeline():
    """Full pipeline: scrape both yards, check DB, send alerts."""
    log.info("=" * 50)
    log.info(f"Junkyard Bot starting — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    log.info("=" * 50)

    # Init DB
    from database import init_db, upsert_vehicle, mark_as_target, get_new_unnotified_targets, get_all_new_unnotified
    init_db()

    targets = load_targets()
    log.info(f"Loaded {len(targets)} target vehicles")

    # ── Scrape Jalopy Jungle ──────────────────────────────────────────────────
    log.info("Scraping Jalopy Jungle...")
    try:
        from scrapers.jalopy import scrape_all as jalopy_scrape
        jalopy_results = jalopy_scrape(targets)
        log.info(f"Jalopy Jungle: {len(jalopy_results)} vehicles found")
    except Exception as e:
        log.error(f"Jalopy Jungle scrape failed: {e}")
        jalopy_results = []

    # ── Scrape Trusty ─────────────────────────────────────────────────────────
    log.info("Scraping Trusty Auto Parts...")
    try:
        from scrapers.trusty import scrape_all as trusty_scrape
        trusty_results = trusty_scrape(targets)
        log.info(f"Trusty: {len(trusty_results)} vehicles found")
    except Exception as e:
        log.error(f"Trusty scrape failed: {e}")
        trusty_results = []

    all_vehicles = jalopy_results + trusty_results
    log.info(f"Total vehicles found: {len(all_vehicles)}")

    # ── Process into DB ───────────────────────────────────────────────────────
    new_count = 0
    new_vehicles = []

    for v in all_vehicles:
        is_new, vid = upsert_vehicle(
            yard=v["yard"],
            location=v["location"],
            year=v["year"],
            make=v["make"],
            model=v["model"],
            row=v.get("row", "")
        )
        v["id"] = vid

        if is_new:
            new_count += 1
            matched, target = is_target(v, targets)
            v["is_target"] = matched
            v["target"]    = target
            if matched:
                mark_as_target(vid)
            new_vehicles.append(v)
            log.info(f"NEW: {v['year']} {v['make']} {v['model']} @ {v['yard']} ({v['location']}) {'← TARGET' if matched else ''}")

    log.info(f"New vehicles this run: {new_count}")

    # ── Send Alerts ───────────────────────────────────────────────────────────
    from telegram_bot import (
        send_new_arrival_alert,
        send_any_vehicle_alert,
        send_daily_digest
    )
    from ebay_prices import build_price_block

    # Alert: new target vehicles
    target_vehicles = [v for v in new_vehicles if v.get("is_target")]
    for v in target_vehicles:
        target = v["target"]
        log.info(f"Sending TARGET alert for {v['year']} {v['make']} {v['model']}")
        price_block = build_price_block(v["make"], v["model"], int(v["year"]), target["parts_to_pull"])
        send_new_arrival_alert(v, target, price_block)

    # Alert: any new vehicle (non-targets)
    non_target_vehicles = [v for v in new_vehicles if not v.get("is_target")]
    for v in non_target_vehicles:
        log.info(f"Sending new vehicle alert for {v['year']} {v['make']} {v['model']}")
        send_any_vehicle_alert(v)

    # Daily digest (always send at 5pm run)
    log.info("Sending daily digest...")
    from database import get_daily_summary
    daily = get_daily_summary()
    send_daily_digest(daily)

    log.info("Pipeline complete.")
    return {"new_vehicles": new_count, "targets_found": len(target_vehicles)}


def run_weekly_report():
    """Send the weekly price trend report — call this on Sundays."""
    log.info("Generating weekly price trend report...")
    from database import get_weekly_price_trends
    from telegram_bot import send_weekly_trend_report
    data = get_weekly_price_trends()
    send_weekly_trend_report(data)
    log.info("Weekly report sent.")


if __name__ == "__main__":
    if "--weekly" in sys.argv:
        run_weekly_report()
    else:
        result = run_pipeline()
        log.info(f"Result: {result}")

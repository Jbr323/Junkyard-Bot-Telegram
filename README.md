# Junkyard-Bot-Telegram
Automatically monitors Jalopy Jungle and Trusty Pick-A-Part daily, cross-references with eBay sold prices, and sends Telegram alerts for vehicles worth pulling parts from.

---

## What It Does

- Scrapes both yards every day at 5 pm
- Compares inventory against your target vehicle list
- Looks up eBay average prices for parts worth pulling
- Sends Telegram alerts with yard, location, row number, and eBay prices
- Sends a daily digest summary every evening
- Sends a weekly price trend report every Sunday at 9 am
- Runs an interactive Telegram bot 24/7 for on-demand searches

---

## Project Structure

```
junkyard_bot/
├── main.py                 ← Daily pipeline runner
├── bot_interactive.py      ← Interactive Telegram bot
├── database.py             ← SQLite inventory tracker
├── ebay_prices.py          ← eBay price fetcher
├── telegram_bot.py         ← Alert message sender
├── targets.json            ← Your vehicle watchlist (edit this)
├── yards.json              ← Yard locations config
├── scrapers/
│   ├── jalopy.py           ← Jalopy Jungle scraper
│   └── trusty.py           ← Trusty Pick-A-Part scraper
├── data/
│   └── inventory.db        ← SQLite database (auto-created)
└── logs/                   ← Daily log files (auto-created)
```

---

## Setup

### 1. Install dependencies

```bash
cd ~/junkyard_bot
pip3 install playwright requests python-telegram-bot schedule pandas streamlit
python3 -m playwright install chromium
```

### 2. Create your Telegram Bot

1. Open Telegram and search **@BotFather**
2. Send `/newbot` and follow the prompts
3. Copy the **Bot Token** it gives you
4. Search **@userinfobot** and send any message to get your **Chat ID**
5. Search for your new bot and tap **Start**

### 3. Get your eBay API Keys

1. Go to https://developer.ebay.com and sign in with your eBay account
2. Go to **My Keys** and copy your **App ID** and **Cert ID**
3. If your keyset is disabled, click the exemption link and select **"I do not persist eBay data"**

### 4. Add credentials to crontab

```bash
crontab -e
```

Add these three lines, replacing the placeholder values with your actual credentials and username:

```
0 17 * * * TELEGRAM_BOT_TOKEN="your_token" TELEGRAM_CHAT_ID="your_chat_id" EBAY_APP_ID="your_app_id" EBAY_CERT_ID="your_cert_id" /usr/bin/python3 /Users/YOUR_NAME/junkyard_bot/main.py >> /Users/YOUR_NAME/junkyard_bot/logs/cron.log 2>&1

0 9 * * 0 TELEGRAM_BOT_TOKEN="your_token" TELEGRAM_CHAT_ID="your_chat_id" EBAY_APP_ID="your_app_id" EBAY_CERT_ID="your_cert_id" /usr/bin/python3 /Users/YOUR_NAME/junkyard_bot/main.py --weekly >> /Users/YOUR_NAME/junkyard_bot/logs/cron.log 2>&1

@reboot sleep 30 && TELEGRAM_BOT_TOKEN="your_token" TELEGRAM_CHAT_ID="your_chat_id" EBAY_APP_ID="your_app_id" EBAY_CERT_ID="your_cert_id" /usr/bin/python3 /Users/YOUR_NAME/junkyard_bot/bot_interactive.py >> /Users/YOUR_NAME/junkyard_bot/logs/bot_interactive.log 2>&1 &
```

Press `Escape`, type `:wq`, hit Enter.

### 5. Keep Mac mini awake

1. Open **System Settings → Battery**
2. Set **Prevent automatic sleeping** to On

### 6. Test it manually

```bash
cd ~/junkyard_bot
python3 main.py
```

---

## Editing Your Target List

Open `targets.json` and add or remove vehicles. Each entry looks like this:

```json
{
  "make": "Mitsubishi",
  "model": "Lancer",
  "years": [2008, 2009, 2010, 2011, 2012, 2013, 2014, 2015, 2016],
  "parts_to_pull": ["driver mirror", "passenger mirror", "tail light", "head light", "BCM module"],
  "priority": "high"
}
```

To add a new vehicle, copy an existing block, change the values, and make sure there is a comma between each block.

**Important:** Never edit targets.json in TextEdit as it converts quotes to smart quotes, which breaks the file. Instead, use the Terminal command:

```bash
cd ~/junkyard_bot
python3 -c "
import json
targets = [
  {'make': 'Mitsubishi', 'model': 'Lancer', 'years': [2008,2009,2010,2011,2012,2013,2014,2015,2016], 'parts_to_pull': ['driver mirror','passenger mirror','tail light','head light','BCM module'], 'priority': 'high'},
  {'make': 'Mitsubishi', 'model': 'Eclipse', 'years': [1995,1996,1997,1998,1999], 'parts_to_pull': ['driver mirror','passenger mirror','tail light','head light','BCM module'], 'priority': 'high'}
]
with open('targets.json', 'w') as f:
    json.dump(targets, f, indent=2)
print('Done')
"
```

---

## Telegram Commands

Send these to your bot anytime:

| Command | Description | Example |
|--------|-------------|---------|
| `/search [make] [model] [year]` | Search both yards right now | `/search Mitsubishi Lancer 2010` |
| `/price [make] [model] [part]` | Look up eBay average price | `/price Mitsubishi Lancer tail light` |
| `/targets` | Show your current watchlist | `/targets` |
| `/status` | Show bot stats and last run | `/status` |
| `/help` | Show all commands | `/help` |

---

## Alert Examples

**Target vehicle found:**
```
🔴 TARGET FOUND — HIGH PRIORITY
━━━━━━━━━━━━━━━━━━━━━━━━
🏚️ Jalopy Jungle — Boise
📍 Row 14
🚗 2010 Mitsubishi Lancer

💰 Parts Worth Pulling:
  ✅ Driver Mirror
     Avg: $45.00 | Min: $20.00 | Max: $85.00 | 24 listings
  ✅ Tail Light
     Avg: $38.00 | Min: $15.00 | Max: $70.00 | 18 listings

⏰ Just arrived — go soon!
```

**Daily digest:**
```
☀️ Daily Digest — March 8, 2026
━━━━━━━━━━━━━━━━━━━━━━━━
📊 8 new vehicles found today
🎯 2 match your target list
...
```

---

## Troubleshooting

**Bot not sending messages after reboot**
- Check `logs/bot_interactive.log` for errors
- Make sure credentials are correct in crontab
- Run `pgrep -a python3` to see if it's running

**Scraper timing out**
- Yard websites can be slow — this is normal
- Check `logs/` for details on which yard timed out
- The bot will skip timed-out searches and continue

**eBay prices showing no data**
- Run `echo $EBAY_APP_ID` — if blank, credentials aren't set
- Make sure your eBay keyset is not disabled at developer.ebay.com/my/keys

**targets.json error**
- Never edit with TextEdit — use the Terminal python3 command above
- Run `python3 -c "import json; json.load(open('targets.json'))"` to validate the file

**Reset the database**
```bash
cd ~/junkyard_bot
rm data/inventory.db
python3 main.py
```

---

## Managing the Bot

| Task | Command |
|------|---------|
| Start interactive bot | `cd ~/junkyard_bot && nohup python3 bot_interactive.py > logs/bot_interactive.log 2>&1 &` |
| Stop interactive bot | `pkill -f bot_interactive.py` |
| Check if running | `pgrep -a python3` |
| View live logs | `tail -f ~/junkyard_bot/logs/bot_interactive.log` |
| Run pipeline now | `cd ~/junkyard_bot && python3 main.py` |
| Send weekly report now | `cd ~/junkyard_bot && python3 main.py --weekly` |
| Reset database | `rm ~/junkyard_bot/data/inventory.db` |

#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════╗
║   Bot Akatsuki no Yona — Buyee                      ║
║   Surveille : セル画 暁のヨナ                         ║
╚══════════════════════════════════════════════════════╝

Installation :
    pip3 install requests beautifulsoup4 schedule

Utilisation :
    python3 yona_bot.py
"""

import requests
import schedule
import time
import json
import os
import re
from datetime import datetime
from urllib.parse import quote
from bs4 import BeautifulSoup

# ──────────────────────────────────────────────
#  CONFIG
# ──────────────────────────────────────────────
CONFIG = {
    "keywords": [
        "セル画 暁のヨナ",
    ],
    "max_price_yen": 0,
    "min_price_yen": 500,
    "check_interval_minutes": 5,
    "seen_file": os.path.expanduser("~/Desktop/yona_seen_ids.json"),
    "log_file":  os.path.expanduser("~/Desktop/yona_bot.log"),
    "discord_webhook": "https://discord.com/api/webhooks/1504840131239215105/ltRYoFVrRSR3CHRXXeLjDy0Ers2eIbyUxlwgt8qcIMnTuq0OmxsBLUq4n2deuUlMxhNC",
}
# ──────────────────────────────────────────────

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ja,fr;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


# ── Utilitaires ────────────────────────────────

def log(msg: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    with open(CONFIG["log_file"], "a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_seen() -> set:
    if os.path.exists(CONFIG["seen_file"]):
        with open(CONFIG["seen_file"], "r") as f:
            return set(json.load(f))
    return set()


def save_seen(seen: set):
    with open(CONFIG["seen_file"], "w") as f:
        json.dump(list(seen), f)


def notify_discord(item: dict):
    url = CONFIG.get("discord_webhook", "")
    if not url:
        return
    embed = {
        "embeds": [{
            "title": item["title"][:256],
            "url": item["buyee_url"],
            "color": 0xFF6B9D,
            "fields": [
                {"name": "💴 Prix", "value": f"¥{item['price']:,}", "inline": True},
                {"name": "⏰ Fin", "value": item.get("end_time", "?"), "inline": True},
            ],
            "thumbnail": {"url": item.get("image", "")},
            "footer": {"text": "🌸 Akatsuki no Yona Bot"},
        }]
    }
    try:
        r = requests.post(url, json=embed, timeout=10)
        if r.status_code not in (200, 204):
            log(f"Discord erreur {r.status_code} : {r.text[:100]}")
    except Exception as e:
        log(f"Discord webhook erreur : {e}")


# ── Scraping Buyee ─────────────────────────────

def search_buyee(keyword: str) -> list:
    encoded = quote(keyword)
    url = f"https://buyee.jp/item/search/query/{encoded}?translationType=1"

    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
    except requests.RequestException as e:
        log(f"Erreur réseau Buyee pour '{keyword}': {e}")
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    items = []

    for card in soup.select(".itemCard, .g-item-list-item, [class*='itemCard']"):
        try:
            # Lien et ID
            link = card.select_one("a[href*='/item/yahoo/auction/']")
            if not link:
                continue
            href = link.get("href", "")
            m = re.search(r"/item/yahoo/auction/([^/?#]+)", href)
            if not m:
                continue
            item_id = m.group(1)

            # Titre
            title_tag = card.select_one(".itemCard__itemName, .g-item-name, [class*='itemName']")
            title = title_tag.get_text(strip=True) if title_tag else href

            # Prix
            price_tag = card.select_one(".itemCard__price, .g-price, [class*='price']")
            price_str = price_tag.get_text(strip=True) if price_tag else "0"
            price = int(re.sub(r"[^\d]", "", price_str) or 0)

            # Filtrer par prix
            if price < CONFIG["min_price_yen"]:
                continue
            if CONFIG["max_price_yen"] > 0 and price > CONFIG["max_price_yen"]:
                continue

            # Image
            img = card.select_one("img")
            image = img.get("src", "") if img else ""

            # Date fin
            end_tag = card.select_one("[class*='time'], [class*='end'], [class*='deadline']")
            end_time = end_tag.get_text(strip=True) if end_tag else "?"

            buyee_url = f"https://buyee.jp/item/yahoo/auction/{item_id}"

            items.append({
                "id":        item_id,
                "title":     title,
                "price":     price,
                "image":     image,
                "end_time":  end_time,
                "buyee_url": buyee_url,
            })
        except Exception as e:
            log(f"Erreur parsing card : {e}")
            continue

    return items


# ── Boucle principale ──────────────────────────

def check_new_items():
    log("🔍 Vérification en cours…")
    seen = load_seen()
    new_count = 0

    for keyword in CONFIG["keywords"]:
        items = search_buyee(keyword)
        log(f"  [{keyword}] → {len(items)} résultat(s)")

        for item in items:
            if item["id"] in seen:
                continue

            new_count += 1
            log(
                f"  🆕 NOUVEAU : {item['title']}\n"
                f"      Prix    : ¥{item['price']:,}\n"
                f"      Fin     : {item['end_time']}\n"
                f"      Buyee   : {item['buyee_url']}"
            )
            notify_discord(item)
            seen.add(item["id"])

    save_seen(seen)

    if new_count == 0:
        log("  Aucun nouvel article.")
    else:
        log(f"  ✨ {new_count} nouvel(s) article(s) !")


def main():
    log("=" * 54)
    log("  Bot Akatsuki no Yona démarré 🌸")
    log(f"  Intervalle : {CONFIG['check_interval_minutes']} min")
    log("=" * 54)

    check_new_items()

    schedule.every(CONFIG["check_interval_minutes"]).minutes.do(check_new_items)

    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    main()

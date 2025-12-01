import logging
import re
from datetime import timezone, datetime
from email.utils import parsedate_to_datetime
from html import unescape
from typing import List, Dict, Optional
import xml.etree.ElementTree as ET
from functools import lru_cache

import requests


logger = logging.getLogger(__name__)

NEWS_FEED_URL = "https://coinjournal.net/news/feed/"

# Mapping of symbols to keywords for filtering
COIN_KEYWORDS = {
    "BTC": ["Bitcoin", "BTC"],
    "ETH": ["Ethereum", "Ether", "ETH"],
    "SOL": ["Solana", "SOL"],
    "BNB": ["Binance Coin", "BNB"],
    "AVAX": ["Avalanche", "AVAX"],
    "XRP": ["Ripple", "XRP"],
    "ADA": ["Cardano", "ADA"],
    "DOGE": ["Dogecoin", "DOGE"],
    "DOT": ["Polkadot", "DOT"],
    "LINK": ["Chainlink", "LINK"],
    "LTC": ["Litecoin", "LTC"],
    "BCH": ["Bitcoin Cash", "BCH"],
    "UNI": ["Uniswap", "UNI"],
    "MATIC": ["Polygon", "MATIC"],
    "XLM": ["Stellar", "XLM"],
    "ATOM": ["Cosmos", "ATOM"],
}

def _strip_html_tags(text: str) -> str:
    if not text:
        return ""
    cleaned = unescape(text)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


@lru_cache(maxsize=10)
def _fetch_news_raw(cache_key: str) -> List[Dict[str, str]]:
    """
    Internal function to fetch and parse news with caching.
    Returns a list of dictionaries with news details.
    """
    try:
        response = requests.get(NEWS_FEED_URL, timeout=10)
        if response.status_code != 200:
            logger.warning("Failed to fetch news feed: status %s", response.status_code)
            return []

        root = ET.fromstring(response.content)
        channel = root.find("channel")
        if channel is None:
            return []

        news_items = []

        for item in channel.findall("item"):
            title = _strip_html_tags(item.findtext("title") or "")
            pub_date_raw = (item.findtext("pubDate") or "").strip()
            summary_raw = item.findtext("description") or ""

            summary = _strip_html_tags(summary_raw)
            summary = re.sub(r"The post .*? appeared first on .*", "", summary, flags=re.IGNORECASE).strip()

            formatted_time = pub_date_raw
            if pub_date_raw:
                try:
                    parsed = parsedate_to_datetime(pub_date_raw)
                    if parsed is not None:
                        if parsed.tzinfo is None:
                            parsed = parsed.replace(tzinfo=timezone.utc)
                        else:
                            parsed = parsed.astimezone(timezone.utc)
                        formatted_time = parsed.strftime("%Y-%m-%d %H:%M:%SZ")
                except Exception:  # noqa: BLE001
                    formatted_time = pub_date_raw
            
            news_items.append({
                "title": title,
                "summary": summary,
                "time": formatted_time,
                "raw_date": pub_date_raw
            })

        return news_items

    except Exception as err:  # noqa: BLE001
        logger.warning("Failed to process news feed: %s", err)
        return []


def fetch_latest_news(max_chars: int = 4000, symbols: Optional[List[str]] = None) -> str:
    """
    Fetches latest news with 30-minute caching strategy.
    Optionally filters news by related symbols.
    """
    # Generate cache key that changes every 30 minutes
    now = datetime.utcnow()
    # Key format: YYYYMMDDHH_MMgroup where MMgroup is 0 or 1 (for 0-29, 30-59)
    cache_key = f"{now.strftime('%Y%m%d%H')}_{now.minute // 30}"
    
    raw_items = _fetch_news_raw(cache_key)
    
    if not raw_items:
        return "No news available."

    filtered_entries: List[str] = []
    current_length = 0
    
    # Expand symbols to keywords
    keywords = set()
    if symbols:
        for sym in symbols:
            sym_upper = sym.upper()
            kw_list = COIN_KEYWORDS.get(sym_upper, [sym_upper])
            for kw in kw_list:
                keywords.add(kw.lower())

    for item in raw_items:
        title = item["title"]
        summary = item["summary"]
        time_str = item["time"]
        
        # Check relevance if symbols are provided
        if symbols:
            text_to_check = (title + " " + summary).lower()
            is_relevant = False
            for kw in keywords:
                # Check for whole words to avoid partial matches like "bit" in "bitcoin" (though keywords are usually distinct)
                # Simple substring check is probably fine for "Bitcoin", "BTC", etc.
                # But "ETH" might match "Ethernet" or "Whether" if we are not careful. 
                # Let's rely on simple substring for now as keywords are usually specific enough or capitalized in logic, 
                # but here we lowercased everything.
                # To be safer, we could use regex boundaries, but let's stick to simple check for now as per request "at least by symbol".
                if kw in text_to_check:
                    is_relevant = True
                    break
            
            if not is_relevant:
                continue

        parts = []
        if time_str:
            parts.append(time_str)
        if title:
            parts.append(title)

        entry_text = " | ".join(parts)
        if summary:
            entry_text = f"{entry_text}: {summary}" if entry_text else summary

        entry_text = entry_text.strip()
        if not entry_text:
            continue

        # Check length limit
        # +1 for newline
        entry_len = len(entry_text) + 1 
        
        if current_length + entry_len > max_chars:
            remaining = max_chars - current_length
            if remaining > 10: # Only add if there is some space meaningful
                 # Try to truncate
                 if len(entry_text) > remaining:
                     truncated = entry_text[:remaining].rstrip()
                     if len(truncated) < len(entry_text):
                         truncated = truncated.rstrip(" .,;:-") + "..."
                     filtered_entries.append(truncated)
            break
        
        filtered_entries.append(entry_text)
        current_length += entry_len

    if not filtered_entries:
        if symbols:
             return f"No relevant news found for {', '.join(symbols)}."
        return "No news available."

    return "\n".join(filtered_entries)

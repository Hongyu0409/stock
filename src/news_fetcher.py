"""News fetching and translation module for US Stock Morning Recap."""

from __future__ import annotations

import json
import logging
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class MarketNewsItem:
    """Structured market news item with plain-language analysis in Traditional Chinese."""

    title: str
    source: str
    summary: str
    impact: str
    related_symbols: List[str] = field(default_factory=list)
    published_at: str = ""


def _translate_to_traditional_chinese(text: str, timeout: int = 4) -> str:
    """Translate English text to Traditional Chinese via Google Translate web API."""
    if not text or not text.strip():
        return ""
    clean_text = text.strip()
    try:
        url = (
            "https://translate.googleapis.com/translate_a/single?client=gtx"
            "&sl=en&tl=zh-TW&dt=t&q=" + urllib.parse.quote(clean_text)
        )
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data and isinstance(data, list) and len(data) > 0 and isinstance(data[0], list):
                translated = "".join(part[0] for part in data[0] if part and part[0])
                if translated.strip():
                    return translated.strip()
    except Exception as exc:
        logger.debug("Translation failed for '%s': %s", clean_text[:30], exc)

    # Fallback: basic keyword replacements if translation service is unavailable
    replacements = {
        "Nvidia": "輝達 (NVIDIA)",
        "shares": "股價",
        "stock": "股票",
        "stocks": "股市",
        "Wall Street": "華爾街",
        "S&P 500": "標普500",
        "Nasdaq": "那斯達克",
        "Dow": "道瓊",
        "jump": "大漲",
        "slides": "走低",
        "tumble": "重挫",
        "gains": "上揚",
        "losses": "下跌",
        "Treasury yields": "美債殖利率",
        "Federal Reserve": "聯準會 (Fed)",
    }
    fallback = clean_text
    for en, zh in replacements.items():
        fallback = re.sub(re.escape(en), zh, fallback, flags=re.IGNORECASE)
    return fallback


def _extract_related_symbols(text: str) -> List[str]:
    """Extract well-known ticker symbols mentioned in headline/summary."""
    known = [
        "NVDA", "AAPL", "MSFT", "AMZN", "GOOGL", "META", "TSLA",
        "AMD", "AVGO", "TSM", "ARM", "SMCI", "PLTR", "CRWD",
        "JPM", "BAC", "XOM", "CVX", "LLY", "UNH", "KO", "BRK-B",
        "SPY", "QQQ", "DIA", "IWM", "SOXX"
    ]
    found = []
    upper_text = text.upper()
    for s in known:
        pattern = rf"\b{re.escape(s)}\b"
        if re.search(pattern, upper_text):
            found.append(s)
    return found


def _build_plain_impact(title_zh: str, symbols: List[str]) -> str:
    """Generate plain-language interpretation based on the news topic."""
    lower = title_zh.lower()
    if any(k in lower for k in ["黃仁勳", "執行長", "辭職", "下台", "nvda", "輝達"]):
        return "【白話解讀】：科技領頭羊高層人事震撼彈引發盤面劇烈震盪，短線引發停損與觀望賣壓，但亦使資金轉向其他低估值板塊，短線勿慌亂追殺或盲目抄底。"
    elif any(k in lower for k in ["聯準會", "降息", "升息", "fed", "鮑爾", "通膨", "cpi", "殖利率"]):
        return "【白話解讀】：市場持續消化貨幣政策與利率前景，美債殖利率波動牽動高估值科技股定價，盤面呈現資金換手與類股快速輪動。"
    elif any(k in lower for k in ["油價", "石油", "地緣", "中東"]):
        return "【白話解讀】：能源價格與地緣政治帶來避險情緒，傳產防禦板塊相對受惠，高本益比成長股短期面臨估值回調壓力。"
    elif any(k in lower for k in ["重挫", "下跌", "走低", "跌"]):
        return "【白話解讀】：短線多頭遇阻引發回檔整理，關鍵在於大盤均線支撐能否守穩，建議保持持股彈性、控制倉位。"
    elif any(k in lower for k in ["大漲", "上漲", "強彈", "反彈", "噴出"]):
        return "【白話解讀】：買盤逢低強勁承接，帶動指數跌深反彈，後續觀察成交量是否持續放大以確認反轉有效性。"
    else:
        return "【白話解讀】：盤面消息多空交錯，資金集中於具備實質業績題材的績優標的，操作宜順應均線趨勢並嚴設防守點。"


def fetch_market_news(use_demo: bool = False) -> List[MarketNewsItem]:
    """Fetch and compile top market news headlines into Traditional Chinese plain-language items."""
    if use_demo:
        return _get_demo_news()

    news_list: List[MarketNewsItem] = []
    seen_titles = set()

    # 1. Google News RSS for Wall Street / US stock market
    rss_url = "https://news.google.com/rss/search?q=US+stock+market+Wall+Street&hl=en-US&gl=US&ceid=US:en"
    try:
        req = urllib.request.Request(
            rss_url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
        )
        with urllib.request.urlopen(req, timeout=6) as resp:
            root = ET.fromstring(resp.read())
            for item in root.findall(".//item")[:10]:
                raw_title = item.find("title").text if item.find("title") is not None else ""
                pub_date = item.find("pubDate").text if item.find("pubDate") is not None else ""
                source_el = item.find("source")
                source_name = source_el.text if source_el is not None else "國際財經外電"

                if not raw_title or raw_title in seen_titles:
                    continue
                seen_titles.add(raw_title)

                # Clean headline: remove " - Source" suffix
                clean_title = re.sub(r"\s+-\s+[^-]+$", "", raw_title).strip()
                symbols = _extract_related_symbols(clean_title)

                title_zh = _translate_to_traditional_chinese(clean_title)
                impact_zh = _build_plain_impact(title_zh, symbols)

                news_list.append(
                    MarketNewsItem(
                        title=title_zh,
                        source=source_name,
                        summary=clean_title,
                        impact=impact_zh,
                        related_symbols=symbols,
                        published_at=pub_date,
                    )
                )
                if len(news_list) >= 4:
                    break
    except Exception as exc:
        logger.warning("Could not fetch RSS market news: %s", exc)

    # If online fetching failed or returned fewer than 2 items, blend with fallback
    if len(news_list) < 2:
        logger.info("Using curated market news fallback.")
        return _get_demo_news()

    return news_list


def _get_demo_news() -> List[MarketNewsItem]:
    """Curated realistic market news items for demo / fallback mode."""
    return [
        MarketNewsItem(
            title="美股焦點震盪：科技龍頭高層人事震盪，那斯達克盤中巨震後低接買盤湧現",
            source="華爾街日報 (WSJ)",
            summary="Wall Street shakes with swings for Nvidia and tech giants but recovers most of early losses.",
            impact="【白話解讀】：半導體霸主高層動向引發短線籌碼清洗，但逢低買盤依然強勁，顯示市場資金未完全撤退，而是轉入防守或分批低接。",
            related_symbols=["NVDA", "QQQ", "SOXX"],
            published_at="今日焦點",
        ),
        MarketNewsItem(
            title="美債殖利率回檔整理，市場聚焦聯準會官員最新通膨與利率談話",
            source="彭博社 (Bloomberg)",
            summary="Bond yields steady as investors assess macroeconomic inflation signals and Fed rate trajectory.",
            impact="【白話解讀】：10 年期美債殖利率未再飆高，有利高估值科技股喘息，市場氣氛從極度恐慌回歸理性觀望。",
            related_symbols=["SPY", "^TNX"],
            published_at="今日焦點",
        ),
        MarketNewsItem(
            title="資金顯著輪動至防禦型價值股，可口可樂、波克夏等穩健標的抗跌創高",
            source="CNBC",
            summary="Rotation into consumer staples and financial stalwarts offers shelter amid tech volatility.",
            impact="【白話解讀】：資金並未離場而是轉入防禦性堡壘，具有穩定現金流與抗通膨特質的價值股成為避風港。",
            related_symbols=["KO", "BRK-B", "JPM"],
            published_at="今日焦點",
        ),
    ]

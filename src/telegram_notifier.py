"""Telegram Bot Formatter and Push Notifier for US Stock Daily Analysis."""

from __future__ import annotations

import html
import logging
import os
from typing import Any, Dict, List, Optional

import requests

from src.analyzer import TradingPick, WeeklyAnalysisReport

logger = logging.getLogger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org"


def _fmt_pct(val: float, is_vix: bool = False) -> str:
    """Format percentage with intuitive color emojis (Green = Up, Red = Down for US stocks)."""
    if val > 0:
        circle = "🟢" if not is_vix else "🔴"
        return f"{circle} ▲+{val:.2f}%"
    elif val < 0:
        circle = "🔴" if not is_vix else "🟢"
        return f"{circle} ▼{val:.2f}%"
    else:
        return "⚪ ─ 0.00%"


def format_telegram_messages(report: WeeklyAnalysisReport, report_type: str = "all") -> List[str]:
    """Format the report into clean, pure-text HTML messages with color emojis for Telegram."""
    # --- Message 1: 🌅 美股昨日收盤晨報 (07:00 推播：前晚美股表現總覽) ---
    m1_lines: List[str] = [
        "🌅 <b>【美股昨日收盤晨報】</b>",
        f"📅 資料日期：{html.escape(report.report_date)}",
        f"🧭 市場溫度：<b>{html.escape(report.market_regime)}</b>",
        f"💡 {html.escape(report.regime_summary)}",
        "━━━━━━━━━━━━━━",
        "📊 <b>【主要指數昨夜與一週表現】</b>",
    ]

    for idx in report.indices:
        c_name = idx.name.split(" ")[0]
        m1_lines.append(
            f"• <b>{html.escape(c_name)} ({idx.symbol})</b>：${idx.close:,.2f}\n"
            f"   昨夜 {_fmt_pct(idx.ret_1d_pct)} ｜ 近一週 {_fmt_pct(idx.ret_5d_pct)}"
        )

    if report.macros:
        m1_lines.append("━━━━━━━━━━━━━━")
        m1_lines.append("🌡️ <b>【市場風險與其他資產】</b>")
        for m in report.macros:
            c_name = m.name.split(" ")[0]
            is_vix = "vix" in m.symbol.lower()
            m1_lines.append(
                f"• {html.escape(c_name)}：{m.close:,.2f}（一週 {_fmt_pct(m.ret_5d_pct, is_vix=is_vix)}）"
            )

    if report.sector_rankings:
        m1_lines.append("━━━━━━━━━━━━━━")
        m1_lines.append("🔄 <b>【11大產業板塊資金輪動】</b>")
        top3 = report.sector_rankings[:3]
        bot3 = report.sector_rankings[-3:]
        t_str = "、".join([f"{s.name.split(' ')[0]}({_fmt_pct(s.ret_5d_pct)})" for s in top3])
        b_str = "、".join([f"{s.name.split(' ')[0]}({_fmt_pct(s.ret_5d_pct)})" for s in bot3])
        m1_lines.append(f"🔥 資金流入（前三強）：{html.escape(t_str)}")
        m1_lines.append(f"❄️ 資金流出（前三弱）：{html.escape(b_str)}")

    if report.volatility_alerts:
        m1_lines.append("━━━━━━━━━━━━━━")
        m1_lines.append("⚡ <b>【昨夜與近一週波動劇烈個股】</b>")
        for a in report.volatility_alerts[:4]:
            m1_lines.append(
                f"• <b>{a.symbol}</b>（${a.close:.2f}）一週 {_fmt_pct(a.ret_5d_pct)}\n"
                f"   高低點震盪幅度：{a.week_range_pct:.1f}%"
            )

    m1_lines.append("━━━━━━━━━━━━━━")
    m1_lines.append("📌 <i>今晚 21:00 將參考最新盤前與盤後動態，為您推播美股精選推薦標的！</i>")

    # --- Message 2: 🎯 美股盤前雷達與精選推薦標的 (21:00 推播：盤前選股) ---
    short_date = report.report_date.split("（")[0]
    m2_lines: List[str] = [
        f"🎯 <b>【美股盤前雷達與精選推薦標的】</b>",
        f"📅 資料日期：{html.escape(short_date)} 21:00（美股開盤前預備）",
        f"🧭 盤前氛圍：<b>{html.escape(report.market_regime)}</b>",
        "💡 系統依早晨盤後及最新盤前動能，精選關鍵支撐/突破標的（風報比 1:2）：",
    ]

    def _append_picks_section(title: str, picks: List[TradingPick], is_short: bool = False) -> None:
        m2_lines.append("━━━━━━━━━━━━━━")
        m2_lines.append(title)
        if not picks:
            m2_lines.append("• 今日無符合條件之標的")
            return
        for idx_num, p in enumerate(picks, start=1):
            tag_str = "、".join(p.tags) if p.tags else "動能良好"
            if is_short:
                sl_label = "若反彈突破此價需注意壓力/停損"
                tp_label = "可能回檔目標價"
            else:
                sl_label = "建議防守停損價"
                tp_label = "分批獲利目標價"

            desc_line = f"   🏢 <b>業務簡介</b>：<i>{html.escape(p.company_desc)}</i>\n" if p.company_desc else ""

            m2_lines.append(
                f"<b>{idx_num}. 【{p.symbol}】</b>（{html.escape(p.sector_name.split(' ')[0])}）評分 <b>{p.score}分</b>\n"
                f"{desc_line}"
                f"   現價：${p.close:.2f}（昨夜 {_fmt_pct(p.ret_1d_pct)} ｜ 一週 {_fmt_pct(p.ret_5d_pct)}）\n"
                f"   📌 重點特徵：{html.escape(tag_str)}\n"
                f"   🎯 參考進場區間：<code>{html.escape(p.entry_zone)}</code>\n"
                f"   🛡️ {sl_label}：<code>${p.stop_loss:.2f} ({p.stop_loss_pct:+.1f}%)</code>\n"
                f"   💰 {tp_label}：<code>目標一 ${p.take_profit_t1:.2f} ({p.take_profit_t1_pct:+.1f}%) ｜ 目標二 ${p.take_profit_t2:.2f} ({p.take_profit_t2_pct:+.1f}%)</code>"
            )

    _append_picks_section("🚀 <b>【強勢突破股（買盤轉強創高）】</b>", report.breakout_picks, is_short=False)
    _append_picks_section("🔄 <b>【優質回檔股（多頭拉回找支撐）】</b>", report.pullback_picks, is_short=False)
    _append_picks_section("⚠️ <b>【弱勢警戒股（跌破重要均線避險）】</b>", report.breakdown_picks, is_short=True)

    m2_lines.append("━━━━━━━━━━━━━━")
    m2_lines.append("📌 <i>溫馨提醒：本清單由演算法自動統計，僅供開盤前觀察與風險控管參考，不代表投資建議。</i>")

    msg1 = "\n".join(m1_lines)
    msg2 = "\n".join(m2_lines)

    if report_type == "morning":
        return [msg1]
    elif report_type == "evening":
        return [msg2]
    return [msg1, msg2]


def discover_telegram_chat_ids(bot_token: str) -> List[str]:
    """Auto-discover all user/group chat_ids that have interacted with the bot via getUpdates."""
    chat_ids: List[str] = []
    try:
        url = f"{TELEGRAM_API_BASE}/bot{bot_token}/getUpdates"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            for update in data.get("result", []):
                cid = None
                if "message" in update and "chat" in update["message"]:
                    cid = str(update["message"]["chat"]["id"])
                elif "channel_post" in update and "chat" in update["channel_post"]:
                    cid = str(update["channel_post"]["chat"]["id"])
                elif "my_chat_member" in update and "chat" in update["my_chat_member"]:
                    cid = str(update["my_chat_member"]["chat"]["id"])
                if cid and cid not in chat_ids:
                    chat_ids.append(cid)
    except Exception as exc:
        logger.warning("Could not auto-fetch Telegram updates: %s", exc)
    return chat_ids


def get_telegram_chat_id(bot_token: str) -> Optional[str]:
    """Backward compatibility: return the first discovered chat ID."""
    discovered = discover_telegram_chat_ids(bot_token)
    return discovered[0] if discovered else None


def get_target_chat_ids(bot_token: str, configured_chat_ids: Optional[str] = None) -> List[str]:
    """Collect and deduplicate all target Telegram chat IDs (from env and/or getUpdates)."""
    targets: List[str] = []

    # 1. Parse configured IDs (comma or whitespace separated)
    raw_cfg = configured_chat_ids if configured_chat_ids is not None else os.getenv("TELEGRAM_CHAT_ID", "")
    for part in raw_cfg.replace(",", " ").split():
        cleaned = part.strip()
        if cleaned and cleaned not in targets:
            targets.append(cleaned)

    # 2. Query getUpdates to discover any additional subscribers who clicked /start
    discovered = discover_telegram_chat_ids(bot_token)
    for cid in discovered:
        if cid not in targets:
            targets.append(cid)

    return targets


def send_telegram_notification(
    report: WeeklyAnalysisReport,
    bot_token: Optional[str] = None,
    chat_id: Optional[str] = None,
    report_type: str = "all",
) -> bool:
    """Send formatted market analysis report to Telegram via Bot API to all subscribers."""
    token = (bot_token or os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    if not token:
        logger.info("TELEGRAM_BOT_TOKEN not configured. Skipping Telegram push.")
        return True

    target_chats = get_target_chat_ids(bot_token=token, configured_chat_ids=chat_id)
    if not target_chats:
        logger.warning(
            "No Telegram Chat IDs found. Please open your bot in Telegram and click 'Start' or configure TELEGRAM_CHAT_ID."
        )
        return False

    logger.info("Preparing to push Telegram report (%s) to %d subscriber(s): %s", report_type, len(target_chats), target_chats)

    messages = format_telegram_messages(report, report_type=report_type)
    send_url = f"{TELEGRAM_API_BASE}/bot{token}/sendMessage"

    overall_success = True
    for cid in target_chats:
        for i, msg in enumerate(messages, start=1):
            try:
                payload = {
                    "chat_id": cid,
                    "text": msg,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                }
                resp = requests.post(send_url, json=payload, timeout=15)
                if resp.status_code == 200:
                    logger.info("Successfully pushed Telegram report message #%d to chat %s", i, cid)
                else:
                    logger.error(
                        "Failed to send Telegram message #%d to %s: HTTP %d %s",
                        i, cid, resp.status_code, resp.text
                    )
                    overall_success = False
            except Exception as exc:
                logger.error("Exception while sending Telegram message #%d to %s: %s", i, cid, exc)
                overall_success = False

    return overall_success

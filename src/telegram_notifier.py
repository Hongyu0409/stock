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


def _fmt_pct(val: float) -> str:
    arrow = "▲" if val > 0 else ("▼" if val < 0 else "─")
    return f"{arrow}{val:+.2f}%"


def format_telegram_messages(report: WeeklyAnalysisReport) -> List[str]:
    """Format the report into 2 clean, structured HTML messages for Telegram."""
    # --- Message 1: 🌅 美股每日早報 (大盤體溫、指數、板塊與異常波動) ---
    m1_lines: List[str] = [
        "🌅 <b>【美股每日早報】</b>",
        f"📅 資料日期：{html.escape(report.report_date)}",
        f"🧭 市場溫度：<b>{html.escape(report.market_regime)}</b>",
        f"💡 {html.escape(report.regime_summary)}",
        "━━━━━━━━━━━━━━",
        "📊 <b>【主要指數近一週走勢】</b>",
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
            m1_lines.append(
                f"• {html.escape(c_name)}：{m.close:,.2f}（一週 {_fmt_pct(m.ret_5d_pct)}）"
            )

    if report.sector_rankings:
        m1_lines.append("━━━━━━━━━━━━━━")
        m1_lines.append("🔄 <b>【本週最夯與最弱產業】</b>")
        top3 = report.sector_rankings[:3]
        bot3 = report.sector_rankings[-3:]
        t_str = "、".join([f"{s.name.split(' ')[0]}({_fmt_pct(s.ret_5d_pct)})" for s in top3])
        b_str = "、".join([f"{s.name.split(' ')[0]}({_fmt_pct(s.ret_5d_pct)})" for s in bot3])
        m1_lines.append(f"🔥 資金流入（最強）：{html.escape(t_str)}")
        m1_lines.append(f"❄️ 資金流出（最弱）：{html.escape(b_str)}")

    if report.volatility_alerts:
        m1_lines.append("━━━━━━━━━━━━━━")
        m1_lines.append("⚡ <b>【本週波動劇烈個股（震盪大）】</b>")
        for a in report.volatility_alerts[:4]:
            m1_lines.append(
                f"• <b>{a.symbol}</b>（${a.close:.2f}）一週漲跌 {a.ret_5d_pct:+.1f}%\n"
                f"   高低點震盪幅度：{a.week_range_pct:.1f}%"
            )

    # --- Message 2: 🎯 今日精選觀察個股 ---
    m2_lines: List[str] = [
        f"🎯 <b>【今日精選觀察個股】</b>{html.escape(report.report_date)}",
        "💡 系統依趨勢強弱自動計算參考價位（風報比 1:2）",
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
                f"   現價：${p.close:.2f}（昨夜 {p.ret_1d_pct:+.1f}% / 一週 {p.ret_5d_pct:+.1f}%）\n"
                f"   📌 重點特徵：{html.escape(tag_str)}\n"
                f"   🎯 參考進場區間：<code>{html.escape(p.entry_zone)}</code>\n"
                f"   🛡️ {sl_label}：<code>${p.stop_loss:.2f} ({p.stop_loss_pct:+.1f}%)</code>\n"
                f"   💰 {tp_label}：<code>目標一 ${p.take_profit_t1:.2f} ({p.take_profit_t1_pct:+.1f}%) ｜ 目標二 ${p.take_profit_t2:.2f} ({p.take_profit_t2_pct:+.1f}%)</code>"
            )

    _append_picks_section("🚀 <b>【強勢突破股（買盤轉強創高）】</b>", report.breakout_picks, is_short=False)
    _append_picks_section("🔄 <b>【優質回檔股（多頭拉回找支撐）】</b>", report.pullback_picks, is_short=False)
    _append_picks_section("⚠️ <b>【弱勢警戒股（跌破重要均線）】</b>", report.breakdown_picks, is_short=True)

    m2_lines.append("━━━━━━━━━━━━━━")
    m2_lines.append("📌 溫馨提醒：本清單由演算法自動統計，僅供日常觀察與風險控管參考，不代表投資建議。")

    msg1 = "\n".join(m1_lines)
    msg2 = "\n".join(m2_lines)
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

    logger.info("Preparing to push Telegram report to %d subscriber(s): %s", len(target_chats), target_chats)

    messages = format_telegram_messages(report)
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

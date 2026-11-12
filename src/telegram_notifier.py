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
    # --- Message 1: 🌅 美股昨日收盤晨報 (07:00 推播 Part 1：盤勢歸納 + 重大新聞 + 自動化技術分析師) ---
    m1_lines: List[str] = [
        "🌅 <b>【美股昨日收盤晨報・盤勢歸納與重大新聞】</b>",
        f"📅 資料日期：{html.escape(report.report_date)}",
        f"🧭 市場格局：<b>{html.escape(report.market_regime)}</b>",
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
        m1_lines.append("🌡️ <b>【市場風險與關鍵資產】</b>")
        for m in report.macros:
            c_name = m.name.split(" ")[0]
            is_vix = "vix" in m.symbol.lower()
            m1_lines.append(
                f"• {html.escape(c_name)}：{m.close:,.2f}（一週 {_fmt_pct(m.ret_5d_pct, is_vix=is_vix)}）"
            )

    if report.colloquial_market_summary:
        m1_lines.append("━━━━━━━━━━━━━━")
        m1_lines.append("🤖 <b>【昨夜大盤深度歸納（白話解讀）】</b>")
        m1_lines.append(html.escape(report.colloquial_market_summary))

    m1_lines.append("━━━━━━━━━━━━━━")
    m1_lines.append("🤖 <b>【自動化技術分析師・大盤趨勢與位階診斷】</b>")
    m1_lines.append(f"• <b>均線與趨勢</b>：{html.escape(report.market_tech.trend_summary)}")
    m1_lines.append("• <b>關鍵支撐與壓力</b>：")
    m1_lines.append(f"   - SPY 支撐：<code>${report.market_tech.spy_support:,.2f}</code> ｜ 壓力：<code>${report.market_tech.spy_resistance:,.2f}</code>")
    m1_lines.append(f"   - QQQ 支撐：<code>${report.market_tech.qqq_support:,.2f}</code> ｜ 壓力：<code>${report.market_tech.qqq_resistance:,.2f}</code>")
    m1_lines.append(f"• <b>動能與情緒</b>：{html.escape(report.market_tech.momentum_summary)}")
    m1_lines.append(f"👉 <b>大盤操作決策</b>：<b>{html.escape(report.market_tech.market_decision)}</b>")
    for idx_step, step_text in enumerate(report.market_tech.decision_steps, start=1):
        m1_lines.append(f"   {idx_step}. {html.escape(step_text)}")

    if report.news_digest:
        m1_lines.append("━━━━━━━━━━━━━━")
        m1_lines.append("📰 <b>【當日重大財經焦點新聞】</b>")
        for n_idx, news in enumerate(report.news_digest[:3], start=1):
            m1_lines.append(
                f"{n_idx}. <b>[{html.escape(news.source)}] {html.escape(news.title)}</b>\n"
                f"   💡 <i>{html.escape(news.impact)}</i>"
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

    # --- Message 2 (Morning Part 2): 🎯 【今天值得密切注意的焦點標的・實戰看盤筆記】 ---
    m_noteworthy_lines: List[str] = []
    if report.noteworthy_tickers:
        short_date_morning = report.report_date.split("（")[0]
        m_noteworthy_lines.extend([
            "🎯 <b>【今天值得密切注意的焦點標的・實戰看盤筆記】</b>",
            f"📅 適用交易日：{html.escape(short_date_morning)}（白話實戰解析・越詳細越好）",
            "💡 精選全市場最具代表性之話題焦點、多頭突破、拉回有守與破位警戒標的：",
        ])
        for idx_nt, t in enumerate(report.noteworthy_tickers, start=1):
            m_noteworthy_lines.append("━━━━━━━━━━━━━━")
            m_noteworthy_lines.append(
                f"<b>{idx_nt}. 【{t.symbol}】{html.escape(t.name)}</b>（{html.escape(t.sector_name.split(' ')[0])}）｜ 決策：<b>{html.escape(t.decision_badge)}</b>\n"
                f"   類別：<b>{html.escape(t.focus_type)}</b>\n"
                f"   現價：<b>${t.close:.2f}</b>（昨夜 {_fmt_pct(t.ret_1d_pct)} ｜ 一週 {_fmt_pct(t.ret_5d_pct)} ｜ 成交量 {t.vol_ratio_1d:.1f}x）\n"
                f"   📌 <b>為什麼今天一定要盯它？（白話核心解析）</b>：\n"
                f"   <i>{html.escape(t.why_noteworthy)}</i>\n"
                f"   📈 <b>技術位階白話診斷</b>：\n"
                f"   {html.escape(t.tech_status_plain)}\n"
                f"   🎯 <b>關鍵位階</b>：支撐 <code>${t.key_support:.2f}</code> ｜ 壓力 <code>${t.key_resistance:.2f}</code>\n"
                f"   💡 <b>今日實戰看盤指南</b>：\n"
                f"   {html.escape(t.today_action_plan)}"
            )
        m_noteworthy_lines.append("━━━━━━━━━━━━━━")
        m_noteworthy_lines.append("📌 <i>今晚 21:00 將依據最新盤前與盤後數據，為您推播完整美股精選推薦標的（含交易點子產生器與量化回測）！</i>")

    # --- Message 2: 🎯 美股盤前雷達與精選推薦標的 (21:00 推播：盤前選股) ---
    short_date = report.report_date.split("（")[0]
    m2_header: List[str] = [
        f"🎯 <b>【美股盤前雷達與精選推薦標的】</b>",
        f"📅 資料日期：{html.escape(short_date)} 21:00（美股開盤前預備）",
        f"🧭 盤前整體氛圍：<b>{html.escape(report.market_regime)}</b>",
        "💡 整合「交易點子產生器」、「自動化技術分析師」與「策略量化回測模型」嚴選推薦標的：",
    ]

    def _format_picks_block(strat_key: str, title: str, picks: List[TradingPick], is_short: bool = False) -> List[str]:
        sec_lines: List[str] = ["━━━━━━━━━━━━━━", title]
        meta = report.backtest_meta.get(strat_key)
        if meta:
            sec_lines.append(
                f"📊 <b>量化回測優勢</b>：勝率 <code>{meta.win_rate}</code> ｜ 獲利因子 <code>{meta.profit_factor}</code> ｜ 最大回撤 <code>{meta.max_drawdown}</code>\n"
                f"💡 <b>策略執行心法</b>：<i>{html.escape(meta.execution_edge)}</i>"
            )
        if not picks:
            sec_lines.append("• 今日無符合條件之標的")
            return sec_lines

        for idx_num, p in enumerate(picks, start=1):
            tag_str = "、".join(p.tags) if p.tags else "動能良好"
            if is_short:
                sl_label = "反彈壓力/停損"
                tp_label = "可能回檔目標"
            else:
                sl_label = "建議防守停損"
                tp_label = "分批獲利目標"

            fund_line = f"   🏢 <b>基本面催化</b>：<i>{html.escape(p.company_desc)}，{html.escape(p.fund_catalyst)}</i>\n" if p.company_desc else ""

            sec_lines.append(
                f"<b>{idx_num}. 【{p.symbol}】</b>（{html.escape(p.sector_name.split(' ')[0])}）評分 <b>{p.score}分</b> ｜ 決策：<b>{html.escape(p.action_decision)}</b>\n"
                f"{fund_line}"
                f"   現價：${p.close:.2f}（昨夜 {_fmt_pct(p.ret_1d_pct)} ｜ 一週 {_fmt_pct(p.ret_5d_pct)}）\n"
                f"   📈 <b>技術型態</b>：{html.escape(p.tech_reason)}\n"
                f"   🎯 <b>關鍵位階</b>：支撐 <code>${p.key_support:.2f}</code> ｜ 壓力 <code>${p.key_resistance:.2f}</code>\n"
                f"   🎯 <b>參考進場區間</b>：<code>{html.escape(p.entry_zone)}</code>\n"
                f"   🛡️ <b>{sl_label}</b>：<code>${p.stop_loss:.2f} ({p.stop_loss_pct:+.1f}%)</code>\n"
                f"   💰 <b>{tp_label}</b>：<code>目標一 ${p.take_profit_t1:.2f} ({p.take_profit_t1_pct:+.1f}%) ｜ 目標二 ${p.take_profit_t2:.2f} ({p.take_profit_t2_pct:+.1f}%)</code>\n"
                f"   ⚖️ <b>風險報酬比</b>：<code>{html.escape(p.risk_reward)}</code> ｜ 特徵：{html.escape(tag_str)}"
            )
        return sec_lines

    b1 = _format_picks_block("breakout", "🚀 <b>【帶量順勢突破股（買盤轉強創高）】</b>", report.breakout_picks, is_short=False)
    b2 = _format_picks_block("pullback", "🔄 <b>【優質回檔找買點股（多頭拉回測支撐）】</b>", report.pullback_picks, is_short=False)
    b3 = _format_picks_block("breakdown", "⚠️ <b>【弱勢跌破避險股（跌破重要均線防守）】</b>", report.breakdown_picks, is_short=True)

    m2_footer: List[str] = [
        "━━━━━━━━━━━━━━",
        "📌 <i>溫馨提醒：本清單由演算法與量化模型自動生成，嚴格執行進場、停損與風報比紀律，不代表個別投資推薦。</i>",
    ]

    all_m2_lines = m2_header + b1 + b2 + b3 + m2_footer
    full_m2_text = "\n".join(all_m2_lines)

    # If evening report exceeds Telegram single message safe limit (~3500 chars), split into 3 readable parts
    evening_messages: List[str] = []
    if len(full_m2_text) > 3500:
        evening_messages.extend([
            "\n".join(m2_header + b1),
            "\n".join(b2),
            "\n".join(b3 + m2_footer),
        ])
    else:
        evening_messages.append(full_m2_text)

    morning_messages = ["\n".join(m1_lines)]
    if m_noteworthy_lines:
        morning_messages.append("\n".join(m_noteworthy_lines))

    if report_type == "morning":
        return morning_messages
    elif report_type == "evening":
        return evening_messages
    return morning_messages + evening_messages


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

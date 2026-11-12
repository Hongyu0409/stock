"""LINE Messaging API Formatter (Flex Carousel + Text) and Markdown Report Generator."""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

import requests

from src.analyzer import TradingPick, WeeklyAnalysisReport

logger = logging.getLogger(__name__)

LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"
LINE_BROADCAST_URL = "https://api.line.me/v2/bot/message/broadcast"
LINE_OAUTH_TOKEN_URL = "https://api.line.me/v2/oauth/accessToken"
LINE_BOT_INFO_URL = "https://api.line.me/v2/bot/info"


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


def format_line_text_messages(report: WeeklyAnalysisReport, report_type: str = "all") -> List[str]:
    """Format the report into mobile-friendly, easy-to-read LINE text messages with color emojis."""
    # Message 1: 🌅 美股昨日收盤晨報 (07:00 推播 Part 1：盤勢歸納 + 當日重大新聞 + 自動化技術分析師)
    lines_1: List[str] = [
        "🌅 【美股昨日收盤晨報・盤勢歸納與重大新聞】",
        f"📅 資料日期：{report.report_date}",
        f"🧭 市場格局：{report.market_regime}",
        f"💡 {report.regime_summary}",
        "━━━━━━━━━━━━━━",
        "📊 【主要指數昨夜與一週表現】",
    ]

    for idx in report.indices:
        c_name = idx.name.split(" ")[0]
        lines_1.append(
            f"• {c_name} ({idx.symbol})：${idx.close:,.2f}\n"
            f"  昨夜 {_fmt_pct(idx.ret_1d_pct)} ｜ 近一週 {_fmt_pct(idx.ret_5d_pct)}"
        )

    if report.macros:
        lines_1.append("━━━━━━━━━━━━━━")
        lines_1.append("🌡️ 【市場風險與關鍵資產】")
        for m in report.macros:
            c_name = m.name.split(" ")[0]
            is_vix = "vix" in m.symbol.lower()
            lines_1.append(
                f"• {c_name}：{m.close:,.2f}（一週 {_fmt_pct(m.ret_5d_pct, is_vix=is_vix)}）"
            )

    if report.colloquial_market_summary:
        lines_1.append("━━━━━━━━━━━━━━")
        lines_1.append("🤖 【昨夜大盤深度歸納（白話解讀）】")
        lines_1.append(report.colloquial_market_summary)

    lines_1.append("━━━━━━━━━━━━━━")
    lines_1.append("🤖 【自動化技術分析師・大盤趨勢與位階診斷】")
    lines_1.append(f"• 均線與趨勢：{report.market_tech.trend_summary}")
    lines_1.append("• 關鍵支撐與壓力：")
    lines_1.append(f"   - SPY 支撐：${report.market_tech.spy_support:,.2f} ｜ 壓力：${report.market_tech.spy_resistance:,.2f}")
    lines_1.append(f"   - QQQ 支撐：${report.market_tech.qqq_support:,.2f} ｜ 壓力：${report.market_tech.qqq_resistance:,.2f}")
    lines_1.append(f"• 動能與情緒：{report.market_tech.momentum_summary}")
    lines_1.append(f"👉 大盤操作決策：{report.market_tech.market_decision}")
    for idx_step, step_text in enumerate(report.market_tech.decision_steps, start=1):
        lines_1.append(f"   {idx_step}. {step_text}")

    if report.news_digest:
        lines_1.append("━━━━━━━━━━━━━━")
        lines_1.append("📰 【當日重大財經焦點新聞】")
        for n_idx, news in enumerate(report.news_digest[:3], start=1):
            lines_1.append(
                f"{n_idx}. [{news.source}] {news.title}\n"
                f"   💡 {news.impact}"
            )

    if report.sector_rankings:
        lines_1.append("━━━━━━━━━━━━━━")
        lines_1.append("🔄 【11大產業板塊資金輪動】")
        top3 = report.sector_rankings[:3]
        bot3 = report.sector_rankings[-3:]
        t_str = "、".join([f"{s.name.split(' ')[0]}({_fmt_pct(s.ret_5d_pct)})" for s in top3])
        b_str = "、".join([f"{s.name.split(' ')[0]}({_fmt_pct(s.ret_5d_pct)})" for s in bot3])
        lines_1.append(f"🔥 資金流入（前三強）：{t_str}")
        lines_1.append(f"❄️ 資金流出（前三弱）：{b_str}")

    # --- Message 2 (Morning Part 2): 🎯 【今天值得密切注意的焦點標的・實戰看盤筆記】 ---
    lines_noteworthy: List[str] = []
    if report.noteworthy_tickers:
        short_date_morning = report.report_date.split("（")[0]
        lines_noteworthy.extend([
            "🎯 【今天值得密切注意的焦點標的・實戰看盤筆記】",
            f"📅 適用交易日：{short_date_morning}（白話實戰解析・越詳細越好）",
            "💡 精選全市場最具代表性之話題焦點、多頭突破、拉回有守與破位警戒標的：",
        ])
        for idx_nt, t in enumerate(report.noteworthy_tickers, start=1):
            lines_noteworthy.append("━━━━━━━━━━━━━━")
            lines_noteworthy.append(
                f"{idx_nt}. 【{t.symbol}】{t.name}（{t.sector_name.split(' ')[0]}）｜ 決策：{t.decision_badge}\n"
                f"   類別：{t.focus_type}\n"
                f"   現價：${t.close:.2f}（昨夜 {_fmt_pct(t.ret_1d_pct)} ｜ 一週 {_fmt_pct(t.ret_5d_pct)} ｜ 成交量 {t.vol_ratio_1d:.1f}x）\n"
                f"   📌 為什麼今天一定要盯它？（白話核心解析）：\n"
                f"   {t.why_noteworthy}\n"
                f"   📈 技術位階白話診斷：\n"
                f"   {t.tech_status_plain}\n"
                f"   🎯 關鍵位階：支撐 ${t.key_support:.2f} ｜ 壓力 ${t.key_resistance:.2f}\n"
                f"   💡 今日實戰看盤指南：\n"
                f"   {t.today_action_plan}"
            )
        lines_noteworthy.append("━━━━━━━━━━━━━━")
        lines_noteworthy.append("📌 今晚 21:00 將依據最新盤前與盤後數據，為您推播完整美股精選推薦標的（含交易點子產生器與量化回測）！")

    # Message 2: 🎯 美股盤前雷達與精選推薦標的 (21:00 推播：盤前選股)
    short_date = report.report_date.split("（")[0]
    lines_2_head: List[str] = [
        f"🎯 【美股盤前雷達與精選推薦標的】",
        f"📅 資料日期：{short_date} 21:00（美股開盤前預備）",
        f"🧭 盤前整體氛圍：{report.market_regime}",
        "💡 整合「交易點子產生器」、「自動化技術分析師」與「策略量化回測模型」嚴選推薦標的：",
    ]

    def _append_picks_block(strat_key: str, title: str, picks: List[TradingPick], is_short: bool = False) -> List[str]:
        sec_lines: List[str] = ["━━━━━━━━━━━━━━", title]
        meta = report.backtest_meta.get(strat_key)
        if meta:
            sec_lines.append(
                f"📊 量化回測優勢：勝率 {meta.win_rate} ｜ 獲利因子 {meta.profit_factor} ｜ 最大回撤 {meta.max_drawdown}\n"
                f"💡 策略執行心法：{meta.execution_edge}"
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

            fund_line = f"   🏢 基本面催化：{p.company_desc}，{p.fund_catalyst}\n" if p.company_desc else ""

            sec_lines.append(
                f"{idx_num}. 【{p.symbol}】（{p.sector_name.split(' ')[0]}）評分 {p.score}分 ｜ 決策：{p.action_decision}\n"
                f"{fund_line}"
                f"   現價：${p.close:.2f}（昨夜 {_fmt_pct(p.ret_1d_pct)} ｜ 一週 {_fmt_pct(p.ret_5d_pct)}）\n"
                f"   📈 技術型態：{p.tech_reason}\n"
                f"   🎯 關鍵位階：支撐 ${p.key_support:.2f} ｜ 壓力 ${p.key_resistance:.2f}\n"
                f"   🎯 參考進場區間：{p.entry_zone}\n"
                f"   🛡️ {sl_label}：${p.stop_loss:.2f} ({p.stop_loss_pct:+.1f}%)\n"
                f"   💰 {tp_label}：目標一 ${p.take_profit_t1:.2f} ({p.take_profit_t1_pct:+.1f}%) ｜ 目標二 ${p.take_profit_t2:.2f} ({p.take_profit_t2_pct:+.1f}%)\n"
                f"   ⚖️ 風險報酬比：{p.risk_reward} ｜ 特徵：{tag_str}"
            )
        return sec_lines

    lb1 = _append_picks_block("breakout", "🚀 【帶量順勢突破股（買盤轉強創高）】", report.breakout_picks, is_short=False)
    lb2 = _append_picks_block("pullback", "🔄 【優質回檔找買點股（多頭拉回測支撐）】", report.pullback_picks, is_short=False)
    lb3 = _append_picks_block("breakdown", "⚠️ 【弱勢跌破避險股（跌破重要均線防守）】", report.breakdown_picks, is_short=True)

    lines_2_foot: List[str] = [
        "━━━━━━━━━━━━━━",
        "📌 溫馨提醒：本清單由演算法與量化模型自動生成，嚴格執行進場、停損與風報比紀律，不代表個別投資推薦。",
    ]

    all_lines_2 = lines_2_head + lb1 + lb2 + lb3 + lines_2_foot
    full_msg_2 = "\n".join(all_lines_2)

    evening_msgs: List[str] = []
    if len(full_msg_2) > 4200:
        part1 = "\n".join(lines_2_head + lb1 + lb2)
        part2 = "\n".join(lb3 + lines_2_foot)
        evening_msgs.extend([part1[:4900], part2[:4900]])
    else:
        evening_msgs.append(full_msg_2[:4900])

    morning_msgs: List[str] = ["\n".join(lines_1)[:4900]]
    if lines_noteworthy:
        morning_msgs.append("\n".join(lines_noteworthy)[:4900])

    if report_type == "morning":
        return morning_msgs
    elif report_type == "evening":
        return evening_msgs
    return morning_msgs + evening_msgs


def _build_pick_bubble(
    title: str,
    subtitle: str,
    header_bg: str,
    picks: List[TradingPick],
    is_short: bool = False,
) -> Dict[str, Any]:
    """Build a single LINE Flex Bubble for a strategy category."""
    body_contents: List[Dict[str, Any]] = []

    if not picks:
        body_contents.append(
            {
                "type": "text",
                "text": "今日無符合條件之標的",
                "size": "sm",
                "color": "#888888",
                "wrap": True,
            }
        )
    else:
        for i, p in enumerate(picks):
            if i > 0:
                body_contents.append({"type": "separator", "margin": "md"})
            ret_color = "#16a34a" if p.ret_5d_pct >= 0 else "#dc2626"
            badge_color = "#dc2626" if is_short else "#2563eb"
            sl_label = "防守價" if is_short else "停損價"
            tp_label = "目標價" if is_short else "獲利目標"

            card_box: Dict[str, Any] = {
                "type": "box",
                "layout": "vertical",
                "margin": "md",
                "spacing": "xs",
                "contents": [
                    {
                        "type": "box",
                        "layout": "horizontal",
                        "contents": [
                            {
                                "type": "text",
                                "text": f"{p.symbol} (${p.close:.2f})",
                                "weight": "bold",
                                "size": "md",
                                "color": "#111827",
                                "flex": 4,
                            },
                            {
                                "type": "text",
                                "text": f"{p.action_decision or f'評分 {p.score}分'}",
                                "weight": "bold",
                                "size": "xs",
                                "color": badge_color,
                                "align": "end",
                                "flex": 3,
                            },
                        ],
                    },
                    {
                        "type": "text",
                        "text": f"昨夜 {p.ret_1d_pct:+.1f}% ｜ 一週 {p.ret_5d_pct:+.1f}% ｜ 風報比 {p.risk_reward}",
                        "size": "xs",
                        "color": ret_color,
                    },
                    *(
                        [
                            {
                                "type": "text",
                                "text": f"🏢 {p.company_desc}",
                                "size": "xxs",
                                "color": "#4b5563",
                                "wrap": True,
                            }
                        ]
                        if p.company_desc
                        else []
                    ),
                    {
                        "type": "text",
                        "text": f"📈 技術：{p.tech_reason}",
                        "size": "xxs",
                        "color": "#374151",
                        "wrap": True,
                    },
                    {
                        "type": "text",
                        "text": f"🎯 關鍵：支撐 ${p.key_support:.2f} ｜ 壓力 ${p.key_resistance:.2f}",
                        "size": "xs",
                        "color": "#1f2937",
                    },
                    {
                        "type": "text",
                        "text": f"🎯 建議區間：{p.entry_zone}",
                        "size": "xs",
                        "color": "#1f2937",
                    },
                    {
                        "type": "text",
                        "text": f"🛡️ {sl_label}：${p.stop_loss:.2f} ({p.stop_loss_pct:+.1f}%)",
                        "size": "xs",
                        "color": "#b91c1c",
                    },
                    {
                        "type": "text",
                        "text": f"💰 {tp_label}：${p.take_profit_t1:.2f} / ${p.take_profit_t2:.2f}",
                        "size": "xs",
                        "color": "#15803d",
                    },
                ],
            }
            body_contents.append(card_box)

    return {
        "type": "bubble",
        "size": "mega",
        "header": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": header_bg,
            "paddingAll": "14px",
            "contents": [
                {
                    "type": "text",
                    "text": title,
                    "weight": "bold",
                    "size": "md",
                    "color": "#ffffff",
                },
                {
                    "type": "text",
                    "text": subtitle,
                    "size": "xs",
                    "color": "#e5e7eb",
                    "margin": "xs",
                },
            ],
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "paddingAll": "14px",
            "contents": body_contents,
        },
    }


def build_line_flex_carousel(report: WeeklyAnalysisReport, report_type: str = "all") -> Dict[str, Any]:
    """Build a 4-bubble LINE Flex Message Carousel for the daily morning report."""
    # Bubble 1: Market & Sector Volatility Overview
    idx_rows: List[Dict[str, Any]] = []
    for idx in report.indices:
        color = "#16a34a" if idx.ret_5d_pct >= 0 else "#dc2626"
        idx_rows.append(
            {
                "type": "box",
                "layout": "horizontal",
                "margin": "xs",
                "contents": [
                    {"type": "text", "text": idx.symbol, "weight": "bold", "size": "xs", "flex": 2},
                    {"type": "text", "text": f"${idx.close:.1f}", "size": "xs", "color": "#4b5563", "flex": 2},
                    {
                        "type": "text",
                        "text": f"1D {idx.ret_1d_pct:+.1f}%",
                        "size": "xs",
                        "color": "#16a34a" if idx.ret_1d_pct >= 0 else "#dc2626",
                        "flex": 3,
                    },
                    {
                        "type": "text",
                        "text": f"5D {idx.ret_5d_pct:+.1f}%",
                        "size": "xs",
                        "weight": "bold",
                        "color": color,
                        "align": "end",
                        "flex": 3,
                    },
                ],
            }
        )

    top_sec = "、".join(f"{s.symbol}({s.ret_5d_pct:+.1f}%)" for s in report.sector_rankings[:3])
    bot_sec = "、".join(f"{s.symbol}({s.ret_5d_pct:+.1f}%)" for s in report.sector_rankings[-3:])

    short_date = report.report_date.split("（")[0]
    overview_bubble: Dict[str, Any] = {
        "type": "bubble",
        "size": "mega",
        "header": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": "#0f172a",
            "paddingAll": "14px",
            "contents": [
                {
                    "type": "text",
                    "text": f"📊 美股市場速報 ({short_date})",
                    "weight": "bold",
                    "size": "md",
                    "color": "#ffffff",
                },
                {
                    "type": "text",
                    "text": report.market_regime,
                    "size": "xs",
                    "color": "#38bdf8",
                    "margin": "xs",
                },
            ],
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "paddingAll": "14px",
            "spacing": "sm",
            "contents": [
                {
                    "type": "text",
                    "text": f"💡 決策：{report.market_tech.market_decision}",
                    "weight": "bold",
                    "size": "xs",
                    "color": "#2563eb",
                },
                {
                    "type": "text",
                    "text": report.market_tech.trend_summary,
                    "size": "xxs",
                    "color": "#4b5563",
                    "wrap": True,
                },
                {"type": "separator", "margin": "sm"},
                {
                    "type": "text",
                    "text": "【主要指數 昨夜 / 本週 漲跌】",
                    "weight": "bold",
                    "size": "xs",
                    "color": "#111827",
                },
                *idx_rows,
                {"type": "separator", "margin": "sm"},
                {
                    "type": "text",
                    "text": f"🔥 最強產業：{top_sec}",
                    "size": "xs",
                    "color": "#15803d",
                    "wrap": True,
                },
                {
                    "type": "text",
                    "text": f"❄️ 最弱產業：{bot_sec}",
                    "size": "xs",
                    "color": "#b91c1c",
                    "wrap": True,
                },
            ],
        },
    }

    meta_bo = report.backtest_meta.get("breakout")
    sub_bo = f"勝率 {meta_bo.win_rate} ｜ 獲利因子 {meta_bo.profit_factor}" if meta_bo else "買盤轉強、突破近期高點"
    b_breakout = _build_pick_bubble(
        title="🚀 帶量順勢突破股",
        subtitle=sub_bo,
        header_bg="#1d4ed8",
        picks=report.breakout_picks,
        is_short=False,
    )

    meta_pb = report.backtest_meta.get("pullback")
    sub_pb = f"勝率 {meta_pb.win_rate} ｜ 獲利因子 {meta_pb.profit_factor}" if meta_pb else "趨勢向上、回測月線找買點"
    b_pullback = _build_pick_bubble(
        title="🔄 強勢回檔找買點股",
        subtitle=sub_pb,
        header_bg="#047857",
        picks=report.pullback_picks,
        is_short=False,
    )

    meta_bd = report.backtest_meta.get("breakdown")
    sub_bd = f"勝率 {meta_bd.win_rate} ｜ 獲利因子 {meta_bd.profit_factor}" if meta_bd else "跌破重要均線、留意下殺風險"
    b_breakdown = _build_pick_bubble(
        title="⚠️ 弱勢跌破避險股",
        subtitle=sub_bd,
        header_bg="#b91c1c",
        picks=report.breakdown_picks,
        is_short=True,
    )

    if report_type == "morning":
        carousel_bubbles = [overview_bubble]
        alt_title = f"🌅 美股昨日收盤晨報 ({short_date})"
    elif report_type == "evening":
        carousel_bubbles = [b_breakout, b_pullback, b_breakdown]
        alt_title = f"🎯 美股盤前精選推薦標的 ({short_date})"
    else:
        carousel_bubbles = [overview_bubble, b_breakout, b_pullback, b_breakdown]
        alt_title = f"🌅 美股晨間與精選戰報 ({report.report_date})"

    return {
        "type": "flex",
        "altText": f"{alt_title} - {report.market_regime}",
        "contents": {
            "type": "carousel",
            "contents": carousel_bubbles,
        },
    }


def _issue_channel_access_token(channel_id: str, channel_secret: str) -> Optional[str]:
    """Issue a short-lived Channel Access Token (30-day) via LINE OAuth2 client_credentials."""
    try:
        resp = requests.post(
            LINE_OAUTH_TOKEN_URL,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "grant_type": "client_credentials",
                "client_id": channel_id,
                "client_secret": channel_secret,
            },
            timeout=15,
        )
        if resp.status_code == 200:
            token = resp.json().get("access_token", "").strip()
            if token:
                logger.info("Successfully issued LINE Channel Access Token via Channel ID & Secret.")
                return token
        logger.error("Failed to issue LINE token via OAuth (%d): %s", resp.status_code, resp.text)
    except Exception as exc:
        logger.error("Error requesting LINE OAuth token: %s", exc)
    return None


def send_line_notification(
    report: WeeklyAnalysisReport,
    channel_access_token: Optional[str] = None,
    user_id: Optional[str] = None,
    mode: str = "both",
    report_type: str = "all",
) -> bool:
    """Push or broadcast the report via LINE Messaging API."""
    token = (channel_access_token or os.getenv("LINE_CHANNEL_ACCESS_TOKEN") or "").strip()
    channel_id = (os.getenv("LINE_CHANNEL_ID") or "").strip()
    channel_secret = (os.getenv("LINE_CHANNEL_SECRET") or "").strip()
    target_ids_raw = (user_id or os.getenv("LINE_USER_ID") or "").strip()

    if not token and channel_id and channel_secret:
        token = _issue_channel_access_token(channel_id, channel_secret) or ""

    if not token:
        logger.warning(
            "LINE_CHANNEL_ACCESS_TOKEN (or LINE_CHANNEL_ID + LINE_CHANNEL_SECRET) is not set. "
            "Skipping live LINE API call (see generated report & preview)."
        )
        return False

    def _make_headers(access_token: str) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
        }

    # Verify token & log bot info (auto-refresh token if 401 and Channel ID/Secret available)
    try:
        info_resp = requests.get(LINE_BOT_INFO_URL, headers=_make_headers(token), timeout=10)
        if info_resp.status_code == 401 and channel_id and channel_secret:
            logger.info("Stored LINE_CHANNEL_ACCESS_TOKEN expired/unauthorized; refreshing via Channel ID & Secret...")
            refreshed = _issue_channel_access_token(channel_id, channel_secret)
            if refreshed:
                token = refreshed
                info_resp = requests.get(LINE_BOT_INFO_URL, headers=_make_headers(token), timeout=10)
        if info_resp.status_code == 200:
            bot_info = info_resp.json()
            logger.info(
                "Connected to LINE Official Account Bot: %s (basicId: %s)",
                bot_info.get("displayName", "Unknown"),
                bot_info.get("basicId", "N/A"),
            )
    except Exception as exc:
        logger.warning("Could not query LINE bot info: %s", exc)

    headers = _make_headers(token)

    messages_payload: List[Dict[str, Any]] = []
    if mode in ("flex", "both"):
        messages_payload.append(build_line_flex_carousel(report, report_type=report_type))
    if mode in ("text", "both"):
        for txt in format_line_text_messages(report, report_type=report_type):
            messages_payload.append({"type": "text", "text": txt})

    # LINE API allows up to 5 message objects per request
    messages_payload = messages_payload[:5]

    if target_ids_raw:
        target_ids = [uid.strip() for uid in target_ids_raw.split(",") if uid.strip()]
        all_ok = True
        for uid in target_ids:
            payload = {"to": uid, "messages": messages_payload}
            resp = requests.post(LINE_PUSH_URL, headers=headers, data=json.dumps(payload), timeout=20)
            if resp.status_code == 200:
                logger.info("Successfully pushed LINE report to target %s...!", uid[:6])
            else:
                logger.error("LINE Push API failed (%d): %s", resp.status_code, resp.text)
                all_ok = False
        return all_ok
    else:
        # Broadcast to all friends of the LINE Official Account Bot
        payload = {"messages": messages_payload}
        resp = requests.post(LINE_BROADCAST_URL, headers=headers, data=json.dumps(payload), timeout=20)
        if resp.status_code == 200:
            logger.info("Successfully broadcasted LINE report to all Bot followers!")
            return True
        logger.error("LINE Broadcast API failed (%d): %s", resp.status_code, resp.text)
        return False


def format_markdown_report(report: WeeklyAnalysisReport) -> str:
    """Generate a full Markdown report for GitHub Actions Summary or local archive."""
    md: List[str] = [
        f"# 🌅 美股近一週波動分析與每日推薦交易戰報 ({report.report_date})",
        f"> **產出時間**：{report.generated_at} ｜ **市場狀態**：**{report.market_regime}**",
        f"> **大盤決策**：**{report.market_tech.market_decision}** ｜ {report.regime_summary}",
        "",
        "---",
        "## 1. 🤖 昨夜大盤深度歸納（白話解讀）與重大新聞焦點",
        f"### 💡 大盤白話總評：\n{report.colloquial_market_summary}",
        "",
        "### 📰 當日重大財經焦點新聞：",
    ]
    for n_idx, news in enumerate(report.news_digest[:4], start=1):
        md.append(f"{n_idx}. **[{news.source}] {news.title}**\n   - *{news.impact}*")

    md.extend([
        "",
        "---",
        "## 2. 🎯 今日值得密切注意的焦點標的・實戰看盤筆記",
        "| 代號 | 標的名稱 | 板塊 | 決策 | 類別 | 最新現價 | 1D / 5D 漲跌 | 關鍵支撐/壓力 | 白話看盤指南 |",
        "| :--- | :--- | :--- | :---: | :---: | ---: | ---: | :--- | :--- |",
    ])
    for t in report.noteworthy_tickers:
        md.append(
            f"| **{t.symbol}** | {t.name} | {t.sector_name.split(' ')[0]} | **{t.decision_badge}** | {t.focus_type} | "
            f"${t.close:.2f} | {t.ret_1d_pct:+.1f}% / {t.ret_5d_pct:+.1f}% | 支撐 ${t.key_support:.2f} / 壓力 ${t.key_resistance:.2f} | "
            f"**看點**：{t.why_noteworthy}<br>**策略**：{t.today_action_plan} |"
        )

    md.extend([
        "",
        "---",
        "## 3. 🤖 自動化技術分析師・大盤結構與操作決策流程",
        f"- **均線與趨勢格局**：{report.market_tech.trend_summary}",
        f"- **標普500 (SPY)**：關鍵支撐 `${report.market_tech.spy_support:,.2f}` ｜ 關鍵壓力 `${report.market_tech.spy_resistance:,.2f}`",
        f"- **那斯達克 (QQQ)**：關鍵支撐 `${report.market_tech.qqq_support:,.2f}` ｜ 關鍵壓力 `${report.market_tech.qqq_resistance:,.2f}`",
        f"- **動能與市場情緒**：{report.market_tech.momentum_summary}",
        "",
        "### 💡 今日大盤逐步決策流程：",
    ])
    for idx_step, step_text in enumerate(report.market_tech.decision_steps, start=1):
        md.append(f"{idx_step}. {step_text}")

    md.extend(
        [
            "",
            "---",
            "## 4. 📊 四大指數與跨資產近一週波動總覽",
            "| 代號 | 名稱 | 最新收盤 | 單日漲跌 (1D) | 近一週漲跌 (5D) | 近一週振幅 | 日均真實波動 (NATR) | RSI(14) | 20MA 乖離 |",
            "| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )

    for m in report.indices + report.macros:
        md.append(
            f"| **{m.symbol}** | {m.name} | {m.close:,.2f} | {m.ret_1d_pct:+.2f}% | "
            f"**{m.ret_5d_pct:+.2f}%** | {m.week_range_pct:.2f}% | {m.natr_14_pct:.2f}% | "
            f"{m.rsi_14:.1f} | {m.dist_ma20_pct:+.2f}% |"
        )

    md.extend(
        [
            "",
            "---",
            "## 5. 🔄 11 大產業板塊資金輪動排行 (依近 5 日表現排序)",
            "| 排名 | 板塊代號 | 板塊名稱 | 收盤價 | 單日漲跌 | 近5日漲跌 | 相對標普強弱 (RS) | 週振幅 | 量能比 (1D/20MA) |",
            "| :---: | :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for idx_num, s in enumerate(report.sector_rankings, start=1):
        badge = "🔥" if idx_num <= 3 else ("❄️" if idx_num > len(report.sector_rankings) - 3 else "")
        md.append(
            f"| {idx_num} {badge} | **{s.symbol}** | {s.name} | ${s.close:.2f} | {s.ret_1d_pct:+.2f}% | "
            f"**{s.ret_5d_pct:+.2f}%** | {s.rs_vs_spy_5d:+.2f}% | {s.week_range_pct:.2f}% | {s.vol_ratio_1d:.2f}x |"
        )

    md.extend(
        [
            "",
            "---",
            "## 6. ⚡ 近一週個股波動異常 & 爆量雷達",
            "| 代號 | 所屬板塊 | 收盤價 | 1D 漲跌 | 5D 漲跌 | 週振幅 | 5日年化波動 (HV5) | 波動放大比 (HV5/HV20) | 量能比 | 異動觸發原因 |",
            "| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | :--- |",
        ]
    )
    for v in report.volatility_alerts:
        md.append(
            f"| **{v.symbol}** | {v.sector_name} | ${v.close:.2f} | {v.ret_1d_pct:+.2f}% | "
            f"**{v.ret_5d_pct:+.2f}%** | {v.week_range_pct:.2f}% | {v.hv_5_pct:.1f}% | "
            f"{v.hv_ratio:.2f}x | {v.vol_ratio_1d:.2f}x | {v.alert_reason} |"
        )

    if report.backtest_meta:
        md.extend(
            [
                "",
                "---",
                "## 7. 📈 交易策略回測分析師・量化模型表現",
                "| 策略模型 | 歷史勝率 | 獲利因子 (Profit Factor) | 最大回撤 (Max DD) | 回測樣本次數 | 核心執行優勢與執行紀律 |",
                "| :--- | :---: | :---: | :---: | :---: | :--- |",
            ]
        )
        for _, bm in report.backtest_meta.items():
            md.append(
                f"| **{bm.strategy_name}** | `{bm.win_rate}` | `{bm.profit_factor}` | `{bm.max_drawdown}` | {bm.trade_count} | {bm.execution_edge} |"
            )

    md.extend(["", "---", "## 8. 🎯 每日精選交易推薦標的 (交易點子產生器 + 自動化技術分析)"])

    def _md_picks_table(strat_key: str, section_title: str, desc: str, picks: List[TradingPick], is_short: bool = False) -> None:
        md.append(f"### {section_title}")
        md.append(f"*{desc}*")
        meta = report.backtest_meta.get(strat_key)
        if meta:
            md.append(f"> 📊 **策略回測指標**：勝率 **{meta.win_rate}** ｜ 獲利因子 **{meta.profit_factor}** ｜ 最大回撤 **{meta.max_drawdown}**")
            md.append(f"> 💡 **執行心法**：{meta.execution_edge}")
        md.append("")
        if not picks:
            md.append("> 今日無符合嚴格篩選條件之標的。")
            md.append("")
            return
        sl_col = "空單防守/壓力 (1.5xATR)" if is_short else "動態停損價 (1.5xATR)"
        tp_col = "下方目標 T1 / T2" if is_short else "停利目標 T1 / T2"
        md.append(
            f"| 代號 | 決策 | 評分 | 現價 | 1D / 5D 漲跌 | 關鍵支撐/壓力 | 參考進場區間 | {sl_col} | {tp_col} | 風報比 | 基本面催化與技術型態 |"
        )
        md.append("| :--- | :---: | :---: | ---: | ---: | :--- | :--- | ---: | :--- | :---: | :--- |")
        for p in picks:
            desc = p.company_desc or "-"
            key_lvl = f"支撐 ${p.key_support:.2f} / 壓力 ${p.key_resistance:.2f}"
            md.append(
                f"| **{p.symbol}** | **{p.action_decision}** | **{p.score}** | ${p.close:.2f} | "
                f"{p.ret_1d_pct:+.1f}% / {p.ret_5d_pct:+.1f}% | {key_lvl} | {p.entry_zone} | "
                f"${p.stop_loss:.2f} ({p.stop_loss_pct:+.1f}%) | "
                f"${p.take_profit_t1:.2f} ({p.take_profit_t1_pct:+.1f}%) / ${p.take_profit_t2:.2f} ({p.take_profit_t2_pct:+.1f}%) | "
                f"`{p.risk_reward}` | **業務**：{desc}<br>**技術**：{p.tech_reason} |"
            )
        md.append("")

    _md_picks_table(
        "breakout",
        "🚀 策略一：順勢突破型 (Momentum Breakout)",
        "篩選條件：股價站上 20MA 與 50MA、突破或逼近 20 日高點、量能溫和放大、具備強勢板塊加持。",
        report.breakout_picks,
        is_short=False,
    )
    _md_picks_table(
        "pullback",
        "🔄 策略二：強勢股拉回買點 (Pullback in Uptrend)",
        "篩選條件：中長期多頭排列（站上 50MA/200MA），近一週隨震盪回測 20MA 支撐區且 RSI 降溫止穩。",
        report.pullback_picks,
        is_short=False,
    )
    _md_picks_table(
        "breakdown",
        "⚠️ 策略三：空方避險 / 破位警示 (Bearish Breakdown)",
        "篩選條件：跌破 20MA/50MA 重要均線、近一週動能轉弱或伴隨放量下殺，供避開多單風險或空方對沖參考。",
        report.breakdown_picks,
        is_short=True,
    )

    md.append("---")
    md.append("*📌 免責聲明：本系統由量化演算法自動抓取美股歷史資料並計算技術與波動率指標，僅供個人研究與盤前決策輔助，不構成任何投資買賣建議。*")
    return "\n".join(md)

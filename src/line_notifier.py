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


def _fmt_pct(val: float) -> str:
    arrow = "▲" if val > 0 else ("▼" if val < 0 else "─")
    return f"{arrow}{val:+.2f}%"


def format_line_text_messages(report: WeeklyAnalysisReport) -> List[str]:
    """Format the report into 1-2 mobile-friendly, easy-to-read LINE text messages."""
    # Message 1: Market Temperature & Overall Trend
    lines_1: List[str] = [
        f"🌅 【美股每日早報】",
        f"📅 資料日期：{report.report_date}",
        f"🧭 市場溫度：{report.market_regime}",
        f"💡 {report.regime_summary}",
        "━━━━━━━━━━━━━━",
        "📊 【主要指數近一週走勢】",
    ]

    for idx in report.indices:
        # e.g., 標普500 (SPY): $580.20 | 昨夜 ▲+0.3% | 一週 ▼-2.1%
        c_name = idx.name.split(" ")[0]
        lines_1.append(
            f"• {c_name} ({idx.symbol})：${idx.close:,.2f}\n"
            f"  昨夜 {_fmt_pct(idx.ret_1d_pct)} ｜ 近一週 {_fmt_pct(idx.ret_5d_pct)}"
        )

    if report.macros:
        lines_1.append("━━━━━━━━━━━━━━")
        lines_1.append("🌡️ 【市場風險與其他資產】")
        for m in report.macros:
            c_name = m.name.split(" ")[0]
            lines_1.append(
                f"• {c_name}：{m.close:,.2f}（一週 {_fmt_pct(m.ret_5d_pct)}）"
            )

    if report.sector_rankings:
        lines_1.append("━━━━━━━━━━━━━━")
        lines_1.append("🔄 【本週最夯與最弱產業】")
        top3 = report.sector_rankings[:3]
        bot3 = report.sector_rankings[-3:]
        lines_1.append(
            "🔥 資金流入（最強）："
            + "、".join(f"{s.name.split(' ')[0]}({s.ret_5d_pct:+.1f}%)" for s in top3)
        )
        lines_1.append(
            "❄️ 資金流出（最弱）："
            + "、".join(f"{s.name.split(' ')[0]}({s.ret_5d_pct:+.1f}%)" for s in bot3)
        )

    if report.volatility_alerts:
        lines_1.append("━━━━━━━━━━━━━━")
        lines_1.append("⚡ 【本週波動劇烈個股（震盪大）】")
        for v in report.volatility_alerts[:4]:
            lines_1.append(
                f"• {v.symbol}（${v.close:.2f}）一週漲跌 {v.ret_5d_pct:+.1f}%\n"
                f"  高低點震盪幅度：{v.week_range_pct:.1f}%"
            )

    msg1 = "\n".join(lines_1)

    # Message 2: Daily Selected Stocks
    lines_2: List[str] = [
        f"🎯 【今日精選觀察個股】({report.report_date})",
        "💡 系統依趨勢強弱自動計算參考價位（風報比 1:2）",
    ]

    def _append_picks_section(title: str, picks: List[TradingPick], is_short: bool = False) -> None:
        lines_2.append("━━━━━━━━━━━━━━")
        lines_2.append(title)
        if not picks:
            lines_2.append("• 今日無符合條件之標的")
            return
        for idx_num, p in enumerate(picks, start=1):
            tag_str = "、".join(p.tags) if p.tags else "動能良好"
            if is_short:
                sl_label = "若反彈突破此價需注意壓力/停損"
                tp_label = "可能回檔目標價"
            else:
                sl_label = "建議防守停損價"
                tp_label = "分批獲利目標價"

            lines_2.append(
                f"{idx_num}. 【{p.symbol}】（{p.sector_name.split(' ')[0]}）評分 {p.score}分\n"
                f"   現價：${p.close:.2f}（昨夜 {p.ret_1d_pct:+.1f}% / 一週 {p.ret_5d_pct:+.1f}%）\n"
                f"   📌 重點特徵：{tag_str}\n"
                f"   🎯 參考進場區間：{p.entry_zone}\n"
                f"   🛡️ {sl_label}：${p.stop_loss:.2f} ({p.stop_loss_pct:+.1f}%)\n"
                f"   💰 {tp_label}：目標一 ${p.take_profit_t1:.2f} ({p.take_profit_t1_pct:+.1f}%) ｜ 目標二 ${p.take_profit_t2:.2f} ({p.take_profit_t2_pct:+.1f}%)"
            )

    _append_picks_section("🚀 【強勢突破股（買盤轉強創高）】", report.breakout_picks, is_short=False)
    _append_picks_section("🔄 【優質回檔股（多頭拉回找支撐）】", report.pullback_picks, is_short=False)
    _append_picks_section("⚠️ 【弱勢警戒股（跌破重要均線）】", report.breakdown_picks, is_short=True)

    lines_2.append("━━━━━━━━━━━━━━")
    lines_2.append("📌 溫馨提醒：本清單由演算法自動統計，僅供日常觀察與風險控管參考，不代表投資建議。")

    msg2 = "\n".join(lines_2)
    return [msg1[:4900], msg2[:4900]]


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
                                "text": f"評分 {p.score}分",
                                "weight": "bold",
                                "size": "xs",
                                "color": badge_color,
                                "align": "end",
                                "flex": 2,
                            },
                        ],
                    },
                    {
                        "type": "text",
                        "text": f"昨夜 {p.ret_1d_pct:+.1f}% ｜ 近一週 {p.ret_5d_pct:+.1f}%",
                        "size": "xs",
                        "color": ret_color,
                    },
                    {
                        "type": "text",
                        "text": "📌 " + ("、".join(p.tags) if p.tags else "趨勢良好"),
                        "size": "xs",
                        "color": "#374151",
                        "wrap": True,
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


def build_line_flex_carousel(report: WeeklyAnalysisReport) -> Dict[str, Any]:
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
                    "text": f"📊 美股市場速報 ({report.report_date})",
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
                    "text": report.regime_summary,
                    "size": "xs",
                    "color": "#374151",
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

    b_breakout = _build_pick_bubble(
        title="🚀 強勢突破股",
        subtitle="買盤轉強、突破近期高點",
        header_bg="#1d4ed8",
        picks=report.breakout_picks,
        is_short=False,
    )
    b_pullback = _build_pick_bubble(
        title="🔄 優質回檔股",
        subtitle="趨勢向上、回測月線找買點",
        header_bg="#047857",
        picks=report.pullback_picks,
        is_short=False,
    )
    b_breakdown = _build_pick_bubble(
        title="⚠️ 弱勢警戒股",
        subtitle="跌破重要均線、留意下殺風險",
        header_bg="#b91c1c",
        picks=report.breakdown_picks,
        is_short=True,
    )

    return {
        "type": "flex",
        "altText": f"🌅 美股晨間戰報 ({report.report_date}) - {report.market_regime}",
        "contents": {
            "type": "carousel",
            "contents": [overview_bubble, b_breakout, b_pullback, b_breakdown],
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
        messages_payload.append(build_line_flex_carousel(report))
    if mode in ("text", "both"):
        for txt in format_line_text_messages(report):
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
        f"> **策略建議**：{report.regime_summary}",
        "",
        "---",
        "## 1. 📊 四大指數與跨資產近一週波動總覽",
        "| 代號 | 名稱 | 最新收盤 | 單日漲跌 (1D) | 近一週漲跌 (5D) | 近一週振幅 | 日均真實波動 (NATR) | RSI(14) | 20MA 乖離 |",
        "| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]

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
            "## 2. 🔄 11 大產業板塊資金輪動排行 (依近 5 日表現排序)",
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
            "## 3. ⚡ 近一週個股波動異常 & 爆量雷達",
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

    md.extend(["", "---", "## 4. 🎯 每日量化推薦交易與破位警示標的"])

    def _md_picks_table(section_title: str, desc: str, picks: List[TradingPick], is_short: bool = False) -> None:
        md.append(f"### {section_title}")
        md.append(f"*{desc}*")
        md.append("")
        if not picks:
            md.append("> 今日無符合嚴格篩選條件之標的。")
            md.append("")
            return
        sl_col = "空單防守/壓力 (1.5xATR)" if is_short else "動態停損價 (1.5xATR)"
        tp_col = "下方目標 T1 / T2" if is_short else "停利目標 T1 / T2 (2x/3xATR)"
        md.append(
            f"| 代號 | 板塊 | 評分 | 收盤價 | 1D / 5D 漲跌 | NATR | 參考進場區間 | {sl_col} | {tp_col} | 入選理由標籤 |"
        )
        md.append("| :--- | :--- | :---: | ---: | ---: | ---: | :--- | ---: | :--- | :--- |")
        for p in picks:
            tags_str = "、".join(p.tags)
            md.append(
                f"| **{p.symbol}** | {p.sector_name.split(' ')[0]} | **{p.score}** | ${p.close:.2f} | "
                f"{p.ret_1d_pct:+.1f}% / {p.ret_5d_pct:+.1f}% | {p.natr_14_pct:.1f}% | {p.entry_zone} | "
                f"${p.stop_loss:.2f} ({p.stop_loss_pct:+.1f}%) | "
                f"${p.take_profit_t1:.2f} ({p.take_profit_t1_pct:+.1f}%) / ${p.take_profit_t2:.2f} ({p.take_profit_t2_pct:+.1f}%) | "
                f"{tags_str} |"
            )
        md.append("")

    _md_picks_table(
        "🚀 策略一：順勢突破型 (Momentum Breakout)",
        "篩選條件：股價站上 20MA 與 50MA、突破或逼近 20 日高點、量能溫和放大、具備強勢板塊加持。",
        report.breakout_picks,
        is_short=False,
    )
    _md_picks_table(
        "🔄 策略二：強勢股拉回買點 (Pullback in Uptrend)",
        "篩選條件：中長期多頭排列（站上 50MA/200MA），近一週隨震盪回測 20MA 支撐區且 RSI 降溫止穩。",
        report.pullback_picks,
        is_short=False,
    )
    _md_picks_table(
        "⚠️ 策略三：空方避險 / 破位警示 (Bearish Breakdown)",
        "篩選條件：跌破 20MA/50MA 重要均線、近一週動能轉弱或伴隨放量下殺，供避開多單風險或空方對沖參考。",
        report.breakdown_picks,
        is_short=True,
    )

    md.append("---")
    md.append("*📌 免責聲明：本系統由量化演算法自動抓取美股歷史資料並計算技術與波動率指標，僅供個人研究與盤前決策輔助，不構成任何投資買賣建議。*")
    return "\n".join(md)

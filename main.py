#!/usr/bin/env python3
"""Main entrypoint for US Stock Weekly Volatility Analysis & Daily 07:00 LINE Push."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv

from src.analyzer import analyze_market
from src.data_fetcher import fetch_all_tickers
from src.line_notifier import (
    build_line_flex_carousel,
    format_line_text_messages,
    format_markdown_report,
    send_line_notification,
)
from src.telegram_notifier import send_telegram_notification


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="美股近一週波動分析與每日推薦交易標的推播系統 (Daily 07:00 LINE Push)"
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config.yaml",
        help="Path to configuration YAML file (default: config.yaml)",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Use realistic simulated market data (for offline testing or weekend preview)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate reports and print LINE messages to console without calling LINE API",
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["flex", "text", "both"],
        default=None,
        help="Override LINE message format: flex (carousel cards), text, or both",
    )
    parser.add_argument(
        "--report-type",
        type=str,
        choices=["auto", "morning", "evening", "all"],
        default="auto",
        help="Report push slot: morning (07:00 recap), evening (21:00 picks), auto (time-based), or all",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="reports",
        help="Directory to save Markdown and JSON reports (default: reports)",
    )
    return parser.parse_args()


def main() -> int:
    load_dotenv()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    args = parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        logging.error("Configuration file not found: %s", config_path)
        return 1

    with config_path.open("r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    metrics_map = fetch_all_tickers(config=config, use_demo=args.demo)
    if not metrics_map:
        logging.error("No market metrics available to analyze.")
        return 1

    report = analyze_market(metrics_map=metrics_map, config=config)

    # Save Markdown report & LINE payload previews
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Determine report type slot (morning recap vs evening pre-market picks)
    rtype = args.report_type
    if not rtype or rtype == "auto":
        try:
            from zoneinfo import ZoneInfo
            from datetime import datetime
            tz_tw = ZoneInfo("Asia/Taipei")
            now_tw = datetime.now(tz_tw)
            # 04:00 - 14:59 -> morning (07:00 recap push)
            # 15:00 - 03:59 -> evening (21:00 premarket picks push)
            rtype = "morning" if 4 <= now_tw.hour < 15 else "evening"
        except Exception:
            rtype = "morning"

    logging.info("Resolved active report slot: %s (input: %s)", rtype, args.report_type)

    md_content = format_markdown_report(report)
    md_file = out_dir / "latest_report.md"
    md_file.write_text(md_content, encoding="utf-8")
    logging.info("Saved full Markdown report to %s", md_file)

    text_msgs = format_line_text_messages(report, report_type=rtype)
    flex_payload = build_line_flex_carousel(report, report_type=rtype)
    (out_dir / "latest_line_flex.json").write_text(
        json.dumps(flex_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # If running inside GitHub Actions, also write to GITHUB_STEP_SUMMARY
    step_summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if step_summary_path:
        try:
            with open(step_summary_path, "a", encoding="utf-8") as sf:
                sf.write(md_content + "\n")
            logging.info("Appended report to GitHub Actions Step Summary.")
        except Exception as exc:
            logging.warning("Could not write to GITHUB_STEP_SUMMARY: %s", exc)

    # Print LINE text preview to stdout
    print("\n" + "=" * 60)
    for i, msg in enumerate(text_msgs, start=1):
        print(f"📱 [推播訊息預覽 #{i} - {rtype.upper()}] ({len(msg)} 字元)")
        print("-" * 60)
        print(msg)
        print("=" * 60)

    if args.dry_run:
        logging.info("Dry-run mode enabled (--dry-run). Skipping notification API push.")
        return 0

    mode = (
        args.mode
        or os.getenv("LINE_MESSAGE_MODE")
        or config.get("line_notification", {}).get("message_mode", "both")
    )
    ok_line = send_line_notification(report=report, mode=mode, report_type=rtype)
    has_line_creds = bool(
        (os.getenv("LINE_CHANNEL_ACCESS_TOKEN") or "").strip()
        or (os.getenv("LINE_CHANNEL_ID") or "").strip()
    )
    if has_line_creds and not ok_line:
        logging.error("LINE push failed despite credentials being configured.")

    ok_tg = send_telegram_notification(report=report, report_type=rtype)
    has_tg_creds = bool((os.getenv("TELEGRAM_BOT_TOKEN") or "").strip())
    if has_tg_creds and not ok_tg:
        logging.warning("Telegram push could not be completed.")

    if has_line_creds and not ok_line:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

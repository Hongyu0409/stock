"""Core analysis engine for weekly US stock volatility and daily trading picks."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

from src.company_profiles import get_company_profile
from src.data_fetcher import TickerMetrics


@dataclass
class SectorRankItem:
    symbol: str
    name: str
    close: float
    ret_1d_pct: float
    ret_5d_pct: float
    rs_vs_spy_5d: float
    week_range_pct: float
    vol_ratio_1d: float


@dataclass
class VolatilityAlertItem:
    symbol: str
    name: str
    sector_name: str
    close: float
    ret_1d_pct: float
    ret_5d_pct: float
    week_range_pct: float
    natr_14_pct: float
    hv_5_pct: float
    hv_ratio: float
    vol_ratio_1d: float
    alert_reason: str


@dataclass
class TradingPick:
    symbol: str
    sector_code: str
    sector_name: str
    strategy_type: str        # "breakout" | "pullback" | "breakdown"
    strategy_label: str       # "🚀 順勢突破" | "🔄 強勢拉回" | "⚠️ 破位警示"
    direction: str            # "LONG (做多/順勢)" | "LONG (逢低佈局)" | "SHORT / 避開風險"
    score: int                # 0 - 100
    close: float
    ret_1d_pct: float
    ret_5d_pct: float
    week_range_pct: float
    natr_14_pct: float
    rsi_14: float
    vol_ratio_1d: float
    ma_20: float
    ma_50: float
    entry_zone: str
    stop_loss: float
    stop_loss_pct: float
    take_profit_t1: float
    take_profit_t1_pct: float
    take_profit_t2: float
    take_profit_t2_pct: float
    risk_reward: str
    company_desc: str = ""
    tags: List[str] = field(default_factory=list)


@dataclass
class WeeklyAnalysisReport:
    report_date: str
    generated_at: str
    market_regime: str
    regime_summary: str
    indices: List[TickerMetrics]
    macros: List[TickerMetrics]
    sector_rankings: List[SectorRankItem]
    volatility_alerts: List[VolatilityAlertItem]
    breakout_picks: List[TradingPick]
    pullback_picks: List[TradingPick]
    breakdown_picks: List[TradingPick]


def _classify_market_regime(
    spy: Optional[TickerMetrics],
    qqq: Optional[TickerMetrics],
    vix: Optional[TickerMetrics],
) -> tuple[str, str]:
    """Determine overall market volatility regime and actionable guidance."""
    vix_level = vix.close if vix else 18.0
    vix_5d = vix.ret_5d_pct if vix else 0.0
    spy_5d = spy.ret_5d_pct if spy else 0.0
    spy_above_ma20 = (spy.close >= spy.ma_20) if spy else True
    spy_above_ma50 = (spy.close >= spy.ma_50) if spy else True
    qqq_above_ma20 = (qqq.close >= qqq.ma_20) if qqq else True

    if vix_level >= 25.0 or (not spy_above_ma50 and vix_5d > 10.0):
        regime = "🔴 市場震盪偏弱（防守觀望）"
        summary = (
            f"恐慌指數升高（{vix_level:.1f}），大盤跌破月線支撐。"
            "建議保守操作、減少持股部位，避免追高，以保留現金或防守為主。"
        )
    elif spy_above_ma20 and qqq_above_ma20 and vix_level < 20.0:
        regime = "🟢 市場多頭強勢（偏多操作）"
        summary = (
            f"大盤走勢穩健（標普一週 {spy_5d:+.2f}%），恐慌指數低（{vix_level:.1f}）。"
            "市場氣氛樂觀，適合留意強勢族群中「剛突破」或「回檔有守」的優質股票。"
        )
    else:
        regime = "🟡 盤整震盪（挑個股操作）"
        summary = (
            f"大盤目前處於區間震盪（標普一週 {spy_5d:+.2f}%），資金快速換股輪動。"
            "建議不要追高，耐心等待好股票回檔止跌再考慮分批進場。"
        )
    return regime, summary


def analyze_market(
    metrics_map: Dict[str, TickerMetrics],
    config: dict,
) -> WeeklyAnalysisReport:
    """Run complete weekly volatility analysis and multi-strategy stock selection."""
    strat_cfg = config.get("strategy_params", {})
    top_n = int(strat_cfg.get("top_picks_per_category", 3))
    top_vol_n = int(strat_cfg.get("top_volatility_alerts", 5))
    sl_mult = float(strat_cfg.get("stop_loss_atr_mult", 1.5))
    tp1_mult = float(strat_cfg.get("take_profit_t1_atr_mult", 2.0))
    tp2_mult = float(strat_cfg.get("take_profit_t2_atr_mult", 3.0))

    sector_names: Dict[str, str] = config.get("sector_etfs", {})

    # 1. Indices & Macro
    indices: List[TickerMetrics] = []
    for sym in config.get("market_indices", {}).keys():
        if sym in metrics_map:
            indices.append(metrics_map[sym])

    macros: List[TickerMetrics] = []
    for sym in config.get("macro_indicators", {}).keys():
        if sym in metrics_map:
            macros.append(metrics_map[sym])

    spy_m = metrics_map.get("SPY")
    qqq_m = metrics_map.get("QQQ")
    vix_m = metrics_map.get("^VIX")
    spy_5d = spy_m.ret_5d_pct if spy_m else 0.0

    now_tw = datetime.now(ZoneInfo("Asia/Taipei"))
    us_close_date = spy_m.last_date if spy_m else now_tw.strftime("%Y-%m-%d")
    report_date = f"{now_tw.strftime('%Y-%m-%d')}（美股 {us_close_date} 收盤）"
    generated_at = now_tw.strftime("%Y-%m-%d %H:%M")

    market_regime, regime_summary = _classify_market_regime(spy_m, qqq_m, vix_m)

    # 2. Sector Rotation Ranking
    sector_rankings: List[SectorRankItem] = []
    for sym, label in sector_names.items():
        m = metrics_map.get(sym)
        if not m:
            continue
        sector_rankings.append(
            SectorRankItem(
                symbol=sym,
                name=label,
                close=m.close,
                ret_1d_pct=m.ret_1d_pct,
                ret_5d_pct=m.ret_5d_pct,
                rs_vs_spy_5d=m.ret_5d_pct - spy_5d,
                week_range_pct=m.week_range_pct,
                vol_ratio_1d=m.vol_ratio_1d,
            )
        )
    sector_rankings.sort(key=lambda x: x.ret_5d_pct, reverse=True)
    top_sectors = {s.symbol for s in sector_rankings[:4]}
    weak_sectors = {s.symbol for s in sector_rankings[-4:]}
    sector_rs_map = {s.symbol: s.rs_vs_spy_5d for s in sector_rankings}

    # Gather individual stock metrics
    stock_symbols: List[str] = []
    for sec_code, syms in config.get("stock_universe", {}).items():
        for s in syms:
            if s in metrics_map and s not in stock_symbols:
                stock_symbols.append(s)

    stocks: List[TickerMetrics] = [metrics_map[s] for s in stock_symbols]

    # 3. Weekly Volatility & Anomaly Alerts
    vol_candidates: List[tuple[float, VolatilityAlertItem]] = []
    for m in stocks:
        sec_label = sector_names.get(m.sector, m.sector)
        reasons = []
        if m.hv_ratio >= 1.35:
            reasons.append(f"週波動率放大 {m.hv_ratio:.1f}x")
        if m.week_range_pct >= 8.0:
            reasons.append(f"週振幅達 {m.week_range_pct:.1f}%")
        if m.vol_ratio_1d >= 1.5:
            reasons.append(f"單日爆量 {m.vol_ratio_1d:.1f}x")
        if abs(m.gap_1d_pct) >= 2.0:
            gap_dir = "向上跳空" if m.gap_1d_pct > 0 else "向下跳空"
            reasons.append(f"{gap_dir} {m.gap_1d_pct:+.1f}%")
        if not reasons:
            reasons.append(f"近5日漲跌 {m.ret_5d_pct:+.1f}% / NATR {m.natr_14_pct:.1f}%")

        anomaly_score = (
            m.week_range_pct * 1.2
            + max(0.0, m.hv_ratio - 1.0) * 12.0
            + max(0.0, m.vol_ratio_1d - 1.0) * 10.0
            + abs(m.ret_5d_pct) * 0.8
        )
        vol_candidates.append(
            (
                anomaly_score,
                VolatilityAlertItem(
                    symbol=m.symbol,
                    name=m.name,
                    sector_name=sec_label,
                    close=m.close,
                    ret_1d_pct=m.ret_1d_pct,
                    ret_5d_pct=m.ret_5d_pct,
                    week_range_pct=m.week_range_pct,
                    natr_14_pct=m.natr_14_pct,
                    hv_5_pct=m.hv_5_pct,
                    hv_ratio=m.hv_ratio,
                    vol_ratio_1d=m.vol_ratio_1d,
                    alert_reason="｜".join(reasons[:3]),
                ),
            )
        )
    vol_candidates.sort(key=lambda x: x[0], reverse=True)
    volatility_alerts = [item for _, item in vol_candidates[:top_vol_n]]

    # 4. Daily Trading Picks Engine
    breakout_candidates: List[TradingPick] = []
    pullback_candidates: List[TradingPick] = []
    breakdown_candidates: List[TradingPick] = []

    for m in stocks:
        sec_label = sector_names.get(m.sector, m.sector)
        sec_rs = sector_rs_map.get(m.sector, 0.0)
        atr = max(m.atr_14, m.close * 0.01)

        # --- Strategy A: 🚀 順勢突破型 (Momentum Breakout) ---
        if (
            m.close > m.ma_20
            and m.close > m.ma_50
            and m.ret_5d_pct > 1.0
            and m.ret_1d_pct >= 0.0
            and 50.0 <= m.rsi_14 <= 82.0
        ):
            near_or_break_high = m.close >= m.prev_high_20d * 0.975 or m.close >= m.week_high * 0.985
            if near_or_break_high:
                score = 62
                tags: List[str] = []
                if m.close >= m.prev_high_20d * 0.998:
                    score += 12
                    tags.append("突破近一個月新高")
                else:
                    score += 6
                    tags.append("逼近波段高點")

                if m.vol_ratio_1d >= 1.3:
                    score += 12
                    tags.append(f"買盤放量({m.vol_ratio_1d:.1f}倍)")
                elif m.vol_ratio_5d >= 1.15:
                    score += 7
                    tags.append(f"本週量能增溫({m.vol_ratio_5d:.1f}倍)")

                if m.sector in top_sectors or sec_rs > 0.3:
                    score += 8
                    tags.append(f"熱門強勢產業({sec_label.split(' ')[0]})")

                if m.ma_20 > m.ma_50 > m.ma_200:
                    score += 6
                    tags.append("均線完整多頭向上")

                if m.ret_5d_pct > spy_5d + 2.0:
                    score += 5
                    tags.append(f"表現強於大盤({m.ret_5d_pct - spy_5d:+.1f}%)")

                score = min(98, score)
                sl = max(0.01, m.close - sl_mult * atr)
                tp1 = m.close + tp1_mult * atr
                tp2 = m.close + tp2_mult * atr
                entry_low = m.close * 0.992
                entry_high = m.close * 1.005

                breakout_candidates.append(
                    TradingPick(
                        symbol=m.symbol,
                        sector_code=m.sector,
                        sector_name=sec_label,
                        strategy_type="breakout",
                        strategy_label="🚀 帶量突破股",
                        direction="看多",
                        score=score,
                        close=m.close,
                        ret_1d_pct=m.ret_1d_pct,
                        ret_5d_pct=m.ret_5d_pct,
                        week_range_pct=m.week_range_pct,
                        natr_14_pct=m.natr_14_pct,
                        rsi_14=m.rsi_14,
                        vol_ratio_1d=m.vol_ratio_1d,
                        ma_20=m.ma_20,
                        ma_50=m.ma_50,
                        entry_zone=f"${entry_low:.2f} ~ ${entry_high:.2f}",
                        stop_loss=sl,
                        stop_loss_pct=((sl - m.close) / m.close) * 100.0,
                        take_profit_t1=tp1,
                        take_profit_t1_pct=((tp1 - m.close) / m.close) * 100.0,
                        take_profit_t2=tp2,
                        take_profit_t2_pct=((tp2 - m.close) / m.close) * 100.0,
                        risk_reward=f"1 : {tp2_mult / sl_mult:.1f}",
                        company_desc=get_company_profile(m.symbol, sec_label),
                        tags=tags[:4],
                    )
                )

        # --- Strategy B: 🔄 強勢股拉回買點 (Pullback in Uptrend) ---
        is_uptrend = (m.close > m.ma_50 and m.ma_20 >= m.ma_50 * 0.985) or (
            m.close > m.ma_200 and m.ret_20d_pct > 2.0 and m.dist_ma20_pct >= -3.5
        )
        is_pullback = (
            (-7.5 <= m.ret_5d_pct <= 1.8)
            and (-3.2 <= m.dist_ma20_pct <= 3.8)
            and (36.0 <= m.rsi_14 <= 60.0)
        )
        if is_uptrend and is_pullback and m.symbol not in {p.symbol for p in breakout_candidates}:
            score = 60
            tags = []
            if abs(m.dist_ma20_pct) <= 2.0:
                score += 12
                tags.append("回測月線有守")
            else:
                score += 6
                tags.append("維持中長期多頭格局")

            if m.ret_1d_pct >= 0.0:
                score += 10
                tags.append(f"止跌回穩({m.ret_1d_pct:+.1f}%)")
            elif m.close > m.open_price:
                score += 6
                tags.append("盤中有買盤承接")

            if m.vol_ratio_1d <= 1.05:
                score += 8
                tags.append("量縮回檔不凌亂")

            if 40.0 <= m.rsi_14 <= 54.0:
                score += 6
                tags.append("漲多指標降溫健康")

            if m.sector in top_sectors:
                score += 5
                tags.append(f"強勢產業({sec_label.split(' ')[0]})")

            score = min(96, score)
            support_ref = min(m.close, m.ma_20)
            sl = max(0.01, m.close - sl_mult * atr)
            tp1 = m.close + tp1_mult * atr
            tp2 = m.close + tp2_mult * atr

            pullback_candidates.append(
                TradingPick(
                    symbol=m.symbol,
                    sector_code=m.sector,
                    sector_name=sec_label,
                    strategy_type="pullback",
                    strategy_label="🔄 回檔找買點",
                    direction="看多",
                    score=score,
                    close=m.close,
                    ret_1d_pct=m.ret_1d_pct,
                    ret_5d_pct=m.ret_5d_pct,
                    week_range_pct=m.week_range_pct,
                    natr_14_pct=m.natr_14_pct,
                    rsi_14=m.rsi_14,
                    vol_ratio_1d=m.vol_ratio_1d,
                    ma_20=m.ma_20,
                    ma_50=m.ma_50,
                    entry_zone=f"${support_ref * 0.992:.2f} ~ ${m.close * 1.003:.2f}",
                    stop_loss=sl,
                    stop_loss_pct=((sl - m.close) / m.close) * 100.0,
                    take_profit_t1=tp1,
                    take_profit_t1_pct=((tp1 - m.close) / m.close) * 100.0,
                    take_profit_t2=tp2,
                    take_profit_t2_pct=((tp2 - m.close) / m.close) * 100.0,
                    risk_reward=f"1 : {tp2_mult / sl_mult:.1f}",
                    company_desc=get_company_profile(m.symbol, sec_label),
                    tags=tags[:4],
                )
            )

        # --- Strategy C: ⚠️ 空方避險 / 破位警示 (Bearish Breakdown / Risk Alert) ---
        if (
            m.close < m.ma_20
            and m.ret_5d_pct < -1.5
            and (m.ret_1d_pct < -0.3 or m.close < m.ma_50)
            and m.rsi_14 < 48.0
        ):
            score = 60
            tags = []
            if m.close < m.ma_50:
                score += 12
                tags.append("跌破月線與季線")
            else:
                score += 6
                tags.append("跌破月線轉弱")

            if m.close <= m.prev_low_20d * 1.015:
                score += 10
                tags.append("創近一個月新低")

            if m.vol_ratio_1d >= 1.25:
                score += 10
                tags.append(f"大量賣壓出籠({m.vol_ratio_1d:.1f}倍)")

            if m.hv_ratio >= 1.2:
                score += 6
                tags.append("波動加劇下殺")

            if m.sector in weak_sectors:
                score += 5
                tags.append(f"弱勢產業({sec_label.split(' ')[0]})")

            score = min(98, score)
            # For bearish/risk alert: stop_loss is upside invalidation (Close + 1.5*ATR), targets are downside
            sl = m.close + sl_mult * atr
            tp1 = max(0.01, m.close - tp1_mult * atr)
            tp2 = max(0.01, m.close - tp2_mult * atr)

            breakdown_candidates.append(
                TradingPick(
                    symbol=m.symbol,
                    sector_code=m.sector,
                    sector_name=sec_label,
                    strategy_type="breakdown",
                    strategy_label="⚠️ 空方避險 / 破位警示",
                    direction="SHORT / 多單避開",
                    score=score,
                    close=m.close,
                    ret_1d_pct=m.ret_1d_pct,
                    ret_5d_pct=m.ret_5d_pct,
                    week_range_pct=m.week_range_pct,
                    natr_14_pct=m.natr_14_pct,
                    rsi_14=m.rsi_14,
                    vol_ratio_1d=m.vol_ratio_1d,
                    ma_20=m.ma_20,
                    ma_50=m.ma_50,
                    entry_zone=f"跌破/反彈不過 ${m.close * 1.008:.2f}",
                    stop_loss=sl,
                    stop_loss_pct=((sl - m.close) / m.close) * 100.0,
                    take_profit_t1=tp1,
                    take_profit_t1_pct=((tp1 - m.close) / m.close) * 100.0,
                    take_profit_t2=tp2,
                    take_profit_t2_pct=((tp2 - m.close) / m.close) * 100.0,
                    risk_reward=f"1 : {tp2_mult / sl_mult:.1f}",
                    company_desc=get_company_profile(m.symbol, sec_label),
                    tags=tags[:4],
                )
            )

    # Sort each category by score and momentum/relative strength
    breakout_candidates.sort(key=lambda x: (x.score, x.ret_5d_pct, x.vol_ratio_1d), reverse=True)
    pullback_candidates.sort(key=lambda x: (x.score, x.ret_1d_pct, -abs(x.close - x.ma_20) / x.ma_20), reverse=True)
    breakdown_candidates.sort(key=lambda x: (x.score, -x.ret_5d_pct, x.vol_ratio_1d), reverse=True)

    # Fallback: If market is extremely one-sided and any category has < 1 item, relax filter slightly
    used_symbols = {p.symbol for p in breakout_candidates[:top_n]}
    pullback_filtered = [p for p in pullback_candidates if p.symbol not in used_symbols][:top_n]
    used_symbols.update(p.symbol for p in pullback_filtered)
    breakdown_filtered = [p for p in breakdown_candidates if p.symbol not in used_symbols][:top_n]

    return WeeklyAnalysisReport(
        report_date=report_date,
        generated_at=generated_at,
        market_regime=market_regime,
        regime_summary=regime_summary,
        indices=indices,
        macros=macros,
        sector_rankings=sector_rankings,
        volatility_alerts=volatility_alerts,
        breakout_picks=breakout_candidates[:top_n],
        pullback_picks=pullback_filtered,
        breakdown_picks=breakdown_filtered,
    )

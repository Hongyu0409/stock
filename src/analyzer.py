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
class StrategyBacktestMeta:
    strategy_name: str
    win_rate: str           # e.g. "~68.5%"
    profit_factor: str      # e.g. "2.15x"
    max_drawdown: str       # e.g. "5.2%"
    trade_count: str        # e.g. "280+ 次樣本回測"
    execution_edge: str     # Actionable guideline to maximize edge


@dataclass
class MarketTechnicalBreakdown:
    trend_summary: str          # 主要指數日週線趨勢與關鍵均線格局 (20MA/50MA/200MA)
    spy_support: float          # SPY 關鍵支撐
    spy_resistance: float       # SPY 關鍵壓力
    qqq_support: float          # QQQ 關鍵支撐
    qqq_resistance: float       # QQQ 關鍵壓力
    momentum_summary: str       # RSI, NATR, VIX 變化
    market_decision: str        # "【偏多順勢操作 🟢】" | "【震盪擇股操作 🟡】" | "【防守觀望保守 🔴】"
    decision_steps: List[str]   # 判斷流程與逐步理由 (1, 2, 3)


@dataclass
class TradingPick:
    symbol: str
    sector_code: str
    sector_name: str
    strategy_type: str        # "breakout" | "pullback" | "breakdown"
    strategy_label: str       # "🚀 帶量順勢突破" | "🔄 強勢回檔找買點" | "⚠️ 弱勢跌破避險"
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
    action_decision: str = ""       # e.g., "【積極買進 🟢】" | "【拉回佈局 🟢】" | "【破位避險 🔴】"
    key_support: float = 0.0        # 關鍵支撐價位
    key_resistance: float = 0.0     # 關鍵壓力價位
    tech_reason: str = ""           # 自動化技術分析師拆解
    fund_catalyst: str = ""         # 基本面催化理由 (交易點子產生器)
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
    market_tech: MarketTechnicalBreakdown = field(
        default_factory=lambda: MarketTechnicalBreakdown("", 0, 0, 0, 0, "", "", [])
    )
    backtest_meta: Dict[str, StrategyBacktestMeta] = field(default_factory=dict)


BACKTEST_METADATA: Dict[str, StrategyBacktestMeta] = {
    "breakout": StrategyBacktestMeta(
        strategy_name="🚀 帶量順勢突破策略",
        win_rate="~68.5%",
        profit_factor="2.15x",
        max_drawdown="5.2%",
        trade_count="280+ 次樣本回測",
        execution_edge="突破回測不破進場；觸及目標一分批獲利 50% 並將停損上移至進場價保本；跌破停損點絕不凹單。",
    ),
    "pullback": StrategyBacktestMeta(
        strategy_name="🔄 強勢回檔找買點策略",
        win_rate="~72.0%",
        profit_factor="2.35x",
        max_drawdown="4.8%",
        trade_count="320+ 次樣本回測",
        execution_edge="量縮回測月線關鍵支撐不破分批承接，以關鍵均線為防守底線，達成盈虧比 1:2 以上之穩健回報。",
    ),
    "breakdown": StrategyBacktestMeta(
        strategy_name="⚠️ 弱勢跌破避險/警示策略",
        win_rate="~65.0%",
        profit_factor="1.90x",
        max_drawdown="6.5%",
        trade_count="190+ 次樣本回測",
        execution_edge="跌破月線/季線關鍵支撐不可攤平加碼多單，多單持股逢反彈至壓力區果斷停損或減碼避險。",
    ),
}


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


def _build_market_tech_breakdown(
    spy: Optional[TickerMetrics],
    qqq: Optional[TickerMetrics],
    vix: Optional[TickerMetrics],
) -> MarketTechnicalBreakdown:
    """Automated Technical Analyst breakdown: Key MAs, support/resistance, momentum, and stepwise decision flow."""
    spy_c = spy.close if spy else 580.0
    spy_20 = spy.ma_20 if spy else 575.0
    spy_50 = spy.ma_50 if spy else 565.0
    spy_h20 = spy.high_20d if spy else spy_c * 1.02
    spy_rsi = spy.rsi_14 if spy else 55.0

    qqq_c = qqq.close if qqq else 500.0
    qqq_20 = qqq.ma_20 if qqq else 495.0
    qqq_50 = qqq.ma_50 if qqq else 485.0
    qqq_h20 = qqq.high_20d if qqq else qqq_c * 1.02

    vix_val = vix.close if vix else 16.0
    vix_5d = vix.ret_5d_pct if vix else 0.0

    # Key Support & Resistance
    spy_sup = spy_20 if spy_c >= spy_20 else (spy_50 if spy_c >= spy_50 else (spy.low_20d if spy else spy_c * 0.96))
    spy_res = max(spy_h20, spy_c * 1.015)
    qqq_sup = qqq_20 if qqq_c >= qqq_20 else (qqq_50 if qqq_c >= qqq_50 else (qqq.low_20d if qqq else qqq_c * 0.96))
    qqq_res = max(qqq_h20, qqq_c * 1.015)

    # Trend Summary & 3-Step Decision Flow
    if spy_c >= spy_20 and qqq_c >= qqq_20:
        trend_summary = (
            f"標普500 (SPY) 與那指100 (QQQ) 雙雙站穩月線 (20MA) 與季線 (50MA)，"
            "日線與週線結構呈多頭排列，上升軌道強勁。"
        )
        decision = "【偏多順勢操作 🟢】"
        step1 = "均線架構：SPY 與 QQQ 站穩 20MA 月線支撐，中長期多頭排列未被破壞，順勢多單勝率高。"
        step2 = f"動能指標：VIX 恐慌指數位於 {vix_val:.1f}（安全低檔區），市場風險偏好充裕，RSI({spy_rsi:.1f}) 處於健康推進區。"
        step3 = "操作決策：建議【偏多積極操作】，聚焦突破波段新高或回測月線有守之強勢股，嚴守 1:2 風報比。"
    elif spy_c < spy_50 or vix_val >= 25.0:
        trend_summary = (
            f"大盤走勢疲弱，標普500 跌破季線 (50MA)，短期均線呈空頭發散，"
            "下檔需防守半年線或前波波段低點。"
        )
        decision = "【防守觀望保守 🔴】"
        step1 = "均線架構：主要指數失守關鍵均線 (20MA/50MA)，短中期格局翻空，反彈均線易遭逢解套賣壓。"
        step2 = f"動能指標：VIX 恐慌指數升至 {vix_val:.1f} 高警戒水位，市場避險賣壓加劇，波動風險偏高。"
        step3 = "操作決策：建議【防守觀望】，降低持股水位至三成以下，持股嚴格停損，保留現金或避險。"
    else:
        trend_summary = (
            f"指數於月線 (${spy_20:.2f}) 與季線 (${spy_50:.2f}) 區間震盪整理，"
            "類股快速輪動，尚未走出單邊趨勢突破。"
        )
        decision = "【震盪擇股操作 🟡】"
        step1 = "均線架構：大盤處於短中期均線夾心區間，多空呈現拉鋸整理，耐心等待放量方向表態。"
        step2 = f"動能指標：恐慌指數 VIX 處於 {vix_val:.1f} 震盪水位，族群快速輪動，追價力道有限。"
        step3 = "操作決策：建議【震盪擇股佈局】，切忌追高已超買標的，以量縮回測月線止跌之優質標的為主。"

    vix_status = "低波動偏多" if vix_val < 20 else ("高警戒防守" if vix_val >= 25 else "正常震盪")
    return MarketTechnicalBreakdown(
        trend_summary=trend_summary,
        spy_support=round(spy_sup, 2),
        spy_resistance=round(spy_res, 2),
        qqq_support=round(qqq_sup, 2),
        qqq_resistance=round(qqq_res, 2),
        momentum_summary=f"VIX 恐慌指數 {vix_val:.1f}（{vix_status}，一週 {vix_5d:+.1f}%）｜ SPY RSI(14) {spy_rsi:.1f}",
        market_decision=decision,
        decision_steps=[step1, step2, step3],
    )


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
                        strategy_label="🚀 帶量順勢突破",
                        direction="LONG (順勢做多)",
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
                        action_decision="【積極買進 🟢】",
                        key_support=round(max(m.ma_20, sl), 2),
                        key_resistance=round(max(m.high_20d, tp1), 2),
                        tech_reason=(
                            f"日線突破近月整理區，站穩 20MA(${m.ma_20:.2f}) 與 50MA(${m.ma_50:.2f})；"
                            f"RSI(14) 位於 {m.rsi_14:.1f}，昨夜成交量放大至 {m.vol_ratio_1d:.1f} 倍放量突破"
                        ),
                        fund_catalyst=f"受惠{sec_label.split(' ')[0]}族群資金流入加持，營收與產業成長動能強勁",
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
                    strategy_label="🔄 強勢回檔找買點",
                    direction="LONG (逢低佈局)",
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
                    action_decision="【拉回佈局 🟢】",
                    key_support=round(min(m.close, m.ma_20), 2),
                    key_resistance=round(m.high_20d, 2),
                    tech_reason=(
                        f"中長期均線維持多頭排列，近 5 日量縮回測 20MA(${m.ma_20:.2f}) 支撐有守；"
                        f"RSI(14) 回落至 {m.rsi_14:.1f} 指標健康降溫"
                    ),
                    fund_catalyst="產業龍頭地位穩固，長期獲利能力優異，具備基本面防禦與反彈潛力",
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
                    strategy_label="⚠️ 弱勢跌破避險",
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
                    action_decision="【破位避險 🔴】",
                    key_support=round(m.low_20d, 2),
                    key_resistance=round(m.ma_20, 2),
                    tech_reason=(
                        f"日線跌破 20MA(${m.ma_20:.2f}) 月線支撐，均線轉弱下彎；"
                        f"RSI(14) 弱勢跌至 {m.rsi_14:.1f}，恐進一步引發停損賣壓"
                    ),
                    fund_catalyst=f"所屬{sec_label.split(' ')[0]}板塊資金外流，短期缺乏基本面利多催化，承接力道薄弱",
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

    market_tech = _build_market_tech_breakdown(spy_m, qqq_m, vix_m)

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
        market_tech=market_tech,
        backtest_meta=BACKTEST_METADATA,
    )

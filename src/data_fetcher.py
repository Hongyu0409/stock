"""Data fetching and technical / volatility indicator calculation module."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class TickerMetrics:
    """Computed weekly volatility, momentum, and technical metrics for a single ticker."""

    symbol: str
    name: str
    sector: str
    last_date: str
    close: float
    open_price: float
    high: float
    low: float
    volume: float

    # Return metrics (%)
    ret_1d_pct: float
    ret_5d_pct: float
    ret_20d_pct: float

    # Weekly Volatility & Amplitude metrics
    week_high: float
    week_low: float
    week_range_pct: float        # (5D High - 5D Low) / 5D Low * 100
    week_max_dd_pct: float       # Max drawdown within last 5 trading days (%)
    gap_1d_pct: float            # Latest session opening gap (%)
    atr_14: float                # 14-day ATR ($)
    natr_14_pct: float           # 14-day ATR / Close (%)
    hv_5_pct: float              # 5-day annualized Historical Volatility (%)
    hv_20_pct: float             # 20-day annualized Historical Volatility (%)
    hv_ratio: float              # hv_5_pct / hv_20_pct (Volatility expansion ratio)

    # Trend & Moving Averages
    ma_20: float
    ma_50: float
    ma_200: float
    dist_ma20_pct: float         # (Close - MA20) / MA20 * 100
    dist_ma50_pct: float         # (Close - MA50) / MA50 * 100
    dist_ma200_pct: float        # (Close - MA200) / MA200 * 100

    # Momentum, Volume & Price levels
    rsi_14: float
    vol_ratio_1d: float          # Latest volume / 20D avg volume
    vol_ratio_5d: float          # 5D avg volume / 20D avg volume
    high_20d: float
    low_20d: float
    prev_high_20d: float         # 20D high excluding latest day (for breakout check)
    prev_low_20d: float          # 20D low excluding latest day (for breakdown check)
    bb_width_pct: float          # Bollinger Bandwidth (20, 2) (%)


def compute_rsi(series: pd.Series, period: int = 14) -> float:
    """Calculate Wilder's RSI for the latest bar."""
    if len(series) < period + 1:
        return 50.0
    delta = series.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    last_gain = float(avg_gain.iloc[-1])
    last_loss = float(avg_loss.iloc[-1])
    if last_loss == 0:
        return 100.0
    rs = last_gain / last_loss
    return float(100.0 - (100.0 / (1.0 + rs)))


def compute_atr(df: pd.DataFrame, period: int = 14) -> float:
    """Calculate Wilder's Average True Range (ATR)."""
    high = df["High"]
    low = df["Low"]
    prev_close = df["Close"].shift(1)
    tr = pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    atr_series = tr.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    val = float(atr_series.iloc[-1])
    return val if not np.isnan(val) else float((high.iloc[-1] - low.iloc[-1]))


def calculate_metrics_from_df(
    symbol: str,
    df: pd.DataFrame,
    name: str = "",
    sector: str = "",
    atr_period: int = 14,
    rsi_period: int = 14,
) -> Optional[TickerMetrics]:
    """Compute TickerMetrics from a daily OHLCV DataFrame."""
    clean = df.dropna(subset=["Close", "High", "Low", "Open"]).copy()
    if len(clean) < 25:
        logger.warning("Ticker %s has insufficient history (%d rows), skipping.", symbol, len(clean))
        return None

    close_s = clean["Close"].astype(float)
    open_s = clean["Open"].astype(float)
    high_s = clean["High"].astype(float)
    low_s = clean["Low"].astype(float)
    vol_s = clean["Volume"].fillna(0).astype(float) if "Volume" in clean.columns else pd.Series(0.0, index=clean.index)

    last_idx = clean.index[-1]
    last_date = last_idx.strftime("%Y-%m-%d") if hasattr(last_idx, "strftime") else str(last_idx)[:10]

    close = float(close_s.iloc[-1])
    open_p = float(open_s.iloc[-1])
    high = float(high_s.iloc[-1])
    low = float(low_s.iloc[-1])
    volume = float(vol_s.iloc[-1])

    prev_close_1d = float(close_s.iloc[-2]) if len(close_s) >= 2 else close
    prev_close_5d = float(close_s.iloc[-6]) if len(close_s) >= 6 else float(close_s.iloc[0])
    prev_close_20d = float(close_s.iloc[-21]) if len(close_s) >= 21 else float(close_s.iloc[0])

    ret_1d_pct = ((close / prev_close_1d) - 1.0) * 100.0 if prev_close_1d else 0.0
    ret_5d_pct = ((close / prev_close_5d) - 1.0) * 100.0 if prev_close_5d else 0.0
    ret_20d_pct = ((close / prev_close_20d) - 1.0) * 100.0 if prev_close_20d else 0.0

    # Weekly (5 trading days) window
    week_high = float(high_s.iloc[-5:].max())
    week_low = float(low_s.iloc[-5:].min())
    week_range_pct = ((week_high - week_low) / week_low * 100.0) if week_low > 0 else 0.0

    # 5-day max drawdown from peak high to subsequent low
    week_closes = close_s.iloc[-6:]
    running_max = week_closes.cummax()
    dd_series = (week_closes - running_max) / running_max * 100.0
    week_max_dd_pct = float(dd_series.min())

    gap_1d_pct = ((open_p - prev_close_1d) / prev_close_1d * 100.0) if prev_close_1d > 0 else 0.0

    atr_14 = compute_atr(clean, period=atr_period)
    natr_14_pct = (atr_14 / close * 100.0) if close > 0 else 0.0

    # Historical Volatility (annualized std of log returns)
    log_rets = np.log(close_s / close_s.shift(1)).dropna()
    hv_5 = float(log_rets.iloc[-5:].std(ddof=1) * np.sqrt(252) * 100.0) if len(log_rets) >= 5 else natr_14_pct * 12.0
    hv_20 = float(log_rets.iloc[-20:].std(ddof=1) * np.sqrt(252) * 100.0) if len(log_rets) >= 20 else hv_5
    if np.isnan(hv_5) or hv_5 <= 0:
        hv_5 = natr_14_pct * np.sqrt(252)
    if np.isnan(hv_20) or hv_20 <= 0:
        hv_20 = hv_5
    hv_ratio = hv_5 / hv_20 if hv_20 > 0 else 1.0

    # Moving averages
    ma_20 = float(close_s.iloc[-20:].mean())
    ma_50 = float(close_s.iloc[-50:].mean()) if len(close_s) >= 50 else ma_20
    ma_200 = float(close_s.iloc[-200:].mean()) if len(close_s) >= 200 else ma_50

    dist_ma20_pct = ((close - ma_20) / ma_20 * 100.0) if ma_20 > 0 else 0.0
    dist_ma50_pct = ((close - ma_50) / ma_50 * 100.0) if ma_50 > 0 else 0.0
    dist_ma200_pct = ((close - ma_200) / ma_200 * 100.0) if ma_200 > 0 else 0.0

    rsi_14 = compute_rsi(close_s, period=rsi_period)

    # Volume ratios
    vol_ma20 = float(vol_s.iloc[-21:-1].mean()) if len(vol_s) >= 21 else float(vol_s.mean())
    vol_ma5 = float(vol_s.iloc[-5:].mean())
    vol_ratio_1d = (volume / vol_ma20) if vol_ma20 > 0 else 1.0
    vol_ratio_5d = (vol_ma5 / vol_ma20) if vol_ma20 > 0 else 1.0

    high_20d = float(high_s.iloc[-20:].max())
    low_20d = float(low_s.iloc[-20:].min())
    prev_high_20d = float(high_s.iloc[-21:-1].max()) if len(high_s) >= 21 else high_20d
    prev_low_20d = float(low_s.iloc[-21:-1].min()) if len(low_s) >= 21 else low_20d

    # Bollinger Bandwidth (20, 2)
    std_20 = float(close_s.iloc[-20:].std(ddof=0))
    bb_upper = ma_20 + 2.0 * std_20
    bb_lower = ma_20 - 2.0 * std_20
    bb_width_pct = ((bb_upper - bb_lower) / ma_20 * 100.0) if ma_20 > 0 else 0.0

    return TickerMetrics(
        symbol=symbol,
        name=name or symbol,
        sector=sector,
        last_date=last_date,
        close=close,
        open_price=open_p,
        high=high,
        low=low,
        volume=volume,
        ret_1d_pct=ret_1d_pct,
        ret_5d_pct=ret_5d_pct,
        ret_20d_pct=ret_20d_pct,
        week_high=week_high,
        week_low=week_low,
        week_range_pct=week_range_pct,
        week_max_dd_pct=week_max_dd_pct,
        gap_1d_pct=gap_1d_pct,
        atr_14=atr_14,
        natr_14_pct=natr_14_pct,
        hv_5_pct=hv_5,
        hv_20_pct=hv_20,
        hv_ratio=hv_ratio,
        ma_20=ma_20,
        ma_50=ma_50,
        ma_200=ma_200,
        dist_ma20_pct=dist_ma20_pct,
        dist_ma50_pct=dist_ma50_pct,
        dist_ma200_pct=dist_ma200_pct,
        rsi_14=rsi_14,
        vol_ratio_1d=vol_ratio_1d,
        vol_ratio_5d=vol_ratio_5d,
        high_20d=high_20d,
        low_20d=low_20d,
        prev_high_20d=prev_high_20d,
        prev_low_20d=prev_low_20d,
        bb_width_pct=bb_width_pct,
    )


def fetch_all_tickers(
    config: dict,
    use_demo: bool = False,
) -> Dict[str, TickerMetrics]:
    """Fetch OHLCV data for all configured indices, macro, sector ETFs, and stocks."""
    ticker_meta: Dict[str, tuple[str, str]] = {}  # symbol -> (name, sector)

    for sym, label in config.get("market_indices", {}).items():
        ticker_meta[sym] = (label, "INDEX")
    for sym, label in config.get("macro_indicators", {}).items():
        ticker_meta[sym] = (label, "MACRO")
    for sym, label in config.get("sector_etfs", {}).items():
        ticker_meta[sym] = (label, sym)

    for sector_code, symbols in config.get("stock_universe", {}).items():
        for sym in symbols:
            if sym not in ticker_meta:
                ticker_meta[sym] = (sym, sector_code)

    if use_demo:
        logger.info("Using simulated demo market dataset (--demo mode)...")
        return generate_demo_metrics(ticker_meta, config)

    symbols_list = list(ticker_meta.keys())
    logger.info("Fetching market data from Yahoo Finance for %d symbols...", len(symbols_list))

    try:
        import yfinance as yf

        raw = yf.download(
            tickers=symbols_list,
            period="1y",
            interval="1d",
            group_by="ticker",
            auto_adjust=True,
            threads=True,
            progress=False,
        )
        # During US Winter Time (05:00-09:20 Taiwan Time / 16:00-20:20 EST),
        # US regular trading has already closed at 05:00 TW, but Yahoo's 1y/1d endpoint
        # may not roll over the latest daily bar until after 20:00 EST post-market closes.
        # Fetching 5d/1h regular-session bars (prepost=False) guarantees we always have
        # today's 05:00 TW closing OHLCV immediately after market close.
        raw_1h = yf.download(
            tickers=symbols_list,
            period="5d",
            interval="1h",
            group_by="ticker",
            auto_adjust=True,
            prepost=False,
            threads=True,
            progress=False,
        )
    except Exception as exc:
        logger.error("Failed to download from Yahoo Finance (%s). Falling back to demo dataset.", exc)
        return generate_demo_metrics(ticker_meta, config)

    if raw is None or raw.empty:
        logger.warning("Empty response from Yahoo Finance. Falling back to demo dataset.")
        return generate_demo_metrics(ticker_meta, config)

    strat = config.get("strategy_params", {})
    atr_period = int(strat.get("atr_period", 14))
    rsi_period = int(strat.get("rsi_period", 14))

    results: Dict[str, TickerMetrics] = {}
    for sym, (name, sector) in ticker_meta.items():
        try:
            if isinstance(raw.columns, pd.MultiIndex):
                if sym not in raw.columns.get_level_values(0):
                    continue
                sub_df = raw[sym].copy()
            else:
                sub_df = raw.copy()

            sub_df = sub_df.dropna(subset=["Close", "High", "Low", "Open"])

            # Merge any newer completed regular session from 1h bars if 1d bars lagged
            if raw_1h is not None and not raw_1h.empty:
                try:
                    if isinstance(raw_1h.columns, pd.MultiIndex):
                        sub_1h = raw_1h[sym].copy() if sym in raw_1h.columns.get_level_values(0) else pd.DataFrame()
                    else:
                        sub_1h = raw_1h.copy()
                    sub_1h = sub_1h.dropna(subset=["Close", "High", "Low", "Open"])
                    if not sub_1h.empty:
                        if getattr(sub_1h.index, "tz", None) is not None:
                            sub_1h.index = sub_1h.index.tz_convert("America/New_York")
                        sub_1h["_date"] = sub_1h.index.strftime("%Y-%m-%d")
                        daily_1h = sub_1h.groupby("_date").agg(
                            {
                                "Open": "first",
                                "High": "max",
                                "Low": "min",
                                "Close": "last",
                                "Volume": "sum",
                            }
                        )
                        existing_dates = {
                            (idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)[:10])
                            for idx in sub_df.index
                        }
                        new_rows = []
                        for d_str, row in daily_1h.iterrows():
                            if d_str not in existing_dates and (not existing_dates or d_str > max(existing_dates)):
                                new_rows.append((pd.Timestamp(d_str), row))
                        if new_rows:
                            if getattr(sub_df.index, "tz", None) is not None:
                                sub_df.index = sub_df.index.tz_localize(None)
                            for ts_idx, row in new_rows:
                                sub_df.loc[ts_idx, ["Open", "High", "Low", "Close", "Volume"]] = [
                                    row["Open"],
                                    row["High"],
                                    row["Low"],
                                    row["Close"],
                                    row["Volume"],
                                ]
                            sub_df = sub_df.sort_index()
                except Exception as merge_exc:
                    logger.debug("1h merge skipped for %s: %s", sym, merge_exc)

            metrics = calculate_metrics_from_df(
                symbol=sym,
                df=sub_df,
                name=name,
                sector=sector,
                atr_period=atr_period,
                rsi_period=rsi_period,
            )
            if metrics is not None:
                results[sym] = metrics
        except Exception as exc:
            logger.debug("Skipping %s due to calculation error: %s", sym, exc)

    if len(results) < 5:
        logger.warning("Too few tickers fetched (%d). Falling back to demo dataset.", len(results))
        return generate_demo_metrics(ticker_meta, config)

    logger.info("Successfully computed metrics for %d/%d tickers.", len(results), len(symbols_list))
    return results


def generate_demo_metrics(
    ticker_meta: Dict[str, tuple[str, str]],
    config: dict,
) -> Dict[str, TickerMetrics]:
    """Generate realistic synthetic US stock market data for testing and offline preview."""
    rng = np.random.default_rng(seed=42)
    today_str = datetime.now().strftime("%Y-%m-%d")
    dates = pd.bdate_range(end=today_str, periods=220)

    # Curated realistic profiles for key tickers so demo output showcases all strategies clearly
    presets = {
        "SPY": (585.0, 0.006, 0.021, 0.008, 1.1),
        "QQQ": (505.0, 0.009, 0.031, 0.011, 1.25),
        "DIA": (435.0, 0.003, 0.012, 0.007, 0.95),
        "IWM": (224.0, -0.004, 0.008, 0.014, 1.15),
        "SOXX": (235.0, 0.015, 0.048, 0.018, 1.45),
        "^VIX": (15.4, -0.055, -0.142, 0.055, 1.10),
        "^TNX": (4.28, -0.008, 0.015, 0.015, 1.0),
        "GLD": (254.0, 0.005, 0.018, 0.009, 1.05),
        "BTC-USD": (75800.0, 0.028, 0.084, 0.032, 1.5),
        # Sector ETFs
        "XLK": (232.0, 0.012, 0.036, 0.012, 1.3),
        "XLC": (94.0, 0.008, 0.025, 0.010, 1.15),
        "XLY": (205.0, 0.007, 0.022, 0.011, 1.1),
        "XLF": (48.5, 0.005, 0.019, 0.009, 1.05),
        "XLI": (138.0, 0.004, 0.014, 0.008, 1.0),
        "XLU": (81.0, 0.002, 0.009, 0.009, 0.95),
        "XLV": (148.0, -0.003, -0.008, 0.008, 0.9),
        "XLP": (81.5, -0.002, -0.005, 0.006, 0.85),
        "XLB": (93.0, -0.005, -0.011, 0.010, 0.95),
        "XLE": (90.5, -0.011, -0.024, 0.015, 1.2),
        "XLRE": (42.5, -0.007, -0.018, 0.011, 1.05),
        # Momentum Breakout candidates
        "NVDA": (146.5, 0.034, 0.078, 0.028, 1.92),
        "PLTR": (55.8, 0.048, 0.145, 0.036, 2.35),
        "ANET": (418.0, 0.027, 0.064, 0.024, 1.74),
        "AVGO": (182.4, 0.022, 0.056, 0.023, 1.58),
        # Pullback in Uptrend candidates
        "META": (588.0, 0.006, -0.018, 0.019, 0.92),
        "MSFT": (426.0, 0.005, -0.012, 0.014, 0.88),
        "AMZN": (208.5, 0.008, -0.015, 0.017, 0.95),
        "COST": (912.0, 0.004, -0.019, 0.012, 0.90),
        # Bearish Breakdown / Risk Alert candidates
        "SMCI": (24.2, -0.085, -0.265, 0.068, 2.85),
        "NKE": (75.4, -0.032, -0.068, 0.025, 1.75),
        "XOM": (115.2, -0.021, -0.046, 0.018, 1.52),
        "BA": (148.5, -0.026, -0.058, 0.026, 1.65),
    }

    results: Dict[str, TickerMetrics] = {}
    for sym, (name, sector) in ticker_meta.items():
        if sym in presets:
            base_price, r1d, r5d, daily_vol, vol_mult = presets[sym]
        else:
            base_price = float(rng.uniform(45.0, 380.0))
            r1d = float(rng.normal(0.002, 0.015))
            r5d = float(r1d + rng.normal(0.005, 0.028))
            daily_vol = float(rng.uniform(0.012, 0.030))
            vol_mult = float(rng.uniform(0.75, 1.65))

        # Construct synthetic 220-day series aligned with target r1d and r5d
        daily_rets = rng.normal(0.0007, daily_vol, size=len(dates))
        # Shape last 5 days to match r5d and r1d
        FourD_ret = (1.0 + r5d) / (1.0 + r1d) - 1.0
        for i in range(-5, -1):
            daily_rets[i] = FourD_ret / 4.0 + rng.normal(0, daily_vol * 0.25)
        daily_rets[-1] = r1d

        # Adjust pullbacks / breakdowns / breakouts so moving averages align naturally
        if sym in ("META", "MSFT", "AMZN", "COST"):
            # Uptrend over 200 days, gentle pullback to MA20 in last 5 days
            daily_rets[-60:-6] = np.abs(daily_rets[-60:-6]) * 0.65 + 0.0018
            daily_rets[-5:-1] = -0.0065
            daily_rets[-1] = abs(r1d)
        elif sym in ("SMCI", "NKE", "XOM", "BA"):
            # Breakdown below MA20 & MA50
            daily_rets[-40:-5] = -0.0025
            daily_rets[-5:-1] = (FourD_ret / 4.0)
            daily_rets[-1] = r1d
        elif sym in ("NVDA", "PLTR", "ANET", "AVGO"):
            # Strong uptrend & fresh 20D breakout
            daily_rets[-60:-5] = 0.0022 + rng.normal(0, daily_vol * 0.4, size=55)
            daily_rets[-5:-1] = FourD_ret / 4.0
            daily_rets[-1] = r1d

        price_path = np.cumprod(1.0 + daily_rets)
        price_path = price_path / price_path[-1] * base_price

        intraday_spread = daily_vol * 1.35
        high_path = price_path * (1.0 + np.abs(rng.normal(intraday_spread * 0.55, intraday_spread * 0.2, size=len(dates))))
        low_path = price_path * (1.0 - np.abs(rng.normal(intraday_spread * 0.55, intraday_spread * 0.2, size=len(dates))))
        open_path = np.roll(price_path, 1) * (1.0 + rng.normal(0, daily_vol * 0.2, size=len(dates)))
        open_path[0] = price_path[0]
        high_path = np.maximum(high_path, np.maximum(price_path, open_path))
        low_path = np.minimum(low_path, np.minimum(price_path, open_path))

        vol_base = rng.uniform(5_000_000, 45_000_000, size=len(dates))
        vol_base[-1] = float(np.mean(vol_base[-21:-1]) * vol_mult)
        vol_base[-5:-1] = float(np.mean(vol_base[-21:-1]) * (0.85 + 0.3 * vol_mult))

        df = pd.DataFrame(
            {
                "Open": open_path,
                "High": high_path,
                "Low": low_path,
                "Close": price_path,
                "Volume": vol_base,
            },
            index=dates,
        )
        m = calculate_metrics_from_df(sym, df, name=name, sector=sector)
        if m is not None:
            results[sym] = m

    return results

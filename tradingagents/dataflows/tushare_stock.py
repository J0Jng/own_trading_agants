"""Tushare stock price data and technical indicators.

Non-A-share tickers are forwarded to MX (妙想) as the fallback
instead of yfinance, keeping all data within domestic Chinese sources.
"""

import logging
from datetime import datetime

import pandas as pd
from dateutil.relativedelta import relativedelta

from .config import get_config
from .tushare_common import (
    _call_pro,
    _dataframe_to_csv_string,
    _normalise_ticker,
    get_pro,
)

logger = logging.getLogger(__name__)

BEST_IND_PARAMS = {
    "close_50_sma": (
        "50 SMA: A medium-term trend indicator. "
        "Usage: Identify trend direction and serve as dynamic support/resistance. "
        "Tips: It lags price; combine with faster indicators for timely signals."
    ),
    "close_200_sma": (
        "200 SMA: A long-term trend benchmark. "
        "Usage: Confirm overall market trend and identify golden/death cross setups. "
        "Tips: It reacts slowly; best for strategic trend confirmation rather than frequent trading entries."
    ),
    "close_10_ema": (
        "10 EMA: A responsive short-term average. "
        "Usage: Capture quick shifts in momentum and potential entry points. "
        "Tips: Prone to noise in choppy markets; use alongside longer averages for filtering false signals."
    ),
    "macd": (
        "MACD: Computes momentum via differences of EMAs. "
        "Usage: Look for crossovers and divergence as signals of trend changes. "
        "Tips: Confirm with other indicators in low-volatility or sideways markets."
    ),
    "macds": (
        "MACD Signal: An EMA smoothing of the MACD line. "
        "Usage: Use crossovers with the MACD line to trigger trades. "
        "Tips: Should be part of a broader strategy to avoid false positives."
    ),
    "macdh": (
        "MACD Histogram: Shows the gap between the MACD line and its signal. "
        "Usage: Visualize momentum strength and spot divergence early. "
        "Tips: Can be volatile; complement with additional filters in fast-moving markets."
    ),
    "rsi": (
        "RSI: Measures momentum to flag overbought/oversold conditions. "
        "Usage: Apply 70/30 thresholds and watch for divergence to signal reversals. "
        "Tips: In strong trends, RSI may remain extreme; always cross-check with trend analysis."
    ),
    "boll": (
        "Bollinger Middle: A 20 SMA serving as the basis for Bollinger Bands. "
        "Usage: Acts as a dynamic benchmark for price movement. "
        "Tips: Combine with the upper and lower bands to effectively spot breakouts or reversals."
    ),
    "boll_ub": (
        "Bollinger Upper Band: Typically 2 standard deviations above the middle line. "
        "Usage: Signals potential overbought conditions and breakout zones. "
        "Tips: Confirm signals with other tools; prices may ride the band in strong trends."
    ),
    "boll_lb": (
        "Bollinger Lower Band: Typically 2 standard deviations below the middle line. "
        "Usage: Indicates potential oversold conditions. "
        "Tips: Use additional analysis to avoid false reversal signals."
    ),
    "atr": (
        "ATR: Averages true range to measure volatility. "
        "Usage: Set stop-loss levels and adjust position sizes based on current market volatility. "
        "Tips: It's a reactive measure, so use it as part of a broader risk management strategy."
    ),
    "vwma": (
        "VWMA: A moving average weighted by volume. "
        "Usage: Confirm trends by integrating price action with volume data. "
        "Tips: Watch for skewed results from volume spikes; use in combination with other volume analyses."
    ),
    "mfi": (
        "MFI: The Money Flow Index is a momentum indicator that uses both price and volume "
        "to measure buying and selling pressure. "
        "Usage: Identify overbought (>80) or oversold (<20) conditions and confirm the strength "
        "of trends or reversals. "
        "Tips: Use alongside RSI or MACD to confirm signals; divergence between price and MFI "
        "can indicate potential reversals."
    ),
}


def get_tushare_stock_data(symbol: str, start_date: str, end_date: str) -> str:
    """Retrieve OHLCV stock data from tushare.

    Uses the tushare ``daily`` API for A-shares; falls back to MX (妙想)
    for non-A-share tickers.
    """
    ts_code = _normalise_ticker(symbol)
    if "." not in ts_code or ts_code.split(".")[-1] not in ("SH", "SZ", "BJ"):
        from .mx_data import get_mx_stock_data
        return get_mx_stock_data(symbol, start_date, end_date)

    datetime.strptime(start_date, "%Y-%m-%d")
    datetime.strptime(end_date, "%Y-%m-%d")

    pro = get_pro()

    try:
        df = pro.daily(
            ts_code=ts_code,
            start_date=start_date.replace("-", ""),
            end_date=end_date.replace("-", ""),
        )
    except Exception as e:
        logger.error("tushare daily failed for %s: %s", ts_code, e)
        return f"Error retrieving stock data for {symbol} from tushare: {str(e)}"

    if df is None or df.empty:
        return f"No stock data found for '{symbol}' from {start_date} to {end_date}"

    df = df.sort_values("trade_date").reset_index(drop=True)
    df.rename(
        columns={
            "trade_date": "Date",
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "vol": "Volume",
        },
        inplace=True,
    )

    for col in ["Open", "High", "Low", "Close"]:
        if col in df.columns:
            df.loc[:, col] = df[col].round(2)

    header = f"# Stock data for {ts_code} from {start_date} to {end_date} (via tushare)\n"
    return _dataframe_to_csv_string(df, header)


def get_tushare_indicators(
    symbol: str,
    indicator: str,
    curr_date: str,
    look_back_days: int = 30,
) -> str:
    """Retrieve technical indicators using stockstats from tushare-sourced data.

    Downloads OHLCV from tushare, wraps via stockstats, and returns
    the same format as the yfinance path so the market analyst sees
    consistent indicator output.
    """
    if indicator not in BEST_IND_PARAMS:
        raise ValueError(
            f"Indicator '{indicator}' is not supported. "
            f"Choose from: {list(BEST_IND_PARAMS.keys())}"
        )

    # 非 A 股（港股/美股等）直接走 MX 指标接口，避免必然失败的 pro.daily 调用
    ts_code = _normalise_ticker(symbol)
    if "." not in ts_code or ts_code.split(".")[-1] not in ("SH", "SZ", "BJ"):
        from .mx_data import get_mx_indicators
        return get_mx_indicators(symbol, indicator, curr_date, look_back_days)

    from stockstats import wrap

    curr_date_dt = datetime.strptime(curr_date, "%Y-%m-%d")
    end_date = curr_date
    before = curr_date_dt - relativedelta(days=look_back_days)

    try:
        # Download OHLCV from tushare instead of yfinance
        start_dt = curr_date_dt - relativedelta(years=1)
        start_str = start_dt.strftime("%Y%m%d")
        end_str = curr_date_dt.strftime("%Y%m%d")

        pro = get_pro()
        df = pro.daily(ts_code=ts_code, start_date=start_str, end_date=end_str)
        if df is None or df.empty:
            raise RuntimeError(f"No stock data for {ts_code} from tushare")

        df = df.sort_values("trade_date").reset_index(drop=True)
        df.rename(columns={"trade_date": "Date", "open": "Open", "high": "High",
                          "low": "Low", "close": "Close", "vol": "Volume"}, inplace=True)
        df["Date"] = pd.to_datetime(df["Date"])
        for col in ["Open", "High", "Low", "Close"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df.dropna(subset=["Close"])

        wrapped = wrap(df)
        wrapped["Date"] = wrapped["Date"].dt.strftime("%Y-%m-%d")
        wrapped[indicator]  # triggers stockstats calculation

        result_dict = {}
        for _, row in wrapped.iterrows():
            date_str = row["Date"]
            val = row[indicator]
            result_dict[date_str] = "N/A" if pd.isna(val) else str(val)

        # Walk backwards day-by-day to build the output
        current_dt = curr_date_dt
        ind_string = ""
        while current_dt >= before:
            date_str = current_dt.strftime("%Y-%m-%d")
            value = result_dict.get(date_str, "N/A: Not a trading day")
            ind_string += f"{date_str}: {value}\n"
            current_dt -= relativedelta(days=1)

    except Exception as e:
        logger.warning("tushare indicator failed for %s: %s — falling back to MX", ts_code, e)
        from .mx_data import get_mx_indicators
        return get_mx_indicators(symbol, indicator, curr_date, look_back_days)

    result = (
        f"## {indicator} values from {before.strftime('%Y-%m-%d')} to {end_date} (via tushare):\n\n"
        + ind_string
        + "\n\n"
        + BEST_IND_PARAMS.get(indicator, "No description available.")
    )
    return result

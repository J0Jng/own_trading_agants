"""Tushare data vendor — shared helpers, pro_api singleton, and caching."""

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
import tushare as ts

from .config import get_config
from .errors import VendorNotConfiguredError
from .utils import safe_ticker_component

logger = logging.getLogger(__name__)

_pro_api_cache: Optional[ts.pro_api] = None
_cached_token: Optional[str] = None


def _get_token() -> str:
    token = os.environ.get("TUSHARE_TOKEN", "").strip()
    if not token:
        raise VendorNotConfiguredError(
            "TUSHARE_TOKEN environment variable is not set. "
            "Set it to your tushare pro API token."
        )
    return token


def get_pro() -> ts.pro_api:
    """Return a cached tushare pro_api instance."""
    global _pro_api_cache, _cached_token
    token = _get_token()
    if _pro_api_cache is None or _cached_token != token:
        _pro_api_cache = ts.pro_api(token)
        _cached_token = token
    return _pro_api_cache


def _call_pro(func, **kwargs):
    """Wrap a pro_api call with retry and error handling; return DataFrame or None."""
    pro = get_pro()
    for attempt in range(3):
        try:
            result = func(pro, **kwargs)
            if isinstance(result, pd.DataFrame) and not result.empty:
                return result
            return None
        except Exception as e:
            if attempt < 2:
                logger.warning("tushare API retry %d/2: %s", attempt + 1, e)
            else:
                logger.error("tushare API error after 3 attempts: %s", e)
                return None


def _normalise_ticker(ticker: str) -> str:
    """Convert a ticker to the tushare ts_code format.

    A-share tickers like '600519.SH' or '000001.SZ' pass through.
    US tickers like 'AAPL' are kept as-is for US data.
    """
    ticker = ticker.strip().upper()
    if "." in ticker and ticker.split(".")[-1] in ("SH", "SZ", "BJ"):
        return ticker
    return ticker


def _cache_path(prefix: str, ticker: str, *parts: str) -> Path:
    cache_dir = Path(get_config().get("data_cache_dir", "."))
    cache_dir.mkdir(parents=True, exist_ok=True)
    safe = safe_ticker_component(ticker).upper()
    filename = f"{prefix}_{safe}_" + "_".join(parts) + ".csv"
    return cache_dir / filename


def _load_cache(path: Path) -> pd.DataFrame | None:
    if path.exists():
        try:
            return pd.read_csv(path, encoding="utf-8")
        except Exception:
            return None
    return None


def _save_cache(df: pd.DataFrame, path: Path) -> None:
    df.to_csv(path, index=False, encoding="utf-8")


def _dataframe_to_csv_string(df: pd.DataFrame, header: str) -> str:
    lines = [header, f"# Total records: {len(df)}"]
    lines.append(f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")
    lines.append(df.to_csv(index=False))
    return "\n".join(lines)

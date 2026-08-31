"""Tushare news and insider-transaction data."""

import logging
from datetime import datetime
from typing import Optional

from dateutil.relativedelta import relativedelta

from .config import get_config
from .tushare_common import (
    _call_pro,
    _dataframe_to_csv_string,
    _normalise_ticker,
    get_pro,
)

logger = logging.getLogger(__name__)


def get_tushare_news(ticker: str, start_date: str, end_date: str) -> str:
    """Retrieve news for a specific stock via tushare ``news`` API.

    Falls back to MX for non-A-share tickers.
    """
    ts_code = _normalise_ticker(ticker)
    if "." not in ts_code or ts_code.split(".")[-1] not in ("SH", "SZ", "BJ"):
        from .mx_data import get_mx_news
        return get_mx_news(ticker, start_date, end_date)

    article_limit = get_config().get("news_article_limit", 20)

    def _fetch(p, **kw):
        return p.news(
            ts_code=ts_code,
            start_date=start_date.replace("-", ""),
            end_date=end_date.replace("-", ""),
            limit=article_limit,
        )

    df = _call_pro(_fetch)

    if df is None or df.empty:
        return f"No news found for {ticker} from {start_date} to {end_date} (via tushare)"

    news_str = f"## {ticker} News (via tushare), from {start_date} to {end_date}:\n\n"
    for _, row in df.head(article_limit).iterrows():
        title = row.get("title", "No title")
        content = row.get("content", "")
        source = row.get("source", "Unknown")
        news_str += f"### {title} (source: {source})\n"
        if content:
            news_str += f"{content[:500]}\n"
        news_str += "\n"

    return news_str


def get_tushare_global_news(
    curr_date: str,
    look_back_days: Optional[int] = None,
    limit: Optional[int] = None,
) -> str:
    """Retrieve global / macro news.

    Delegates to MX (妙想) for broad macro coverage via East Money search.
    """
    from .mx_data import get_mx_global_news
    return get_mx_global_news(curr_date, look_back_days, limit)


def get_tushare_insider_transactions(ticker: str) -> str:
    """Retrieve insider / holder trade data via tushare ``stk_holdertrade``.

    Falls back to MX for non-A-share tickers.
    """
    ts_code = _normalise_ticker(ticker)
    if "." not in ts_code or ts_code.split(".")[-1] not in ("SH", "SZ", "BJ"):
        from .mx_data import get_mx_insider_transactions
        return get_mx_insider_transactions(ticker)

    def _fetch(p, **kw):
        return p.stk_holdertrade(ts_code=ts_code)

    df = _call_pro(_fetch)

    if df is None or df.empty:
        return f"No insider transaction data found for '{ticker}' (via tushare)"

    header = f"# Insider / Holder Trade data for {ts_code} (via tushare)\n"
    return _dataframe_to_csv_string(df, header)

"""MX (妙想) data vendor — natural-language financial data via East Money.

Two API endpoints are used:
- ``/claw/query`` (structured data) for OHLCV, indicators, financials, insider
- ``/claw/news-search`` (news search) for ticker news and global macro news

All data stays within domestic Chinese sources — no foreign vendor fallbacks.

Rate limiting: calls are throttled to one every 1.2 seconds to respect
the MX API speed limit. Rate-limit errors (code 113) trigger a 5-second
backoff before retry.
"""

import logging
import os
import time
from datetime import datetime
from threading import Lock
from typing import Any, Dict, List, Optional

import pandas as pd
import requests

from .config import get_config
from .errors import VendorNotConfiguredError

logger = logging.getLogger(__name__)

MX_API_URL = "https://mkapi2.dfcfs.com/finskillshub/api/claw/query"
MX_NEWS_API_URL = "https://mkapi2.dfcfs.com/finskillshub/api/claw/news-search"

# Minimum interval between MX API calls (seconds). MX 妙想 has a speed
# limit; spacing calls avoids hitting it during multi-tool agent runs.
# Override via config key ``mx_min_call_interval``.
_MIN_CALL_INTERVAL = 1.2

# Backoff base (seconds) when a rate-limit (status 113) is returned.
_RATE_LIMIT_BACKOFF_BASE = 5.0

# Maximum retries per call.
_MAX_RETRIES = 3

# Global state for inter-call throttling.
_last_call_time: float = 0.0
_rate_lock = Lock()


def _get_mx_timeout() -> int:
    """Return the configured MX request timeout (seconds)."""
    return get_config().get("mx_request_timeout", 30)


def _get_mx_interval() -> float:
    """Return the configured minimum interval between MX calls (seconds)."""
    return get_config().get("mx_min_call_interval", 1.2)


def _get_mx_api_key() -> str:
    key = os.environ.get("MX_APIKEY", "").strip()
    if not key:
        raise VendorNotConfiguredError("MX_APIKEY environment variable not set")
    return key


def _rate_limited_post(url: str, json_data: Dict[str, Any], timeout: int) -> requests.Response:
    """POST to a MX API endpoint with inter-call throttling and rate-limit retries.

    - Enforces a minimum interval between successive calls.
    - Retries with exponential backoff on HTTP 429 or MX status 113
      (rate limit / daily quota exceeded).
    """
    global _last_call_time

    for attempt in range(_MAX_RETRIES):
        # Throttle: ensure minimum gap since last call
        with _rate_lock:
            elapsed = time.monotonic() - _last_call_time
            wait = max(0.0, _get_mx_interval() - elapsed)
        if wait > 0:
            time.sleep(wait)

        with _rate_lock:
            _last_call_time = time.monotonic()

        try:
            resp = requests.post(
                url,
                headers={"Content-Type": "application/json", "apikey": _get_mx_api_key()},
                json=json_data,
                timeout=timeout,
            )

            # MX returns a 200 with status code in body for rate-limit
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == 113:
                    # Daily quota or rate limit — back off and retry
                    backoff = _RATE_LIMIT_BACKOFF_BASE * (2 ** attempt)
                    logger.warning(
                        "MX rate limit (status 113) on attempt %d/%d, backing off %.1fs",
                        attempt + 1, _MAX_RETRIES, backoff,
                    )
                    if attempt < _MAX_RETRIES - 1:
                        time.sleep(backoff)
                        continue
                    logger.error("MX rate limit exhausted after %d retries for %s", _MAX_RETRIES, url)
                return resp

            if resp.status_code == 429:
                backoff = _RATE_LIMIT_BACKOFF_BASE * (2 ** attempt)
                logger.warning(
                    "MX HTTP 429 on attempt %d/%d, backing off %.1fs",
                    attempt + 1, _MAX_RETRIES, backoff,
                )
                if attempt < _MAX_RETRIES - 1:
                    time.sleep(backoff)
                    continue
            resp.raise_for_status()
            return resp

        except (requests.Timeout, requests.ConnectionError) as e:
            if attempt < _MAX_RETRIES - 1:
                backoff = 2.0 * (2 ** attempt)
                logger.warning("MX request failed: %s — retry %d/%d in %.1fs", e, attempt + 2, _MAX_RETRIES, backoff)
                time.sleep(backoff)
                continue
            raise

    # Should not reach here, but satisfy the type checker
    raise RuntimeError(f"MX API call failed after {_MAX_RETRIES} retries: {url}")


def _call_mx(query: str, timeout: int = None) -> Dict[str, Any]:
    """Call the MX structured-data API (rate-limited) and return the parsed JSON response."""
    if timeout is None:
        timeout = _get_mx_timeout()
    try:
        resp = _rate_limited_post(MX_API_URL, {"toolQuery": query}, timeout)
        data = resp.json()
        if data.get("status") != 0:
            logger.warning("MX API error: status=%s message=%s", data.get("status"), data.get("message"))
            return {}
        return data
    except Exception as e:
        logger.error("MX API call failed: %s", e)
        return {}


def _call_mx_news_search(query: str, timeout: int = None) -> List[Dict[str, Any]]:
    """Call the MX news-search API (rate-limited) and return a list of article dicts.

    Returns an empty list on any error or no results.
    """
    if timeout is None:
        timeout = _get_mx_timeout()
    try:
        resp = _rate_limited_post(MX_NEWS_API_URL, {"query": query}, timeout)
        data = resp.json()
        if data.get("status") != 0:
            logger.warning(
                "MX news-search API error: status=%s message=%s",
                data.get("status"), data.get("message"),
            )
            return []

        items = []
        try:
            inner = data["data"]["data"]["llmSearchResponse"]["data"]
            items = inner if isinstance(inner, list) else []
        except (KeyError, TypeError):
            logger.warning("MX news-search response missing expected path")
            return []

        return items
    except Exception as e:
        logger.error("MX news-search call failed: %s", e)
        return []


def _format_news_articles(items: List[Dict[str, Any]], label: str, limit: Optional[int] = None) -> str:
    """Format MX news-search results as a readable text block."""
    type_cn_map = {
        "REPORT": "研报",
        "NEWS": "新闻",
        "ANNOUNCEMENT": "公告",
    }

    items = items[:limit] if limit else items

    if not items:
        return f"No {label} articles found via MX"

    lines = [
        f"# {label} (via MX 妙想搜索)",
        f"# Total articles: {len(items)}",
        f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
    ]

    for i, item in enumerate(items, 1):
        title = item.get("title", "无标题")
        content = item.get("content", "")
        date = item.get("date", "")
        ins_name = item.get("insName", "")
        info_type = item.get("informationType", "")
        rating = item.get("rating", "")
        entity_name = item.get("entityFullName", "")

        type_cn = type_cn_map.get(info_type, info_type)

        lines.append(f"--- {i}. {title} ---")

        meta_parts = []
        if entity_name:
            meta_parts.append(f"相关: {entity_name}")
        if ins_name:
            meta_parts.append(f"来源: {ins_name}")
        if date:
            meta_parts.append(f"日期: {date.split()[0]}")
        if type_cn:
            meta_parts.append(f"类型: {type_cn}")
        if rating:
            meta_parts.append(f"评级: {rating}")

        if meta_parts:
            lines.append(" | ".join(meta_parts))

        if content:
            lines.append("")
            # Truncate very long articles to keep prompts manageable
            if len(content) > 800:
                content = content[:800] + "...(截断)"
            lines.append(content)
        lines.append("")

    return "\n".join(lines)


def _get_tables(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract dataTableDTOList from MX structured-data API response."""
    try:
        return result["data"]["data"]["searchDataResultDTO"]["dataTableDTOList"]
    except (KeyError, TypeError):
        return []


def _table_to_dataframe(dto: Dict[str, Any]) -> Optional[pd.DataFrame]:
    """Convert a single MX dataTableDTO to a pandas DataFrame."""
    table = dto.get("table") or {}
    if not isinstance(table, dict):
        return None
    headers = table.get("headName") or []
    if not isinstance(headers, list) or len(headers) == 0:
        return None

    name_map = dto.get("nameMap") or {}
    if isinstance(name_map, list):
        name_map = {str(i): v for i, v in enumerate(name_map)}

    indicator_order = dto.get("indicatorOrder") or []

    data_keys = [k for k in table.keys() if k != "headName"]
    key_order = [k for k in indicator_order if k in data_keys]
    key_order += [k for k in data_keys if k not in key_order]

    rows = []
    for idx, date_val in enumerate(headers):
        row = {"date": str(date_val)}
        for key in key_order:
            col_name = str(name_map.get(key, name_map.get(str(key), str(key))))
            values = table.get(key, [])
            val = values[idx] if idx < len(values) else ""
            row[str(col_name)] = str(val) if val is not None else ""
        rows.append(row)

    if not rows:
        return None
    return pd.DataFrame(rows)


def _dto_list_to_csv(dtos: List[Dict[str, Any]], label: str) -> str:
    """Convert MX table list to CSV string with header."""
    dfs = []
    for dto in dtos:
        df = _table_to_dataframe(dto)
        if df is not None and not df.empty:
            dfs.append(df)
    if not dfs:
        return f"No {label} data available from MX"
    combined = pd.concat(dfs, ignore_index=True)
    header = f"# {label} (via MX)\n# Total records: {len(combined)}\n"
    header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    return header + combined.to_csv(index=False)


def _dto_list_to_kv(dtos: List[Dict[str, Any]], label: str) -> str:
    """Convert MX table list to key: value text (for fundamentals-like data)."""
    lines = [f"# {label} (via MX)", f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ""]
    for dto in dtos:
        df = _table_to_dataframe(dto)
        if df is None or df.empty:
            continue
        for _, row in df.iterrows():
            for col in df.columns:
                lines.append(f"{col}: {row[col]}")
            lines.append("")
    return "\n".join(lines)


# --- Public vendor functions ---

def get_mx_stock_data(symbol: str, start_date: str, end_date: str) -> str:
    """Retrieve OHLCV stock data via MX structured-data query."""
    query = f"{symbol} 从{start_date}到{end_date}每天的开盘价 收盘价 最高价 最低价 成交量"
    logger.info("MX stock query: %s", query)
    result = _call_mx(query)
    dtos = _get_tables(result)
    if not dtos:
        return f"No stock data found for '{symbol}' via MX"
    return _dto_list_to_csv(dtos, f"Stock data for {symbol}")


# MX OHLCV 列名可能为中文或英文，统一映射到 stockstats 所需的标准列名
_OHLCV_COLUMN_ALIASES = {
    "Date": ("date", "Date", "日期", "交易日期", "trade_date"),
    "Open": ("open", "Open", "开盘价", "开盘"),
    "High": ("high", "High", "最高价", "最高"),
    "Low": ("low", "Low", "最低价", "最低"),
    "Close": ("close", "Close", "收盘价", "收盘"),
    "Volume": ("volume", "Volume", "vol", "成交量", "成交"),
}


def _normalise_ohlcv_columns(df: pd.DataFrame) -> Optional[pd.DataFrame]:
    """把 MX OHLCV DataFrame 的列名统一映射为 stockstats 标准列名。

    MX 返回的列名可能是中文（开盘价/收盘价/…）或英文（open/close/…），
    本函数负责兼容两者。缺少必要列（Date/Open/High/Low/Close）时返回 None。
    """
    if df is None or df.empty:
        return None

    rename_map = {}
    for target, aliases in _OHLCV_COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in df.columns:
                rename_map[alias] = target
                break

    df = df.rename(columns=rename_map)

    required = {"Date", "Open", "High", "Low", "Close"}
    if not required.issubset(df.columns):
        return None

    keep = [c for c in ("Date", "Open", "High", "Low", "Close", "Volume") if c in df.columns]
    return df[keep]


def _compute_indicators_locally(
    symbol: str, indicator: str, curr_date: str, look_back_days: int = 30
) -> str:
    """本地兜底：MX 指标接口空表时，用 MX OHLCV + stockstats 计算指标。

    MX 指标接口只覆盖均线族 + ATR，对 RSI/MACD/BOLL/EMA/VWMA 等返回空表。
    此时改为拉取 MX OHLCV（提前约 400 自然日，保证 200 日均线有足够历史），
    再用本地 stockstats 计算，输出格式与 tushare 路径保持一致。
    """
    from datetime import timedelta
    from io import StringIO

    from stockstats import wrap

    curr_dt = datetime.strptime(curr_date, "%Y-%m-%d")
    start_str = (curr_dt - timedelta(days=400)).strftime("%Y-%m-%d")
    before = curr_dt - timedelta(days=look_back_days)

    # 拉取 MX OHLCV（比指标接口更可靠）
    ohlcv_csv = get_mx_stock_data(symbol, start_str, curr_date)
    if ohlcv_csv.startswith("No stock data"):
        return f"No indicator data for '{symbol}' '{indicator}' via MX"

    try:
        df = pd.read_csv(StringIO(ohlcv_csv), comment="#")
        df = _normalise_ohlcv_columns(df)
        if df is None:
            return f"No indicator data for '{symbol}' '{indicator}' via MX"

        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        for col in ["Open", "High", "Low", "Close", "Volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df.dropna(subset=["Close"])
        df = df.sort_values("Date").reset_index(drop=True)

        wrapped = wrap(df)
        wrapped["Date"] = wrapped["Date"].dt.strftime("%Y-%m-%d")
        wrapped[indicator]  # 触发 stockstats 计算

        result_dict = {}
        for _, row in wrapped.iterrows():
            date_str = row["Date"]
            val = row[indicator]
            result_dict[date_str] = "N/A" if pd.isna(val) else str(val)

        # 从 curr_date 起逐日回溯输出（与 tushare 路径一致）
        current_dt = curr_dt
        ind_string = ""
        while current_dt >= before:
            date_str = current_dt.strftime("%Y-%m-%d")
            value = result_dict.get(date_str, "N/A: Not a trading day")
            ind_string += f"{date_str}: {value}\n"
            current_dt -= timedelta(days=1)

        # 复用 tushare 的指标描述（延迟 import 避免循环依赖）
        from .tushare_stock import BEST_IND_PARAMS

        description = BEST_IND_PARAMS.get(indicator, "No description available.")
    except Exception as e:
        logger.warning("本地 stockstats 计算 '%s' '%s' 失败: %s", symbol, indicator, e)
        return f"No indicator data for '{symbol}' '{indicator}' via MX"

    result = (
        f"## {indicator} values from {before.strftime('%Y-%m-%d')} to {curr_date} "
        f"(via MX + local stockstats):\n\n"
        + ind_string
        + "\n\n"
        + description
    )
    return result


def get_mx_indicators(symbol: str, indicator: str, curr_date: str, look_back_days: int = 30) -> str:
    """Retrieve technical indicator data via MX structured-data query."""
    from datetime import timedelta
    curr_dt = datetime.strptime(curr_date, "%Y-%m-%d")
    start_dt = curr_dt - timedelta(days=look_back_days)
    start_str = start_dt.strftime("%Y-%m-%d")

    INDICATOR_NAMES = {
        "rsi": "RSI相对强弱指标",
        "macd": "MACD指标",
        "macds": "MACD信号线",
        "macdh": "MACD柱",
        "close_50_sma": "50日均线",
        "close_200_sma": "200日均线",
        "close_10_ema": "10日指数移动平均线",
        "boll": "布林带中轨",
        "boll_ub": "布林带上轨",
        "boll_lb": "布林带下轨",
        "atr": "ATR平均真实波幅",
        "vwma": "成交量加权移动平均线",
        "mfi": "MFI资金流量指标",
    }
    ind_name = INDICATOR_NAMES.get(indicator, indicator)
    query = f"{symbol} 从{start_str}到{curr_date}每天的{ind_name}"
    result = _call_mx(query)
    dtos = _get_tables(result)
    if not dtos:
        # MX 指标接口只覆盖均线族 + ATR，其余指标返回空表时走本地 stockstats 兜底
        return _compute_indicators_locally(symbol, indicator, curr_date, look_back_days)
    return _dto_list_to_csv(dtos, f"{indicator} for {symbol}")


def get_mx_fundamentals(ticker: str, curr_date: str = None) -> str:
    """Get company fundamentals via MX structured-data query."""
    query = f"{ticker} 每股收益 净资产收益率 营收 净利润 总市值 市盈率 市净率 公司简介"
    result = _call_mx(query)
    dtos = _get_tables(result)
    if not dtos:
        return f"No fundamentals data for '{ticker}' via MX"
    return _dto_list_to_kv(dtos, f"Company Fundamentals for {ticker}")


def get_mx_balance_sheet(ticker: str, freq: str = "quarterly", curr_date: str = None) -> str:
    """Get balance sheet via MX structured-data query."""
    period = "近三年每季度" if freq == "quarterly" else "近五年每年"
    query = f"{ticker} {period}资产负债表 总资产 总负债 股东权益"
    result = _call_mx(query)
    dtos = _get_tables(result)
    if not dtos:
        return f"No balance sheet data for '{ticker}' via MX"
    return _dto_list_to_csv(dtos, f"Balance Sheet for {ticker}")


def get_mx_cashflow(ticker: str, freq: str = "quarterly", curr_date: str = None) -> str:
    """Get cash flow via MX structured-data query."""
    period = "近三年每季度" if freq == "quarterly" else "近五年每年"
    query = f"{ticker} {period}现金流量表 经营活动现金流 投资活动现金流 筹资活动现金流"
    result = _call_mx(query)
    dtos = _get_tables(result)
    if not dtos:
        return f"No cash flow data for '{ticker}' via MX"
    return _dto_list_to_csv(dtos, f"Cash Flow for {ticker}")


def get_mx_income_statement(ticker: str, freq: str = "quarterly", curr_date: str = None) -> str:
    """Get income statement via MX structured-data query."""
    period = "近三年每季度" if freq == "quarterly" else "近五年每年"
    query = f"{ticker} {period}利润表 营业收入 营业成本 营业利润 净利润"
    result = _call_mx(query)
    dtos = _get_tables(result)
    if not dtos:
        return f"No income statement data for '{ticker}' via MX"
    return _dto_list_to_csv(dtos, f"Income Statement for {ticker}")


# --- News functions using dedicated MX news-search API ---

def get_mx_news(ticker: str, start_date: str, end_date: str) -> str:
    """Retrieve stock-specific news via MX news-search API.

    Uses the dedicated ``/claw/news-search`` endpoint which returns
    structured articles (title, content, source, date, type).
    Falls back to tushare if no results.
    """
    article_limit = get_config().get("news_article_limit", 20)
    query = f"{ticker} 从{start_date}到{end_date}的重要新闻公告研报"
    logger.info("MX news-search query: %s", query)
    items = _call_mx_news_search(query)
    if not items:
        logger.info("MX news-search returned no results for %s, falling back to tushare", ticker)
        from .tushare_news import get_tushare_news
        return get_tushare_news(ticker, start_date, end_date)
    return _format_news_articles(items, f"News for {ticker}", limit=article_limit)


def get_mx_global_news(curr_date: str, look_back_days: Optional[int] = None, limit: Optional[int] = None) -> str:
    """Retrieve global/macro news via MX news-search API.

    Uses the dedicated ``/claw/news-search`` endpoint with macro-economic
    query terms. Falls back to tushare if no results.
    """
    from datetime import timedelta
    cfg = get_config()
    if look_back_days is None:
        look_back_days = cfg.get("global_news_lookback_days", 7)
    if limit is None:
        limit = cfg.get("global_news_article_limit", 10)
    curr_dt = datetime.strptime(curr_date, "%Y-%m-%d")
    start_dt = curr_dt - timedelta(days=look_back_days)
    start_str = start_dt.strftime("%Y-%m-%d")

    queries = cfg.get("global_news_queries", [])
    query = f"从{start_str}到{curr_date} {' '.join(queries)}"
    logger.info("MX global news-search query: %s", query)
    items = _call_mx_news_search(query)
    if not items:
        logger.info("MX global news-search returned no results, falling back to tushare")
        from .tushare_news import get_tushare_global_news
        return get_tushare_global_news(curr_date, look_back_days, limit)
    return _format_news_articles(items, "Global News", limit=limit)


def get_mx_insider_transactions(ticker: str) -> str:
    """Retrieve insider transactions via MX structured-data query."""
    query = f"{ticker} 高管增减持 股东交易 大宗交易"
    result = _call_mx(query)
    dtos = _get_tables(result)
    if not dtos:
        return f"No insider transaction data for '{ticker}' via MX"
    return _dto_list_to_csv(dtos, f"Insider Transactions for {ticker}")

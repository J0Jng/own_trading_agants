"""Tushare fundamental / financial statement data."""

import logging
from datetime import datetime

import pandas as pd

from .tushare_common import (
    _call_pro,
    _dataframe_to_csv_string,
    _normalise_ticker,
    get_pro,
)

logger = logging.getLogger(__name__)


def _is_ashare(ts_code: str) -> bool:
    return "." in ts_code and ts_code.split(".")[-1] in ("SH", "SZ", "BJ")


def get_tushare_fundamentals(ticker: str, curr_date: str = None) -> str:
    """Get company fundamentals overview from tushare.

    For A-shares uses ``stock_basic``, ``daily_basic``, and
    ``fina_indicator``. For non-A-share tickers, falls back to MX (妙想).
    """
    ts_code = _normalise_ticker(ticker)
    if not _is_ashare(ts_code):
        from .mx_data import get_mx_fundamentals
        return get_mx_fundamentals(ticker, curr_date)

    pro = get_pro()

    def _fetch_info(p, **kw):
        return p.stock_basic(ts_code=ts_code, fields="ts_code,name,industry")

    info_df = _call_pro(_fetch_info)
    info = info_df.iloc[0].to_dict() if info_df is not None and not info_df.empty else {}

    # daily_basic for valuation metrics
    def _fetch_daily(p, **kw):
        return p.daily_basic(
            ts_code=ts_code,
            trade_date=(curr_date.replace("-", "") if curr_date else datetime.now().strftime("%Y%m%d")),
            fields="close,pe,pe_ttm,pb,ps,ps_ttm,total_mv,circ_mv",
        )

    daily_df = _call_pro(_fetch_daily)
    daily = daily_df.iloc[0].to_dict() if daily_df is not None and not daily_df.empty else {}

    # fina_indicator for profitability / health
    def _fetch_fina(p, **kw):
        return p.fina_indicator(
            ts_code=ts_code,
            fields="roe,roa,grossprofit_margin,netprofit_margin,debt_to_assets,current_ratio,eps,bps,or_yoy,profit_dedt",
        )

    fina_df = _call_pro(_fetch_fina)
    latest = fina_df.iloc[0].to_dict() if fina_df is not None and not fina_df.empty else {}

    fields = [
        ("Name", info.get("name")),
        ("Industry", info.get("industry")),
        ("Market Cap (10k CNY)", daily.get("total_mv")),
        ("Circulating Market Cap", daily.get("circ_mv")),
        ("PE Ratio", daily.get("pe")),
        ("PE Ratio (TTM)", daily.get("pe_ttm")),
        ("Price to Book", daily.get("pb")),
        ("Price to Sales", daily.get("ps")),
        ("Price to Sales (TTM)", daily.get("ps_ttm")),
        ("EPS", latest.get("eps")),
        ("BPS (Book Value Per Share)", latest.get("bps")),
        ("ROE (%)", latest.get("roe")),
        ("ROA (%)", latest.get("roa")),
        ("Gross Profit Margin (%)", latest.get("grossprofit_margin")),
        ("Net Profit Margin (%)", latest.get("netprofit_margin")),
        ("Debt to Assets (%)", latest.get("debt_to_assets")),
        ("Current Ratio", latest.get("current_ratio")),
        ("Revenue YoY (%)", latest.get("or_yoy")),
    ]

    lines = []
    for label, value in fields:
        if value is not None:
            lines.append(f"{label}: {value}")

    header = f"# Company Fundamentals for {ts_code} (via tushare)\n"
    header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    return header + "\n".join(lines)


_FINANCIAL_FIELDS = {
    "balancesheet": "ts_code,ann_date,f_ann_date,end_date,report_type,total_assets,total_liab,total_hldr_eqy_exc_min_int,total_cur_assets,total_cur_liab,inventories,accounts_receiv,goodwill,intan_assets,monetary_cap",
    "cashflow": "ts_code,ann_date,f_ann_date,end_date,report_type,n_cashflow_act,n_cashflow_inv_act,n_cashflow_fin_act,free_cashflow",
    "income": "ts_code,ann_date,f_ann_date,end_date,report_type,total_revenue,revenue,oper_cost,sell_expense,admin_expense,fin_expense,operate_profit,total_profit,n_income,n_income_attr_p",
}


def _fetch_financial_statement(ts_code: str, api_name: str, freq: str, curr_date: str) -> str:
    """Generic fetcher for balance sheet / cashflow / income via tushare."""
    if not _is_ashare(ts_code):
        from .mx_data import (
            get_mx_balance_sheet,
            get_mx_cashflow,
            get_mx_income_statement,
        )
        fallback = {"balancesheet": get_mx_balance_sheet, "cashflow": get_mx_cashflow, "income": get_mx_income_statement}
        return fallback[api_name](ts_code, freq, curr_date)

    fields = _FINANCIAL_FIELDS.get(api_name, "")

    def _fetch(p, **kw):
        fn = getattr(p, api_name)
        kwargs = {"ts_code": ts_code}
        if fields:
            kwargs["fields"] = fields
        return fn(**kwargs)

    df = _call_pro(_fetch)

    if df is None or df.empty:
        return f"No {api_name} data found for '{ts_code}'"

    if curr_date:
        cutoff = pd.Timestamp(curr_date)
        if "end_date" in df.columns:
            df["_end_dt"] = pd.to_datetime(df["end_date"], errors="coerce")
            df = df[df["_end_dt"] <= cutoff]
            df = df.drop(columns=["_end_dt"])

    header = f"# {api_name.capitalize()} data for {ts_code} ({freq}) (via tushare)\n"
    return _dataframe_to_csv_string(df, header)


def get_tushare_balance_sheet(ticker: str, freq: str = "quarterly", curr_date: str = None) -> str:
    return _fetch_financial_statement(_normalise_ticker(ticker), "balancesheet", freq, curr_date)


def get_tushare_cashflow(ticker: str, freq: str = "quarterly", curr_date: str = None) -> str:
    return _fetch_financial_statement(_normalise_ticker(ticker), "cashflow", freq, curr_date)


def get_tushare_income_statement(ticker: str, freq: str = "quarterly", curr_date: str = None) -> str:
    return _fetch_financial_statement(_normalise_ticker(ticker), "income", freq, curr_date)

"""날짜/기간 유틸리티"""
import calendar
from datetime import datetime, timedelta

import pandas as pd


def to_month_end(date: pd.Timestamp | str) -> pd.Timestamp:
    """날짜를 해당 월의 마지막 영업일로 변환"""
    ts = pd.Timestamp(date)
    return ts + pd.offsets.MonthEnd(0)


def to_month_end_bday(date: pd.Timestamp | str) -> pd.Timestamp:
    """날짜를 해당 월의 마지막 영업일(business day)로 변환"""
    ts = pd.Timestamp(date)
    return ts + pd.offsets.BMonthEnd(0)


def resample_to_monthly(
    df: pd.DataFrame,
    value_col: str,
    method: str = "last",
) -> pd.DataFrame:
    """
    일간/주간 DataFrame을 월말 기준으로 리샘플링.

    Args:
        df: [date, value_col] — date는 index 또는 컬럼
        value_col: 값 컬럼명
        method: "last" (월말값), "mean" (월평균)
    Returns:
        월간 DataFrame[date, value_col]
    """
    if "date" in df.columns:
        df = df.set_index("date")

    df.index = pd.DatetimeIndex(df.index)

    if method == "last":
        monthly = df[[value_col]].resample("ME").last()
    elif method == "mean":
        monthly = df[[value_col]].resample("ME").mean()
    else:
        raise ValueError(f"Unknown method: {method}")

    monthly = monthly.dropna()
    monthly = monthly.reset_index()
    monthly.columns = ["date", value_col]
    return monthly


def get_last_friday_of_month(year: int, month: int) -> datetime:
    """해당 월의 마지막 금요일 반환 (CME BTC 만기일)"""
    last_day = calendar.monthrange(year, month)[1]
    date = datetime(year, month, last_day)

    # 금요일(4)까지 역순 탐색
    while date.weekday() != 4:
        date -= timedelta(days=1)

    return date


def days_to_expiry(current_date: pd.Timestamp) -> int:
    """
    현재 날짜에서 CME BTC 근월물 만기까지 잔존일 계산.
    만기 지남 → 다음 월물 만기까지.
    """
    dt = current_date.to_pydatetime() if hasattr(current_date, "to_pydatetime") else current_date
    year, month = dt.year, dt.month

    expiry = get_last_friday_of_month(year, month)

    if dt > expiry:
        # 다음 월물
        if month == 12:
            year += 1
            month = 1
        else:
            month += 1
        expiry = get_last_friday_of_month(year, month)

    delta = (expiry - dt).days
    return max(delta, 1)  # 최소 1일 (0 방지)

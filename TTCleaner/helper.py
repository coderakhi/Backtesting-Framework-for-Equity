import pandas as pd
import datetime as dt
import pandas_market_calendars as mcal
from .constants import EQ_FILE_DIR
import os


def get_eq_min_df(instrument):
    df = pd.read_csv(os.path.join(EQ_FILE_DIR, f"{instrument}-EQ.csv"))
    df["datetime"] = pd.to_datetime(df["datetime"])
    df = df.sort_values("datetime")
    return df


def get_continuous_min_df(df, start_date, end_date):
    assert ({"datetime", "open", "high", "low", "close", "volume", "ticker", "instrument", "expiry", "option_type", "strike", "oi"} - set(df.columns) == set()), "Check you columns"
    df["datetime"] = pd.to_datetime(df["datetime"])
    df = df.sort_values(by="datetime")
    calendar = mcal.get_calendar("NSE")
    valid_dates = list(calendar.schedule(start_date=start_date, end_date=end_date).index.date)
    final_df = pd.DataFrame()
    start_datetime = dt.datetime.combine(date=start_date, time=dt.time(9, 15, 59))
    end_datetime = dt.datetime.combine(date=end_date, time=dt.time(15, 29, 59))
    final_df["datetime"] = pd.date_range(start=start_datetime, end=end_datetime, freq="1min")
    condition = (final_df["datetime"].dt.date.isin(valid_dates)) & (final_df["datetime"].dt.time >= dt.time(9, 15, 59)) & (final_df["datetime"].dt.time <= dt.time(15, 29, 59))
    final_df = final_df[condition]
    result_df = pd.merge_asof(final_df, df, on="datetime")
    result_df = result_df.ffill().bfill()
    return result_df

def clean_kiteconnect_min_eq_data(data, instrument_file_row):
    data_df = pd.DataFrame(data=data)
    data_df = data_df.rename(columns={"date": "datetime"})
    data_df["datetime"] = pd.to_datetime(data_df["datetime"])
    data_df["datetime"] = data_df["datetime"].dt.tz_localize(None)
    data_df["ticker"] = f"{instrument_file_row['tradingsymbol']}-EQ"
    data_df["instrument"] = instrument_file_row['tradingsymbol']
    data_df["expiry"] = None
    data_df["option_type"] = None
    data_df["strike"] = None
    data_df["oi"] = None
    data_df = get_continuous_min_df(df=data_df, start_date=data_df["datetime"].dt.date.min(), end_date=data_df["datetime"].dt.date.max())
    return data_df


def save_to_min_eq_files(data_df, instrument_file_row):
    data_df.to_csv(os.path.join(EQ_FILE_DIR, f"{instrument_file_row['tradingsymbol']}-EQ.csv"), index=False)
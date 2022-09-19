import pandas as pd
import datetime as dt
import pandas_market_calendars as mcal



def get_continious_min_data(df,start_date,end_date):
    assert({'date','open','high','low','close','volume'}-set(df.columns)==set())
    df['date']=pd.to_datetime(df['date'])
    df=df.sort_values(by='date')
    calendar=mcal.get_calendar('NSE')
    valid_dates=calendar.schedule(start_date=start_date,end_date=end_date).index.date
    final_df=pd.DataFrame()
    start_date_time=dt.datetime.combine(start_date=start_date,time=dt.time(9,15,59))
    end_date_time=dt.datetime.combine(ebd_date=end_date,time=dt.time(3,29,59))
    final_df['date_time']=pd.date_range(start_date_time,end_date_time,freq='1min')




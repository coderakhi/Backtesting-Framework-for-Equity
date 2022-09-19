import pandas as pd
from .constants import Interval
import pandas_market_calendars as mcal
import datetime as dt
import pprint



class ChartWindow:
    def __init__(self, df, additional_intervals=None):
        if additional_intervals is None:
            additional_intervals = list()
        assert ({"ticker", "datetime", "instrument", "expiry", "strike", "option_type", "open", "high", "low", "close", "volume", "oi"} - set(df.columns)) == set(), "Some columns are missing, please check"
        assert set(additional_intervals) - {Interval.MINUTE3, Interval.MINUTE5, Interval.MINUTE15, Interval.MINUTE30, Interval.MINUTE45, Interval.HOUR, Interval.DAY, Interval.WEEK, Interval.MONTH} == set(), "Invalid Intervals present"
        assert len(df) > 0, "Length of Dataframe should be greater then 0"
        self.df = df.set_index("datetime")
        self.df = self.df.sort_index()
        self.main_cols = ["open", "high", "low", "close", "volume", "oi"]
        self.start_date = self.df.index.date.min()
        self.end_date = self.df.index.date.max()
        self.current_datetime = None
        self.additional_intervals = additional_intervals
        self.candle_timings = {}
        self.additional_candle_current_timings = {}
        self.screens = {}

        row = dict(self.df.iloc[0][self.main_cols])

        for interval in  self.additional_intervals:
            self.candle_timings[interval] = Interval.get_candle_timings(self.start_date, self.end_date, interval)
            self.additional_candle_current_timings[interval] = self.candle_timings[interval].pop(0)
            start_candle = self.additional_candle_current_timings[interval].get("start_candle")
            self.screens[interval] = pd.DataFrame(columns=self.main_cols, data=[row], index=[start_candle])


    def update_current_datetime(self, current_datetime):
        self.current_datetime = current_datetime
        updated_candle = self.df.loc[current_datetime, self.main_cols]

        for interval in  self.additional_intervals:
            if self.current_datetime <= self.additional_candle_current_timings[interval].get("end_candle"):
                last_candle_index = self.screens[interval].iloc[-1].name
                old_candle = dict(self.screens[interval].iloc[-1])
                old_candle["high"] = max(old_candle["high"], updated_candle["high"])
                old_candle["low"] = min(old_candle["low"], updated_candle["low"])
                old_candle["close"] = updated_candle["close"]
                old_candle["oi"] = updated_candle["oi"]
                old_candle["volume"] = old_candle["volume"] + updated_candle["volume"]
                self.screens[interval].loc[last_candle_index, old_candle.keys()] = list(old_candle.values())
                getattr(self, f"ON_{interval}_UPDATE")(self.screens[interval])
            elif self.current_datetime > self.additional_candle_current_timings[interval].get("end_candle"):
                updated_candle = dict(updated_candle)
                self.additional_candle_current_timings[interval] = self.candle_timings[interval].pop(0)
                new_candle_index = self.additional_candle_current_timings[interval].get("start_candle")
                self.screens[interval].loc[new_candle_index, updated_candle.keys()] = list(updated_candle.values())
                # print(self.screens[interval])
                getattr(self, f"ON_{interval}_UPDATE")(self.screens[interval])
            else:
                raise Exception("Something went wrong")

            if self.current_datetime == self.additional_candle_current_timings[interval].get("end_candle"):
                getattr(self, f"ON_{interval}_CLOSE")(self.screens[interval])

            self.screens[interval] = self.screens[interval].tail(400)
        print(self.screens[interval])
        self.ON_CHARTWINDOW_UPDATE()

    @staticmethod
    def get_all_minute_candles(data_start_date, data_end_data):
        calendar = mcal.get_calendar("NSE")
        dates = list(calendar.schedule(start_date=data_start_date, end_date=data_end_data).index.date)
        times = list(pd.date_range("09:15:59", "15:29:59", freq="1min").time)
        result = []
        for date in dates:
            for time in times:
                result.append(dt.datetime.combine(date, time))
        return sorted(result)

    def GET_LASTEST(self, interval):
        assert interval in [Interval.MINUTE1] + self.additional_intervals, f"{interval} no valid"
        return dict(self.screens[interval].iloc[-1])

    def GET_MINUTE1_LASTEST(self):
        return self.GET_LASTEST(Interval.MINUTE1)

    def GET_MINUTE3_LASTEST(self):
        return self.GET_LASTEST(Interval.MINUTE3)

    def GET_MINUTE5_LASTEST(self):
        return self.GET_LASTEST(Interval.MINUTE5)

    def GET_MINUTE15_LASTEST(self):
        return self.GET_LASTEST(Interval.MINUTE15)

    def GET_MINUTE30_LASTEST(self):
        return self.GET_LASTEST(Interval.MINUTE30)

    def GET_MINUTE45_LASTEST(self):
        return self.GET_LASTEST(Interval.MINUTE45)

    def GET_HOUR_LASTEST(self):
        return self.GET_LASTEST(Interval.HOUR)

    def GET_DAY_LASTEST(self):
        return self.GET_LASTEST(Interval.DAY)

    def GET_WEEK_LASTEST(self):
        return self.GET_LASTEST(Interval.WEEK)

    def GET_MONTH_LASTEST(self):
        return self.GET_LASTEST(Interval.MONTH)

    def ON_MINUTE1_UPDATE(self, df):
        pass

    def ON_MINUTE3_UPDATE(self, df):
        pass

    def ON_MINUTE5_UPDATE(self, df):
        pass

    def ON_MINUTE15_UPDATE(self, df):
        pass

    def ON_MINUTE30_UPDATE(self, df):
        pass

    def ON_MINUTE45_UPDATE(self, df):
        pass

    def ON_HOUR_UPDATE(self, df):
        pass

    def ON_DAY_UPDATE(self, df):
        pass

    def ON_WEEK_UPDATE(self, df):
        pass

    def ON_MONTH_UPDATE(self, df):
        pass

    def ON_MINUTE1_CLOSE(self, df):
        pass

    def ON_MINUTE3_CLOSE(self, df):
        pass

    def ON_MINUTE5_CLOSE(self, df):
        pass

    def ON_MINUTE15_CLOSE(self, df):
        pass

    def ON_MINUTE30_CLOSE(self, df):
        pass

    def ON_MINUTE45_CLOSE(self, df):
        pass

    def ON_HOUR_CLOSE(self, df):
        pass

    def ON_DAY_CLOSE(self, df):
        pass

    def ON_WEEK_CLOSE(self, df):
        pass

    def ON_MONTH_CLOSE(self, df):
        pass

    def ON_CHARTWINDOW_UPDATE(self):
        pass

import pandas as pd
import datetime as dt
import pandas_market_calendars as mcal


class Interval:
    MINUTE1 = "MINUTE1"
    MINUTE3 = "MINUTE3"
    MINUTE5 = "MINUTE5"
    MINUTE15 = "MINUTE15"
    MINUTE30 = "MINUTE30"
    MINUTE45 = "MINUTE45"
    HOUR = "HOUR"
    DAY = "DAY"
    WEEK = "WEEK"
    MONTH = "MONTH"

    mappings = {
        MINUTE1: "1min",
        MINUTE3: "3min",
        MINUTE5: "5min",
        MINUTE15: "15min",
        MINUTE30: "30min",
        MINUTE45: "45min",
        HOUR: "60min"
    }

    @staticmethod
    def get_candle_timings(start_date, end_date, interval):
        calendar = mcal.get_calendar("NSE")
        dates_index = calendar.schedule(start_date=start_date, end_date=end_date).index
        dates = list(dates_index)

        result = []
        if interval in Interval.mappings:
            start_times = list(pd.date_range("09:15:59", "15:29:59", freq=Interval.mappings[interval]).time)
            end_times = list(pd.date_range("09:15:59", "15:29:59", freq=Interval.mappings[interval]).shift()[:-1].map(lambda x: x - dt.timedelta(minutes=1)).time)
            end_times.append(dt.time(15, 29, 59))
            assert len(start_times) == len(end_times), "Start times and end times should be equal"

            for date in dates:
                for index in range(0, len(start_times)):
                    result.append({
                        "start_candle": dt.datetime.combine(date, start_times[index]),
                        "end_candle": dt.datetime.combine(date, end_times[index])
                    })
        elif interval == Interval.DAY:
            result = list(map(lambda x: {
                "start_candle": dt.datetime.combine(x, dt.time(9, 15, 59)),
                "end_candle": dt.datetime.combine(x, dt.time(15, 29, 59))
            }, dates))
        elif interval == Interval.WEEK:
            temp_df = pd.DataFrame()
            temp_df["date"] = dates_index
            temp_df["year"] = temp_df["date"].dt.isocalendar().year
            temp_df["week"] = temp_df["date"].dt.isocalendar().week
            result = list(temp_df.groupby(["year", "week"]).apply(lambda gdf: {
                "start_candle": dt.datetime.combine(gdf.iloc[0]["date"], dt.time(9, 15, 59)),
                "end_candle": dt.datetime.combine(gdf.iloc[-1]["date"], dt.time(15, 29, 59))
            }))
        elif interval == Interval.MONTH:
            temp_df = pd.DataFrame()
            temp_df["date"] = dates_index
            temp_df["year"] = temp_df["date"].dt.year
            temp_df["month"] = temp_df["date"].dt.month
            result = list(temp_df.groupby(["year", "month"]).apply(lambda gdf: {
                "start_candle": dt.datetime.combine(gdf.iloc[0]["date"], dt.time(9, 15, 59)),
                "end_candle": dt.datetime.combine(gdf.iloc[-1]["date"], dt.time(15, 29, 59))
            }))

        return sorted(result, key=lambda x: x["start_candle"])


print(Interval.get_candle_timings(start_date=dt.date(2022, 6, 1), end_date=dt.date(2022, 7, 30),
                                 interval=Interval.HOUR))
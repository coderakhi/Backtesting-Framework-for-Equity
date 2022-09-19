from six import StringIO, PY2
from six.moves.urllib.parse import urljoin
import csv
import json
import dateutil.parser
import logging
import datetime
import requests
import kiteconnectProxy.exceptions as ex
import pandas as pd
log = logging.getLogger("brokers")


class KiteConnectProxy(object):
    _default_root_uri = "https://kite.zerodha.com"
    _default_timeout = 7  # In seconds


    #region Constants
    #region Product types
    PRODUCT_MIS = "MIS"
    PRODUCT_CNC = "CNC"
    PRODUCT_NRML = "NRML"
    PRODUCT_CO = "CO"
    PRODUCT_BO = "BO"
    #endregion

    #region Order types
    ORDER_TYPE_MARKET = "MARKET"
    ORDER_TYPE_LIMIT = "LIMIT"
    ORDER_TYPE_SLM = "SL-M"
    ORDER_TYPE_SL = "SL"
    #endregion

    # region Varities
    VARIETY_REGULAR = "regular"
    VARIETY_BO = "bo"
    VARIETY_CO = "co"
    VARIETY_AMO = "amo"
    #end region

    # Transaction type
    TRANSACTION_TYPE_BUY = "BUY"
    TRANSACTION_TYPE_SELL = "SELL"

    # Validity
    VALIDITY_DAY = "DAY"
    VALIDITY_IOC = "IOC"

    # Position Type
    POSITION_TYPE_DAY = "day"
    POSITION_TYPE_OVERNIGHT = "overnight"

    # Exchanges
    EXCHANGE_NSE = "NSE"
    EXCHANGE_BSE = "BSE"
    EXCHANGE_NFO = "NFO"
    EXCHANGE_CDS = "CDS"
    EXCHANGE_BFO = "BFO"
    EXCHANGE_MCX = "MCX"
    EXCHANGE_BCD = "BCD"

    # Margins segments
    MARGIN_EQUITY = "equity"
    MARGIN_COMMODITY = "commodity"

    # Status constants
    STATUS_COMPLETE = "COMPLETE"
    STATUS_REJECTED = "REJECTED"
    STATUS_CANCELLED = "CANCELLED"

    # GTT order type
    GTT_TYPE_OCO = "two-leg"
    GTT_TYPE_SINGLE = "single"

    # GTT order status
    GTT_STATUS_ACTIVE = "active"
    GTT_STATUS_TRIGGERED = "triggered"
    GTT_STATUS_DISABLED = "disabled"
    GTT_STATUS_EXPIRED = "expired"
    GTT_STATUS_CANCELLED = "cancelled"
    GTT_STATUS_REJECTED = "rejected"
    GTT_STATUS_DELETED = "deleted"
    #endregion

    #region routes
    _routes = {
        "api.login": "/api/login",
        "api.twofa": "/api/twofa",

        "user.profile": "/oms/user/profile/full",
        "user.margins": "/oms/user/margins",

        "orders": "/oms/orders",
        "trades": "/oms/trades",

        "order.info": "/oms/orders/{order_id}",
        "order.place": "/oms/orders/{variety}",
        "order.modify": "/oms/orders/{variety}/{order_id}",
        "order.cancel": "/oms/orders/{variety}/{order_id}",
        "order.trades": "/oms/orders/{order_id}/trades",

        "portfolio.positions": "/oms/portfolio/positions",
        "portfolio.holdings": "/oms/portfolio/holdings",
        "portfolio.positions.convert": "/oms/portfolio/positions",

        "market/instruments/all": "https://api.kite.trade/instruments",
        "market/instruments": "https://api.kite.trade/instruments/{exchange}",

        "market.historical": "/oms/instruments/historical/{instrument_token}/{interval}",
        "market.trigger_range": "/oms/instruments/trigger_range/{transaction_type}",

        "market.quote": "/oms/quote",
        "market.quote.ohlc": "/oms/quote/ohlc",
        "market.quote.ltp": "/oms/quote/ltp",

        # GTT endpoints
        "gtt": "/oms/gtt/triggers",
        "gtt.place": "/oms/gtt/triggers",
        "gtt.info": "/oms/gtt/triggers/{trigger_id}",
        "gtt.modify": "/oms/gtt/triggers/{trigger_id}",
        "gtt.delete": "/oms/gtt/triggers/{trigger_id}",

        # Margin computation endpoints
        "order.margins": "/oms/margins/orders",
        "order.margins.basket": "/oms/margins/basket"
    }
    #endregion

    def __init__(self,
                 username,
                 password,
                 twofa,
                 access_token=None,
                 root=None,
                 debug=False,
                 timeout=None,
                 proxies=None,
                 pool=None,
                 disable_ssl=False):

        """
        Initialise a new Kite Connect client instance.

        - `api_key` is the key issued to you
        - `access_token` is the token obtained after the login flow in
            exchange for the `request_token` . Pre-login, this will default to None,
        but once you have obtained it, you should
        persist it in a database or session to pass
        to the Kite Connect class initialisation for subsequent requests.
        - `root` is the API end point root. Unless you explicitly
        want to send API requests to a non-default endpoint, this
        can be ignored.
        - `debug`, if set to True, will serialise and print requests
        and responses to stdout.
        - `timeout` is the time (seconds) for which the API client will wait for
        a request to complete before it fails. Defaults to 7 seconds
        - `proxies` to set requests proxy.
        Check [python requests documentation](http://docs.python-requests.org/en/master/user/advanced/#proxies) for usage and examples.
        - `pool` is manages request pools. It takes a dict of params accepted by HTTPAdapter as described here in [python requests documentation](http://docs.python-requests.org/en/master/api/#requests.adapters.HTTPAdapter)
        - `disable_ssl` disables the SSL verification while making a request.
        If set requests won't throw SSLError if its set to custom `root` url without SSL.
        """

        self.debug = debug
        self.username = username
        self.password = password
        self.twofa = twofa
        self.session_expiry_hook = None
        self.disable_ssl = disable_ssl
        self.access_token = access_token
        self.cookies = {}
        self.proxies = proxies if proxies else {}

        self.root = root or self._default_root_uri
        self.timeout = timeout or self._default_timeout

        if pool:
            self.reqsession = requests.Session()
            reqadapter = requests.adapters.HTTPAdapter(**pool)
            self.reqsession.mount("https://", reqadapter)
        else:
            self.reqsession = requests

        # disable requests SSL warning
        requests.packages.urllib3.disable_warnings()

        self.set_session_expiry_hook(self.session_expiry_hook_method)


    def session_expiry_hook_method(self):
        self.invalidate_access_token()
        self.generate_session()

    def set_session_expiry_hook(self, method):
        if not callable(method):
            raise TypeError("Invalid input type. Only functions are accepted.")

        self.session_expiry_hook = method

    def set_access_token(self, access_token):
        self.access_token = access_token

    def set_cookies(self, cookie_val):
        self.cookies = cookie_val

    def generate_session(self):
        response = self._post(route="api.login", params={"user_id": self.username, "password": self.password})
        request_id = response.get("request_id")
        self._post(route="api.twofa", params={"user_id": self.username, "request_id": request_id, "twofa_value": self.twofa})
        if self.cookies.get("enctoken"):
            self.set_access_token(self.cookies.get("enctoken"))
        else:
            raise ex.TokenException("Invalid TWOFA authentication")

    def invalidate_access_token(self):
        self.access_token = None
        self.cookies = {}

    def margins(self):
        return self._get("user.margins")

    def profile(self):
        return self._get("user.profile")

    # orders
    def place_order(self,
                    variety,
                    exchange,
                    tradingsymbol,
                    transaction_type,
                    quantity,
                    product,
                    order_type,
                    price=None,
                    validity=None,
                    disclosed_quantity=None,
                    trigger_price=None,
                    squareoff=None,
                    stoploss=None,
                    trailing_stoploss=None,
                    tag=None):
        """Place an order."""
        params = locals()
        del(params["self"])

        for k in list(params.keys()):
            if params[k] is None:
                del(params[k])

        return self._post("order.place",
                          url_args={"variety": variety},
                          params=params)["order_id"]

    def modify_order(self,
                     variety,
                     order_id,
                     parent_order_id=None,
                     quantity=None,
                     price=None,
                     order_type=None,
                     trigger_price=None,
                     validity=None,
                     disclosed_quantity=None):
        """Modify an open order."""
        params = locals()
        del(params["self"])

        for k in list(params.keys()):
            if params[k] is None:
                del(params[k])

        return self._put("order.modify",
                         url_args={"variety": variety, "order_id": order_id},
                         params=params)["order_id"]

    def cancel_order(self, variety, order_id, parent_order_id=None):
        """Cancel an order."""
        return self._delete("order.cancel",
                            url_args={"variety": variety, "order_id": order_id},
                            params={"parent_order_id": parent_order_id})["order_id"]

    def exit_order(self, variety, order_id, parent_order_id=None):
        """Exit a BO/CO order."""
        return self.cancel_order(variety, order_id, parent_order_id=parent_order_id)

    def _format_response(self, data):
        """Parse and format responses."""

        if type(data) == list:
            _list = data
        elif type(data) == dict:
            _list = [data]

        for item in _list:
            # Convert date time string to datetime object
            for field in ["order_timestamp", "exchange_timestamp", "created", "last_instalment", "fill_timestamp", "timestamp", "last_trade_time"]:
                if item.get(field) and len(item[field]) == 19:
                    item[field] = dateutil.parser.parse(item[field])

        return _list[0] if type(data) == dict else _list

    # orderbook and tradebook
    def orders(self):
        """Get list of orders."""
        return self._format_response(self._get("orders"))

    def order_history(self, order_id):
        """
        Get history of individual order.

        - `order_id` is the ID of the order to retrieve order history.
        """
        return self._format_response(self._get("order.info", url_args={"order_id": order_id}))

    def trades(self):
        """
        Retrieve the list of trades executed (all or ones under a particular order).

        An order can be executed in tranches based on market conditions.
        These trades are individually recorded under an order.
        """
        return self._format_response(self._get("trades"))

    def order_trades(self, order_id):
        """
        Retrieve the list of trades executed for a particular order.

        - `order_id` is the ID of the order to retrieve trade history.
        """
        return self._format_response(self._get("order.trades", url_args={"order_id": order_id}))

    def positions(self):
        """Retrieve the list of positions."""
        return self._get("portfolio.positions")

    def holdings(self):
        """Retrieve the list of equity holdings."""
        return self._get("portfolio.holdings")

    def convert_position(self,
                         exchange,
                         tradingsymbol,
                         transaction_type,
                         position_type,
                         quantity,
                         old_product,
                         new_product):
        """Modify an open position's product type."""
        return self._put("portfolio.positions.convert", params={
            "exchange": exchange,
            "tradingsymbol": tradingsymbol,
            "transaction_type": transaction_type,
            "position_type": position_type,
            "quantity": quantity,
            "old_product": old_product,
            "new_product": new_product
        })

    def instruments(self, exchange=None):
        if exchange:
            return self._parse_instruments(self._get("market/instruments", url_args={"exchange": exchange}))
        else:
            return self._parse_instruments(self._get("market/instruments/all"))

    def quote(self, *instruments):
        """
        Retrieve quote for list of instruments.

        - `instruments` is a list of instruments, Instrument are in the format of `exchange:tradingsymbol`. For example NSE:INFY
        """
        ins = list(instruments)

        # If first element is a list then accept it as instruments list for legacy reason
        if len(instruments) > 0 and type(instruments[0]) == list:
            ins = instruments[0]

        data = self._get("market.quote", params={"i": ins})
        return {key: self._format_response(data[key]) for key in data}

    def ohlc(self, *instruments):
        """
        Retrieve OHLC and market depth for list of instruments.

        - `instruments` is a list of instruments, Instrument are in the format of `exchange:tradingsymbol`. For example NSE:INFY
        """
        ins = list(instruments)

        # If first element is a list then accept it as instruments list for legacy reason
        if len(instruments) > 0 and type(instruments[0]) == list:
            ins = instruments[0]

        return self._get("market.quote.ohlc", params={"i": ins})

    def ltp(self, *instruments):
        """
        Retrieve last price for list of instruments.

        - `instruments` is a list of instruments, Instrument are in the format of `exchange:tradingsymbol`. For example NSE:INFY
        """
        ins = list(instruments)

        # If first element is a list then accept it as instruments list for legacy reason
        if len(instruments) > 0 and type(instruments[0]) == list:
            ins = instruments[0]

        return self._get("market.quote.ltp", params={"i": ins})

    def historical_data(self, instrument_token, from_date, to_date, interval, continuous=False, oi=False):
        """
        Retrieve historical data (candles) for an instrument.

        Although the actual response JSON from the API does not have field
        names such has 'open', 'high' etc., this function call structures
        the data into an array of objects with field names. For example:

        - `instrument_token` is the instrument identifier (retrieved from the instruments()) call.
        - `from_date` is the From date (datetime object or string in format of yyyy-mm-dd HH:MM:SS.
        - `to_date` is the To date (datetime object or string in format of yyyy-mm-dd HH:MM:SS).
        - `interval` is the candle interval (minute, day, 5 minute etc.).
        - `continuous` is a boolean flag to get continuous data for futures and options instruments.
        - `oi` is a boolean flag to get open interest.
        """
        date_string_format = "%Y-%m-%d"
        result = []

        li = list(pd.date_range(start=from_date, end=to_date, freq="1D").to_pydatetime())
        for x in [li[i:i + 20] for i in range(0, len(li), 20)]:
            start_date = x[0].strftime(date_string_format)
            end_date = x[-1].strftime(date_string_format)

            data = self._get("market.historical",
                             url_args={"instrument_token": instrument_token, "interval": interval},
                             params={
                                 "from": start_date,
                                 "to": end_date,
                                 "interval": interval,
                                 "continuous": 1 if continuous else 0,
                                 "oi": 1 if oi else 0
                             })

            result.extend(self._format_historical(data))
        return result

    def _format_historical(self, data):
        records = []
        for d in data["candles"]:
            record = {
                "date": dateutil.parser.parse(d[0]),
                "open": d[1],
                "high": d[2],
                "low": d[3],
                "close": d[4],
                "volume": d[5],
            }
            if len(d) == 7:
                record["oi"] = d[6]
            records.append(record)

        return records

    def trigger_range(self, transaction_type, *instruments):
        """Retrieve the buy/sell trigger range for Cover Orders."""
        ins = list(instruments)

        # If first element is a list then accept it as instruments list for legacy reason
        if len(instruments) > 0 and type(instruments[0]) == list:
            ins = instruments[0]

        return self._get("market.trigger_range",
                         url_args={"transaction_type": transaction_type.lower()},
                         params={"i": ins})

    def get_gtts(self):
        """Fetch list of gtt existing in an account"""
        return self._get("gtt")

    def get_gtt(self, trigger_id):
        """Fetch details of a GTT"""
        return self._get("gtt.info", url_args={"trigger_id": trigger_id})

    def _get_gtt_payload(self, trigger_type, tradingsymbol, exchange, trigger_values, last_price, orders):
        """Get GTT payload"""
        if type(trigger_values) != list:
            raise ex.InputException("invalid type for `trigger_values`")
        if trigger_type == self.GTT_TYPE_SINGLE and len(trigger_values) != 1:
            raise ex.InputException("invalid `trigger_values` for single leg order type")
        elif trigger_type == self.GTT_TYPE_OCO and len(trigger_values) != 2:
            raise ex.InputException("invalid `trigger_values` for OCO order type")

        condition = {
            "exchange": exchange,
            "tradingsymbol": tradingsymbol,
            "trigger_values": trigger_values,
            "last_price": last_price,
        }

        gtt_orders = []
        for o in orders:
            # Assert required keys inside gtt order.
            for req in ["transaction_type", "quantity", "order_type", "product", "price"]:
                if req not in o:
                    raise ex.InputException("`{req}` missing inside orders".format(req=req))
            gtt_orders.append({
                "exchange": exchange,
                "tradingsymbol": tradingsymbol,
                "transaction_type": o["transaction_type"],
                "quantity": int(o["quantity"]),
                "order_type": o["order_type"],
                "product": o["product"],
                "price": float(o["price"]),
            })

        return condition, gtt_orders

    def place_gtt(
        self, trigger_type, tradingsymbol, exchange, trigger_values, last_price, orders
    ):
        """
        Place GTT order

        - `trigger_type` The type of GTT order(single/two-leg).
        - `tradingsymbol` Trading symbol of the instrument.
        - `exchange` Name of the exchange.
        - `trigger_values` Trigger values (json array).
        - `last_price` Last price of the instrument at the time of order placement.
        - `orders` JSON order array containing following fields
            - `transaction_type` BUY or SELL
            - `quantity` Quantity to transact
            - `price` The min or max price to execute the order at (for LIMIT orders)
        """
        # Validations.
        assert trigger_type in [self.GTT_TYPE_OCO, self.GTT_TYPE_SINGLE]
        condition, gtt_orders = self._get_gtt_payload(trigger_type, tradingsymbol, exchange, trigger_values, last_price, orders)

        return self._post("gtt.place", params={
            "condition": json.dumps(condition),
            "orders": json.dumps(gtt_orders),
            "type": trigger_type})

    def modify_gtt(
        self, trigger_id, trigger_type, tradingsymbol, exchange, trigger_values, last_price, orders
    ):
        """
        Modify GTT order

        - `trigger_type` The type of GTT order(single/two-leg).
        - `tradingsymbol` Trading symbol of the instrument.
        - `exchange` Name of the exchange.
        - `trigger_values` Trigger values (json array).
        - `last_price` Last price of the instrument at the time of order placement.
        - `orders` JSON order array containing following fields
            - `transaction_type` BUY or SELL
            - `quantity` Quantity to transact
            - `price` The min or max price to execute the order at (for LIMIT orders)
        """
        condition, gtt_orders = self._get_gtt_payload(trigger_type, tradingsymbol, exchange, trigger_values, last_price, orders)

        return self._put("gtt.modify",
                         url_args={"trigger_id": trigger_id},
                         params={
                             "condition": json.dumps(condition),
                             "orders": json.dumps(gtt_orders),
                             "type": trigger_type})

    def delete_gtt(self, trigger_id):
        """Delete a GTT order."""
        return self._delete("gtt.delete", url_args={"trigger_id": trigger_id})

    def order_margins(self, params):
        """
        [
          {
            "exchange": "NSE",
            "tradingsymbol": "UPL",
            "transaction_type": "BUY",
            "variety": "regular",
            "product": "CNC",
            "order_type": "SL-M",
            "quantity": 1,
            "trigger_price": 824.65
          }
        ]
        """
        return self._post("order.margins", params=params, is_json=True)

    def basket_order_margins(self, params, consider_positions=True, mode=None):
        """
        Calculate total margins required for basket of orders including margin benefits

        - `params` is list of orders to fetch basket margin
        [
          {
            "exchange": "NSE",
            "tradingsymbol": "NIFTYBEES",
            "transaction_type": "BUY",
            "variety": "regular",
            "product": "CNC",
            "order_type": "SL-M",
            "quantity": 1,
            "price": 0,
            "trigger_price": 0.01,
            "squareoff": 0,
            "stoploss": 0
          },
          {
            "exchange": "NSE",
            "tradingsymbol": "NIRAJ",
            "transaction_type": "BUY",
            "variety": "regular",
            "product": "CNC",
            "order_type": "SL-M",
            "quantity": 1,
            "price": 0,
            "trigger_price": 0.05,
            "squareoff": 0,
            "stoploss": 0
          }
        ]
        - `consider_positions` is a boolean to consider users positions
        - `mode` is margin response mode type. compact - Compact mode will only give the total margins

        """
        return self._post("order.margins.basket",
                          params=params,
                          is_json=True,
                          query_params={'consider_positions': consider_positions, 'mode': mode})

    def _parse_instruments(self, data):
        # decode to string for Python 3
        d = data
        # Decode unicode data
        if not PY2 and type(d) == bytes:
            d = data.decode("utf-8").strip()

        records = []
        reader = csv.DictReader(StringIO(d))

        for row in reader:
            row["instrument_token"] = int(row["instrument_token"])
            row["last_price"] = float(row["last_price"])
            row["strike"] = float(row["strike"])
            row["tick_size"] = float(row["tick_size"])
            row["lot_size"] = int(row["lot_size"])

            # Parse date
            if len(row["expiry"]) == 10:
                row["expiry"] = dateutil.parser.parse(row["expiry"]).date()

            records.append(row)

        return records

    def _parse_mf_instruments(self, data):
        # decode to string for Python 3
        d = data
        if not PY2 and type(d) == bytes:
            d = data.decode("utf-8").strip()

        records = []
        reader = csv.DictReader(StringIO(d))

        for row in reader:
            row["minimum_purchase_amount"] = float(row["minimum_purchase_amount"])
            row["purchase_amount_multiplier"] = float(row["purchase_amount_multiplier"])
            row["minimum_additional_purchase_amount"] = float(row["minimum_additional_purchase_amount"])
            row["minimum_redemption_quantity"] = float(row["minimum_redemption_quantity"])
            row["redemption_quantity_multiplier"] = float(row["redemption_quantity_multiplier"])
            row["purchase_allowed"] = bool(int(row["purchase_allowed"]))
            row["redemption_allowed"] = bool(int(row["redemption_allowed"]))
            row["last_price"] = float(row["last_price"])

            # Parse date
            if len(row["last_price_date"]) == 10:
                row["last_price_date"] = dateutil.parser.parse(row["last_price_date"]).date()

            records.append(row)

        return records

    def _user_agent(self):
        return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/97.0.4692.71 Safari/537.36"

    def _get(self, route, url_args=None, params=None, is_json=False):
        return self._request(route, "GET", url_args=url_args, params=params, is_json=is_json)

    def _post(self, route, url_args=None, params=None, is_json=False, query_params=None):
        return self._request(route, "POST", url_args=url_args, params=params, is_json=is_json, query_params=query_params)

    def _put(self, route, url_args=None, params=None, is_json=False, query_params=None):
        return self._request(route, "PUT", url_args=url_args, params=params, is_json=is_json, query_params=query_params)

    def _delete(self, route, url_args=None, params=None, is_json=False):
        return self._request(route, "DELETE", url_args=url_args, params=params, is_json=is_json)

    def _request(self, route, method, url_args=None, params=None, is_json=False, query_params=None):
        if url_args:
            uri = self._routes[route].format(**url_args)
        else:
            uri = self._routes[route]

        url = uri if "/" in route else urljoin(self.root, uri)

        # Custom headers
        headers = {
            "Authority": "kite.zerodha.com",
            "Scheme": "https",
            "X-Kite-Version": "2.9.10",
            "User-Agent": self._user_agent(),
            "x-kite-userid": self.username,
            "Origin" : "https://kite.zerodha.com",
            "Referer": "https://kite.zerodha.com/"
        }

        if self.access_token:
            headers["Authorization"] = "enctoken {}".format(self.access_token)



        if self.debug:
            log.debug("Request: {method} {url} {params} {headers}".format(method=method, url=url, params=params, headers=headers))

        # prepare url query params
        if method in ["GET", "DELETE"]:
            query_params = params

        try:
            response = self.reqsession.request(method,
                url,
                json=params if (method in ["POST", "PUT"] and is_json) else None,
                data=params if (method in ["POST", "PUT"] and not is_json) else None,
                params=query_params,
                headers=headers,
                cookies=self.cookies,
                verify=not self.disable_ssl,
                allow_redirects=True,
                timeout=self.timeout,
                proxies=self.proxies)

        except Exception as e:
            raise e

        if self.debug:
            log.debug("Response: {code} {content}".format(code=response.status_code, content=response.content))

        if response.cookies:
            for key, value in response.cookies.items():
                self.cookies[key] = value

        if "json" in response.headers["content-type"]:
            try:
                data = json.loads(response.content.decode("utf8"))
            except ValueError:
                raise ex.DataException("Couldn't parse the JSON response received from the server: {content}".format(content=response.content))

            # api error
            if data.get("status") == "error" or data.get("error_type"):
                # Call session hook if its registered and TokenException is raised
                if (self.session_expiry_hook and response.status_code == 403 and data["error_type"] == "TokenException" ) or (self.session_expiry_hook and response.status_code == 400 and data["error_type"] == "InputException"):
                    self.session_expiry_hook()
                else:
                    exp = getattr(ex, data.get("error_type"), ex.GeneralException)
                    raise exp(data["message"], code=response.status_code)

            return data["data"]
        elif "csv" in response.headers["content-type"]:
            return response.content
        else:
            raise ex.DataException("Unknown Content-Type ({content_type}) with response: ({content})".format(content_type=response.headers["content-type"], content=response.content))

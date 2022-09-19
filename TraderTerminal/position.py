import uuid
from .constants import TransactionType, InstrumentType, PositionType


class Position:
    def __init__(self, ticker, position_type, transaction_type, price, qty, entry_datetime, tag_id, charges=0):
        self.position_id = str(uuid.uuid4())
        self.ticker = ticker
        self.entry_datetime = entry_datetime
        self.exit_datetime = None
        self.position_type = position_type
        self.transaction_type = transaction_type
        self.price = price
        self.buy_value = price * qty if self.transaction_type == TransactionType.BUY else 0
        self.buy_qty = qty if self.transaction_type == TransactionType.BUY else 0
        self.sell_value = price * qty if self.transaction_type == TransactionType.SELL else 0
        self.sell_qty = qty if self.transaction_type == TransactionType.SELL else 0
        self.net_qty = self.buy_qty - self.sell_qty
        self.m2m = 0
        self.margin = ticker.get_margin(position_type=position_type, transaction_type=transaction_type, price=price, qty=qty)
        self.orders = 1
        self.charges = charges
        self.tag_id = tag_id

        if self.position_type == PositionType.NRML:
            self.ticker.listener_func_nrml = self.update_m2m
        elif self.position_type == PositionType.MIS:
            self.ticker.listener_func_mis = self.update_m2m

        assert not (ticker.instrument_type == InstrumentType.EQ and position_type == PositionType.NRML and transaction_type == TransactionType.SELL), "Short selling in EQ NRML not allowed"

    def add_transaction(self, transaction_type, qty, price, datetime):
        if transaction_type != self.transaction_type:
            assert qty <= abs(self.net_qty), "Square off the position before creating a new trade in opposite direction"

        self.price = price

        if transaction_type == TransactionType.BUY:
            self.buy_value = self.buy_value + self.price * qty
            self.buy_qty = self.buy_qty + qty
        elif transaction_type == TransactionType.SELL:
            self.sell_value = self.sell_value + self.price * qty
            self.sell_qty = self.sell_qty + qty

        self.net_qty = self.buy_qty - self.sell_qty
        self.exit_datetime = datetime if self.net_qty == 0 else self.exit_datetime
        self.m2m = self.sell_value - self.buy_value + (self.net_qty * self.price)

        if self.net_qty == 0:
            self.margin = 0
        else:
            average_price = self.buy_value/self.buy_qty if self.transaction_type == TransactionType.BUY else self.sell_value/self.sell_qty
            self.margin = self.ticker.get_margin(position_type=self.position_type, transaction_type=self.transaction_type, price=average_price, qty=abs(self.net_qty))

        self.orders = self.orders + 1

    def accumulate_order_charges(self, charge):
        self.charges = self.charges + charge

    def get_dict_repr(self):
        result = self.ticker.get_dict_repr()
        result.update({
            "position_id": self.position_id,
            "entry_datetime": self.entry_datetime,
            "exit_datetime": self.exit_datetime,
            "position_type": self.position_type,
            "transaction_type": self.transaction_type,
            "price": self.price,
            "buy_value": self.buy_value,
            "buy_qty": self.buy_qty,
            "sell_value": self.sell_value,
            "sell_qty": self.sell_qty,
            "net_qty": self.net_qty,
            "m2m": self.m2m,
            "charges": self.charges,
            "profit": self.m2m - self.charges,
            "margin": self.margin,
            "orders": self.orders,
            "tag_id": self.tag_id
        })

        return result

    def update_m2m(self, price):
        self.price = price
        self.m2m = self.sell_value - self.buy_value + (self.net_qty * self.price)

    def __del__(self):
        if self.position_type == PositionType.NRML:
            self.ticker.listener_func_nrml = None
        elif self.position_type == PositionType.MIS:
            self.ticker.listener_func_mis = None
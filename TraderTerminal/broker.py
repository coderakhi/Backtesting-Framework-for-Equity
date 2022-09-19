import pandas as pd
from .constants import PositionType
from .position import Position
from .ticker import Ticker
from .order import Order


class Broker:
    def __init__(self, margin_available):
        self.margin_available = margin_available
        self.margin_blocked = 0
        self.m2m = 0

        self.positions = {
            PositionType.MIS: {},
            PositionType.NRML: {}
        }
        self.tradebook = []
        self.orderbook = []
        self.ledger = []

    def make_ticker(self, symbol, instrument_type, margin_per_lot_or_multiplier, price=None, expiry=None, strike_price=None, lot_size=None):
        return Ticker(symbol=symbol, instrument_type=instrument_type, margin_per_lot_or_multiplier=margin_per_lot_or_multiplier, price=price, expiry=expiry, broker=self, strike_price=strike_price, lot_size=lot_size)

    def transact(self, ticker, price, qty, datetime, position_type, transaction_type, tag_id):
        current_order = Order(ticker=ticker, price=price, qty=qty, datetime=datetime, position_type=position_type, transaction_type=transaction_type, tag_id=tag_id)
        current_position = self.create_or_modify_position(ticker=ticker, price=price, qty=qty, datetime=datetime, position_type=position_type, transaction_type=transaction_type, tag_id=tag_id)

        req_margin = self.evaluate_margin_obligations()
        profit = self.evaluate_booked_profits()
        charges = current_order.charges

        ### for ledger
        self.satisfy_and_log_margin_obligations_in_ledger(datetime=datetime, req_margin=req_margin, profit=profit, charge=charges, order_id=current_order.order_id, position_id=current_position.position_id, tag_id=tag_id)

        ### for tradebook
        current_position.accumulate_order_charges(charge=charges)
        self.log_squared_positions_in_tradebook()

        ## for orderbook
        current_order.margin_available = self.margin_available
        current_order.margin_blocked = self.margin_blocked
        current_order.position_id = current_position.position_id
        self.log_to_orderbook(current_order)

        return current_order.order_id, current_position.position_id


    def create_or_modify_position(self, ticker, price, qty, datetime, position_type, transaction_type, tag_id):
        all_positions = self.get_positions()
        existing_position = self.get_positions(ticker=ticker, position_type=position_type)

        if existing_position is None:
            new_position = Position(ticker=ticker, position_type=position_type, transaction_type=transaction_type, price=price, qty=qty, entry_datetime=datetime, tag_id=tag_id)
            all_positions[position_type][ticker.ticker_id] = new_position
            return new_position
        else:
            existing_position.add_transaction(transaction_type=transaction_type, qty=qty, price=price, datetime=datetime)
            return existing_position

    def get_positions(self, ticker=None, position_type=None):
        positions = self.positions

        if ticker is not None and position_type is not None:
            positions = positions.get(position_type).get(ticker.ticker_id)

        return positions

    def evaluate_margin_obligations(self):
        req_margin = 0
        for position_type in [PositionType.MIS, PositionType.NRML]:
            for position in list(self.positions[position_type].values()):
                    req_margin = req_margin + position.margin
        return req_margin

    def evaluate_booked_profits(self):
        profit = 0
        for position_type in [PositionType.MIS, PositionType.NRML]:
            for position in list(self.positions[position_type].values()):
                profit = profit + (position.m2m if position.net_qty == 0 else 0)
        return profit

    def satisfy_and_log_margin_obligations_in_ledger(self, datetime, req_margin, profit, charge, order_id, position_id, tag_id):
        assert req_margin < self.margin_available + self.margin_blocked + profit - charge, "Insufficient margin to execute transaction"

        margin_offset = self.margin_blocked - req_margin
        self.margin_available = self.margin_available + margin_offset
        self.margin_blocked = self.margin_blocked - margin_offset

        if margin_offset != 0:
            self.log_to_ledger(datetime=datetime, margin_available=self.margin_available, margin_blocked=self.margin_blocked, order_id=order_id, position_id=position_id, tag_id=tag_id, reason="Margin obligations")

        if profit != 0:
            self.margin_available = self.margin_available + profit
            self.log_to_ledger(datetime=datetime, margin_available=self.margin_available, margin_blocked=self.margin_blocked, order_id=order_id, position_id=position_id, tag_id=tag_id, reason="Trade P/L")

        if charge != 0:
            self.margin_available = self.margin_available - charge
            self.log_to_ledger(datetime=datetime, margin_available=self.margin_available, margin_blocked=self.margin_blocked, order_id=order_id, position_id=position_id, tag_id=tag_id, reason="Charges")

    def log_squared_positions_in_tradebook(self):
        for position_type in [PositionType.MIS, PositionType.NRML]:
            for ticker_id in list(self.positions[position_type].keys()):
                position = self.positions.get(position_type).get(ticker_id)
                if position.net_qty == 0:
                    self.tradebook.append(position.get_dict_repr())
                    self.positions.get(position_type).pop(ticker_id)


    def log_to_orderbook(self, order):
        self.orderbook.append(order.get_dict_repr())

    def log_to_ledger(self, datetime, margin_available, margin_blocked, order_id=None, position_id=None, tag_id=None, reason=None):
        self.ledger.append({
            "datetime": datetime,
            "margin_available": margin_available,
            "margin_blocked": margin_blocked,
            "order_id": order_id,
            "position_id": position_id,
            "tag_id": tag_id,
            "reason": reason
        })

    def update_m2m(self):
        m2m = 0
        for position in self.positions[PositionType.MIS].values():
            m2m = m2m + position.m2m
        for position in self.positions[PositionType.NRML].values():
            m2m = m2m + position.m2m
        self.m2m = m2m
        return m2m

    def perform_end_of_day_actions(self):
        assert len(self.positions.get(PositionType.MIS)) == 0, "MIS Positions are not squared off"

    def get_tradebook(self):
        return pd.DataFrame(data=self.tradebook)

    def get_orderbook(self):
        return pd.DataFrame(data=self.orderbook)

    def get_ledger(self):
        return pd.DataFrame(data=self.ledger)


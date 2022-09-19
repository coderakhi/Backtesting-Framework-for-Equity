from .constants import InstrumentType, PositionType, TransactionType
import uuid


class Ticker:
    def __init__(self, symbol, instrument_type, margin_per_lot_or_multiplier, broker, price=None, expiry=None, strike_price=None, lot_size=None):
        assert instrument_type in [InstrumentType.EQ, InstrumentType.FUT, InstrumentType.CE, InstrumentType.PE], "Invalid Instrument Type"

        if instrument_type == InstrumentType.EQ:
            expiry = strike_price = lot_size = None
            assert margin_per_lot_or_multiplier <= 1, "Multiplier should be mentioned for EQ which should be below 1"
        elif instrument_type == InstrumentType.FUT:
            strike_price = None
            assert all([expiry, lot_size]), "FUT ticker should have an expiry, lot_size"
        else:
            assert all([expiry, strike_price, lot_size]), "OPT ticker should have expiry, strike_price and lost_size"

        self.ticker_id = str(uuid.uuid4())
        self.symbol = symbol
        self.instrument_type = instrument_type
        self.margin_per_lot_or_multiplier = margin_per_lot_or_multiplier
        self.expiry = expiry
        self.strike_price = strike_price
        self.lot_size = lot_size
        self.price = price
        self.broker = broker
        self.listener_func_nrml = None
        self.listener_func_mis = None

    def get_dict_repr(self):
        result = {
            "ticker_id": self.ticker_id,
            "symbol": self.symbol,
            "instrument_type": self.instrument_type,
            "expiry": self.expiry,
            "strike_price": self.strike_price
        }
        return result

    def update_price(self, price):
        self.price = price

        if self.listener_func_nrml is not None:
            self.listener_func_nrml(price)
            self.broker.update_m2m()

        if self.listener_func_mis is not None:
            self.listener_func_mis(price)
            self.broker.update_m2m()

    def buy(self, datetime, price=None, qty=None, lots=None, tag_id=None, position_type=PositionType.NRML):
        assert price is not None or self.price is not None, "price cannot be None"
        if qty is not None and self.lot_size is not None:
            assert qty % self.lot_size == 0, "Qty should be multiple of lot size"
        if self.expiry is not None:
            assert datetime.date() <= self.expiry, "Instrument cannot be traded after expiry"
        if lots is not None:
            assert self.lot_size is not None, "Lot size cannot be None"
            qty = self.lot_size * lots
        if price is not None:
            self.update_price(price)
        return self.broker.transact(ticker=self, price=self.price, qty=qty, datetime=datetime, position_type=position_type, transaction_type=TransactionType.BUY, tag_id=tag_id)

    def sell(self, datetime, price=None, qty=None, lots=None, tag_id=None, position_type=PositionType.NRML):
        assert price is not None or self.price is not None, "price cannot be None"
        if qty is not None and self.lot_size is not None:
            assert qty % self.lot_size == 0, "Qty should be multiple of lot size"
        if self.expiry is not None:
            assert datetime.date() <= self.expiry, "Instrument cannot be traded after expiry"
        if lots is not None:
            assert self.lot_size is not None, "Lot size cannot be None"
            qty = self.lot_size * lots
        if price is not None:
            self.update_price(price)
        return self.broker.transact(ticker=self, price=self.price, qty=qty, datetime=datetime, position_type=position_type, transaction_type=TransactionType.SELL, tag_id=tag_id)

    def squareoff(self, datetime, price=None, tag_id=None, position_type=PositionType.NRML):
        assert price is not None or self.price is not None, "price cannot be None"
        if price is not None:
            self.update_price(price)

        position = self.broker.positions.get(position_type, {}).get(self.ticker_id)

        if position is None or position.net_qty == 0:
            return

        if position.net_qty > 0:
            return self.sell(datetime=datetime, price=price, qty=abs(position.net_qty), tag_id=tag_id, position_type=position_type)
        else:
            return self.buy(datetime=datetime, price=price, qty=abs(position.net_qty), tag_id=tag_id, position_type=position_type)

    def get_margin(self, position_type, transaction_type, price, qty):
        if self.instrument_type == InstrumentType.EQ:
            if position_type == PositionType.MIS:
                return price * qty * self.margin_per_lot_or_multiplier
            elif position_type == PositionType.NRML:
                return price * qty
        elif self.instrument_type == InstrumentType.FUT:
            return (self.margin_per_lot_or_multiplier / self.lot_size) * qty
        elif self.instrument_type in [InstrumentType.CE, InstrumentType.PE]:
            if transaction_type == TransactionType.BUY:
                return price * qty
            elif transaction_type == TransactionType.SELL:
                return (self.margin_per_lot_or_multiplier / self.lot_size) * qty

    def get_transaction_charges(self, position_type, transaction_type, price, qty):
        charges = {}

        ### EQUITY
        if self.instrument_type == InstrumentType.EQ:
            charges["transaction_charges"] = (0.00345 / 100) * price * qty

            if position_type == PositionType.MIS:
                charges["brokrage"] = min((0.03 / 100) * price * qty, 20)
                charges["stt"] = (0.0025 / 100) * price * qty if transaction_type == TransactionType.SELL else 0
                charges["stamp_charges"] = (0.003 / 100) * (price * qty) if transaction_type == TransactionType.BUY else 0

            elif position_type == PositionType.NRML:
                charges["brokrage"] = 0
                charges["stt"] = (0.1 / 100) * price * qty
                charges["dp_charges"] = 15.93 if transaction_type == TransactionType.SELL else 0
                charges["stamp_charges"] = (0.015 / 100) * (price * qty) if transaction_type == TransactionType.BUY else 0

        ### FUT
        elif self.instrument_type == InstrumentType.FUT:
            charges["transaction_charges"] = (0.002 / 100) * price * qty
            charges["brokrage"] = min((0.03 / 100) * price * qty, 20)
            charges["stt"] = (0.01 / 100) * price * qty if transaction_type == TransactionType.SELL else 0
            charges["stamp_charges"] = (0.002 / 100) * (price * qty) if transaction_type == TransactionType.BUY else 0

        ### OPTIONS
        elif self.instrument_type in [InstrumentType.CE, InstrumentType.PE]:
            charges["transaction_charges"] = (0.053 / 100) * price * qty
            charges["brokrage"] = 20
            charges["stt"] = (0.05 / 100) * price * qty if transaction_type == TransactionType.SELL else 0
            charges["stamp_charges"] = (0.003 / 100) * (price * qty) if transaction_type == TransactionType.BUY else 0


        ### GENERAL
        charges["gst"] = (18 / 100) * (charges["brokrage"] + charges["transaction_charges"])
        charges["sebi_charges"] = (10 / 10000000) * (price * qty)


        total = round(sum(charges.values()), 2)
        return total
import uuid

class Order:
    def __init__(self, ticker, price, qty, datetime, position_type, transaction_type, tag_id, margin_available=None, margin_blocked=None, position_id=None):
        self.order_id = str(uuid.uuid4())
        self.ticker = ticker
        self.price = price
        self.qty = qty
        self.datetime = datetime
        self.position_type = position_type
        self.transaction_type = transaction_type
        self.margin_available = margin_available
        self.margin_blocked = margin_blocked
        self.charges = self.ticker.get_transaction_charges(position_type=self.position_type, transaction_type=self.transaction_type, price=self.price, qty=self.qty)
        self.tag_id = tag_id
        self.position_id = position_id

    def get_dict_repr(self):
        result = self.ticker.get_dict_repr()
        result.update({
            "order_id": self.order_id,
            "price": self.price,
            "qty": self.qty,
            "datetime": self.datetime,
            "transaction_type": self.transaction_type,
            "position_type": self.position_type,
            "margin_available": self.margin_available,
            "margin_blocked": self.margin_blocked,
            "charges": self.charges,
            "tag_id": self.tag_id,
            "position_id": self.position_id,
        })
        return result
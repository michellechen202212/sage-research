PRAGMA foreign_keys = ON;

CREATE TABLE customer (
  customer_id TEXT PRIMARY KEY,
  display_name TEXT NOT NULL
);

CREATE TABLE commerce_order (
  order_id TEXT PRIMARY KEY,
  customer_id TEXT NOT NULL REFERENCES customer(customer_id),
  channel TEXT NOT NULL,
  order_number TEXT NOT NULL,
  currency_code TEXT,
  order_total_cents INTEGER NOT NULL,
  created_at TEXT NOT NULL,
  ordered_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE order_line (
  order_line_id TEXT PRIMARY KEY,
  order_id TEXT NOT NULL REFERENCES commerce_order(order_id),
  sku TEXT NOT NULL,
  quantity INTEGER NOT NULL,
  line_amount_cents INTEGER NOT NULL
);

CREATE TABLE fulfillment_event (
  fulfillment_event_id TEXT PRIMARY KEY,
  order_line_id TEXT NOT NULL REFERENCES order_line(order_line_id),
  event_type TEXT NOT NULL,
  amount_cents INTEGER NOT NULL,
  event_at TEXT NOT NULL
);

CREATE TABLE payment (
  payment_id TEXT PRIMARY KEY,
  customer_id TEXT NOT NULL REFERENCES customer(customer_id),
  order_id TEXT REFERENCES commerce_order(order_id),
  provider_reference TEXT NOT NULL
);

CREATE TABLE payment_event (
  event_id TEXT PRIMARY KEY,
  payment_id TEXT NOT NULL REFERENCES payment(payment_id),
  event_type TEXT NOT NULL,
  status TEXT NOT NULL,
  amount_cents INTEGER NOT NULL,
  event_at TEXT NOT NULL,
  ingested_at TEXT NOT NULL,
  currency_code TEXT
);

CREATE TABLE pos_receipt (
  receipt_id TEXT PRIMARY KEY,
  customer_id TEXT NOT NULL REFERENCES customer(customer_id),
  store_code TEXT NOT NULL,
  receipt_number TEXT NOT NULL,
  currency_code TEXT,
  receipt_total_cents INTEGER NOT NULL,
  transacted_at TEXT NOT NULL
);

CREATE TABLE receipt_item_occurrence (
  receipt_item_id TEXT PRIMARY KEY,
  receipt_id TEXT NOT NULL REFERENCES pos_receipt(receipt_id),
  sku TEXT NOT NULL,
  quantity INTEGER NOT NULL,
  item_amount_cents INTEGER NOT NULL
);

CREATE TABLE tender_leg (
  tender_leg_id TEXT PRIMARY KEY,
  receipt_id TEXT NOT NULL REFERENCES pos_receipt(receipt_id),
  tender_type TEXT NOT NULL,
  amount_cents INTEGER NOT NULL
);

CREATE TABLE merchandise_return (
  return_id TEXT PRIMARY KEY,
  customer_id TEXT NOT NULL REFERENCES customer(customer_id),
  original_order_id TEXT REFERENCES commerce_order(order_id),
  merchandise_value_cents INTEGER NOT NULL,
  currency_code TEXT,
  returned_at TEXT NOT NULL
);



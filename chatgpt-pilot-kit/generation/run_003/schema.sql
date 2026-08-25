-- Synthetic commerce investigation schema
CREATE TABLE customer_reference (
    customer_ref_id TEXT PRIMARY KEY,
    display_name TEXT
);

CREATE TABLE orders (
    order_id TEXT PRIMARY KEY,
    customer_ref_id TEXT REFERENCES customer_reference(customer_ref_id),
    order_number TEXT NOT NULL,
    ordered_total NUMERIC(12,2) NOT NULL,
    ordered_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP NOT NULL
);

CREATE TABLE order_line (
    order_line_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL REFERENCES orders(order_id),
    sku TEXT NOT NULL,
    ordered_quantity NUMERIC(12,3) NOT NULL,
    line_merchandise_amount NUMERIC(12,2) NOT NULL,
    line_tax_amount NUMERIC(12,2) NOT NULL
);

CREATE TABLE payment (
    payment_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL REFERENCES orders(order_id),
    payment_amount NUMERIC(12,2) NOT NULL
);

CREATE TABLE payment_authorization (
    authorization_id TEXT PRIMARY KEY,
    payment_id TEXT NOT NULL REFERENCES payment(payment_id),
    authorization_amount NUMERIC(12,2) NOT NULL,
    authorization_status TEXT NOT NULL,
    authorized_at TIMESTAMP NOT NULL
);

CREATE TABLE payment_settlement (
    settlement_id TEXT PRIMARY KEY,
    payment_id TEXT NOT NULL REFERENCES payment(payment_id),
    settlement_amount NUMERIC(12,2) NOT NULL,
    settlement_type TEXT NOT NULL,
    settled_at TIMESTAMP NOT NULL
);

CREATE TABLE fulfillment_event (
    fulfillment_event_id TEXT PRIMARY KEY,
    order_line_id TEXT NOT NULL REFERENCES order_line(order_line_id),
    fulfilled_quantity NUMERIC(12,3) NOT NULL,
    occurred_at TIMESTAMP NOT NULL
);

CREATE TABLE pos_receipt (
    receipt_id TEXT PRIMARY KEY,
    customer_ref_id TEXT REFERENCES customer_reference(customer_ref_id),
    business_date DATE NOT NULL,
    location_id TEXT NOT NULL,
    register_id TEXT NOT NULL,
    transaction_number TEXT NOT NULL,
    receipt_total NUMERIC(12,2) NOT NULL
);

CREATE TABLE pos_item_occurrence (
    receipt_item_id TEXT PRIMARY KEY,
    receipt_id TEXT NOT NULL REFERENCES pos_receipt(receipt_id),
    sku TEXT NOT NULL,
    quantity NUMERIC(12,3) NOT NULL,
    item_amount NUMERIC(12,2) NOT NULL
);

CREATE TABLE pos_tender_leg (
    tender_leg_id TEXT PRIMARY KEY,
    receipt_id TEXT NOT NULL REFERENCES pos_receipt(receipt_id),
    tender_type TEXT NOT NULL,
    tender_amount NUMERIC(12,2) NOT NULL
);

CREATE TABLE merchandise_return (
    return_id TEXT PRIMARY KEY,
    customer_ref_id TEXT REFERENCES customer_reference(customer_ref_id),
    original_order_id TEXT NULL,
    original_receipt_id TEXT NULL,
    return_merchandise_value NUMERIC(12,2) NOT NULL,
    returned_at TIMESTAMP NOT NULL
);

CREATE TABLE refund (
    refund_id TEXT PRIMARY KEY,
    return_id TEXT NULL REFERENCES merchandise_return(return_id),
    refund_amount NUMERIC(12,2) NOT NULL,
    refunded_at TIMESTAMP NOT NULL
);

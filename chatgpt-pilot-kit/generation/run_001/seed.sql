INSERT INTO customer_reference VALUES ('C1','Synthetic Customer 1');

INSERT INTO orders VALUES
('O1','C1','100001',100.00,'2026-01-10 10:00:00','2026-01-10 10:05:00');

INSERT INTO order_line VALUES
('L1','O1','SKU-A',1,40.00,0.00),
('L2','O1','SKU-A',1,60.00,0.00);

INSERT INTO payment VALUES
('P1','O1',100.00),
('P2','O1',100.00);

INSERT INTO payment_authorization VALUES
('A1','P1',100.00,'DECLINED','2026-01-10 10:01:00'),
('A2','P1',100.00,'APPROVED','2026-01-10 10:02:00');

INSERT INTO payment_settlement VALUES
('S1','P2',60.00,'CAPTURE','2026-01-11 08:00:00'),
('S2','P2',40.00,'CAPTURE','2026-01-11 08:05:00');

INSERT INTO fulfillment_event VALUES
('F-E1','L1',0.4,'2026-01-11 09:00:00'),
('F-E2','L1',0.6,'2026-01-12 09:00:00');

INSERT INTO pos_receipt VALUES
('R1','C1','2026-01-10','LOC1','REG1','TX100',100.00),
('R2','C1','2026-01-11','LOC1','REG1','TX101',50.00);

INSERT INTO pos_item_occurrence VALUES
('I1','R1','SKU-X',1,40.00),
('I2','R1','SKU-Y',1,60.00),
('I3','R2','SKU-Z',1,50.00);

INSERT INTO pos_tender_leg VALUES
('T1','R1','CASH',30.00),
('T2','R1','VISA',70.00),
('T3','R2','CASH',20.00),
('T4','R2','CASH',30.00);

INSERT INTO merchandise_return VALUES
('RET1','C1','O1',NULL,100.00,'2026-01-15 12:00:00');

INSERT INTO refund VALUES
('RF1','RET1',80.00,'2026-01-16 09:30:00');

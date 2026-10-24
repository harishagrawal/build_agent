# Requirement: Customer spend summary

Given a JSON file of individual orders, produce a CSV report of total spend
per customer.

## Details

- Each input record has: `customer`, `item`, `quantity`, `unit_price`.
- Compute `total_spend = sum(quantity * unit_price)` per customer, across all
  of that customer's orders.
- Output one row per customer with columns: `customer`, `total_spend`,
  `order_count` (number of order line items that customer had).
- Round `total_spend` to 2 decimal places.
- Sort rows by `total_spend` descending (highest spender first).
- If the input file is empty (no orders), still write a CSV with just the
  header row.

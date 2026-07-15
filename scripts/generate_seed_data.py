#!/usr/bin/env python3
"""Deterministic fiction-retail seed data. Regenerating produces identical
CSVs (fixed RNG seed) so the committed seeds are reproducible."""
import csv
import random
from datetime import date, timedelta
from pathlib import Path

SEED_DIR = Path(__file__).resolve().parent.parent / "dbt_demo_project" / "seeds"
RNG = random.Random(20260715)

FIRST = ["Ada", "Grace", "Alan", "Edsger", "Barbara", "Donald", "Radia",
         "Vint", "Margaret", "Dennis", "Katherine", "Linus"]
LAST = ["Lovelace", "Hopper", "Turing", "Dijkstra", "Liskov", "Knuth",
        "Perlman", "Cerf", "Hamilton", "Ritchie", "Johnson", "Torvalds"]
COUNTRIES = ["AU", "US", "GB", "SG", "DE", "JP"]
STATUSES = ["completed"] * 55 + ["shipped"] * 20 + ["pending"] * 10 + \
           ["cancelled"] * 8 + ["refunded"] * 7


def main() -> None:
    SEED_DIR.mkdir(parents=True, exist_ok=True)
    customers = []
    for i in range(1, 61):
        customers.append({
            "customer_id": f"C{i:04d}",
            "full_name": f"{RNG.choice(FIRST)} {RNG.choice(LAST)}",
            "email": f"user{i:04d}@example.com",
            "country": RNG.choice(COUNTRIES),
            "signup_date": (date(2025, 1, 1) +
                            timedelta(days=RNG.randint(0, 400))).isoformat(),
        })
    with open(SEED_DIR / "raw_customers.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(customers[0]))
        w.writeheader()
        w.writerows(customers)

    orders = []
    for i in range(1, 301):
        cust = RNG.choice(customers)
        orders.append({
            "order_id": f"O{i:05d}",
            "customer_id": cust["customer_id"],
            "order_date": (date(2026, 1, 1) +
                           timedelta(days=RNG.randint(0, 180))).isoformat(),
            "order_status": RNG.choice(STATUSES),
            "order_total": f"{RNG.uniform(9.5, 480.0):.2f}",
            "currency": "USD",
        })
    with open(SEED_DIR / "raw_orders.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(orders[0]))
        w.writeheader()
        w.writerows(orders)
    print(f"wrote {len(customers)} customers, {len(orders)} orders -> {SEED_DIR}")


if __name__ == "__main__":
    main()

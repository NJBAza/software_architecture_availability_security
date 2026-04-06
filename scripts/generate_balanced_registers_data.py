"""Generate balanced synthetic CSV data for registers/data."""

from __future__ import annotations

import csv
import random
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "registers" / "data"

N_STOCK = 5000
N_ORDERS = 50000
N_ITEMS = 150000
N_RESERVATIONS = 20000
N_RECON_RUNS = 5000

SEED = 4109


def _fmt_dt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _write_csv(path: Path, fieldnames: list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(fieldnames)
        w.writerows(rows)


def generate() -> None:
    random.seed(SEED)
    base = datetime(2026, 3, 1, 8, 0, 0)

    warehouses = [f"WH{i:03d}" for i in range(1, 31)]
    sellers = [f"SELLER{i:03d}" for i in range(1, 121)]
    skus = [f"SKU{i:04d}" for i in range(1, 1201)]
    hot_stock = {f"STK{i:05d}" for i in range(1, 51)}

    stock_rows: list[list[str]] = []
    for i in range(1, N_STOCK + 1):
        sid = f"STK{i:05d}"
        sku = random.choice(skus)
        wh = random.choice(warehouses)
        if sid in hot_stock:
            qty_on_hand = random.randint(800, 1800)
            qty_reserved = random.randint(0, 100)
        else:
            qty_on_hand = random.randint(80, 900)
            qty_reserved = random.randint(0, int(qty_on_hand * 0.25))
        version = random.randint(1, 12)
        stock_rows.append([sid, sku, wh, str(qty_on_hand), str(qty_reserved), str(version)])

    reservations_rows: list[list[str]] = []
    for i in range(1, N_RESERVATIONS + 1):
        rid = f"RSV{i:06d}"
        idem = f"{random.getrandbits(128):032x}"
        sid = f"STK{random.randint(1, N_STOCK):05d}"
        qty = random.randint(1, 3)
        status = "ACTIVE" if random.random() < 0.88 else "EXPIRED"
        oid = f"ORD{random.randint(1, N_ORDERS):06d}"
        expires = base + timedelta(minutes=random.randint(5, 60 * 24 * 7))
        evt = f"EVT{random.randint(1, 999999):06d}"
        reservations_rows.append([rid, idem, sid, str(qty), status, oid, _fmt_dt(expires), evt])

    sales_rows: list[list[str]] = []
    for i in range(1, N_ORDERS + 1):
        oid = f"ORD{i:06d}"
        seller = random.choice(sellers)
        store = random.choice(warehouses)
        status = random.choices(
            ["CONFIRMED", "PENDING", "CANCELLED"],
            weights=[78, 18, 4],
            k=1,
        )[0]
        total = round(random.uniform(30, 3200), 2)
        res_ref = f"RSV{random.randint(1, N_RESERVATIONS):06d}" if random.random() < 0.7 else ""
        created = base + timedelta(seconds=i * 17)
        sales_rows.append([oid, seller, store, status, f"{total:.2f}", res_ref, _fmt_dt(created)])

    order_items_rows: list[list[str]] = []
    for i in range(1, N_ITEMS + 1):
        item = f"ITEM{i:07d}"
        oid = f"ORD{random.randint(1, N_ORDERS):06d}"
        sku = random.choice(skus)
        qty = random.randint(1, 5)
        price = round(random.uniform(8, 700), 2)
        order_items_rows.append([item, oid, sku, str(qty), f"{price:.2f}"])

    recon_rows: list[list[str]] = []
    for i in range(1, N_RECON_RUNS + 1):
        run = f"RUN{i:05d}"
        executed = base + timedelta(hours=i)
        anomalies = random.randint(0, 12)
        neg = "True" if random.random() < 0.03 else "False"
        ghost = random.randint(0, 4)
        action = random.choice(["none", "rollback", "alert"])
        recon_rows.append([run, _fmt_dt(executed), str(anomalies), neg, str(ghost), action])

    _write_csv(
        DATA_DIR / "warehouse_stock.csv",
        ["stock_id", "sku_id", "warehouse_id", "qty_on_hand", "qty_reserved", "version"],
        stock_rows,
    )
    _write_csv(
        DATA_DIR / "reservations.csv",
        ["reservation_id", "idempotency_key", "stock_id", "quantity", "status", "order_id", "expires_at", "outbox_event_id"],
        reservations_rows,
    )
    _write_csv(
        DATA_DIR / "sales_orders.csv",
        ["order_id", "seller_id", "store_id", "status", "total_amount", "reservation_id", "created_at"],
        sales_rows,
    )
    _write_csv(
        DATA_DIR / "order_items.csv",
        ["item_id", "order_id", "sku_id", "quantity", "unit_price"],
        order_items_rows,
    )
    _write_csv(
        DATA_DIR / "reconciliation_runs.csv",
        ["run_id", "executed_at", "anomalies_found", "stock_negativo", "reservas_fantasma", "action_taken"],
        recon_rows,
    )

    print(
        {
            "warehouse_stock": N_STOCK,
            "reservations": N_RESERVATIONS,
            "sales_orders": N_ORDERS,
            "order_items": N_ITEMS,
            "reconciliation_runs": N_RECON_RUNS,
            "path": str(DATA_DIR),
        }
    )


if __name__ == "__main__":
    generate()

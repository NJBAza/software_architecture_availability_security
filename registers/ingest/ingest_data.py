#!/usr/bin/env python

import re

import click
import pandas as pd
from sqlalchemy import create_engine, text
from tqdm.auto import tqdm


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [col.strip().lower() for col in df.columns]
    return df


def safe_ident(name: str) -> str:
    if not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*", name):
        raise ValueError(f"Invalid SQL identifier: {name}")
    return name


def column_exists(conn, table_name: str, column_name: str) -> bool:
    result = conn.execute(
        text("""
            SELECT COUNT(*)
            FROM information_schema.columns
            WHERE table_name = :table_name
              AND column_name = :column_name
        """),
        {"table_name": table_name, "column_name": column_name},
    )
    return result.scalar() > 0


def pk_exists(conn, table_name: str) -> bool:
    result = conn.execute(
        text("""
            SELECT COUNT(*)
            FROM information_schema.table_constraints
            WHERE table_name = :table_name
              AND constraint_type = 'PRIMARY KEY'
        """),
        {"table_name": table_name},
    )
    return result.scalar() > 0


def sync_sales_orders_sequence(conn):
    conn.execute(
        text("""
        SELECT setval(
            'sales_orders_seq',
            GREATEST(
                COALESCE(
                    (
                        SELECT MAX(
                            CASE
                                WHEN order_id ~ '^ORD[0-9]+$'
                                THEN CAST(SUBSTRING(order_id FROM 4) AS INTEGER)
                                ELSE 0
                            END
                        )
                        FROM sales_orders
                    ),
                    0
                ),
                1
            ),
            true
        )
    """)
    )


def apply_sales_orders_metadata(conn):
    conn.execute(
        text("""
        CREATE SEQUENCE IF NOT EXISTS sales_orders_seq START 1
    """)
    )

    if column_exists(conn, "sales_orders", "order_id"):
        conn.execute(
            text("""
            ALTER TABLE sales_orders
            ALTER COLUMN order_id SET DEFAULT
            'ORD' || LPAD(nextval('sales_orders_seq')::TEXT, 6, '0')
        """)
        )
        conn.execute(
            text("""
            ALTER TABLE sales_orders
            ALTER COLUMN order_id SET NOT NULL
        """)
        )

    if column_exists(conn, "sales_orders", "created_at"):
        conn.execute(
            text("""
            ALTER TABLE sales_orders
            ALTER COLUMN created_at SET DEFAULT CURRENT_TIMESTAMP
        """)
        )
        conn.execute(
            text("""
            ALTER TABLE sales_orders
            ALTER COLUMN created_at SET NOT NULL
        """)
        )

    # fill only missing values, preserving CSV-provided values
    conn.execute(
        text("""
        UPDATE sales_orders
        SET order_id = 'ORD' || LPAD(nextval('sales_orders_seq')::TEXT, 6, '0')
        WHERE order_id IS NULL
    """)
    )

    conn.execute(
        text("""
        UPDATE sales_orders
        SET created_at = CURRENT_TIMESTAMP
        WHERE created_at IS NULL
    """)
    )

    sync_sales_orders_sequence(conn)

    if not pk_exists(conn, "sales_orders"):
        conn.execute(
            text("""
            ALTER TABLE sales_orders
            ADD CONSTRAINT sales_orders_pk PRIMARY KEY (order_id)
        """)
        )


@click.command()
@click.option("--pg-user", default="root", help="PostgreSQL user")
@click.option("--pg-pass", default="root", help="PostgreSQL password")
@click.option("--pg-host", default="localhost", help="PostgreSQL host")
@click.option("--pg-port", default=5432, type=int, help="PostgreSQL port")
@click.option("--pg-db", default="warehouse_reservations", help="PostgreSQL database name")
@click.option("--csv-file", required=True, help="Path to local CSV file")
@click.option("--target-table", required=True, help="Target table name")
@click.option("--chunksize", default=50, type=int, help="Chunk size for reading CSV")
def run(pg_user, pg_pass, pg_host, pg_port, pg_db, csv_file, target_table, chunksize):
    target_table = safe_ident(target_table)

    engine = create_engine(
        f"postgresql+psycopg2://{pg_user}:{pg_pass}@{pg_host}:{pg_port}/{pg_db}"
    )

    df_iter = pd.read_csv(
        csv_file,
        iterator=True,
        chunksize=chunksize,
        low_memory=False,
    )

    first = True
    total_rows = 0

    for df_chunk in tqdm(df_iter, desc="Loading CSV chunks"):
        df_chunk = normalize_columns(df_chunk)

        if first:
            df_chunk.head(0).to_sql(
                name=target_table,
                con=engine,
                if_exists="replace",
                index=False,
            )
            first = False

        df_chunk.to_sql(
            name=target_table,
            con=engine,
            if_exists="append",
            index=False,
        )
        total_rows += len(df_chunk)

    with engine.begin() as conn:
        if target_table == "sales_orders":
            apply_sales_orders_metadata(conn)

    with engine.connect() as conn:
        result = conn.execute(text(f"SELECT COUNT(*) FROM {target_table}"))
        count_in_db = result.scalar()

    print("Finished ingestion.")
    print(f"Rows loaded from CSV: {total_rows}")
    print(f"Rows in database table '{target_table}': {count_in_db}")


if __name__ == "__main__":
    run()

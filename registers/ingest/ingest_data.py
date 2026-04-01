#!/usr/bin/env python

import click
import pandas as pd
from sqlalchemy import create_engine, text
from tqdm.auto import tqdm


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [col.strip().lower() for col in df.columns]
    return df


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
    """Ingest local CSV data into PostgreSQL database."""
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
                name=target_table, con=engine, if_exists="replace", index=False
            )
            first = False

        df_chunk.to_sql(name=target_table, con=engine, if_exists="append", index=False)

        total_rows += len(df_chunk)

    with engine.connect() as conn:
        result = conn.execute(text(f"SELECT COUNT(*) FROM {target_table}"))
        count_in_db = result.scalar()

    print("Finished ingestion.")
    print(f"Rows loaded from CSV: {total_rows}")
    print(f"Rows in database table '{target_table}': {count_in_db}")


if __name__ == "__main__":
    run()

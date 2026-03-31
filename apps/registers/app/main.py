import os
from fastapi import FastAPI
from sqlalchemy import create_engine, text

DB_HOST = os.getenv("DB_HOST", "pgdatabase")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "ny_taxi")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "root")

DATABASE_URL = f"postgresql+psycopg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

app = FastAPI(title="Taxi API")

engine = create_engine(DATABASE_URL)


@app.get("/")
def root():
    return {"message": "FastAPI + PostgreSQL is running"}


@app.get("/health")
def health():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@app.get("/taxis/count")
def taxis_count():
    with engine.connect() as conn:
        result = conn.execute(text("SELECT COUNT(*) FROM taxis"))
        count = result.scalar()
    return {"table": "taxis", "rows": count}


@app.get("/taxis/preview")
def taxis_preview(limit: int = 10):
    query = text(f"SELECT * FROM taxis LIMIT {limit}")
    with engine.connect() as conn:
        result = conn.execute(query)
        rows = [dict(row._mapping) for row in result]
    return {
        "table": "taxis",
        "limit": limit,
        "rows": rows
    }
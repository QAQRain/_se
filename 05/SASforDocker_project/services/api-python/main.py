from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

app = FastAPI()

class Health(BaseModel):
    status: str
    service: str
    ts: str

@app.get("/health", response_model=Health)
async def health():
    return Health(status="ok", service="api-python", ts=datetime.utcnow().isoformat() + "Z")

@app.get("/db")
async def db_check():
    dsn = {
        "host": os.getenv("DB_HOST", "postgres"),
        "port": os.getenv("DB_PORT", "5432"),
        "user": os.getenv("DB_USER", "sas"),
        "password": os.getenv("DB_PASS", "saspass"),
        "database": os.getenv("DB_NAME", "sasdb"),
    }
    try:
        conn = psycopg2.connect(**dsn)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM health_check ORDER BY id")
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
        conn.close()
        return {"status": "ok", "rows": rows}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

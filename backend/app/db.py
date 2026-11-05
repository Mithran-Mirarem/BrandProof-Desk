import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = os.getenv("BRANDPROOF_DB_PATH", str(Path(__file__).resolve().parent.parent / "brandproof.db"))

@contextmanager
def conn():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    try:
        yield db
        db.commit()
    finally:
        db.close()

def now():
    return datetime.now(timezone.utc).isoformat()

def init_db():
    with conn() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS brand_profile (
            id INTEGER PRIMARY KEY CHECK (id=1),
            name TEXT NOT NULL,
            tone TEXT NOT NULL,
            required_terms TEXT NOT NULL,
            forbidden_terms TEXT NOT NULL,
            approved_facts TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS reviews (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            channel TEXT NOT NULL,
            brief TEXT NOT NULL,
            original_text TEXT NOT NULL,
            revised_text TEXT NOT NULL,
            status TEXT NOT NULL,
            findings TEXT NOT NULL,
            agent_mode TEXT NOT NULL,
            agent_plan TEXT NOT NULL DEFAULT '[]',
            evidence TEXT NOT NULL DEFAULT '[]',
            summary TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS audit_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            review_id TEXT NOT NULL,
            event TEXT NOT NULL,
            detail TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """)
        # Lightweight schema migrations for existing local databases.
        review_cols={r[1] for r in db.execute("PRAGMA table_info(reviews)").fetchall()}
        for col, definition in [("agent_plan", "TEXT NOT NULL DEFAULT '[]'"), ("evidence", "TEXT NOT NULL DEFAULT '[]'"), ("summary", "TEXT NOT NULL DEFAULT ''")]:
            if col not in review_cols:
                db.execute(f"ALTER TABLE reviews ADD COLUMN {col} {definition}")
        row = db.execute("SELECT id FROM brand_profile WHERE id=1").fetchone()
        if not row:
            db.execute("""INSERT INTO brand_profile
            (id,name,tone,required_terms,forbidden_terms,approved_facts,updated_at)
            VALUES (1,?,?,?,?,?,?)""", (
                "Northstar Analytics",
                "Professional, clear, confident and evidence-led. Avoid hype, absolute guarantees and exaggerated superlatives. Prefer specific benefits and plain language.",
                json.dumps(["Northstar Analytics", "analytics workspace"]),
                json.dumps(["guaranteed results", "100% success", "revolutionary", "best in the world"]),
                json.dumps([
                    {"id":"FACT-001","claim":"Northstar Analytics provides dashboards, reporting and workflow insights.","source":"Approved product facts v1.2","valid_until":"2027-12-31","status":"approved"},
                    {"id":"FACT-002","claim":"Customer outcomes vary by organisation, data quality and implementation.","source":"Approved product facts v1.2","valid_until":"2027-12-31","status":"approved"},
                    {"id":"POLICY-003","claim":"Do not promise guaranteed financial, operational or customer outcomes.","source":"Brand claims policy v1.0","valid_until":"2027-12-31","status":"approved"}
                ]), now()))

def get_brand():
    with conn() as db:
        row = db.execute("SELECT * FROM brand_profile WHERE id=1").fetchone()
        return {"name":row["name"],"tone":row["tone"],"required_terms":json.loads(row["required_terms"]),
                "forbidden_terms":json.loads(row["forbidden_terms"]),"approved_facts":json.loads(row["approved_facts"]),"updated_at":row["updated_at"]}

def save_brand(data):
    with conn() as db:
        db.execute("""UPDATE brand_profile SET name=?,tone=?,required_terms=?,forbidden_terms=?,approved_facts=?,updated_at=? WHERE id=1""",
                   (data["name"],data["tone"],json.dumps(data["required_terms"]),json.dumps(data["forbidden_terms"]),json.dumps(data["approved_facts"]),now()))

def add_review(review):
    with conn() as db:
        db.execute("""INSERT INTO reviews
            (id,title,channel,brief,original_text,revised_text,status,findings,agent_mode,agent_plan,evidence,summary,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",(
            review["id"],review["title"],review["channel"],review["brief"],review["original_text"],review["revised_text"],
            review["status"],json.dumps(review["findings"]),review["agent_mode"],json.dumps(review.get("agent_plan",[])),
            json.dumps(review.get("evidence",[])),review.get("summary",""),review["created_at"],review["updated_at"]))
        db.execute("INSERT INTO audit_events(review_id,event,detail,created_at) VALUES (?,?,?,?)",
                   (review["id"],"review_created","Content submitted for brand governance review",review["created_at"]))

def get_review(review_id):
    with conn() as db:
        row = db.execute("SELECT * FROM reviews WHERE id=?",(review_id,)).fetchone()
        if not row: return None
        result = dict(row)
        for field in ("findings","agent_plan","evidence"):
            result[field] = json.loads(result[field])
        return result

def list_reviews():
    with conn() as db:
        rows = db.execute("SELECT * FROM reviews ORDER BY created_at DESC").fetchall()
        out=[]
        for row in rows:
            item=dict(row)
            for field in ("findings","agent_plan","evidence"):
                item[field]=json.loads(item[field])
            out.append(item)
        return out

def update_review(review_id, **fields):
    allowed={"status","revised_text","findings"}
    fields={k:(json.dumps(v) if k=="findings" else v) for k,v in fields.items() if k in allowed}
    fields["updated_at"]=now()
    with conn() as db:
        sql=", ".join(f"{k}=?" for k in fields)
        db.execute(f"UPDATE reviews SET {sql} WHERE id=?",(*fields.values(),review_id))

def audit(review_id,event,detail):
    with conn() as db:
        db.execute("INSERT INTO audit_events(review_id,event,detail,created_at) VALUES (?,?,?,?)",(review_id,event,detail,now()))

def get_audit(review_id):
    with conn() as db:
        rows=db.execute("SELECT event,detail,created_at FROM audit_events WHERE review_id=? ORDER BY id DESC",(review_id,)).fetchall()
        return [dict(r) for r in rows]

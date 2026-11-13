import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone, date
from pathlib import Path

DB_PATH = os.getenv("BRANDPROOF_DB_PATH", str(Path(__file__).resolve().parent.parent / "brandproof.db"))

@contextmanager
def conn():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    try:
        yield db
        db.commit()
    finally:
        db.close()

def now():
    return datetime.now(timezone.utc).isoformat()

def _json(value, fallback):
    try:
        return json.loads(value) if value else fallback
    except (TypeError, ValueError):
        return fallback

def _effective_status(record):
    status = (record.get("status") or "approved").lower()
    today = date.today()
    if status not in {"approved", "pending_verification", "archived", "expired", "scheduled"}:
        status = "pending_verification"
    if status == "approved":
        try:
            valid_from = date.fromisoformat(record["valid_from"]) if record.get("valid_from") else None
            valid_until = date.fromisoformat(record["valid_until"]) if record.get("valid_until") else None
        except ValueError:
            return "pending_verification"
        if valid_from and valid_from > today:
            return "scheduled"
        if valid_until and valid_until < today:
            return "expired"
    return status

def init_db():
    with conn() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS brand_profile (
            id INTEGER PRIMARY KEY CHECK (id=1), name TEXT NOT NULL, tone TEXT NOT NULL,
            required_terms TEXT NOT NULL, forbidden_terms TEXT NOT NULL,
            approved_facts TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS reviews (
            id TEXT PRIMARY KEY, title TEXT NOT NULL, channel TEXT NOT NULL, brief TEXT NOT NULL,
            original_text TEXT NOT NULL, revised_text TEXT NOT NULL, status TEXT NOT NULL,
            findings TEXT NOT NULL, agent_mode TEXT NOT NULL, agent_plan TEXT NOT NULL DEFAULT '[]',
            evidence TEXT NOT NULL DEFAULT '[]', summary TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS audit_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT, review_id TEXT NOT NULL,
            event TEXT NOT NULL, detail TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS evidence_records (
            id TEXT PRIMARY KEY, claim TEXT NOT NULL, source TEXT NOT NULL,
            source_url TEXT NOT NULL DEFAULT '', owner TEXT NOT NULL DEFAULT '',
            version TEXT NOT NULL DEFAULT '1.0', valid_from TEXT NOT NULL DEFAULT '',
            valid_until TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'approved',
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS evidence_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT, evidence_id TEXT NOT NULL,
            event TEXT NOT NULL, detail TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS visual_config (
            id INTEGER PRIMARY KEY CHECK (id=1), palette TEXT NOT NULL DEFAULT '[]',
            logo_reference_path TEXT NOT NULL DEFAULT '', logo_reference_name TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS visual_reviews (
            id TEXT PRIMARY KEY, filename TEXT NOT NULL, findings TEXT NOT NULL,
            palette TEXT NOT NULL, ocr_text TEXT NOT NULL DEFAULT '',
            sha256 TEXT NOT NULL DEFAULT '', width INTEGER NOT NULL DEFAULT 0,
            height INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL
        );
        """)
        review_cols={r[1] for r in db.execute("PRAGMA table_info(reviews)").fetchall()}
        for col, definition in [("agent_plan", "TEXT NOT NULL DEFAULT '[]'"), ("evidence", "TEXT NOT NULL DEFAULT '[]'"), ("summary", "TEXT NOT NULL DEFAULT ''")]:
            if col not in review_cols:
                db.execute(f"ALTER TABLE reviews ADD COLUMN {col} {definition}")
        row = db.execute("SELECT id FROM brand_profile WHERE id=1").fetchone()
        if not row:
            facts = [
                {"id":"FACT-001","claim":"Northstar Analytics provides dashboards, reporting and workflow insights.","source":"Approved product facts v1.2","owner":"Brand team","version":"1.2","valid_from":"2026-01-01","valid_until":"2027-12-31","status":"approved"},
                {"id":"FACT-002","claim":"Customer outcomes vary by organisation, data quality and implementation.","source":"Approved product facts v1.2","owner":"Brand team","version":"1.2","valid_from":"2026-01-01","valid_until":"2027-12-31","status":"approved"},
                {"id":"POLICY-003","claim":"Do not promise guaranteed financial, operational or customer outcomes.","source":"Brand claims policy v1.0","owner":"Legal and brand team","version":"1.0","valid_from":"2026-01-01","valid_until":"2027-12-31","status":"approved"}
            ]
            db.execute("""INSERT INTO brand_profile (id,name,tone,required_terms,forbidden_terms,approved_facts,updated_at)
                VALUES (1,?,?,?,?,?,?)""", (
                "Northstar Analytics",
                "Professional, clear, confident and evidence-led. Avoid hype, absolute guarantees and exaggerated superlatives. Prefer specific benefits and plain language.",
                json.dumps(["Northstar Analytics", "analytics workspace"]),
                json.dumps(["guaranteed results", "100% success", "revolutionary", "best in the world"]),
                json.dumps(facts), now()))
        # One-time migration: enrich legacy JSON facts with provenance fields.
        count = db.execute("SELECT COUNT(*) FROM evidence_records").fetchone()[0]
        if count == 0:
            profile = db.execute("SELECT approved_facts FROM brand_profile WHERE id=1").fetchone()
            for idx, fact in enumerate(_json(profile[0] if profile else "[]", []), 1):
                _insert_evidence(db, fact, default_id=f"FACT-{idx:03d}")
        visual_cols={r[1] for r in db.execute("PRAGMA table_info(visual_reviews)").fetchall()}
        for col, definition in [("sha256", "TEXT NOT NULL DEFAULT ''"), ("width", "INTEGER NOT NULL DEFAULT 0"), ("height", "INTEGER NOT NULL DEFAULT 0")]:
            if col not in visual_cols:
                db.execute(f"ALTER TABLE visual_reviews ADD COLUMN {col} {definition}")
        db.execute("INSERT OR IGNORE INTO visual_config(id,palette,updated_at) VALUES (1,'[]',?)", (now(),))

def _insert_evidence(db, record, default_id=None):
    stamp = now()
    evidence_id = str(record.get("id") or default_id or f"FACT-{int(datetime.now().timestamp())}")[:80]
    db.execute("""INSERT OR REPLACE INTO evidence_records
        (id,claim,source,source_url,owner,version,valid_from,valid_until,status,created_at,updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)""", (
        evidence_id, str(record.get("claim", "")).strip(), str(record.get("source", "User-added approved source")),
        str(record.get("source_url", "")), str(record.get("owner", "Unassigned")),
        str(record.get("version", "1.0")), str(record.get("valid_from", "")),
        str(record.get("valid_until", record.get("expires_at", ""))),
        str(record.get("status", "approved")), str(record.get("created_at", stamp)), stamp))
    return evidence_id

def list_evidence_records():
    with conn() as db:
        rows = db.execute("SELECT * FROM evidence_records ORDER BY updated_at DESC, id").fetchall()
    result=[]
    for row in rows:
        item=dict(row)
        item["source_status"] = item["status"]
        item["status"] = _effective_status(item)
        item["is_current"] = item["status"] == "approved"
        try:
            expiry = date.fromisoformat(item.get("valid_until", "")) if item.get("valid_until") else None
            item["expires_soon"] = bool(item["status"] == "approved" and expiry and 0 <= (expiry - date.today()).days <= 30)
        except ValueError:
            item["expires_soon"] = False
        result.append(item)
    return result

def create_evidence_record(record):
    with conn() as db:
        evidence_id = _insert_evidence(db, record)
        db.execute("INSERT INTO evidence_events(evidence_id,event,detail,created_at) VALUES (?,?,?,?)", (
            evidence_id, "created", f"Created from {record.get('source', 'unspecified source')} · owner {record.get('owner', 'unassigned')} · version {record.get('version', '1.0')} · state {record.get('status', 'pending_verification')}", now()))
    return get_evidence_record(evidence_id)

def get_evidence_record(evidence_id):
    with conn() as db:
        row=db.execute("SELECT * FROM evidence_records WHERE id=?", (evidence_id,)).fetchone()
    if not row: return None
    item=dict(row); item["source_status"]=item["status"]; item["status"]=_effective_status(item); item["is_current"]=item["status"]=="approved"
    return item

def update_evidence_record(evidence_id, record):
    with conn() as db:
        previous=db.execute("SELECT * FROM evidence_records WHERE id=?", (evidence_id,)).fetchone()
        if not previous: return None
        previous=dict(previous)
        tracked = ("claim", "source", "source_url", "owner", "version", "valid_from", "valid_until", "status")
        changed = [field for field in tracked if str(previous.get(field, "")) != str(record.get(field, ""))]
        db.execute("""UPDATE evidence_records SET claim=?,source=?,source_url=?,owner=?,version=?,valid_from=?,valid_until=?,status=?,updated_at=? WHERE id=?""", (
            str(record.get("claim", "")).strip(), str(record.get("source", "")), str(record.get("source_url", "")),
            str(record.get("owner", "")), str(record.get("version", "1.0")), str(record.get("valid_from", "")),
            str(record.get("valid_until", "")), str(record.get("status", "pending_verification")), now(), evidence_id))
        db.execute("INSERT INTO evidence_events(evidence_id,event,detail,created_at) VALUES (?,?,?,?)", (
            evidence_id, "updated", f"Updated fields: {', '.join(changed) if changed else 'no material fields'} · new version {record.get('version', '1.0')} · state {record.get('status', 'pending_verification')}", now()))
    return get_evidence_record(evidence_id)

def delete_evidence_record(evidence_id):
    with conn() as db:
        previous=db.execute("SELECT source,owner,version FROM evidence_records WHERE id=?", (evidence_id,)).fetchone()
        if not previous: return False
        db.execute("INSERT INTO evidence_events(evidence_id,event,detail,created_at) VALUES (?,?,?,?)", (
            evidence_id, "deleted", f"Deleted record from {previous['source']} · owner {previous['owner']} · version {previous['version']}", now()))
        db.execute("DELETE FROM evidence_records WHERE id=?", (evidence_id,))
        return True

def get_evidence_history(evidence_id):
    with conn() as db:
        rows=db.execute("SELECT event,detail,created_at FROM evidence_events WHERE evidence_id=? ORDER BY id DESC", (evidence_id,)).fetchall()
    return [dict(row) for row in rows]

def get_visual_config():
    with conn() as db:
        row=db.execute("SELECT * FROM visual_config WHERE id=1").fetchone()
    item=dict(row) if row else {"palette":"[]","logo_reference_path":"","logo_reference_name":""}
    return {"palette":_json(item.get("palette"), []), "logo_reference_name":item.get("logo_reference_name", ""), "has_logo_reference":bool(item.get("logo_reference_path"))}

def save_visual_palette(palette):
    with conn() as db:
        db.execute("UPDATE visual_config SET palette=?,updated_at=? WHERE id=1", (json.dumps(palette), now()))
    return get_visual_config()

def set_logo_reference(path, name):
    with conn() as db:
        db.execute("UPDATE visual_config SET logo_reference_path=?,logo_reference_name=?,updated_at=? WHERE id=1", (path, name, now()))
    return get_visual_config()

def clear_logo_reference():
    with conn() as db:
        db.execute("UPDATE visual_config SET logo_reference_path='',logo_reference_name='',updated_at=? WHERE id=1", (now(),))
    return get_visual_config()

def get_logo_reference_path():
    with conn() as db:
        row=db.execute("SELECT logo_reference_path FROM visual_config WHERE id=1").fetchone()
    return row[0] if row and row[0] else ""

def add_visual_review(item):
    with conn() as db:
        db.execute("INSERT INTO visual_reviews(id,filename,findings,palette,ocr_text,sha256,width,height,created_at) VALUES (?,?,?,?,?,?,?,?,?)", (
            item["id"], item["filename"], json.dumps(item["findings"]), json.dumps(item.get("palette", item.get("dominant_colors", []))),
            item.get("ocr_text", ""), item.get("sha256", ""), int(item.get("width", 0)), int(item.get("height", 0)), item["created_at"]))
    return item

def list_visual_reviews():
    with conn() as db:
        rows=db.execute("SELECT * FROM visual_reviews ORDER BY created_at DESC").fetchall()
    return [{**dict(r), "findings":_json(r["findings"], []), "palette":_json(r["palette"], [])} for r in rows]

def get_brand():
    with conn() as db:
        row = db.execute("SELECT * FROM brand_profile WHERE id=1").fetchone()
    return {"name":row["name"],"tone":row["tone"],"required_terms":_json(row["required_terms"],[]),
            "forbidden_terms":_json(row["forbidden_terms"],[]),"approved_facts":list_evidence_records(),"updated_at":row["updated_at"]}

def save_brand(data):
    with conn() as db:
        db.execute("""UPDATE brand_profile SET name=?,tone=?,required_terms=?,forbidden_terms=?,approved_facts=?,updated_at=? WHERE id=1""",
            (data["name"],data["tone"],json.dumps(data["required_terms"]),json.dumps(data["forbidden_terms"]),json.dumps(data["approved_facts"]),now()))
        # Keep the legacy JSON editor backward-compatible while retaining enriched fields.
        for idx, fact in enumerate(data["approved_facts"], 1):
            evidence_id = str(fact.get("id") or f"FACT-{idx:03d}")
            current = db.execute("SELECT * FROM evidence_records WHERE id=?", (evidence_id,)).fetchone()
            merged = dict(current) if current else {}
            merged.update(fact)
            _insert_evidence(db, merged, default_id=f"FACT-{idx:03d}")
            tracked = ("claim", "source", "source_url", "owner", "version", "valid_from", "valid_until", "status")
            if current is None:
                detail = f"Created through brand vault · source {merged.get('source', 'unspecified')} · owner {merged.get('owner', 'unassigned')}"
                db.execute("INSERT INTO evidence_events(evidence_id,event,detail,created_at) VALUES (?,?,?,?)", (evidence_id, "created", detail, now()))
            else:
                changed = [field for field in tracked if str(current[field] or "") != str(merged.get(field, ""))]
                if changed:
                    detail = f"Updated through brand vault · fields: {', '.join(changed)} · version {merged.get('version', '1.0')}"
                    db.execute("INSERT INTO evidence_events(evidence_id,event,detail,created_at) VALUES (?,?,?,?)", (evidence_id, "updated", detail, now()))

def add_review(review):
    with conn() as db:
        db.execute("""INSERT INTO reviews (id,title,channel,brief,original_text,revised_text,status,findings,agent_mode,agent_plan,evidence,summary,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",(
            review["id"],review["title"],review["channel"],review["brief"],review["original_text"],review["revised_text"],
            review["status"],json.dumps(review["findings"]),review["agent_mode"],json.dumps(review.get("agent_plan",[])),
            json.dumps(review.get("evidence",[])),review.get("summary",""),review["created_at"],review["updated_at"]))
        db.execute("INSERT INTO audit_events(review_id,event,detail,created_at) VALUES (?,?,?,?)",
            (review["id"],"review_created","Content submitted for brand governance review",review["created_at"]))

def _review_from_row(row):
    if not row: return None
    result=dict(row)
    for field in ("findings","agent_plan","evidence"):
        result[field]=_json(result.get(field),[])
    return result

def get_review(review_id):
    with conn() as db: row=db.execute("SELECT * FROM reviews WHERE id=?",(review_id,)).fetchone()
    return _review_from_row(row)

def list_reviews():
    with conn() as db: rows=db.execute("SELECT * FROM reviews ORDER BY created_at DESC").fetchall()
    return [_review_from_row(row) for row in rows]

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

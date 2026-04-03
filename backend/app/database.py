"""SQLite database manager for FairFuel."""
import sqlite3
import math
import logging
from typing import Optional
from app.config import DB_PATH, EARTH_RADIUS_KM

logger = logging.getLogger(__name__)

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-64000")
    conn.create_function("haversine", 4, _haversine)
    return conn

def _haversine(lat1, lon1, lat2, lon2):
    try:
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1; dlon = lon2 - lon1
        a = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
        return EARTH_RADIUS_KM * 2 * math.asin(math.sqrt(a))
    except: return 99999.0

def init_db():
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS stations (
            id_impianto INTEGER PRIMARY KEY,
            gestore TEXT, bandiera TEXT, tipo_impianto TEXT,
            nome_impianto TEXT, indirizzo TEXT, comune TEXT,
            provincia TEXT, latitudine REAL, longitudine REAL
        );
        CREATE TABLE IF NOT EXISTS prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_impianto INTEGER NOT NULL, descr_carburante TEXT NOT NULL,
            prezzo REAL NOT NULL, is_self INTEGER NOT NULL DEFAULT 1,
            dt_comunic TEXT, FOREIGN KEY (id_impianto) REFERENCES stations(id_impianto)
        );
        CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT);
        CREATE INDEX IF NOT EXISTS idx_stations_comune ON stations(comune);
        CREATE INDEX IF NOT EXISTS idx_stations_provincia ON stations(provincia);
        CREATE INDEX IF NOT EXISTS idx_stations_bandiera ON stations(bandiera);
        CREATE INDEX IF NOT EXISTS idx_stations_coords ON stations(latitudine, longitudine);
        CREATE INDEX IF NOT EXISTS idx_prices_impianto ON prices(id_impianto);
        CREATE INDEX IF NOT EXISTS idx_prices_fuel_self_price ON prices(descr_carburante, is_self, prezzo);
    """)
    conn.commit(); conn.close()

def get_last_update():
    conn = get_connection()
    cur = conn.execute("SELECT value FROM metadata WHERE key='last_update'")
    row = cur.fetchone(); conn.close()
    return row["value"] if row else None

def get_stats():
    conn = get_connection(); c = conn.cursor()
    c.execute("SELECT COUNT(*) as n FROM stations"); stations = c.fetchone()["n"]
    c.execute("SELECT COUNT(*) as n FROM prices"); prices = c.fetchone()["n"]
    c.execute("SELECT COUNT(DISTINCT bandiera) as n FROM stations"); brands = c.fetchone()["n"]
    conn.close()
    return {"stations": stations, "prices": prices, "brands": brands, "last_update": get_last_update()}


import requests as _requests
from app.config import TURSO_URL, TURSO_TOKEN


def _turso_execute(sql, args=None):
    """Execute SQL against Turso via HTTP API. Returns list of row dicts."""
    if not TURSO_URL or not TURSO_TOKEN:
        return []
    base = TURSO_URL.replace("libsql://", "https://")
    url = f"{base}/v2/pipeline"
    stmt = {"sql": sql}
    if args:
        stmt["args"] = args
    payload = {"requests": [{"type": "execute", "stmt": stmt}, {"type": "close"}]}
    try:
        resp = _requests.post(
            url, json=payload,
            headers={"Authorization": f"Bearer {TURSO_TOKEN}",
                     "Content-Type": "application/json"},
            timeout=10
        )
        resp.raise_for_status()
        data = resp.json()
        result = data["results"][0]
        if result["type"] == "error":
            raise RuntimeError(result["error"]["message"])
        rows_data = result["response"]["result"]
        cols = [c["name"] for c in rows_data["cols"]]
        return [dict(zip(cols, [v.get("value") for v in row])) for row in rows_data["rows"]]
    except Exception as exc:
        logger.error(f"Turso error: {exc}")
        return []


def init_turso_db():
    """Create user_reports table in Turso if not exists."""
    if not TURSO_URL or not TURSO_TOKEN:
        logger.warning("TURSO_URL/TURSO_TOKEN not set — community prices disabled")
        return
    _turso_execute(
        "CREATE TABLE IF NOT EXISTS user_reports ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "id_impianto INTEGER NOT NULL, "
        "descr_carburante TEXT NOT NULL, "
        "is_self INTEGER NOT NULL DEFAULT 0, "
        "prezzo REAL NOT NULL, "
        "segnalato_il TEXT NOT NULL)"
    )
    logger.info("Turso DB ready")


def save_user_report(id_impianto: int, descr_carburante: str, is_self: bool, prezzo: float):
    from datetime import datetime
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    _turso_execute(
        "INSERT INTO user_reports (id_impianto, descr_carburante, is_self, prezzo, segnalato_il) "
        "VALUES (?, ?, ?, ?, ?)",
        [
            {"type": "integer", "value": str(id_impianto)},
            {"type": "text",    "value": descr_carburante},
            {"type": "integer", "value": "1" if is_self else "0"},
            {"type": "float",   "value": str(prezzo)},
            {"type": "text",    "value": now},
        ]
    )


def get_user_reports(id_impianto_list: list) -> dict:
    """Returns {id_impianto: [reports]} for the given station IDs."""
    if not TURSO_URL or not TURSO_TOKEN or not id_impianto_list:
        return {}
    placeholders = ",".join("?" * len(id_impianto_list))
    rows = _turso_execute(
        f"SELECT * FROM user_reports WHERE id_impianto IN ({placeholders}) ORDER BY id DESC",
        [{"type": "integer", "value": str(i)} for i in id_impianto_list]
    )
    result = {}
    for row in rows:
        iid = int(row["id_impianto"])
        result.setdefault(iid, []).append({
            "descr_carburante": row["descr_carburante"],
            "is_self": bool(int(row["is_self"] or 0)),
            "prezzo": float(row["prezzo"]),
            "segnalato_il": row["segnalato_il"],
        })
    return result


def get_station_coords(id_impianto: int) -> Optional[dict]:
    """Returns {latitudine, longitudinee} for a station, or None."""
    conn = get_connection()
    cur = conn.execute(
        "SELECT latitudine, longitudinee FROM stations WHERE id_impianto = ?",
        (id_impianto,)
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return {"lat": row["latitudine"], "lon": row["longitudinee"]}

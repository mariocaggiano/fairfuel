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

"""Data ingestion: download, parse, clean, and load MIMIT CSV data."""
import io, tarfile, logging, sqlite3
from datetime import datetime
from typing import Optional
import pandas as pd
import requests
from app.config import ANAGRAFICA_URL, PREZZI_URL, CSV_ENCODING
from app.database import get_connection

logger = logging.getLogger(__name__)

def download_csv(url: str, timeout: int = 120) -> Optional[str]:
    logger.info(f"Downloading: {url}")
    try:
        resp = requests.get(url, timeout=timeout, stream=True)
        resp.raise_for_status()
        raw = resp.content
        try:
            with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as tar:
                for m in tar.getmembers():
                    if m.name.endswith(".csv"):
                        f = tar.extractfile(m)
                        if f: return f.read().decode(CSV_ENCODING, errors="replace")
        except: pass
        return raw.decode(CSV_ENCODING, errors="replace")
    except requests.RequestException as e:
        logger.error(f"Download failed {url}: {e}")
        return None

def _detect_delimiter(text: str) -> str:
    first_line = text.split("\n", 1)[0]
    for d in ["|", ";", ","]:
        if d in first_line: return d
    return "|"

def _read_csv(text: str) -> pd.DataFrame:
    sep = _detect_delimiter(text)
    return pd.read_csv(io.StringIO(text), sep=sep, encoding=CSV_ENCODING, dtype=str, on_bad_lines="skip")

def _normalize_columns(df: pd.DataFrame, mapping: dict) -> pd.DataFrame:
    col_map = {}
    for col in df.columns:
        key = col.strip().lower().replace(" ","").replace("_","")
        for pattern, target in mapping.items():
            if pattern in key: col_map[col] = target; break
    return df.rename(columns=col_map)

def parse_anagrafica(csv_text: str) -> pd.DataFrame:
    df = _read_csv(csv_text)
    df = _normalize_columns(df, {
        "idimpianto":"id_impianto","gestore":"gestore","bandiera":"bandiera",
        "tipoimpianto":"tipo_impianto","nome":"nome_impianto","indirizzo":"indirizzo",
        "comune":"comune","provincia":"provincia","latitudine":"latitudine","longitudine":"longitudine",
    })
    if "id_impianto" not in df.columns: raise ValueError("Missing id_impianto")
    df["id_impianto"] = pd.to_numeric(df["id_impianto"], errors="coerce")
    df = df.dropna(subset=["id_impianto"]); df["id_impianto"] = df["id_impianto"].astype(int)
    for c in ["latitudine","longitudine"]:
        if c in df.columns:
            df[c] = df[c].astype(str).str.replace(",","."); df[c] = pd.to_numeric(df[c], errors="coerce")
    if {"latitudine","longitudine"}.issubset(df.columns):
        mask = df["latitudine"].between(35,48) & df["longitudine"].between(6,19)
        df = df[mask]
    for c in ["gestore","bandiera","nome_impianto","indirizzo","comune","provincia"]:
        if c in df.columns: df[c] = df[c].astype(str).str.strip()
    if "bandiera" in df.columns: df["bandiera"] = df["bandiera"].str.title()
    df = df.drop_duplicates(subset=["id_impianto"])
    logger.info(f"Parsed {len(df)} stations"); return df

FUEL_MAP = {
    "benzina":"Benzina","benzina senza piombo":"Benzina","benzina super":"Benzina",
    "gasolio":"Gasolio","diesel":"Gasolio","gpl":"GPL","metano":"Metano",
    "gnl":"GNL","l-gnc":"Metano","gnc":"Metano",
}

def parse_prezzi(csv_text: str) -> pd.DataFrame:
    df = _read_csv(csv_text)
    df = _normalize_columns(df, {
        "idimpianto":"id_impianto","descr":"descr_carburante","carburante":"descr_carburante",
        "prezzo":"prezzo","self":"is_self","dtcomu":"dt_comunic","data":"dt_comunic",
    })
    if "id_impianto" not in df.columns or "prezzo" not in df.columns:
        raise ValueError("Missing columns in prezzi")
    df["id_impianto"] = pd.to_numeric(df["id_impianto"], errors="coerce")
    df = df.dropna(subset=["id_impianto"]); df["id_impianto"] = df["id_impianto"].astype(int)
    df["prezzo"] = df["prezzo"].astype(str).str.replace(",","."); df["prezzo"] = pd.to_numeric(df["prezzo"], errors="coerce")
    df = df[df["prezzo"].between(0.5, 5.0)]
    if "is_self" in df.columns:
        df["is_self"] = df["is_self"].astype(str).str.strip().str.lower().map(lambda x: 1 if x in ("1","true","si","sì","self") else 0)
    else: df["is_self"] = 1
    if "descr_carburante" in df.columns:
        df["descr_carburante"] = df["descr_carburante"].astype(str).str.strip().str.lower().map(lambda x: FUEL_MAP.get(x, x.title()))
    logger.info(f"Parsed {len(df)} prices"); return df

def load_to_db(stations_df: pd.DataFrame, prices_df: pd.DataFrame):
    conn = get_connection(); cur = conn.cursor()
    try:
        cur.execute("DELETE FROM prices"); cur.execute("DELETE FROM stations")
        scols = [c for c in ["id_impianto","gestore","bandiera","tipo_impianto","nome_impianto","indirizzo","comune","provincia","latitudine","longitudine"] if c in stations_df.columns]
        cur.executemany(f"INSERT OR IGNORE INTO stations ({','.join(scols)}) VALUES ({','.join('?'*len(scols))})", stations_df[scols].values.tolist())
        pcols = [c for c in ["id_impianto","descr_carburante","prezzo","is_self","dt_comunic"] if c in prices_df.columns]
        cur.executemany(f"INSERT INTO prices ({','.join(pcols)}) VALUES ({','.join('?'*len(pcols))})", prices_df[pcols].values.tolist())
        now = datetime.now().isoformat()
        cur.execute("INSERT OR REPLACE INTO metadata (key, value) VALUES ('last_update', ?)", (now,))
        conn.commit(); logger.info(f"DB refreshed: {len(stations_df)} stations, {len(prices_df)} prices")
    except Exception as e:
        conn.rollback(); logger.error(f"DB load failed: {e}"); raise
    finally: conn.close()

def refresh_data() -> dict:
    ana = download_csv(ANAGRAFICA_URL); pre = download_csv(PREZZI_URL)
    if not ana: raise RuntimeError("Failed to download anagrafica")
    if not pre: raise RuntimeError("Failed to download prezzi")
    sdf = parse_anagrafica(ana); pdf = parse_prezzi(pre)
    load_to_db(sdf, pdf)
    return {"stations_loaded": len(sdf), "prices_loaded": len(pdf),
            "unique_brands": int(sdf["bandiera"].nunique()) if "bandiera" in sdf.columns else 0,
            "fuel_types": pdf["descr_carburante"].unique().tolist() if "descr_carburante" in pdf.columns else [],
            "timestamp": datetime.now().isoformat()}

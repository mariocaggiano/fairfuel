"""Configuration constants for FairFuel."""
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "fairfuel.db")

MIMIT_BASE_URL = "https://www.mimit.gov.it/images/exportCSV"
ANAGRAFICA_URL = f"{MIMIT_BASE_URL}/anagrafica_impianti_attivi.csv"
PREZZI_URL = f"{MIMIT_BASE_URL}/prezzo_alle_8.csv"

CSV_DELIMITER = "|"
CSV_ENCODING = "utf-8"

EARTH_RADIUS_KM = 6371.0

PORT = int(os.environ.get("PORT", 8000))
HOST = os.environ.get("HOST", "0.0.0.0")

CORS_ORIGINS = os.environ.get(
    "CORS_ORIGINS",
    "http://localhost:3000,http://localhost:5173,http://127.0.0.1:5500"
).split(",")

SCHEDULER_HOUR = int(os.environ.get("SCHEDULER_HOUR", "9"))
SCHEDULER_MINUTE = int(os.environ.get("SCHEDULER_MINUTE", "15"))

os.makedirs(DATA_DIR, exist_ok=True)

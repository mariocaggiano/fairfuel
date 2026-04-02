"""Tornado request handlers for FairFuel API."""
import asyncio, json, logging, os
import tornado.web
from app.database import get_connection, get_stats
from app.ingestion import refresh_data
from app.config import CORS_ORIGINS

logger = logging.getLogger(__name__)

FRONTEND_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend"
)


class BaseHandler(tornado.web.RequestHandler):
    def set_default_headers(self):
        origin = self.request.headers.get("Origin", "")
        if origin in CORS_ORIGINS or ".vercel.app" in origin:
            self.set_header("Access-Control-Allow-Origin", origin)
        else:
            self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.set_header("Access-Control-Allow-Headers", "Content-Type")
        self.set_header("Content-Type", "application/json; charset=utf-8")

    def options(self, *args):
        self.set_status(204)
        self.finish()

    def write_json(self, data, status=200):
        self.set_status(status)
        self.write(json.dumps(data, ensure_ascii=False, default=str))


class StationsHandler(BaseHandler):
    def get(self):
        try:
            comune = self.get_argument("comune", None)
            provincia = self.get_argument("provincia", None)
            bandiera = self.get_argument("bandiera", None)
            carburante = self.get_argument("carburante", None)
            self_service = self.get_argument("self_service", None)
            lat = self.get_argument("lat", None)
            lon = self.get_argument("lon", None)
            radius = self.get_argument("radius", None)
            sort = self.get_argument("sort", "price_asc")
            limit = min(int(self.get_argument("limit", "200")), 500)
            offset = int(self.get_argument("offset", "0"))

            conn = get_connection()
            cur = conn.cursor()
            params = []
            conditions = []
            sel = (
                "s.id_impianto, s.bandiera, s.nome_impianto, s.indirizzo, "
                "s.comune, s.provincia, s.latitudine, s.longitudine, "
                "p.descr_carburante, p.prezzo, p.is_self, p.dt_comunic"
            )

            if lat and lon:
                lat_f, lon_f = float(lat), float(lon)
                sel += ", haversine(s.latitudine, s.longitudine, ?, ?) as distanza"
                params.extend([lat_f, lon_f])
                if radius:
                    r = float(radius)
                    dlat = r / 111.0
                    dlon = r / (111.0 * 0.73)
                    conditions += [
                        "s.latitudine BETWEEN ? AND ?",
                        "s.longitudine BETWEEN ? AND ?",
                    ]
                    params += [lat_f - dlat, lat_f + dlat, lon_f - dlon, lon_f + dlon]

            base_q = f"SELECT {sel} FROM prices p JOIN stations s ON p.id_impianto = s.id_impianto"

            if comune:
                conditions.append("LOWER(s.comune) LIKE ?")
                params.append(f"%{comune.lower()}%")
            if provincia:
                conditions.append("UPPER(s.provincia) = ?")
                params.append(provincia.upper())
            if bandiera:
                conditions.append("LOWER(s.bandiera) LIKE ?")
                params.append(f"%{bandiera.lower()}%")
            if carburante:
                conditions.append("LOWER(p.descr_carburante) = ?")
                params.append(carburante.lower())
            if self_service is not None:
                conditions.append("p.is_self = ?")
                params.append(int(self_service))

            if conditions:
                base_q += " WHERE " + " AND ".join(conditions)

            if lat and lon and radius:
                base_q = f"SELECT * FROM ({base_q}) sub WHERE sub.distanza <= ?"
                params.append(float(radius))

            order = (
                ("distanza ASC, prezzo ASC" if sort == "price_asc" else "distanza ASC, prezzo DESC")
                if lat and lon
                else ("prezzo ASC" if sort == "price_asc" else "prezzo DESC")
            )
            final_q = f"SELECT * FROM ({base_q}) final ORDER BY {order} LIMIT ? OFFSET ?"
            params += [limit, offset]

            cur.execute(final_q, params)
            rows = cur.fetchall()
            conn.close()

            results = []
            for row in rows:
                item = {k: row[k] for k in row.keys() if k != "distanza"}
                item["is_self"] = bool(row["is_self"])
                try:
                    item["distanza_km"] = round(row["distanza"], 2)
                except Exception:
                    pass
                results.append(item)

            self.write_json({"count": len(results), "results": results})
        except Exception as e:
            logger.exception("StationsHandler error")
            self.write_json({"error": str(e)}, 500)


class FiltersHandler(BaseHandler):
    def get(self):
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute(
                "SELECT DISTINCT bandiera FROM stations "
                "WHERE bandiera NOT IN ('','None','nan') ORDER BY bandiera"
            )
            brands = [r["bandiera"] for r in cur.fetchall()]
            cur.execute(
                "SELECT DISTINCT descr_carburante FROM prices "
                "WHERE descr_carburante NOT IN ('','None','nan') ORDER BY descr_carburante"
            )
            fuels = [r["descr_carburante"] for r in cur.fetchall()]
            cur.execute(
                "SELECT DISTINCT provincia FROM stations "
                "WHERE provincia NOT IN ('','None','nan') ORDER BY provincia"
            )
            provinces = [r["provincia"] for r in cur.fetchall()]
            cur.execute(
                "SELECT DISTINCT comune FROM stations "
                "WHERE comune NOT IN ('','None','nan') ORDER BY comune"
            )
            municipalities = [r["comune"] for r in cur.fetchall()]
            conn.close()
            self.write_json({
                "brands": brands,
                "fuel_types": fuels,
                "provinces": provinces,
                "municipalities": municipalities,
            })
        except Exception as e:
            self.write_json({"error": str(e)}, 500)


class StatsHandler(BaseHandler):
    def get(self):
        try:
            self.write_json(get_stats())
        except Exception as e:
            self.write_json({"error": str(e)}, 500)


class RefreshHandler(BaseHandler):
    async def post(self):
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, refresh_data)
            self.write_json({"status": "ok", **result})
        except Exception as e:
            logger.error(f"RefreshHandler error: {e}")
            self.write_json({"error": str(e)}, 500)


class HealthHandler(BaseHandler):
    def get(self):
        self.write_json({"status": "healthy", "app": "fairfuel"})


class IndexHandler(tornado.web.RequestHandler):
    def get(self):
        idx = os.path.join(FRONTEND_DIR, "index.html")
        if os.path.exists(idx):
            self.set_header("Content-Type", "text/html; charset=utf-8")
            with open(idx) as f:
                self.write(f.read())
        else:
            self.set_status(404)
            self.write("Frontend not found")

"""FairFuel — Tornado server."""
import asyncio, os, logging
import tornado.web, tornado.ioloop
from app.config import PORT, HOST
from app.database import init_db, get_stats, init_turso_db
from app.ingestion import refresh_data
from app.scheduler import start_scheduler
from app.handlers import StationsHandler, FiltersHandler, StatsHandler, RefreshHandler, HealthHandler, IndexHandler, ReportPriceHandler, FRONTEND_DIR

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

def make_app():
    return tornado.web.Application([
        (r"/api/stations", StationsHandler),
        (r"/api/filters", FiltersHandler),
        (r"/api/stats", StatsHandler),
        (r"/api/report-price", ReportPriceHandler),
        (r"/api/refresh", RefreshHandler),
        (r"/api/health", HealthHandler),
        (r"/.*", IndexHandler),
    ],
    static_path=FRONTEND_DIR if os.path.isdir(FRONTEND_DIR) else None,
    static_url_prefix="/static/",
    debug=os.environ.get("DEBUG","false").lower()=="true")

async def _bootstrap():
    init_db()
    init_turso_db()
    stats = get_stats()
    if stats["stations"] == 0:
        logger.info("Empty DB — loading MIMIT data...")
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, refresh_data)
            logger.info(f"Loaded {result['stations_loaded']} stations")
        except Exception as e:
            logger.error(f"Initial load failed: {e}")
    start_scheduler()

def start_server():
    make_app().listen(PORT, address=HOST)
    logger.info(f"FairFuel running → http://{HOST}:{PORT}")
    loop = tornado.ioloop.IOLoop.current()
    loop.add_callback(_bootstrap)
    loop.start()

if __name__ == "__main__":
    start_server()

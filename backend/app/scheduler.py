"""Daily scheduler — no extra dependencies."""
import sched, threading, time, logging
from datetime import datetime, timedelta
from app.config import SCHEDULER_HOUR, SCHEDULER_MINUTE

logger = logging.getLogger(__name__)
_scheduler = sched.scheduler(time.monotonic, time.sleep)
_thread = None; _running = False

def _seconds_until_next_run():
    now = datetime.now()
    target = now.replace(hour=SCHEDULER_HOUR, minute=SCHEDULER_MINUTE, second=0, microsecond=0)
    if target <= now: target += timedelta(days=1)
    delta = (target - now).total_seconds()
    logger.info(f"Next refresh at {target.strftime('%H:%M')} (in {delta/3600:.1f}h)")
    return delta

def _run_refresh():
    try:
        from app.ingestion import refresh_data
        result = refresh_data()
        logger.info(f"Auto-refresh done: {result['stations_loaded']} stations")
    except Exception as e:
        logger.error(f"Auto-refresh failed: {e}")
    finally:
        if _running: _schedule_next()

def _schedule_next():
    _scheduler.enter(_seconds_until_next_run(), 1, _run_refresh)

def _scheduler_loop():
    _schedule_next(); _scheduler.run()

def start_scheduler():
    global _thread, _running
    if _thread and _thread.is_alive(): return
    _running = True
    _thread = threading.Thread(target=_scheduler_loop, daemon=True, name="fairfuel-scheduler")
    _thread.start()
    logger.info(f"Scheduler started — daily refresh at {SCHEDULER_HOUR:02d}:{SCHEDULER_MINUTE:02d}")

def stop_scheduler():
    global _running; _running = False
    for ev in list(_scheduler.queue):
        try: _scheduler.cancel(ev)
        except ValueError: pass

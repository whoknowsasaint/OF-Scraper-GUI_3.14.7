import time
import ofscraper.utils.logs.close as close_log
import ofscraper.utils.cache.cache as cache


def shutdown():
    # Stop Rich live display to prevent progress bar spam on exit
    try:
        from ofscraper.utils.live.live import stop_live, get_live
        stop_live()
        live = get_live()
        if live.is_started:
            live.stop()
    except Exception:
        pass
    time.sleep(3)
    close_log.gracefulClose()
    closeThreadExecutor()
    closeCache()


def forcedShutDown():
    # Stop Rich live display to prevent progress bar spam on exit
    try:
        from ofscraper.utils.live.live import stop_live, get_live
        stop_live()
        live = get_live()
        if live.is_started:
            live.stop()
    except Exception:
        pass
    time.sleep(3)
    closeThreadExecutor()
    closeCache()

def closeThreadExecutor():
    try:
        import ofscraper.commands.scraper.actions.utils.globals as common_globals

        if hasattr(common_globals, "thread") and common_globals.thread:
            common_globals.thread.shutdown(wait=True)
            common_globals.thread = None
    except ImportError:
        pass


def closeCache():
    try:
        cache.close()
    except Exception:
        pass

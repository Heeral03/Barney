"""A small in-memory TTL cache for search calls, so repeating a query does not spend API quota."""
import functools
import threading
import time


def ttl_cache(seconds: float, maxsize: int = 256):
    """Cache a function of hashable arguments that returns a list. Empty results are not cached (a transient
    failure should be retried), and callers get a copy so they cannot corrupt the cached list."""
    def wrap(fn):
        store: dict = {}
        lock = threading.Lock()

        @functools.wraps(fn)
        def inner(*args):
            now = time.monotonic()
            with lock:
                hit = store.get(args)
                if hit and now - hit[0] < seconds:
                    return list(hit[1])
            result = fn(*args)
            if result:
                with lock:
                    if len(store) >= maxsize:
                        store.pop(min(store, key=lambda k: store[k][0]))
                    store[args] = (now, list(result))
            return result

        return inner

    return wrap

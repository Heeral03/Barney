"""Is it worth waiting? Plain calendar advice from how Indian retail and product launches usually run.

Nothing here is a live feed: these are typical patterns, said as such ("usually", "often"), never as a promise. The windows
are approximate dates for the current festive and sale seasons; extend `SALES` each year.
"""
from datetime import date, timedelta

# (name, start, end): approximate sale windows
SALES = [
    ("Diwali sales", date(2026, 10, 12), date(2026, 11, 12)),
    ("Black Friday and Cyber Monday sales", date(2026, 11, 20), date(2026, 12, 2)),
    ("Republic Day sales", date(2027, 1, 13), date(2027, 1, 27)),
    ("Amazon Prime Day", date(2027, 7, 10), date(2027, 7, 20)),
    ("Festive season sales (Big Billion Days, Great Indian Festival)", date(2027, 9, 25), date(2027, 10, 12)),
]

# category word -> (usual launch month, what launches)
LAUNCHES = {
    "iphone": (9, "Apple usually launches new iPhones in September"),
    "macbook": (10, "Apple often refreshes MacBooks in the autumn"),
    "galaxy": (1, "Samsung usually launches its new Galaxy S phones in January or February"),
    "laptop": (1, "new laptop chips are usually announced at CES in January"),
    "phone": (9, "most big phone launches cluster around September and January"),
    "airpods": (9, "Apple often updates AirPods alongside its autumn launches"),
}
WINDOW_DAYS = 45


def advice(product: str, today: date | None = None) -> str:
    """One short line about timing, or "" when there is nothing useful to say."""
    today = today or date.today()
    text = (product or "").lower().replace("_", " ")
    for name, start, end in SALES:
        if start <= today <= end:
            return f"{name} are on right now, so this is usually a good time to buy."
        if today < start <= today + timedelta(days=WINDOW_DAYS):
            days = (start - today).days
            return f"{name} usually begin around {start.strftime('%d %b')} (about {days} days from now). If you are not in a hurry, prices on this kind of product often dip then."
    for word, (month, why) in LAUNCHES.items():
        if word in text:
            gap = (month - today.month) % 12
            if gap in (0, 1):
                return f"Heads up: {why}, so a newer model may be close. These are usual patterns, not confirmed dates."
            break
    return ""

"""bus_api.py -- TransportAPI wrapper for the Galactic Unicorn (MicroPython).

Fetches live departures for one bus stop, filters to the routes we care
about, drops anything we couldn't reach in time on foot, and returns the
next two viable departures.

Designed to be import-safe on CPython too (for unit testing), but the
network call uses `urequests` which is MicroPython-only.
"""

try:
    import urequests as _requests  # MicroPython
except ImportError:  # pragma: no cover -- CPython fallback for local tests
    import requests as _requests

try:
    import utime as _time  # MicroPython
except ImportError:  # pragma: no cover
    import time as _time


_BASE_URL = "https://transportapi.com/v3/uk/bus/stop/{}/live.json"


# --- Time helpers ------------------------------------------------------------

def _hhmm_to_minutes(hhmm):
    """Convert 'HH:MM' to minutes since midnight. Returns None if malformed."""
    if not hhmm or len(hhmm) < 4 or ":" not in hhmm:
        return None
    try:
        h, m = hhmm.split(":", 1)
        return int(h) * 60 + int(m)
    except (ValueError, TypeError):
        return None


def _minutes_until(now_mins, bus_mins):
    """Minutes from `now_mins` until `bus_mins`, allowing one midnight wrap."""
    delta = bus_mins - now_mins
    # If the bus time already passed today by more than 2 hours, assume it's
    # tomorrow (API returns a small forward window so this wrap is rare).
    if delta < -120:
        delta += 24 * 60
    return delta


# --- Core --------------------------------------------------------------------

def _pick_best_time(dep):
    """Prefer live `expected_departure_time`, then `best_departure_estimate`,
    then `aimed_departure_time`. Returns (hhmm_string, is_live_bool)."""
    live = dep.get("expected_departure_time")
    if live:
        return live, True
    best = dep.get("best_departure_estimate")
    if best:
        return best, False
    aimed = dep.get("aimed_departure_time")
    if aimed:
        return aimed, False
    return None, False


def fetch_raw(app_id, app_key, stop_atcocode, limit=10, timeout=8):
    """Call TransportAPI and return parsed JSON. Caller handles exceptions.

    The response MUST be closed to avoid leaking sockets on MicroPython, so
    we json-decode eagerly and close before returning.

    timeout is short by design -- on a captive-portal or broken network
    urequests' connect phase is the only thing we can reliably bound, so we
    want to bail fast and let the main loop retry rather than park for 15s
    on every poll.
    """
    url = _BASE_URL.format(stop_atcocode)
    # Build query string manually so we don't depend on urequests' params kwarg.
    qs = "app_id={}&app_key={}&group=route&limit={}&nextbuses=yes".format(
        app_id, app_key, limit,
    )
    full = url + "?" + qs
    resp = _requests.get(full, timeout=timeout)
    try:
        if resp.status_code != 200:
            raise OSError("HTTP {}".format(resp.status_code))
        return resp.json()
    finally:
        try:
            resp.close()
        except Exception:
            pass


def _extract_departures(payload, routes):
    """Flatten the `departures` dict into a list of raw dep dicts we care about."""
    out = []
    deps = payload.get("departures") or {}
    wanted = set(routes)
    for route, items in deps.items():
        if route not in wanted:
            continue
        for dep in items or []:
            # Filter out anything explicitly cancelled.
            status = dep.get("status") or {}
            cancellation = status.get("cancellation") or {}
            if cancellation.get("value") is True:
                continue
            out.append(dep)
    return out


def _now_local_minutes():
    """Minutes since midnight in local time, per MicroPython's `localtime()`.

    On the Pico we set the RTC to local time in main.py (UTC + BST offset), so
    this is already what we want.
    """
    lt = _time.localtime()
    return lt[3] * 60 + lt[4]


def get_soonest_two_viable_departures(
    app_id, app_key, stop_atcocode, routes, walk_minutes,
    now_local_minutes=None,
    payload=None,
):
    """Return (first, second) viable departures as dicts, or (None, None).

    Args:
      app_id, app_key, stop_atcocode: TransportAPI parameters.
      routes: iterable of route numbers as strings, e.g. ["385", "383"].
      walk_minutes: buses leaving sooner than this are dropped.
      now_local_minutes: optional override for testing; defaults to the RTC.
      payload: optional pre-fetched JSON (skips the HTTP call). Used by tests.

    Each returned dict (or None) looks like:
      {"route": "385", "destination": "Mellor", "minutes_until_leave": 6,
       "bus_time_hhmm": "12:12", "is_live": False}
    """
    if payload is None:
        payload = fetch_raw(app_id, app_key, stop_atcocode)

    if now_local_minutes is None:
        now_local_minutes = _now_local_minutes()

    candidates = []
    for dep in _extract_departures(payload, routes):
        hhmm, is_live = _pick_best_time(dep)
        bus_mins = _hhmm_to_minutes(hhmm)
        if bus_mins is None:
            continue
        minutes_until_bus = _minutes_until(now_local_minutes, bus_mins)
        minutes_until_leave = minutes_until_bus - walk_minutes
        if minutes_until_leave < 0:
            # Can't make this one on foot.
            continue
        candidates.append({
            "route": str(dep.get("line") or dep.get("line_name") or "?"),
            "destination": (dep.get("direction") or "").strip() or "?",
            "minutes_until_leave": minutes_until_leave,
            "minutes_until_bus": minutes_until_bus,
            "bus_time_hhmm": hhmm,
            "is_live": is_live,
        })

    candidates.sort(key=lambda d: d["minutes_until_leave"])
    first = candidates[0] if candidates else None
    second = candidates[1] if len(candidates) > 1 else None
    return first, second


def get_upcoming_departures(
    app_id, app_key, stop_atcocode, routes, count,
    direction_contains=None,
    now_local_minutes=None,
    payload=None,
):
    """Return up to `count` soonest departures matching routes + direction.

    Used by the Alexia profile: no walk-time subtraction, no "viable" filter --
    it just wants the next N buses matching the route and going the right way.

    Args:
      app_id, app_key, stop_atcocode: TransportAPI parameters.
      routes: iterable of route numbers as strings, e.g. ["192"].
      count: max number of departures to return.
      direction_contains: if set, only keep departures whose `direction`
        string contains this substring (case-insensitive). e.g. "piccadilly"
        to filter a bidirectional stop to just the inbound side.
      now_local_minutes: optional override for testing.
      payload: optional pre-fetched JSON (skips HTTP). Used by tests.

    Returns a list of dicts:
      [{"route": "192", "destination": "Manchester Piccadilly",
        "minutes_until_bus": 10, "bus_time_hhmm": "07:52", "is_live": True}, ...]
    """
    if payload is None:
        payload = fetch_raw(app_id, app_key, stop_atcocode)

    if now_local_minutes is None:
        now_local_minutes = _now_local_minutes()

    needle = direction_contains.lower() if direction_contains else None

    rows = []
    for dep in _extract_departures(payload, routes):
        hhmm, is_live = _pick_best_time(dep)
        bus_mins = _hhmm_to_minutes(hhmm)
        if bus_mins is None:
            continue
        minutes_until_bus = _minutes_until(now_local_minutes, bus_mins)
        if minutes_until_bus < 0:
            # Bus time is already behind us; skip.
            continue
        direction = (dep.get("direction") or "").strip()
        if needle and needle not in direction.lower():
            continue
        rows.append({
            "route": str(dep.get("line") or dep.get("line_name") or "?"),
            "destination": direction or "?",
            "minutes_until_bus": minutes_until_bus,
            "bus_time_hhmm": hhmm,
            "is_live": is_live,
        })

    rows.sort(key=lambda d: d["minutes_until_bus"])
    return rows[:count]

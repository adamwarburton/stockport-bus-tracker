"""weather_api.py -- Open-Meteo wrapper for the Alexia profile.

Returns a compact dict the display layer turns into one of three messages:

  raining now + ends known   -> "12 RAIN NOW ENDS IN 45 MIN"
  raining now + no end       -> "12 RAINING NOW"
  dry + rain coming soon     -> "12 RAIN IN 15 MIN ENDS IN 45 MIN"
  dry + no rain in forecast  -> "12 NO RAIN TODAY"

Open-Meteo is free, no API key, and serves a `minutely_15` precipitation
array covering the requested forecast window at 15-minute resolution -- good
enough to answer "do I need an umbrella?".

Designed to be import-safe under CPython (for the laptop smoke test) and
under MicroPython on the Pico.
"""

try:
    import urequests as _requests  # MicroPython
except ImportError:  # pragma: no cover -- CPython fallback
    import requests as _requests


_BASE_URL = "https://api.open-meteo.com/v1/forecast"

# Precipitation at or above this (mm in a 15-minute slot) counts as "raining"
# for umbrella purposes. 0.1mm is a light drizzle -- still wet, still worth
# a brolly.
_RAIN_THRESHOLD_MM = 0.1


def fetch_raw(lat, lon, timeout=15):
    """Call Open-Meteo and return parsed JSON. Caller handles exceptions."""
    url = (
        "{base}?latitude={lat}&longitude={lon}"
        "&current=temperature_2m"
        "&minutely_15=precipitation"
        "&forecast_days=1"
        "&timezone=auto"
    ).format(base=_BASE_URL, lat=lat, lon=lon)
    resp = _requests.get(url, timeout=timeout)
    try:
        if resp.status_code != 200:
            raise OSError("HTTP {}".format(resp.status_code))
        return resp.json()
    finally:
        try:
            resp.close()
        except Exception:
            pass


def _locate_current_slot(times, now_iso):
    """Return the index of the 15-min slot covering `now_iso`.

    Open-Meteo minutely_15 times are quarter-hour marks in the same tz as
    `current.time`, so `times[i] <= now < times[i+1]`. Falls back to 0 if
    everything is in the future (clock skew) or -1 if everything is past.
    """
    if not times:
        return 0
    idx = 0
    found = False
    for i, t in enumerate(times):
        if t <= now_iso:
            idx = i
            found = True
        else:
            break
    return idx if found else 0


def _analyse_rain(times, precips, now_iso, threshold=_RAIN_THRESHOLD_MM):
    """Walk the precipitation series to decide the rain state.

    Returns (raining_now, rain_starts_in, rain_ends_in) with minute values
    quantised to 15-minute multiples (the sampling interval).
    """
    if not times or not precips:
        return False, None, None

    current_idx = _locate_current_slot(times, now_iso)

    def mm(i):
        try:
            v = precips[i]
            return float(v) if v is not None else 0.0
        except (TypeError, ValueError, IndexError):
            return 0.0

    raining_now = mm(current_idx) >= threshold
    rain_starts_in = None
    rain_ends_in = None

    if raining_now:
        # Walk forward until we find a dry slot.
        for j in range(current_idx + 1, len(precips)):
            if mm(j) < threshold:
                rain_ends_in = (j - current_idx) * 15
                break
        return True, None, rain_ends_in

    # Dry now. Find the next wet slot, then the slot after that where it dries.
    for j in range(current_idx + 1, len(precips)):
        if mm(j) >= threshold:
            rain_starts_in = (j - current_idx) * 15
            for k in range(j + 1, len(precips)):
                if mm(k) < threshold:
                    rain_ends_in = (k - current_idx) * 15
                    break
            break
    return False, rain_starts_in, rain_ends_in


def get_weather(lat, lon, payload=None):
    """Fetch (or accept) a payload and return a normalised weather dict.

    Dict shape:
      {
        "temp_c":         int or None,   # rounded degrees celsius
        "raining_now":    bool,
        "rain_starts_in": int or None,   # minutes until rain starts
        "rain_ends_in":   int or None,   # minutes until rain stops
      }
    """
    if payload is None:
        payload = fetch_raw(lat, lon)

    current = payload.get("current") or {}
    temp_c = None
    raw_temp = current.get("temperature_2m")
    if raw_temp is not None:
        try:
            temp_c = int(round(float(raw_temp)))
        except (ValueError, TypeError):
            pass

    minutely = payload.get("minutely_15") or {}
    times = minutely.get("time") or []
    precips = minutely.get("precipitation") or []
    now_iso = current.get("time") or (times[0] if times else "")

    raining_now, rain_starts_in, rain_ends_in = _analyse_rain(
        times, precips, now_iso,
    )

    return {
        "temp_c": temp_c,
        "raining_now": raining_now,
        "rain_starts_in": rain_starts_in,
        "rain_ends_in": rain_ends_in,
    }

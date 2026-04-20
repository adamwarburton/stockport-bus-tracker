"""test_api.py -- one-shot smoke test for the TransportAPI bus stop endpoint.

Runs on a regular laptop with CPython 3 + `requests` (NOT on the Pico).
Just prints the raw JSON so we can eyeball it and confirm services 385 and 383
show up for Stockport Grand Central Stop RR before writing the MicroPython
version.

    pip install requests
    python3 test_api.py
"""

import json
import sys

try:
    import requests
except ImportError:
    print("ERROR: `requests` is not installed. Run: pip install requests")
    sys.exit(1)

# Hardcoded here for the smoke test -- the real Pico code reads from config.py.
APP_ID = "e2431c45"
APP_KEY = "078307ef6590575a0abf6b44f75f46c7"
STOP_ATCOCODE = "1800SG14861"
ROUTES_OF_INTEREST = {"385", "383"}

URL = f"https://transportapi.com/v3/uk/bus/stop/{STOP_ATCOCODE}/live.json"
PARAMS = {
    "app_id": APP_ID,
    "app_key": APP_KEY,
    "group": "route",
    "limit": 10,
    "nextbuses": "yes",
}


def main() -> int:
    print(f"GET {URL}")
    print(f"params: {PARAMS}")
    print("-" * 60)
    resp = requests.get(URL, params=PARAMS, timeout=15)
    print(f"HTTP {resp.status_code}")
    print("-" * 60)

    try:
        payload = resp.json()
    except ValueError:
        print("Response body was not JSON:")
        print(resp.text[:2000])
        return 2

    print(json.dumps(payload, indent=2))
    print("-" * 60)

    departures = payload.get("departures", {})
    present = set(departures.keys())
    print(f"Routes present in departures: {sorted(present)}")
    matched = ROUTES_OF_INTEREST & present
    missing = ROUTES_OF_INTEREST - present
    print(f"Matched our routes of interest: {sorted(matched)}")
    if missing:
        print(f"WARNING: expected routes missing from response: {sorted(missing)}")

    return 0 if matched else 3


if __name__ == "__main__":
    sys.exit(main())

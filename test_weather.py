"""test_weather.py -- laptop-side smoke test for the Open-Meteo weather feed.

Mirrors test_api.py in style: pip install requests, run on CPython, eyeball
the printed state. Confirms the endpoint is reachable and the `minutely_15`
precipitation series is present before we trust it on the Pico.

    pip install requests
    python3 test_weather.py
"""

import json
import sys

try:
    import requests  # noqa: F401  -- checked so we fail fast with a nice message
except ImportError:
    print("ERROR: `requests` is not installed. Run: pip install requests")
    sys.exit(1)

import weather_api

# Defaults match the Alexia bedroom coords in config.example.py. Override
# on the command line: `python3 test_weather.py 53.5 -2.1`.
LAT = 53.398231
LON = -2.136303


def main() -> int:
    lat = float(sys.argv[1]) if len(sys.argv) > 1 else LAT
    lon = float(sys.argv[2]) if len(sys.argv) > 2 else LON

    print(f"Fetching Open-Meteo forecast for ({lat}, {lon})")
    print("-" * 60)
    try:
        payload = weather_api.fetch_raw(lat, lon)
    except Exception as e:
        print(f"Fetch failed: {e}")
        return 2

    current = payload.get("current") or {}
    minutely = payload.get("minutely_15") or {}
    print(f"current.time:        {current.get('time')}")
    print(f"current.temperature: {current.get('temperature_2m')}")
    print(f"minutely slots:      {len(minutely.get('time') or [])}")
    print("-" * 60)

    result = weather_api.get_weather(lat, lon, payload=payload)
    print("Normalised state:")
    print(json.dumps(result, indent=2))

    # Match the display wording so you can eyeball what Alexia will actually see.
    print("-" * 60)
    from display import _format_weather  # noqa: WPS450 -- intentional private import
    print("Display would show:")
    print(f"  {_format_weather(result)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

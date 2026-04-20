"""main.py -- entry point for the Stockport bus ticker.

Runs on the Pimoroni Galactic Unicorn (Pico 2 W) under Pimoroni MicroPython.
Pimoroni's firmware auto-runs main.py at boot, so dropping this file on the
Pico is all the install you need.

What happens here:
  1. Bring up WiFi (with retry).
  2. Sync the clock from NTP (UTC), then apply the UK GMT/BST offset.
  3. Loop forever:
       - every SCROLL_TICK_MS ms: scroll the display one pixel,
       - every second:           re-render "minutes until leave" from cached
                                 data so the countdown feels live,
       - every POLL_INTERVAL:    hit TransportAPI and refresh the cache,
                                 unless we're outside POLL_WINDOW.
  4. Never crash. API/WiFi errors just change the fallback message.

Thonny's shell panel is our only console, so print() generously.
"""

import gc
import network
import ntptime
import utime

from galactic import GalacticUnicorn
from picographics import PicoGraphics, DISPLAY_GALACTIC_UNICORN

import config
import WIFI_CONFIG
import bus_api
import display as dsp


# --- Time helpers ------------------------------------------------------------

def _last_sunday_mday(year, month):
    """Return the day-of-month of the last Sunday in (year, month) UTC."""
    # Walk back from day 31 until localtime says it's a Sunday (wd=6).
    for day in range(31, 24, -1):
        try:
            ts = utime.mktime((year, month, day, 1, 0, 0, 0, 0))
        except (OverflowError, ValueError):
            continue
        wd = utime.localtime(ts)[6]
        if wd == 6:
            return day
    return 25  # fallback, should never happen


def is_bst(now_utc_tuple):
    """True if UK is on BST (UTC+1) at this UTC moment.

    BST runs from 01:00 UTC on the last Sunday of March to 01:00 UTC on the
    last Sunday of October.
    """
    y, mo, d, h, mi, _, _, _ = now_utc_tuple
    if mo < 3 or mo > 10:
        return False
    if 3 < mo < 10:
        return True
    start = _last_sunday_mday(y, 3)
    end = _last_sunday_mday(y, 10)
    if mo == 3:
        if d < start:
            return False
        if d > start:
            return True
        return h >= 1
    # mo == 10
    if d < end:
        return True
    if d > end:
        return False
    return h < 1


def sync_clock():
    """Set the RTC to local UK time. Call after WiFi is up."""
    print("NTP: syncing clock...")
    for attempt in range(4):
        try:
            ntptime.settime()  # sets RTC to UTC
            break
        except Exception as e:
            print("NTP attempt {} failed: {}".format(attempt + 1, e))
            utime.sleep(2)
    else:
        print("NTP: giving up, clock will be wrong")
        return

    # Nudge the RTC by the UK offset.
    utc = utime.localtime()
    offset_seconds = 3600 if is_bst(utc) else 0
    if offset_seconds:
        ts = utime.mktime(utc) + offset_seconds
        lt = utime.localtime(ts)
        # RTC order is (year, month, day, weekday, hour, min, sec, subsec).
        import machine
        machine.RTC().datetime(
            (lt[0], lt[1], lt[2], lt[6], lt[3], lt[4], lt[5], 0)
        )
    print("Clock set to local time: {}".format(_hhmm_now()))


def _hhmm_now():
    lt = utime.localtime()
    return "{:02d}:{:02d}".format(lt[3], lt[4])


def _now_local_minutes():
    lt = utime.localtime()
    return lt[3] * 60 + lt[4]


def _in_poll_window():
    start, end = config.POLL_WINDOW
    hour = utime.localtime()[3]
    return start <= hour < end


# --- WiFi --------------------------------------------------------------------

def connect_wifi(ticker):
    """Block until WiFi is up. Updates the ticker so the user sees progress."""
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    try:
        wlan.config(pm=0xa11140)  # disable powersave -- more reliable connect
    except Exception:
        pass
    country = getattr(WIFI_CONFIG, "COUNTRY", "GB")
    try:
        network.country(country)
    except Exception:
        pass

    ticker.set_spans(dsp.compose_fallback("CONNECTING..."))
    print("WiFi: connecting to '{}'".format(WIFI_CONFIG.SSID))

    attempts = 0
    while not wlan.isconnected():
        if not wlan.isconnected() and wlan.status() <= 0:
            try:
                wlan.connect(WIFI_CONFIG.SSID, WIFI_CONFIG.PSK)
            except Exception as e:
                print("WiFi connect() raised: {}".format(e))
        # Tick the display a few times so it keeps scrolling during connect.
        for _ in range(25):
            ticker.tick(config.SCROLL_SPEED_PX)
            utime.sleep_ms(config.SCROLL_TICK_MS)
        attempts += 1
        if attempts > 40:
            print("WiFi: stuck, cycling interface")
            ticker.set_spans(dsp.compose_fallback("WIFI DOWN  RECONNECTING"))
            wlan.active(False)
            utime.sleep(2)
            wlan.active(True)
            attempts = 0

    print("WiFi: connected, ifconfig={}".format(wlan.ifconfig()))
    return wlan


# --- Main loop ---------------------------------------------------------------

def _compose_for(first, second):
    """Decide what spans to show given the currently cached departures."""
    clock = _hhmm_now()
    if first is None:
        return dsp.compose_fallback("NO BUSES  CHECK BACK LATER", clock), False
    urgent = (
        config.URGENT_FLASH_THRESHOLD > 0
        and first["minutes_until_leave"] <= config.URGENT_FLASH_THRESHOLD
    )
    return dsp.compose_normal(first, second, clock), urgent


def _decrement_cached(first, second):
    """Locally subtract one minute from the cached countdowns. Drop any that
    go negative (we'd no longer be able to catch them)."""
    def tick(d):
        if d is None:
            return None
        d["minutes_until_leave"] = d["minutes_until_leave"] - 1
        d["minutes_until_bus"] = d["minutes_until_bus"] - 1
        if d["minutes_until_leave"] < 0:
            return None
        return d
    first = tick(first)
    second = tick(second)
    if first is None and second is not None:
        first, second = second, None
    return first, second


def poll_api():
    """Call TransportAPI. Returns (first, second) or raises on failure."""
    return bus_api.get_soonest_two_viable_departures(
        app_id=config.APP_ID,
        app_key=config.APP_KEY,
        stop_atcocode=config.STOP_ATCOCODE,
        routes=config.ROUTES,
        walk_minutes=config.WALK_MINUTES,
        now_local_minutes=_now_local_minutes(),
    )


def run():
    unicorn = GalacticUnicorn()
    graphics = PicoGraphics(display=DISPLAY_GALACTIC_UNICORN)
    unicorn.set_brightness(0.6)
    ticker = dsp.Ticker(graphics, unicorn,
                        width=GalacticUnicorn.WIDTH,
                        height=GalacticUnicorn.HEIGHT)

    connect_wifi(ticker)
    sync_clock()

    first = None
    second = None
    last_poll_ms = -10**9  # force immediate poll on first iteration
    last_second_ms = utime.ticks_ms()
    last_minute_mark = utime.localtime()[4]
    status = "OK"  # OK | OFFLINE | OUTSIDE_HOURS

    # Initial message before the first poll completes.
    ticker.set_spans(dsp.compose_fallback("STARTING..."))

    while True:
        now_ms = utime.ticks_ms()

        # Scroll every frame.
        ticker.tick(config.SCROLL_SPEED_PX)

        # Per-second: refresh the clock in the rendered message.
        if utime.ticks_diff(now_ms, last_second_ms) >= 1000:
            last_second_ms = now_ms
            # Per-minute: decrement the countdown so we stay live between polls.
            current_minute = utime.localtime()[4]
            if current_minute != last_minute_mark:
                last_minute_mark = current_minute
                first, second = _decrement_cached(first, second)

            if status == "OUTSIDE_HOURS":
                ticker.set_spans(
                    dsp.compose_fallback("OUTSIDE HOURS", _hhmm_now())
                )
            elif status == "OFFLINE":
                ticker.set_spans(
                    dsp.compose_fallback("OFFLINE  RETRYING", _hhmm_now())
                )
            else:
                spans, urgent = _compose_for(first, second)
                ticker.set_spans(spans, urgent=urgent)

        # Poll the API on schedule.
        if utime.ticks_diff(now_ms, last_poll_ms) >= config.POLL_INTERVAL_SECONDS * 1000:
            last_poll_ms = now_ms
            if not _in_poll_window():
                status = "OUTSIDE_HOURS"
                first, second = None, None
                print("[{}] outside poll window, skipping API".format(_hhmm_now()))
            else:
                try:
                    first, second = poll_api()
                    status = "OK"
                    print("[{}] poll ok: first={}, second={}".format(
                        _hhmm_now(), first, second,
                    ))
                except Exception as e:
                    status = "OFFLINE"
                    print("[{}] poll failed: {}".format(_hhmm_now(), e))
                gc.collect()

        utime.sleep_ms(config.SCROLL_TICK_MS)


if __name__ == "__main__":
    run()

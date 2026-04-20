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

def _configured_networks():
    """Normalise WIFI_CONFIG into a list of {ssid, psk} dicts.

    Accepts either the new NETWORKS list shape or the legacy top-level
    SSID/PSK globals (wrapped into a one-element list). Empty/missing
    entries are dropped so the caller can treat empty-list as "nothing
    configured".
    """
    networks = getattr(WIFI_CONFIG, "NETWORKS", None)
    if networks:
        return [n for n in networks if n.get("ssid")]
    ssid = getattr(WIFI_CONFIG, "SSID", "")
    psk = getattr(WIFI_CONFIG, "PSK", "")
    return [{"ssid": ssid, "psk": psk}] if ssid else []


def _scan_visible(wlan):
    """Return {ssid: strongest_rssi} for nearby APs. Empty dict if scan fails."""
    try:
        scan = wlan.scan()
    except Exception as e:
        print("WiFi scan failed: {}".format(e))
        return {}
    out = {}
    for ap in scan:
        try:
            ssid = ap[0].decode("utf-8")
        except Exception:
            continue
        if not ssid:
            continue
        rssi = ap[3]
        if ssid not in out or rssi > out[ssid]:
            out[ssid] = rssi
    return out


def _attempt_connect(wlan, ticker, ssid, psk, timeout_sec=20):
    """Try one SSID/PSK. Return True on success, False on timeout/failure.

    Keeps the ticker scrolling during the wait so the display stays alive.
    """
    try:
        wlan.disconnect()
    except Exception:
        pass
    utime.sleep_ms(300)
    try:
        wlan.connect(ssid, psk)
    except Exception as e:
        print("WiFi connect() raised for '{}': {}".format(ssid, e))
        return False

    start = utime.ticks_ms()
    while not wlan.isconnected():
        # Keep the scroll alive during connect.
        for _ in range(25):
            ticker.tick(config.SCROLL_SPEED_PX)
            utime.sleep_ms(config.SCROLL_TICK_MS)
        # Status codes: -1 fail, -2 no matching SSID, -3 bad password.
        s = wlan.status()
        if s in (-1, -2, -3):
            print("WiFi status {} for '{}', giving up".format(s, ssid))
            return False
        if utime.ticks_diff(utime.ticks_ms(), start) > timeout_sec * 1000:
            print("WiFi connect timeout for '{}'".format(ssid))
            return False
    return True


def connect_wifi(ticker):
    """Scan, then try each configured network strongest-first.

    Loops forever until connected. Returns the WLAN handle.
    """
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    try:
        wlan.config(pm=0xa11140)  # disable powersave -- more reliable connect
    except Exception:
        pass
    try:
        network.country(getattr(WIFI_CONFIG, "COUNTRY", "GB"))
    except Exception:
        pass

    configured = _configured_networks()
    if not configured:
        print("WiFi: no networks configured in WIFI_CONFIG.py")
        ticker.set_spans(dsp.compose_fallback("NO WIFI CONFIGURED"))
        # Nothing we can do -- keep scrolling so the device isn't a brick.
        while True:
            ticker.tick(config.SCROLL_SPEED_PX)
            utime.sleep_ms(config.SCROLL_TICK_MS)

    while True:
        ticker.set_spans(dsp.compose_fallback("SCANNING..."))
        visible = _scan_visible(wlan)
        print("Visible SSIDs: {}".format(sorted(visible.keys())))

        # Visible configured networks, strongest signal first.
        ranked = [(visible[c["ssid"]], c) for c in configured if c["ssid"] in visible]
        ranked.sort(key=lambda x: x[0], reverse=True)

        # Try configured-but-invisible networks last (might be hidden SSIDs).
        for cfg in configured:
            if cfg["ssid"] not in visible:
                ranked.append((-999, cfg))

        for rssi, cfg in ranked:
            label = cfg["ssid"][:12].upper()
            ticker.set_spans(dsp.compose_fallback("WIFI: " + label))
            print("Trying '{}' (rssi={})".format(cfg["ssid"], rssi))
            if _attempt_connect(wlan, ticker, cfg["ssid"], cfg["psk"]):
                print("WiFi: connected to '{}', ifconfig={}".format(
                    cfg["ssid"], wlan.ifconfig(),
                ))
                return wlan

        # Everything failed. Cycle the interface and try again after a pause.
        print("All networks failed, cycling interface")
        ticker.set_spans(dsp.compose_fallback("NO WIFI FOUND  RETRYING"))
        try:
            wlan.active(False)
        except Exception:
            pass
        utime.sleep(5)
        wlan.active(True)
        utime.sleep(25)

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


def _refresh_display(ticker, status, first, second):
    """Push a new span set into the ticker. Only call when the content
    actually changes -- set_spans resets the scroll position."""
    if status == "OUTSIDE_HOURS":
        ticker.set_spans(dsp.compose_fallback("OUTSIDE HOURS", _hhmm_now()))
    elif status == "OFFLINE":
        ticker.set_spans(dsp.compose_fallback("OFFLINE  RETRYING", _hhmm_now()))
    else:
        spans, urgent = _compose_for(first, second)
        ticker.set_spans(spans, urgent=urgent)


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

    wlan = connect_wifi(ticker)
    sync_clock()

    first = None
    second = None
    last_poll_ms = -10**9  # force immediate poll on first iteration
    last_second_ms = utime.ticks_ms()
    last_minute_mark = -1   # sentinel -> forces first-minute render
    status = "OK"           # OK | OFFLINE | OUTSIDE_HOURS

    # Initial message before the first poll completes. Set once here; we only
    # call set_spans() again when the visible content actually changes (minute
    # rollover, poll result, or status transition). set_spans() resets the
    # scroll position, so calling it every second makes the message restart.
    ticker.set_spans(dsp.compose_fallback("STARTING..."))

    while True:
        now_ms = utime.ticks_ms()

        # Scroll every frame.
        ticker.tick(config.SCROLL_SPEED_PX)

        # Per-second: look for a minute rollover. Clock and countdown only
        # change once a minute, so no need to re-render more often than that.
        if utime.ticks_diff(now_ms, last_second_ms) >= 1000:
            last_second_ms = now_ms
            current_minute = utime.localtime()[4]
            if current_minute != last_minute_mark:
                if last_minute_mark != -1:
                    # Real minute tick -- decrement cached countdowns.
                    first, second = _decrement_cached(first, second)
                last_minute_mark = current_minute
                _refresh_display(ticker, status, first, second)

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
                    # If WiFi dropped out from under us, bring it back up.
                    try:
                        if not wlan.isconnected():
                            print("[{}] WiFi dropped, reconnecting".format(_hhmm_now()))
                            wlan = connect_wifi(ticker)
                    except Exception as re:
                        print("WiFi reconnect raised: {}".format(re))
                gc.collect()
            # Fresh poll result (or status change) -- refresh the display now
            # rather than waiting up to 60s for the next minute rollover.
            _refresh_display(ticker, status, first, second)

        utime.sleep_ms(config.SCROLL_TICK_MS)


if __name__ == "__main__":
    run()

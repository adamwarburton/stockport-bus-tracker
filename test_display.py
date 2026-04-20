"""test_display.py -- render a hardcoded message on the Galactic Unicorn.

Upload to the Pico and run in Thonny to eyeball the scrolling layout WITHOUT
any network calls. Verifies the display pipeline works before we plug in the
API layer.

    >>> from test_display import run
    >>> run()
"""

import utime

from galactic import GalacticUnicorn
from picographics import PicoGraphics, DISPLAY_GALACTIC_UNICORN

import display as dsp
import config


def run():
    unicorn = GalacticUnicorn()
    graphics = PicoGraphics(display=DISPLAY_GALACTIC_UNICORN)
    unicorn.set_brightness(0.6)

    ticker = dsp.Ticker(graphics, unicorn,
                        width=GalacticUnicorn.WIDTH,
                        height=GalacticUnicorn.HEIGHT)

    fake_first = {
        "route": "385",
        "destination": "Mellor",
        "minutes_until_leave": 3,          # triggers urgent flash
        "minutes_until_bus": 3 + config.WALK_MINUTES,
        "bus_time_hhmm": "12:12",
        "is_live": True,
    }
    fake_second = {
        "route": "383",
        "destination": "Marple-Romiley Circular",
        "minutes_until_leave": 12,
        "minutes_until_bus": 16,
        "bus_time_hhmm": "12:21",
        "is_live": False,
    }
    spans = dsp.compose_normal(fake_first, fake_second, "12:09")
    urgent = fake_first["minutes_until_leave"] <= config.URGENT_FLASH_THRESHOLD
    ticker.set_spans(spans, urgent=urgent)

    print("Test message loaded. Scrolling forever -- Ctrl+C to stop.")
    while True:
        ticker.tick(config.SCROLL_SPEED_PX)
        utime.sleep_ms(config.SCROLL_TICK_MS)


if __name__ == "__main__":
    run()

"""buttons.py -- tap detector + palette cycler for the Galactic Unicorn.

Alexia's profile uses two buttons on the top edge of the board:
  A  -- single tap cycles through the colour palette.
  B  -- single tap forces an immediate refresh of buses + weather.

Double-tap on either button is reserved for future use but supported by the
detector. The main loop polls `TapDetector.poll(pressed_now)` once per frame
and acts on whatever it returns.

Kept deliberately tiny -- no threads, no interrupts. The Galactic Unicorn's
`unicorn.is_pressed(SWITCH_X)` is cheap and the main loop ticks ~25x/sec
which is fine for debounce + tap detection.
"""

try:
    import utime as _time  # MicroPython
except ImportError:  # pragma: no cover
    import time as _time


# Two presses inside this many ms count as a double-tap. 350ms is the sweet
# spot between "felt like a double tap" and "accidental second press".
_DOUBLE_TAP_MS = 350


class TapDetector:
    """Edge-triggered single/double-tap detector for one button.

    Call `poll(pressed_now)` with the current pressed bool every frame.
    Returns one of None / "single" / "double".

    A single-tap is emitted only AFTER the double-tap window has lapsed
    without a second press, so "single" and "double" never both fire for
    one gesture.
    """

    def __init__(self, double_tap_ms=_DOUBLE_TAP_MS):
        self._double_ms = double_tap_ms
        self._last_pressed = False
        self._first_press_ms = None  # timestamp of the first press awaiting a partner

    def poll(self, pressed_now):
        now = _time.ticks_ms() if hasattr(_time, "ticks_ms") else int(_time.time() * 1000)
        pressed = bool(pressed_now)
        press_edge = pressed and not self._last_pressed
        self._last_pressed = pressed

        if press_edge:
            if self._first_press_ms is not None and _diff_ms(now, self._first_press_ms) <= self._double_ms:
                # Second press within window -> double-tap, clear state.
                self._first_press_ms = None
                return "double"
            # First press -- start the window.
            self._first_press_ms = now
            return None

        # No new press. If a first press is old enough, promote it to a single.
        if (
            self._first_press_ms is not None
            and _diff_ms(now, self._first_press_ms) > self._double_ms
        ):
            self._first_press_ms = None
            return "single"
        return None


def _diff_ms(now, then):
    """ms between two timestamps, tolerant of ticks_ms wraparound."""
    if hasattr(_time, "ticks_diff"):
        return _time.ticks_diff(now, then)
    return now - then


class PaletteCycler:
    """Holds a palette of (r,g,b) tuples and the current index.

    `advance()` moves to the next colour and returns it; `colour` reads the
    current entry. Empty/None palettes fall back to amber so the display
    never goes dark by accident.
    """

    def __init__(self, palette):
        self._palette = list(palette) if palette else [(255, 140, 0)]
        self._idx = 0

    @property
    def colour(self):
        return self._palette[self._idx]

    def advance(self):
        self._idx = (self._idx + 1) % len(self._palette)
        return self.colour

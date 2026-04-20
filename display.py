"""display.py -- scrolling amber ticker for the Galactic Unicorn (53x11).

Exposes a `Ticker` class that:
  - owns the PicoGraphics + GalacticUnicorn pair (injected, so tests can mock),
  - accepts a list of (text, rgb) spans plus a state flag,
  - advances one pixel per `tick()` call,
  - renders to the display on each tick.

The main loop calls tick() ~every 10ms to get a smooth scroll; it calls
set_message() whenever the underlying data changes.

All layout assumes the default 53x11 Galactic Unicorn geometry. Font is
PicoGraphics' built-in bitmap8 which stands 8px tall and leaves a 1px top
and 2px bottom margin in the 11px band -- comfy.
"""

# Amber -- classic bus/rail dot-matrix colour.
AMBER = (255, 140, 0)
AMBER_DIM = (140, 70, 0)       # readable through the acrylic diffuser
AMBER_BRIGHT = (255, 200, 80)

_FONT = "bitmap8"
_FONT_HEIGHT = 8
_GAP_BETWEEN_LOOPS_PX = 12  # blank pixels between the end of the message and


class Ticker:
    """Scrolling amber ticker.

    Args:
      graphics: a PicoGraphics instance, already created by the caller.
      unicorn:  a GalacticUnicorn instance, already created by the caller.
      width:    display width in pixels (53 for Galactic Unicorn).
      height:   display height in pixels (11 for Galactic Unicorn).
    """

    def __init__(self, graphics, unicorn, width=53, height=11):
        self.graphics = graphics
        self.unicorn = unicorn
        self.width = width
        self.height = height
        self._spans = [("", AMBER)]
        self._span_widths = [0]
        self._total_width = 0
        self._scroll_x = 0
        self._flash_phase = 0  # toggles 0/1 for the urgent-flash effect
        self._urgent = False
        try:
            self.graphics.set_font(_FONT)
        except Exception:
            # Some PicoGraphics builds accept font on every draw call instead;
            # silently ignore if set_font is unavailable.
            pass

    # --- Message composition --------------------------------------------------

    def set_spans(self, spans, urgent=False):
        """Replace the displayed message. `spans` is a list of (text, (r,g,b))
        tuples. `urgent` flips on the flash effect for the first span."""
        if not spans:
            spans = [("", AMBER)]
        self._spans = spans
        self._span_widths = [self._measure(text) for text, _ in spans]
        gap_width = self._measure(" " * 3)  # visible space before loop repeats
        self._total_width = sum(self._span_widths) + _GAP_BETWEEN_LOOPS_PX + gap_width
        self._urgent = bool(urgent)
        # Reset scroll so the new message starts off the right edge.
        self._scroll_x = -self.width

    def _measure(self, text):
        try:
            return self.graphics.measure_text(text, 1)
        except Exception:
            # Rough fallback: bitmap8 glyphs are ~6px wide including kerning.
            return len(text) * 6

    # --- Rendering ------------------------------------------------------------

    def tick(self, scroll_speed_px=1):
        """Draw one frame and advance the scroll position by `scroll_speed_px`."""
        g = self.graphics

        # Clear.
        g.set_pen(g.create_pen(0, 0, 0))
        g.clear()

        # Draw each span in sequence at the current scroll offset. We draw the
        # message twice (once starting at -scroll_x, once at -scroll_x +
        # total_width) so the loop wraps seamlessly.
        y = (self.height - _FONT_HEIGHT) // 2

        for loop_offset in (0, self._total_width):
            x = -self._scroll_x + loop_offset
            for idx, (text, rgb) in enumerate(self._spans):
                if not text:
                    continue
                colour = self._effective_colour(idx, rgb)
                r, gr, b = colour
                g.set_pen(g.create_pen(r, gr, b))
                # Skip spans that are fully off-screen to save draw calls.
                span_w = self._span_widths[idx]
                if x + span_w >= 0 and x <= self.width:
                    g.text(text, x, y, -1, 1)
                x += span_w

        self.unicorn.update(g)

        # Advance scroll + flash phase.
        self._scroll_x += scroll_speed_px
        if self._scroll_x >= self._total_width:
            self._scroll_x -= self._total_width
        self._flash_phase = (self._flash_phase + 1) % 40  # ~0.4s cycle at 10ms

    def _effective_colour(self, span_idx, rgb):
        """Apply the urgent-flash effect to the first span when enabled."""
        if self._urgent and span_idx == 0:
            # Alternate between bright and dim every ~0.2s.
            return AMBER_BRIGHT if self._flash_phase < 20 else AMBER_DIM
        return rgb


# --- Message builders --------------------------------------------------------
#
# These return a list of (text, rgb) spans ready for Ticker.set_spans().
# Kept here so the composition rules live next to the renderer.


def compose_normal(first, second, clock_hhmm):
    """Build the "LEAVE IN N MIN..." spans from two departure dicts + clock.

    `first` is required; `second` may be None.
    """
    leave_in = first["minutes_until_leave"]
    if leave_in == 0:
        head = "LEAVE NOW"
    elif leave_in == 1:
        head = "LEAVE IN 1 MIN"
    else:
        head = "LEAVE IN {} MIN".format(leave_in)

    route = first["route"]
    dest = first["destination"].upper()
    live_tag = "" if first.get("is_live") else "~"  # "~" = timetable-only

    parts = [
        (head + "  ", AMBER_BRIGHT),
        ("{}{} TO {}".format(live_tag, route, dest), AMBER),
    ]
    if second is not None:
        parts.append((
            "  NEXT {} AT {}".format(second["route"], second["bus_time_hhmm"]),
            AMBER,
        ))
    parts.append(("  {}".format(clock_hhmm), AMBER_DIM))
    return parts


def compose_fallback(message, clock_hhmm=None):
    """Spans for fallback/error states."""
    spans = [(message, AMBER)]
    if clock_hhmm:
        spans.append(("  {}".format(clock_hhmm), AMBER_DIM))
    return spans

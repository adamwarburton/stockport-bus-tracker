# config.py -- personal settings for the bus ticker.
#
# Copy this file to config.py on the Pico and fill in the values below.
# DO NOT commit config.py (it is in .gitignore) -- the real file contains an
# API key.
#
# Where to get the TransportAPI credentials:
#   1. Sign up at https://developer.transportapi.com/
#   2. Create an app. The portal will give you an "app id" and "app key".
#   3. Free tier is 30 requests/day -- bump POLL_INTERVAL_SECONDS to 600 if you
#      stay on free. Home tier (GBP 5/month) is 300/day and fits the default
#      3-minute poll over a 13-hour window comfortably (~260 req/day).

# --- Which profile to run ----------------------------------------------------
# "stockport" -- the original "leave in N min" ticker for Grand Central.
# "alexia"    -- bus 192 + weather + sleep window + button colour cycling.
#
# One codebase, both devices. Each Pico picks its profile via its own
# config.py; everything else (WiFi, NTP, scrolling) is shared.
PROFILE = "stockport"

# --- TransportAPI credentials (both profiles) --------------------------------
APP_ID = "your_app_id_here"
APP_KEY = "your_app_key_here"

# =============================================================================
# Stockport profile
# =============================================================================

# ATCO code for the bus stop. Find yours at https://www.travelinedata.org.uk/
# or by searching TransportAPI. Default below is Stockport Grand Central Stop RR.
STOP_ATCOCODE = "1800SG14861"

# Only departures for these service/line numbers are shown.
ROUTES = ["385", "383"]

# Minutes from your desk to the bus stop. Any bus leaving sooner than this is
# filtered out (you couldn't catch it anyway), and the on-screen "LEAVE IN N
# MIN" counter is "minutes until bus" minus this value.
WALK_MINUTES = 4

# Seconds between TransportAPI polls. Between polls we decrement the cached
# countdown locally so the display stays live.
POLL_INTERVAL_SECONDS = 180  # 3 minutes

# Local-time hours (24h) during which we poll the API. Outside this window we
# show "OUTSIDE HOURS" and skip network calls entirely to save the quota.
# Tuple is (start_hour_inclusive, end_hour_exclusive).
POLL_WINDOW = (7, 20)

# Amber -- classic bus/rail dot-matrix colour.
AMBER_RGB = (255, 140, 0)

# Flash the "LEAVE IN N MIN" section brighter when the soonest viable bus is
# this close (in minutes-until-leave). Set to 0 to disable.
URGENT_FLASH_THRESHOLD = 5

# =============================================================================
# Alexia profile
# =============================================================================

# Stop ATCO for the 192 at the end of the road.
ALEXIA_STOP_ATCOCODE = "1800SG40001"

# Routes to show on Alexia's device.
ALEXIA_ROUTES = ["192"]

# Direction filter -- a departure is only shown if its `direction` string
# contains this substring (case-insensitive). Set to "" to show both
# directions.
ALEXIA_DIRECTION_CONTAINS = "piccadilly"

# How many upcoming departure times to show on the ticker (e.g. 3 -> "10, 12, 15 MIN").
ALEXIA_BUS_COUNT = 3

# Weather (Open-Meteo -- free, no API key). Default coords are the bedroom
# location the user supplied; tune if the device moves.
ALEXIA_WEATHER_LAT = 53.398231
ALEXIA_WEATHER_LON = -2.136303

# Seconds between weather polls. Open-Meteo has no hard quota but be polite.
ALEXIA_WEATHER_POLL_SECONDS = 600  # 10 minutes

# Sleep window -- the LED panel is blanked between these times (local).
# Device stays powered on so buttons + WiFi still work; only the display
# goes dark. Tuple is (hour, minute). Crosses midnight: 20:00 -> 06:30.
ALEXIA_SLEEP_START = (20, 0)
ALEXIA_SLEEP_END = (6, 30)

# Colour palette Alexia cycles through with a single tap of button A.
# Index 0 is the power-on default; each tap advances one step and wraps.
ALEXIA_PALETTE = [
    (255, 140, 0),     # amber
    (255,  70,  70),   # red
    ( 90, 210, 120),   # green
    ( 90, 150, 255),   # blue
    (210, 110, 255),   # purple
    (255, 110, 190),   # pink
    (255, 255, 255),   # white
]

# =============================================================================
# Shared scrolling / timing
# =============================================================================

# Pixels per frame tick. Lower = smoother + slower scroll.
SCROLL_SPEED_PX = 2
SCROLL_TICK_MS = 40

# config.py -- personal settings for the Stockport bus ticker.
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

# --- TransportAPI credentials ------------------------------------------------
APP_ID = "your_app_id_here"
APP_KEY = "your_app_key_here"

# --- Which stop to monitor ---------------------------------------------------
# ATCO code for the bus stop. Find yours at https://www.travelinedata.org.uk/
# or by searching TransportAPI. Default below is Stockport Grand Central Stop RR.
STOP_ATCOCODE = "1800SG14861"

# --- Which routes we care about ----------------------------------------------
# Only departures for these service/line numbers are shown. Edit freely.
ROUTES = ["385", "383"]

# --- Walk time ---------------------------------------------------------------
# Minutes from your desk to the bus stop. Any bus leaving sooner than this is
# filtered out (you couldn't catch it anyway), and the on-screen "LEAVE IN N
# MIN" counter is "minutes until bus" minus this value.
WALK_MINUTES = 4

# --- Polling -----------------------------------------------------------------
# Seconds between TransportAPI polls. Between polls we decrement the cached
# countdown locally so the display stays live.
POLL_INTERVAL_SECONDS = 180  # 3 minutes

# Local-time hours (24h) during which we poll the API. Outside this window we
# show "OUTSIDE HOURS" and skip network calls entirely to save the quota.
# Tuple is (start_hour_inclusive, end_hour_exclusive).
POLL_WINDOW = (7, 20)

# --- Display -----------------------------------------------------------------
# Amber -- classic bus/rail dot-matrix colour.
AMBER_RGB = (255, 140, 0)

# Pixels per frame tick. Lower = smoother + slower scroll.
SCROLL_SPEED_PX = 1
SCROLL_TICK_MS = 40

# Flash the "LEAVE IN N MIN" section brighter when the soonest viable bus is
# this close (in minutes-until-leave). Set to 0 to disable.
URGENT_FLASH_THRESHOLD = 5

# Stockport Bus Ticker

A tiny Pimoroni Galactic Unicorn displaying the next bus as a scrolling
amber ticker. Two profiles live in one codebase -- flip `PROFILE` in
`config.py` to pick.

**Stockport profile** -- "leave in N minutes" for the commute home:

```
LEAVE IN 6 MIN · 385 TO MELLOR · NEXT 383 AT 17:42 · 16:51
```

- Shows the single soonest bus on my chosen routes (`385`, `383`)
- Subtracts my 4-minute walk so the number is "leave your desk in N"
- Filters out buses you couldn't make on foot
- Flashes the first segment brighter when it's 5 minutes or less
- Fallback messages for no buses / offline / outside hours

**Alexia profile** -- next three 192s toward Piccadilly + weather + sleep window:

```
192  10 MIN  12 MIN  15 MIN   12 RAIN IN 15 MIN ENDS IN 45 MIN   07:42
```

- Shows the next three upcoming departures for route `192` (direction-filtered)
- Weather from Open-Meteo (free, no API key): temperature + one of three rain
  states so the question "do I need an umbrella?" has a one-glance answer
- Button `A` single-tap cycles through a colour palette (amber/red/green/blue/
  purple/pink/white)
- Button `B` single-tap forces an immediate refresh of buses + weather
- LED panel blanks between 20:00 and 06:30 so it doesn't keep a kid awake;
  device stays powered on and auto-refreshes on wake

## Hardware

- [Pimoroni Galactic Unicorn (PIM734)](https://shop.pimoroni.com/products/galactic-unicorn)
  - Pico 2 W on board, 53x11 RGB LED matrix
- A micro-USB cable (the Galactic Unicorn's jack is micro-USB, not USB-C)
- WiFi

## One-time setup

### 1. Flash Pimoroni MicroPython (if the Pico is brand new)

Download the latest `pimoroni-picow-*.uf2` from
<https://github.com/pimoroni/unicorn/releases/latest>, hold **BOOTSEL** on
the Pico while plugging it in, and drag the `.uf2` onto the `RPI-RP2`
drive that appears. The Pico reboots into MicroPython.

### 2. Clone this repo and copy the example configs

```bash
git clone https://github.com/adamwarburton/stockport-bus-tracker
cd stockport-bus-tracker
cp WIFI_CONFIG.example.py WIFI_CONFIG.py
cp config.example.py config.py
```

### 3. Fill in `WIFI_CONFIG.py`

List every network you want the Pico to be able to connect to. On boot
it scans for visible APs and picks the strongest match -- so the same
Pico moves from home to office without needing re-flashing.

```python
NETWORKS = [
    {"ssid": "MyHomeWiFi",   "psk": "hunter2"},
    {"ssid": "OfficeWiFi",   "psk": "correct-horse-battery-staple"},
    {"ssid": "PhoneHotspot", "psk": "backup-network"},
]

COUNTRY = "GB"
```

Notes:

- Order doesn't matter -- signal strength picks the winner.
- Add phone hotspots, guest networks, anywhere you want the ticker to
  just work.
- The legacy `SSID = "..."` / `PSK = "..."` format is still accepted
  for backwards compatibility; if `NETWORKS` is missing the Pico falls
  back to those globals.

### 4. Fill in `config.py`

Grab a free TransportAPI app id/key from
<https://developer.transportapi.com/> and drop them in. If you stay on
the free tier (30 requests/day), bump `POLL_INTERVAL_SECONDS` to `600`
and narrow `POLL_WINDOW` -- otherwise you'll blow the quota in an hour.

Pick a profile at the top of the file -- either `"stockport"` or `"alexia"`.
Settings for the other profile are ignored, so it's fine to leave them
filled in.

**Shared**:

| Variable | Default | Notes |
| --- | --- | --- |
| `PROFILE` | `"stockport"` | `"stockport"` or `"alexia"` |
| `APP_ID` / `APP_KEY` | -- | From <https://developer.transportapi.com/> |
| `SCROLL_SPEED_PX` / `SCROLL_TICK_MS` | `2` / `40` | Scroll speed |

**Stockport profile**:

| Variable | Default | Notes |
| --- | --- | --- |
| `STOP_ATCOCODE` | `1800SG14861` | Grand Central Stop RR |
| `ROUTES` | `["385", "383"]` | Edit to whatever you ride |
| `WALK_MINUTES` | `4` | Cuts the count by this many, drops buses you couldn't catch |
| `POLL_INTERVAL_SECONDS` | `180` | 3 min -> ~260 reqs/day inside a 13h window |
| `POLL_WINDOW` | `(7, 20)` | Only poll between these hours (local) |
| `AMBER_RGB` | `(255, 140, 0)` | Change if you hate amber (philistine) |
| `URGENT_FLASH_THRESHOLD` | `5` | Flash when bus is this close (min). 0 = disable |

**Alexia profile**:

| Variable | Default | Notes |
| --- | --- | --- |
| `ALEXIA_STOP_ATCOCODE` | `1800SG40001` | End of the road, 192 toward Piccadilly |
| `ALEXIA_ROUTES` | `["192"]` | Routes to show |
| `ALEXIA_DIRECTION_CONTAINS` | `"piccadilly"` | Filter to one direction. `""` disables |
| `ALEXIA_BUS_COUNT` | `3` | How many upcoming departures to show |
| `ALEXIA_WEATHER_LAT` / `ALEXIA_WEATHER_LON` | Stockport | Open-Meteo uses these |
| `ALEXIA_WEATHER_POLL_SECONDS` | `600` | 10 min is plenty for a domestic forecast |
| `ALEXIA_SLEEP_START` / `ALEXIA_SLEEP_END` | `(20,0)` / `(6,30)` | Panel blanks between these |
| `ALEXIA_PALETTE` | 7 colours | Cycled by the `A` button |

Reuses `POLL_INTERVAL_SECONDS` from the Stockport settings for TransportAPI.

### Alexia profile -- buttons

Both buttons live on the top edge of the Galactic Unicorn, labelled on
the silkscreen.

| Button | Single tap |
| --- | --- |
| `A` | Cycle display colour (wraps round) |
| `B` | Force an immediate bus + weather refresh |

Taps are edge-detected at ~25Hz, so presses of up to ~40ms register
reliably. A 350ms window separates single from double (double-tap is
reserved for future use).

### 5. Upload the files to the Pico via Thonny

1. Install [Thonny](https://thonny.org/).
2. Open Thonny, pick **Run -> Interpreter -> MicroPython (Raspberry Pi
   Pico)** in Options, and select your Pico.
3. Open each file from this repo and use **File -> Save copy...** ->
   **Raspberry Pi Pico**, saving with the same filename.
4. You need at minimum: `main.py`, `config.py`, `WIFI_CONFIG.py`,
   `bus_api.py`, `display.py`. For the Alexia profile also upload
   `weather_api.py` and `buttons.py`. `test_display.py` is optional.
5. Reset the Pico (unplug/replug, or click the red stop button then
   green play). It'll auto-run `main.py`.

## Testing

### Smoke-test the API from your laptop

Before even touching the Pico:

```bash
pip install requests
python3 test_api.py       # TransportAPI buses
python3 test_weather.py   # Open-Meteo weather (Alexia profile)
```

`test_api.py` should print HTTP 200 and a JSON blob containing your
routes. `test_weather.py` prints the normalised state (`RAIN NOW ENDS
IN 45 MIN` etc.) so you can eyeball what Alexia's ticker would show.

### Verify the display without WiFi

Upload `test_display.py` alongside the other files, then in Thonny open
it and hit play. You should see a hardcoded "LEAVE IN 3 MIN..." message
scrolling with the urgent flash on. If that works, the display pipeline
is healthy; any problem after that is network or API.

### Watch the live logs

Leave Thonny connected while `main.py` runs -- the shell panel at the
bottom is your only console, and `main.py` prints one line per poll,
per WiFi retry, and per NTP sync.

## Troubleshooting

**Nothing lights up.** Did you flash Pimoroni's MicroPython build
specifically? The stock Raspberry Pi build doesn't include the
`galactic` or `picographics` modules. Also check brightness in
`main.py` -- `unicorn.set_brightness(0.6)`.

**`NO WIFI FOUND  RETRYING` forever.** None of the networks in
`NETWORKS` are visible, or they are but the password is wrong. The
Thonny shell prints the visible SSIDs each scan -- compare that list
against `NETWORKS`. The Pico 2 W doesn't support WiFi 6-only networks;
move it to a 2.4GHz network if yours is dual-band. `network.country("GB")`
improves connect reliability on UK channels -- don't remove it.

**Pico picked the wrong network.** If two networks with similar names
are visible (e.g. a neighbour with a confusing SSID, or a guest SSID
you didn't mean to join), remove the unwanted entry from `NETWORKS` --
the scanner picks whichever matching SSID has the strongest signal, and
that isn't always yours.

**`NO WIFI CONFIGURED`.** `NETWORKS` is empty and the legacy `SSID`
global isn't set either. Fill in `WIFI_CONFIG.py`.

**`OFFLINE  RETRYING`.** The API call raised. Watch Thonny's shell for
the exception. Most commonly:
- 403: wrong `APP_ID`/`APP_KEY`.
- 429: quota exceeded (you're on free tier polling too often).
- Timeout: transient, it'll recover on the next poll.

**Route numbers I want aren't showing.** Edit `ROUTES` in `config.py`
and re-upload. If the route exists but is only scheduled (not live),
you'll see a `~` prefix before the number on the display.

**Clock is an hour off.** The BST/GMT logic is in `is_bst()` in
`main.py`. It flips at 01:00 UTC on the last Sunday of March/October.
If you're travelling outside the UK, comment out the offset logic in
`sync_clock()`.

**Changing colours.** Tweak `AMBER_RGB` in `config.py` or, for the
flash/dim variants, the constants at the top of `display.py`.

## Files

| File | What it does |
| --- | --- |
| `main.py` | Entry point. Runs on boot. Dispatches to `run_stockport()` or `run_alexia()` by `config.PROFILE`. |
| `bus_api.py` | TransportAPI wrapper. `get_soonest_two_viable_departures` (Stockport) + `get_upcoming_departures` (Alexia). |
| `weather_api.py` | Open-Meteo wrapper -- temperature + three-state rain summary. |
| `display.py` | `Ticker` class + composition helpers for both profiles. |
| `buttons.py` | Tap detector + palette cycler for the Alexia profile. |
| `config.py` | Your API keys, profile, stop, routes, timings. Gitignored. |
| `config.example.py` | Committed template. |
| `WIFI_CONFIG.py` | WiFi creds. Gitignored. |
| `WIFI_CONFIG.example.py` | Committed template. |
| `test_api.py` | Laptop-side CPython smoke test for TransportAPI. |
| `test_weather.py` | Laptop-side CPython smoke test for Open-Meteo. |
| `test_display.py` | On-Pico visual test using hardcoded data. |

# WIFI_CONFIG.py -- WiFi credentials for the Pimoroni Galactic Unicorn.
#
# Copy this file to WIFI_CONFIG.py on the Pico and fill in your networks.
# DO NOT commit WIFI_CONFIG.py (it is in .gitignore).
#
# At startup the Pico scans for visible access points and connects to the
# strongest match from NETWORKS. Order in the list does NOT matter -- signal
# strength wins. Add as many as you like (home, office, phone hotspot, ...).

NETWORKS = [
    {"ssid": "HomeWiFiName", "psk": "homepassword"},
    {"ssid": "OfficeWiFiName", "psk": "officepassword"},
]

COUNTRY = "GB"

# Backwards-compat: the legacy single-credential format (top-level SSID/PSK)
# is still accepted if NETWORKS is absent. Leave that file untouched if you
# haven't migrated yet. Example of the legacy shape:
#
#     SSID = "OnlyOneNetwork"
#     PSK = "itspassword"
#     COUNTRY = "GB"

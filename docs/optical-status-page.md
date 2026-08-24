# Optical Status Page (uhttpd)

A tiny dependency-free status page for the EN7571/LDDLA optical front-end,
served by `uhttpd`. Shows module identity, readiness, TX state and laser
bias current, auto-refreshing every 5 s — plus TX on/off buttons.

![requires](https://img.shields.io/badge/requires-BOB%20cal%20loaded-orange)

## Prerequisites

1. The `airoha/en7571` driver bound to the chip (`0x70` on i2c0).
2. A valid **BOB calibration blob** at `/lib/firmware/airoha/en7571_bob.bin`
   (400 bytes; 225 real bytes padded with `FF`). See
   [optical-bob.md](optical-bob.md) for the extraction method.
3. `uhttpd` installed and running with default `/www` docroot and
   `/cgi-bin` CGI prefix.

## Install

```sh
# persist in the overlay so it survives reboots
mkdir -p /overlay/upper/www/cgi-bin
cp examples/optical-status.cgi /overlay/upper/www/cgi-bin/optical-status
chmod +x /overlay/upper/www/cgi-bin/optical-status
cp examples/optical.html        /overlay/upper/www/optical.html
/etc/init.d/uhttpd restart
```

Open `http://<device-ip>/optical.html`.

## Notes

* Power/bias readings are **zero while the laser is off** (`tx_enabled=0`);
  they become meaningful once a GPON link is activated.
* The page is intentionally read+TX-toggle only. It does not touch any
  other subsystem.
* If your driver probes before the overlay mounts (built-in driver), force
  a re-probe once after boot:

```sh
echo 0-0070 > /sys/bus/i2c/drivers/en7571/unbind
echo 0-0070 > /sys/bus/i2c/drivers/en7571/bind
```

or ship an init script that does this late in boot.

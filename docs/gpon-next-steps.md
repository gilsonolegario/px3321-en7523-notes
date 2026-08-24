# 🌐 GPON / xPON Next Steps

[← Back to README](../README.md) · [Hardware overview →](hardware.md)

Bringing fiber connectivity up on mainline is the last big milestone.
The drivers are present (`AIROHA_XPON`, optical front-end); what remains is
the protocol stack and provisioning.

## What already works

* XPON MAC block exposes rich state via `/proc/xpon/ponInfo`
  (mode GPON, activation registers, GEM/GTC counters)
* Optical front-end driver with DDMI once the BOB table is loaded
  (see [optical-bob.md](optical-bob.md))
* Provisioning identity readable from the stock side:
  GPON serial number, registration ID, PLOAM password
  (`prolinecmd xponsn/xponpwd/GponRegId` fields)

## The missing piece: OMCI

After physical link (state O4/O5 negotiation), the **OLT** provisions the
ONT through OMCI (ITU-T G.988): VLANs, T-CONTs, GEM ports, QoS queues and
the bridging path that carries actual traffic.

A community **open-source OMCI daemon** has reached **O5 state on live ISP
fiber** (full handshake + hardware-offloaded PPPoE/NAT at near-gigabit),
originally developed for EcoNet MIPS boards and considered portable to the
ARM EN7523. See the pkt.wiki EcoNet Linux project and the work by
thienanh95/AKoo7.

## Provisioning identity

The OLT authorizes the unit by serial number / registration ID. On stock,
these are visible via `prolinecmd`:

```sh
prolinecmd serialnum get     # via raw reservearea read if no 'get' verb
prolinecmd GponRegId ...
```

and in the bootloader environment (`GponSerialNumber=...`). When testing a
mainline port against a live ISP line, inject exactly these values through
UCI/runtime configuration — a mismatched identity means the OLT ignores you.

## References

* [hack-gpon.org](https://hack-gpon.org) — GPON reverse engineering hub
* [pkt.wiki — EcoNet Linux](https://econet-linux.pkt.wiki)
* OpenWrt EcoNet MIPS upstream target discussions

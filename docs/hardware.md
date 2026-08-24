# Hardware Overview

| Component | Detail |
|---|---|
| SoC | Airoha **EN7523** (ARMv7, 2× Cortex-A53 @ up to 1.0 GHz, package `EN7529CT`) |
| RAM | 512 MiB DDR3-1866 (usable ~456 MiB after ATF/NPU/QDMA reservations) |
| NAND | Micron SPI-NAND **256 MiB** (128 KiB blocks) via airoha-spi / SNFI |
| Ethernet | Airoha eth (10G internal) + **MT7530 DSA** switch: 4× GbE LAN |
| Wi-Fi | **MT7916** DBDC on PCIe: 2.4 GHz 2×2 (phy0) + 5 GHz 3×3 (phy1), AX3000 |
| Optical | Integrated **EN7571 LDDLA/BOSA** GPON front-end, i2c address **0x70** |
| VoIP | SLIC/FXS subsystem present (`/proc/fxs`, `/proc/slic` in vendor kernel) |
| Crypto | Inside-Secure EIP93 |
| Boot ROM | EN7523 bootrom → ATF (256 KiB reserved at 0x80000000) |

## Reserved memory map (kernel view)

```
0x80000000 .. 0x8003FFFF   atf          (256 KiB, nomap)
0x84000000 .. 0x840FFFFF   npu-binary   (1 MiB, nomap)
0x84D00000 .. 0x862FFFFF   npu-pkt      (22 MiB, nomap)
0x86400000 .. 0x883FFFFF   qdma0-buf    (32 MiB, nomap)
0x88400000 .. 0x893FFFFF   qdma1-buf    (16 MiB, nomap)
```

## CPU frequency

The `airoha-cpufreq` driver reports package `EN7529CT`, maximum **1.0 GHz**.
Governors available: `conservative`, `ondemand`, `powersave`, `performance`.

!!! tip
    Pinning `performance` early in boot saves several seconds of wall time —
    the default `ondemand` governor ramps too slowly for short-lived boot work.

## UART console

The serial console is **UART1 at 0x1FBF0000**, exposed on header **J1**
(115200 8N1, 3.3 V logic). See [uart.md](uart.md) for pinout and the discovery method.

## Notes

* The SoC is ARMv7 32-bit mode despite Cortex-A53 cores.
* The optical front-end chip (EN7571) hangs off **i2c0 @ 0x70** and provides
  its own driver surface in mainline ports (`optical_frontend` class).
* No RTC: clock starts from flash mtimes via `sysfixtime` — never trust
  absolute timestamps across boots; only deltas within one boot are real.

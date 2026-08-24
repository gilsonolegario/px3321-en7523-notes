# UART Console

The serial console is **UART1** (`0x1FBF0000`, ns16550-compatible),
**115200 8N1**, **3.3 V logic**.

## The header (J1)

The PCB has an unpopulated factory header marked **J1**, 5 positions,
with one **empty slot** separating ground from the signal group:

```text
 position:   1      2      3     4     5
           [GND]  [ -- ] [TX]  [RX]  [VCC]
            |             |     |     |
         isolated       signal group   3V3 only!
```

| Pin | Function | Notes |
|---|---|---|
| 1 | **GND** | Physically separated from the other four — easy to spot |
| 2 | *empty* | No pin populated |
| 3 | **TX** (board → host) | Connect to adapter RX |
| 4 | **RX** (host → board) | Connect to adapter TX |
| 5 | **VCC** | 3.3 V — leave unconnected |

!!! warning
    * Never feed 5 V into any of these pads.
    * You do **not** need VCC for serial — the adapter is self-powered from USB.
    * Swapping TX/RX by mistake is harmless (no data flows); wrong polarity
      costs nothing but silence.

## Discovery method (how this pinout was confirmed)

With a capture running continuously on the host, sweep a single signal wire
across the candidate pins every few seconds:

1. Console output appearing while touching a pin identifies it as **TX**
   (board → host). On a boot-looping device, a power cycle during the sweep
   guarantees bootloader text on the correct pin.
2. Pressing `Enter` repeatedly helps find **RX**: prompts echo back.
3. GND can be found with a multimeter by continuity to the chassis or the
   power-barrel shell.

## Host-side quick test

On Linux the CH340/CH341 works out of the box (`ch341` kernel module):

```python
import serial, time
s = serial.Serial("/dev/ttyUSB0", 115200, timeout=1)
s.write(b"\r\n")
time.sleep(0.5)
print(s.read(4096))
```

On macOS, avoid third-party WCH drivers entirely — recent macOS versions ship
working support, and mixing kext+DriverKit builds creates two competing
`/dev/cu.*` nodes where only one receives data (a very confusing trap).

## What the console gives you

| Boot stage | What you see |
|---|---|
| zloader/tcboot | `bootflag==1 --> booting from second image`, FIT hash verification |
| Kernel | full earlycon and printk |
| OpenWrt preinit | failsafe prompt: press `[f]` within the window |
| Running system | full console shell (`Please press Enter to activate this console`) |

The failsafe window is the single most valuable recovery tool on this board:
it works even when the installed system panics later in boot.

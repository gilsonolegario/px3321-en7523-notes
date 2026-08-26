# 🔬 Bootloader Deep Dive — ZHAL / zloader / U-Boot on EN7523

[← Back to README](../README.md)

Complete reverse-engineering reference for the PX3321-T1 bootloader stack,
cross-referenced from UART captures, GPL source analysis, community patches,
and upstream U-Boot development.

---

## 1. Boot Chain Overview

```text
┌─────────────────────────────────────────────────────────────┐
│                    POWER ON RESET                            │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  EN7523 BootROM (Mask ROM, internal)                        │
│  • Initializes SPI NAND controller                          │
│  • Loads BL2 from NAND offset 0x0                           │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  ATF (BL31) — ARM Trusted Firmware                          │
│  • Address: 0x80000000 (256 KiB)                            │
│  • DDR3-1866 init (512 MB)                                  │
│  • PSCI v1.1 services                                       │
│  • NO easy chain-load of U-Boot (ATF-2.3 limitation)        │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  ZHAL / tcboot (U-Boot 2014.04-rc1 + ZHAL extension)       │
│  • SPI NAND offset: 0x50000 (15.7 KiB zloader payload)      │
│  • Load address: 0x81800000                                  │
│  • Image name: "zld-2.5 05/22/2023 15:32:47"                │
│  • Shell prompt: ZHAL>                                       │
│  • 33 proprietary AT* commands (NO standard U-Boot cmds)     │
│  • Autoboot: 5 seconds (Enter to interrupt)                  │
│  • Reads bootflag from reservearea+0x200000                  │
│  • Validates HDR2 header + FIT image CRC                     │
│  • Injects kernel cmdline (ethaddr, root=, bootflag, GPIOs)  │
└──────────────────────────┬──────────────────────────────────┘
                           │
              ┌────────────┴────────────┐
              │ bootflag == '0'         │ bootflag == '1'
              ▼                         ▼
┌──────────────────────┐  ┌──────────────────────┐
│ tclinux (primary)    │  │ tclinux_slave ★       │
│ mtd2 kernel          │  │ mtd5 kernel (FIT)     │
│ mtd3 rootfs          │  │ mtd6 rootfs           │
│ ~48 MiB              │  │ ~49 MiB (our OpenWrt) │
└──────────┬───────────┘  └──────────┬───────────┘
           │                         │
           └────────────┬────────────┘
                        ▼
┌─────────────────────────────────────────────────────────────┐
│  FIT Image + HDR2 Header                                    │
│  • HDR2: 372 bytes (magic "HDR2", CRC32, checksum)          │
│  • FIT: kernel@1 (LZMA), fdt@1, filesystem@1 (squashfs)     │
│  • ECONET CRC32: poly 0xEDB88320, init 0xFFFFFFFF           │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Linux Kernel Decompress                                     │
│  • LZMA decompress to 0x80208000 (entry = load addr)         │
│  • DTB from FIT (contains memory map, GPIOs, ethernet)       │
│  • Kernel cmdline from zloader (NOT from DTB /chosen)        │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Linux 6.18.41 (OpenWrt SNAPSHOT)                           │
│  • ARMv7 SMP, cortex-a7, airoha/en7523 target                │
│  • root=/dev/mtdblock6 (JFFS2 overlay on mtd7)               │
│  • console=ttyS0,115200n8                                    │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. ZHAL Shell — Complete Reference

### Accessing ZHAL

1. Connect UART (115200 8N1) — J1 header on PCB
2. Reboot: `zycli reboot` (NOT `reboot` — plain reboot may silently no-op)
3. Press **Enter** during 5-second autoboot countdown
4. `ZHAL>` prompt appears

> [!WARNING]
> The ZHAL shell is **locked by default** for write commands.
> `EngDebugFlag=0x1` must be set (via `fw_setenv` from Linux or `ATEN` challenge)
> before `ATBT`/`ATSW`/`ATSB`/`ATWF` will work.

### All 33 Commands

#### Flash Operations
| Command | Syntax | Description |
|---|---|---|
| ATER | `ATER x,y` | Erase flash: offset `x`, length `y` |
| ATRF | `ATRF x,y,z` | Read flash → RAM: offset `x`, length `y`, RAM addr `z` |
| ATWF | `ATWF x,y,z` | Write RAM → flash: RAM addr `x`, length `y`, flash offset `z` |
| ATDS | `ATDS x,y` | Dump spare area: block `x`, page `y` |
| ATCB | `ATCB` | Copy flash → working buffer |
| ATSB | `ATSB` | Save working buffer → flash |

#### Firmware Upgrade (TFTP)
| Command | Syntax | Description |
|---|---|---|
| ATUR | `ATUR [y:]x` | Upgrade RAS image (`x`=file, `y`=host IP) |
| ATUB | `ATUB [y:]x` | Upgrade ZLD image (zloader itself!) |
| ATUD | `ATUD [y:]x` | Upgrade ROMD image |
| ATUM | `ATUM [y:]x` | Upgrade ROMFILE image |
| ATMB | `ATMB [x,y]` | Upgrade firmware via Multiboot |
| ATLD | `ATLD x,[y]` | Load file `x` to RAM addr `y` via TFTP |

#### Partition Management
| Command | Syntax | Description |
|---|---|---|
| ATCD | `ATCD` | Erase RomD partition |
| ATCM | `ATCM` | Erase ROMFILE partition |
| ATCR | `ATCR` | Erase data partition |
| ATCMISC | `ATCMISC` | Erase misc partition |

#### Memory / Debug
| Command | Syntax | Description |
|---|---|---|
| ATDU | `ATDU x,y` | Dump memory: address `x`, length `y` |
| ATWW | `ATWW x,y,z` | Write memory: addr `x`, value `y`, length `z` |
| ATCMP | `ATCMP x,y,z` | Compare memory regions `x` and `y`, length `z` |
| ATRT | `ATRT [x,y,z,u]` | RAM test (level, start, end, iterations) |

#### Board Configuration
| Command | Syntax | Description |
|---|---|---|
| ATSH | `ATSH` | Dump manufacturer data (model, serial, MACs, FW version) |
| ATWM | `ATWM x` | Set MAC in working buffer |
| ATWZ | `ATWZ x,y,z,u,v` | Set MAC, country, EngDbgFlag, FeatureBit, MAC count |
| ATCO | `ATCO x` | Set country code in working buffer |
| ATSN | `ATSN x` | Set serial number to flash |
| ATGS | `ATGS x,y` | Set GPON serial number to flash |
| ATCK | `ATCK [x,y,z]` | Show/write/reset PSK, admin, supervisor passwords |
| ATBT | `ATBT x` | Block0 write enable (1=enable, 0=disable) |

#### Security / Boot
| Command | Syntax | Description |
|---|---|---|
| ATEN | `ATEN x[,y]` | Set BootExtension Debug Flag (`y`=password) |
| ATSE | `ATSE x` | Show seed of password generator |
| ATDC | `ATDC` | Disable check model mechanism |

#### System
| Command | Syntax | Description |
|---|---|---|
| ATSR | `ATSR [x]` | System reboot |
| ATSW | `ATSW` | Swap boot image to other partition |
| ATGO | `ATGO` | Boot the system |
| ATGU | `ATGU` | Go to U-Boot CLI mode (**requires 2× Enter**) |
| ATLED | `ATLED [x,y]` | Set LED (`x`=number, `y`=0/off 1/on 2/fast 3/slow) |
| ATPIO | `ATPIO x,y[,z]` | GPIO (s=set, w=write, r=read; pin; value) |
| ATHE | `ATHE` | Show command list |

---

## 3. Critical Quirks (from UART + community)

### `ATGU` Requires Two Passes
ZHAL intercepts the **first** `ATGU`: it prints `zloader_on=0` and relaunches
the zloader banner with a fresh countdown. Stop that countdown with Enter and
issue `ATGU` **again** — the second call falls through to the real U-Boot
autoboot window.

Two nearly identical countdowns appear on serial, owned by different programs:

| Countdown | Owner | Action |
|---|---|---|
| 5 s | zld-2.5 | press Enter → back to `ZHAL>` |
| 3 s | U-Boot itself (`bootdelay=3`) | **hands off** — silence lets it expire → `ECNT>` |

Touching the keyboard during the 3-second window aborts into the wrong path.
Exit back to OpenWrt afterwards with `reset`.", "edit1 ATGU")

# EDIT 2 — ECNT> em pratica + dumps de RAM (entra antes de ATBT)
replace_once(### Inside the `ECNT>` Shell

`bdinfo` ground truth from hardware:

```text
DRAM bank   = 0x80000000 (size 0x1F000000)
relocation  = 0x9EE00000
baudrate    = 115200
```

Beyond anything ZHAL offers, the shell exposes the full 2014.04-rc1 toolkit:
`md`/`mw`/`cmp`/`crc32`/`mtest`, `printenv`/`setenv`/`saveenv`/`editenv`,
`mtd`/`mtdparts`/`chpart`, `imginfo`/`iminfo`/`imxtract`, **`bootflag`
read/swap**, `ping`/`tftpboot`, `loadb`/`loadx`/`loady`, `fdt`, `efuse`,
`fip_test`, `go`/`goaddr`.

### Reading the Running Loaders from RAM

Sitting at `ZHAL>`, both loaders remain alive and decompressed in DRAM —
dumping them there beats reading their LZMA-wrapped flash copies:

```text
ATDU 0x81700000,0x18000    # zld-2.5 decompressed (96 KB)
ATDU 0x9EE00000,0x40000    # tcboot/U-Boot as-running, relocated (256 KB)
```

`strings` alone recovers the whole AT command table and help texts; capstone
does the rest. The relocation address doubles as proof of where U-Boot
executes from.

### ATBT 1 Required Before Any Flash Write

### ATBT 1 Required Before Any Flash Write
Without `ATBT 1` (block0 write enable), all write commands fail with
"Can't write to protected Flash". This is a safety mechanism.

### zycli reboot vs reboot
Plain `reboot` may silently no-op on the stock firmware. Always use
`zycli reboot` to ensure a clean restart that allows catching the
zloader countdown on serial.

### fwidcheck and modelcheck
These are ENABLED on stock firmware. Must disable before web firmware
upgrade/downgrade:
```sh
zycli fwidcheck off
zycli modelcheck off
```

---

## 4. Dual-Image Swap Flow

```text
# From ZHAL shell:
ATBT 1         # unlock block0 writes
ATSW           # swap bootflag (0↔1)
ATSR           # reboot to apply

# From Linux (stock):
sys bootflag read     # read current flag
sys bootflag swap     # flip it
zycli reboot          # apply
```

The bootflag is a single ASCII byte (`'0'` or `'1'`) at
`reservearea + 0x200000` (flash offset `0x0FFC0000`).

---

## 5. Kernel Command Line Construction

The zloader injects the kernel command line — the DTB's `/chosen/bootargs`
is **NOT used** on stock (OpenWrt DTB must be self-sufficient).

From UART capture, the injected cmdline:

```text
sdram_conf=0x00108893
ethaddr=XX:XX:XX:XX:XX:XX
snmp_sysobjid=1.2.3.4.5
country_code=D0
ether_gpio=0c
power_gpio=1515
username=<redacted>
password=<redacted>
dsl_gpio=0a
internet_gpio=01
multi_upgrade_gpio=0b0a03010604051b1a00000000000000
onu_type=2
qdma_init=31
root=/dev/mtdblock6
ro
console=ttyS0,115200n8
earlycon
bootflag=1
serdes_sel=0
tclinux_info=0x1cd1af7,0x2090,...
```

| Variable | Source | Purpose |
|---|---|---|
| `sdram_conf` | Board config | DRAM timing |
| `ethaddr` | reservearea | Factory MAC |
| `country_code` | reservearea | Regulatory domain |
| `*_gpio` | reservearea | GPIO pin assignments |
| `username`/`password` | ROMFILE | Default web credentials |
| `root` | Hardcoded | Root filesystem device |
| `bootflag` | reservearea | Which image is active |
| `tclinux_info` | FIT header | Firmware metadata pointers |

---

## 6. Flash Layout (precise offsets)

```text
0x00000000 ┌─────────────────────┐
           │ u-boot (mtd0)       │ 512 KB
           │ 0x00000-0x080000    │ U-Boot 2014.04 + ZHAL
0x00080000 ├─────────────────────┤
           │ romfile (mtd1)      │ 256 KB
           │ 0x08000-0x0C0000    │ Factory config container
0x000C0000 ├─────────────────────┤
           │ kernel (mtd2)       │ ~4 MB
           │ 0x0C000-0x4C0858    │ Primary kernel (HDR2+FIT)
0x04C08580 ├─────────────────────┤
           │ rootfs (mtd3)       │ ~44 MB
           │ 0x4C0858-0x30C0000  │ Primary squashfs
0x030C0000 ├─────────────────────┤
           │ kernel_slave (mtd5) │ ~4 MB  ★
           │ 0x30C0000-0x34C0858 │ Our kernel (FIT)
0x034C0858 ├─────────────────────┤
           │ rootfs_slave (mtd6) │ ~20 MB ★
           │ 0x34C0858-0x49C0000 │ Our squashfs
0x049C0000 ├─────────────────────┤
           │ rootfs_data (mtd7)  │ ~24 MB
           │ 0x49C0000-0x61C0000 │ JFFS2 overlay
0x061C0000 ├─────────────────────┤
           │ wwan (mtd9)         │ 1 MB (unused on this SKU)
0x062C0000 ├─────────────────────┤
           │ data (mtd10)        │ 4 MB (vendor storage)
0x066C0000 ├─────────────────────┤
           │ rom-d (mtd11)       │ 1 MB (vendor writes at boot)
0x067C0000 ├─────────────────────┤
           │ misc (mtd12)        │ ~118 MB (bad-block pool)
0x0DDC0000 ├─────────────────────┤
           │ reservearea (mtd13) │ ~2.25 MB
           │  +0x000: MT7916 EEPROM (4 KB)
           │  +0x140000: BOB table (laser calibration)
           │  +0x200000: bootflag (ASCII '0'/'1')
0x0E000000 └─────────────────────┘
```

### Inside mtd0 — FIP certificates, zloader image, environment block

Byte-level anatomy of the 512 KB `u-boot` partition (from ATRF/ATDU dumps):

| Offset | Contents |
|---|---|
| `0x00000` | Preloader / BootROM header (NOP sled + vector) |
| `0x10000` | tcboot code start (`42eeffea` ARM branch vector) |
| `0x20000` | ASN.1 FIP certificates — *"SoC Firmware Content Certificate"* |
| `0x30000` | Hash/key blobs |
| `0x40000` | Fully erased |
| `0x50000` | `zld-2.5` legacy uImage — LZMA standalone, 16 063 B payload, load `0x81700000`, entry `0x81700204` |
| `0x70000` | **Environment block** (last 64 KB sector) |

Runtime `printenv` at `ECNT>` matches the raw `0x70000..0x80000` dump
variable-for-variable — this block *is* the live environment.

The vendor SDK source explains the write path: `common/ecnt/env_flash.c`
implements `saveenv()` with a CRC32-headed `env_t` written at
`CONFIG_ENV_MTK_OFFSET`, which resolves dynamically through
`ecnt_get_ubootenv_mtd_offset()` (`drivers/misc/ecnt/image/ecnt_mtd.c`) by
looking up the partition named `MTK_UBOOT_ENV`. Notably, the block's current
data starts mid-sector (`baudrate=` at `+0xC14A`) with no CRC prefix right
before it — evidence that the present content was written by the Linux-side
parser (`en7523_evb_mtk_env_parser.h`), not by U-Boot's `saveenv`. Treat
`saveenv` as untested until exercised deliberately, with a fresh block backup
in hand.

---

## 7. Vendor Tools (from GPL + docs)

### zycli — the multi-tool
`/bin/zycli` (135 KB); symlinks change behavior by `argv[0]`:
- `sys` → bootflag read/swap/checksum, misc flash ops
- `wan` / `ethwanctl` → WAN interface control
- `restoredefault` → factory reset
- `swversion` → firmware version

### prolinecmd — factory provisioning
Reads/writes the `proline_Para` structure in reservearea:
- `serialnum`, `xponsn`, `xponpwd` → GPON identity
- `mt7570bob get` → laser BOB calibration table
- `webpwd`, `ssid`, `wpakey` → wireless defaults
- Header: `global_inc/uapi/flash_layout/prolinecmd.h` (GPL source)

### zyledctl — LED control
Maps to `/proc/tc3162/led_*` knobs. LED names: POWER_G/R, INET_G/R,
xPON_G/R, Wlan0/1, WPS0/1, USB0/1_G, DECT.

---

## 8. GPL Source Code

### Yuzhii0718/ZyXEL_PX3321-T1 (GitHub, now404)
GPL release: `V544ACHK0C0_GPL.tar.gz` — the official Zyxel GPL package
for firmware V5.44(ACHK.0)C0. Repo was taken down but the tarball
structure includes:
- `package/` — vendor apps (zycli, prolinecmd, etc.)
- `target/linux/` — kernel + patches
- `scripts/` — build + flash scripts
- `global_inc/uapi/flash_layout/` — flash map headers

### Key GPL Headers
- `flash_layout/prolinecmd.h` — reservearea structure offsets
- `flash_layout/flash_layout.h` — partition table definition
- Boot command construction in zloader source (if available in GPL)

---

## 9. Community Patches & Upstream

### carlicious/zloader (EX5601, adaptable)
Patched zloader that:
- Reimplements `get_boot_flag()` ignoring zyfwinfo validation
- Makes `ATSW` write only the boot_flag byte
- Fixes cmdline search in DTB (incompatible with OpenWrt's `/chosen`)
- Keeps engineering mode always on

### U-Boot Mainline EN7523 (Mikhail Kshevetskiy)
19-patch series on `lists.denx.de/u-boot/2025-November/602123.html`:
- Console UART, ethernet/switch, SPI-NAND (non-DMA)
- `configs/en7523_evb_defconfig`
- Tested on EN7562; Linux boot NOT yet verified
- **Chain-load workaround**: package new U-Boot as FIT image disguised
  as kernel, load via `bootm` from old zloader (no flash write needed)

### OpenWrt PR #20104
EN7523 carry set — includes PX3321-T1 support (branch `px3321-subm-v3-clean`).

### hack-gpon.org / bmork zyeng
- `zyeng` unlocks ZHAL via Ethernet without root
- Alternative to `ATEN` password challenge

---

## 10. Bootloader Replacement Strategy

### Phase 1: Dump (no risk)
```text
# From ZHAL:
ATRF 0x50000,0x4000,0x80000000    # load zloader to RAM
ATDU 0x80000000,0x4000            # dump to serial (capture offline)
```
Then: `strings -t x dump.bin | grep -iE 'trx|hdr0|tftp|bootcmd|setenv'`

### Phase 2: Chain-load Test (zero flash writes)
1. Build a U-Boot for EN7523 — either from the vendor SDK tree
   [`Yuzhii0718/bootloader-en75xx`](https://github.com/Yuzhii0718/bootloader-en75xx)
   (the exact `tcboot` + u-boot-2014.04-rc1 sources behind this bootloader,
   public) or from Mikhail Kshevetskiy's mainline series.
2. Package as FIT image: `type="kernel", os="linux", compression="lzma"`,
   load/entry=`0x81e00000`.
3. Load via TFTP — `ATLD tclinux.bin,0x81000000` then `ATGO` from ZHAL, or
   `tftpboot` + `bootm` straight from the `ECNT>` shell.
4. Success criterion: console, NAND (SNFI) and Ethernet all up from RAM.

### Phase 3: Persist to the Slave Slots Only (reversible)
Once Phase 2 proves stable:
1. Full flash dump first: `ATRF 0x0,0xE00000,0x80000000` (224 chunks),
   verified offline before anything else.
2. Package the proven image with HDR2 + ECONET CRC32 variant
   (poly `0xEDB88320`, no final XOR).
3. Write **only** into `kernel_slave` / `rootfs_slave` / `tclinux_slave`.
4. Flip the bootflag byte (`ATSW`, or `zycli sys bootflag` from stock). The
   stock slot stays as the permanent rescue image.

### Hard Invariants
1. **Never write**: mtd0 (`u-boot` — its tail sector holds the environment),
   mtd1 (`romfile`), reservearea.
2. Every flash write is a deliberate, individually authorized operation,
   preceded by a verified same-day backup.

### Risks
1. **No dual-image rollback** if ATSW/bootflag mechanism is lost
2. **cmdline dependency** — stock kernel expects zloader-injected args
3. **reservearea destruction** = bricked WiFi + optical calibration
4. **FIP/zloader version mismatch** = brick (cannot be recovered via UART)
5. **Environment loss** = defaults on next boot; restoring means rewriting a
   sector inside mtd0 — the strongest reason it stays backed up and untouched

---

## 11. References

| Resource | URL |
|---|---|
| px3321-en7523-notes | `github.com/gilsonolegario/px3321-en7523-notes` |
| openwrt-px3321 (build repo) | `github.com/gilsonolegario/openwrt-px3321` |
| U-Boot EN7523 upstream | `lists.denx.de/u-boot/2025-November/602123.html` |
| carlicious/zloader | `github.com/carlicious/zloader` |
| OpenWrt EN7523 carry set | PR `openwrt/openwrt#20104` |
| hack-gpon.org Zyxel | `hack-gpon.org/zyxel` |
| firmware-utils zytrx | `git.openwrt.org` commit `dd6f02a3` |
| Zyxel PX3321-T1 product | `zyxel.com/service-provider/global/en/products/fiber-oltsonts/gpon/hgus/px3321-t1` |

---

*Compiled from UART captures, GPL source analysis, community patches,
and upstream U-Boot development. 2026-08-25 session.*

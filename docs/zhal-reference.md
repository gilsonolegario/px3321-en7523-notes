# 🖥️ ZHAL Reference — Zyxel Hardware Abstraction Layer

[← Back to README](../README.md) · [Boot chain →](boot-chain.md)

The PX3321-T1 bootloader is **not standard U-Boot** — it is a Zyxel-proprietary
shell called **ZHAL** (Zyxel Hardware Abstraction Layer), built on top of
U-Boot 2014.04-rc1 with the ZHAL extension. The prompt is `ZHAL>`.

---

## Accessing ZHAL

1. Connect UART console (115200 8N1)
2. Reboot the device
3. Press **Enter** during the autoboot countdown (5-second window, ~T+17s after reboot)
4. The `ZHAL>` prompt appears

---

## Complete Command Reference (33 commands)

### Flash Operations

| Command | Syntax | Description |
|---|---|---|
| **ATER** | `ATER x,y` | Erase flash at offset `x` with length `y` |
| **ATRF** | `ATRF x,y,z` | Read flash to RAM: offset `x`, length `y`, RAM address `z` |
| **ATWF** | `ATWF x,y,z` | Write RAM to flash: RAM address `x`, length `y`, flash offset `z` |
| **ATDS** | `ATDS x,y` | Dump spare area data: block `x`, page `y` |
| **ATCB** | `ATCB` | Copy flash to working buffer |
| **ATSB** | `ATSB` | Save working buffer to flash |

### Firmware Upgrade (via TFTP)

| Command | Syntax | Description |
|---|---|---|
| **ATUR** | `ATUR [y:]x` | Upgrade RAS image (`x` = filename, `y` = host IP) |
| **ATUB** | `ATUB [y:]x` | Upgrade ZLD image (zloader/bootloader) |
| **ATUD** | `ATUD [y:]x` | Upgrade ROMD image |
| **ATUM** | `ATUM [y:]x` | Upgrade ROMFILE image |
| **ATMB** | `ATMB [x,y]` | Upgrade firmware via Multiboot |

### Partition Management

| Command | Syntax | Description |
|---|---|---|
| **ATCD** | `ATCD` | Erase RomD partition |
| **ATCM** | `ATCM` | Erase ROMFILE partition |
| **ATCR** | `ATCR` | Erase data partition |
| **ATCMISC** | `ATCMISC` | Erase misc partition |

### Memory / Debug

| Command | Syntax | Description |
|---|---|---|
| **ATDU** | `ATDU x,y` | Dump memory/register at address `x`, length `y` |
| **ATWW** | `ATWW x,y,z` | Write value `y` to address `x`, length `z` |
| **ATCMP** | `ATCMP x,y,z` | Compare two memory regions (addresses `x`, `y`, length `z`) |
| **ATRT** | `ATRT [x,y,z,u]` | RAM read/write test (level, start, end, iterations) |

### Board / Factory Configuration

| Command | Syntax | Description |
|---|---|---|
| **ATSH** | `ATSH` | Dump manufacturer data (model, serial, MACs, firmware version) |
| **ATWM** | `ATWM x` | Set MAC address in working buffer |
| **ATWZ** | `ATWZ x,y,z,u,v` | Set Zyxel MAC, country code, EngDbgFlag, FeatureBit, MAC count |
| **ATCO** | `ATCO x` | Set country code in working buffer |
| **ATSN** | `ATSN x` | Set serial number to flash |
| **ATGS** | `ATGS x,y` | Set GPON serial number to flash |
| **ATCK** | `ATCK [x,y,z]` | Show, write, or reset PSK, admin, and supervisor keys |
| **ATBT** | `ATBT x` | Block0 write enable (1=enable, 0=disable) |

### Security / Boot

| Command | Syntax | Description |
|---|---|---|
| **ATEN** | `ATEN x[,y]` | Set BootExtension Debug Flag (`y` = password) |
| **ATSE** | `ATSE x` | Show seed of password generator |
| **ATDC** | `ATDC` | Disable check model mechanism |

### System

| Command | Syntax | Description |
|---|---|---|
| **ATSR** | `ATSR [x]` | System reboot |
| **ATLD** | `ATLD x,[y]` | Load file `x` to RAM address `y` via TFTP |
| **ATSW** | `ATSW` | Swap boot image to other partition (reboot to apply) |
| **ATGO** | `ATGO` | Boot the system |
| **ATGU** | `ATGU` | Go back to U-Boot command line mode (does NOT expose standard U-Boot commands) |
| **ATLED** | `ATLED [x,y]` | Set LED (`x` = LED number, `y` = mode: 0=off, 1=on, 2=fast, 3=slow) |
| **ATPIO** | `ATPIO x,y[,z]` | Set GPIO (`x` = s/set, w/write, r/read; `y` = pin; `z` = value) |
| **ATHE** | `ATHE` | Show command list (this help) |

---

## Manufacturer Data (ATSH)

```
Firmware Version       : V5.44(ACHK.0)C0
Bootbase Version       : V2.5 | 05/22/2023 15:32:47
Vendor Name            : Zyxel Communications Corp.
Product Model          : PX3321-T1
Serial Number          : XXXXXXXXXXXXX
Gpon Serial Number     : XXXXXXXXXXXXXXXX
First MAC Address      : XXXXXXXXXXXXXX
Last MAC Address       : XXXXXXXXXXXXXX
MAC Address Quantity   : 16
Default Country Code   : D0
Boot Module Debug Flag : 01
RootFS      Checksum   : 0424BFE9
Kernel      Checksum   : A7DC0FCD
Main Feature Bits      : 00
```

> [!NOTE]
> This data is from a **specific unit** — serial numbers, MACs, and checksums
> are per-unit. The format and field names are universal for the PX3321-T1.

---

## Key Findings

### ZHAL ≠ Standard U-Boot

- `printenv`, `setenv`, `bdinfo`, `version` and all standard U-Boot commands
  are **not available** in ZHAL
- **`ATGU` requires TWO keystrokes**: the first reboot drops back into ZHAL;
  the second drops into the real U-Boot CLI where `setenv`/`saveenv` work
- The ZHAL shell is **locked by default** — `EngDebugFlag=0x1` or a
  password challenge (`ATSE`/`ATEN`) is needed for write commands
- **`ATBT 1`** (block0 write enable) is required before any flash write;
  without it: "Can't write to protected Flash"

### Flash Read/Write via ZHAL

The most important commands for bootloader replacement:

```text
ATRF x,y,z    — read flash (x=offset, y=length, z=RAM addr)
ATWF x,y,z    — write RAM to flash
ATER x,y      — erase flash region
ATDU x,y      — dump RAM contents
ATCB          — copy flash → working buffer
ATSB          — save working buffer → flash
ATBT 1        — UNLOCK flash writes (required before ATWF/ATER/ATSB)
```

This means we can:
1. **Dump the entire zloader binary** via `ATRF` + `ATDU`
2. **Read the U-Boot environment** from flash for reverse engineering
3. **Write a new bootloader** via `ATWF` (dangerous — no recovery if it fails)

### Dual-Image Swap Flow

```text
ATBT 1         — unlock block0 writes
ATSW           — swap bootflag (0↔1)
ATSR           — reboot to apply
```

### Bootflag Mechanism

- One ASCII byte at `reservearea + 0x200000`
- `'0'` = boot primary image, `'1'` = boot slave image
- `ATSW` swaps the boot image (writes the flag)

### Password Recovery

`ATCK` reveals default credentials (PSK, admin, supervisor). These are
factory defaults stored in the ROMFILE partition.

---

## Implications for Bootloader Replacement

### Upstream U-Boot for EN7523

A 19-patch series by Mikhail Kshevetskiy exists for mainline U-Boot:
console UART, ethernet/switch, SPI-NAND (non-DMA), clk, reset, DTS,
and `configs/en7523_evb_defconfig`. Tested on EN7562 but **Linux boot
not yet verified**. The Airoha ATF-2.3 does not allow easy chain-load —
the workaround is packaging the new U-Boot as a FIT image disguised as
a kernel (`type="kernel", os="linux"`, LZMA, entry `0x81e00000`) and
using `bootm` from the old zloader. This avoids touching the flash.

Reference: `lists.denx.de/u-boot/2025-November/602123.html`

### Community Patches

- **carlicious/zloader** — patched zloader for EX5601: reimplements
  `get_boot_flag()` ignoring zyfwinfo, makes `ATSW` write only the
  boot_flag, fixes cmdline search in DTB, keeps engineering mode always on
- **cjdelisle/ATENv3** — algorithm for `ATEN` password challenge
- **bmork/zyeng** — unlocks ZHAL via Ethernet without root
- **OpenWrt PR #20104** — EN7523 carry set (includes PX3321-T1)

### Risks for PX3321-T1

1. Losing `ATSW`/bootflag = no dual-image rollback
2. Kernel/OpenWrt expects cmdline injected by tcboot (`ethaddr=`,
   `root=`, GPIO map) — replacement must reproduce this or DTB must
   be self-sufficient
3. MT7916 calibration and EN7571 BOB data live in `reservearea` —
   this partition must survive any bootloader replacement
4. Mixing zloader version with FIP version = brick

### Safe Testing Path

1. **Dump current zloader**: `ATRF 0x50000,0x4000,0x80000000` then `ATDU`
2. **Test via chain-load** (no flash write): package new U-Boot as FIT
   kernel image, load via TFTP (`ATLD`), boot with `ATGO`
3. **Preserve factory data**: reservearea (MAC, EEPROM, calibration,
   BOB table) must never be erased
4. **Keep dual-image**: any replacement must implement bootflag or
   Multiboot upgrade protocol

---

## References

| Resource | URL |
|---|---|
| U-Boot EN7523 upstream series | `lists.denx.de/u-boot/2025-November/602123.html` |
| carlicious/zloader (EX5601 patches) | `github.com/carlicious/zloader` |
| cjdelisle/ATENv3 password algo | `github.com/cjdelisle/…` |
| bmork zyeng (Ethernet unlock) | `github.com/bmork` |
| OpenWrt EN7523 carry set | PR `openwrt/openwrt#20104` |
| hack-gpon.org Zyxel unlock | `hack-gpon.org/zyxel` |
| firmware-utils zytrx (TRX header RE) | `git.openwrt.org` commit `dd6f02a3` |

---

*Discovered via UART console and community research, 2026-08-25 session.*

# 🔧 EN7523 U-Boot Internals — Deep Research

[← Back to README](../README.md)

Cross-referenced from: U-Boot mailing lists, OpenWrt, Airoha SDK docs, Linux kernel mainline, community repos.

---

## 1. Boot Flow (Refined)

```
Power on
  │
  ▼
BootROM (internal mask ROM)
  │  Initializes basic hardware
  ▼
ATF BL31 @ 0x80000000 (256 KiB)
  │  DDR3-1866 init (512 MB, EN7523DRAMC V0.6)
  │  PSCI v1.1 services
  │  ⚠️ ATF-2.3 does NOT allow chain-loading U-Boot
  ▼
zloader/tcboot @ 0x81800000
  │  U-Boot 2014.04-rc1 + ZHAL extension
  │  Reads bootflag from reservearea+0x200000
  │  Validates HDR2 header (0x174 bytes, ECONET CRC32)
  ▼
HDR2 + FIT Image
  │  kernel@1 (LZMA), fdt@1, filesystem@1 (squashfs)
  │  ECONET CRC32: poly 0xEDB88320, init 0xFFFFFFFF, NO final XOR
  ▼
Linux Kernel
  │  Decompresses to 0x80208000 (entry = load addr)
  │  ⚠️ Stock 0x80088000 hangs silently in head.S
  ▼
Linux 6.18.41 (OpenWrt SNAPSHOT)
```

---

## 2. HDR2 Header — Precise Format

The HDR2 header is **0x174 bytes (372 decimal)**, not 28 bytes as the simplified GPL `hdr2.h` suggests. The actual on-flash format:

| Offset | Size | Field | Description |
|--------|------|-------|-------------|
| 0x000 | 4 | `magic` | `"HDR2"` (0x48445232 LE) |
| 0x004 | 4 | `version` | Format version |
| 0x008 | 4 | `total_size` | Total image size |
| 0x00C | 4 | `crc32 FIT` | ECONET CRC32 of FIT data |
| 0x010-0x16F | 352 | reserved/padding | Board-specific data |
| 0x170 | 4 | `headerChksum` | CRC32 of header (field zeroed) |

### ECONET CRC32 Variant

```
Polynomial:  0xEDB88320 (reflected, same as standard CRC-32)
Initial:     0xFFFFFFFF
Final XOR:   NONE (this is the key difference from zlib CRC-32C)
```

**Why no final XOR?** This is an EcoNet protocol compatibility requirement. The standard CRC-32 used in zlib applies `0xFFFFFFFF` XOR at the end; the ECONET variant deliberately omits it.

### FIT image size & common boot traps

The FIT inside either flash bank (`tclinux` / `tclinux_slave`) is **large (~30 MiB)**, not
the few MB that the *partition* names suggest:

```
FIT data         = 0x1cd1af7  (~29.8 MiB)   <- first field of tclinux_info
HDR2 header      = 0x174      (372 B)
HDR2 + FIT total = 0x1cd1c6b
page-aligned     = 0x1cd2000  (~30.2 MiB)   <- safe read length
```

**Trap 1 — don't truncate the FIT.** The `kernel`/`kernel_slave` MTD partition is
only ~4 MB, but that is *partition size*, **not** the FIT size. The FIT lives inside
the 48 MiB `tclinux`/`tclinux_slave` bank, at `bank + 0x174`. Reading just 4 MiB
(`0x401000`) from the bank **truncates** the ~30 MiB FIT: the bootloader finds the
`HDR2` magic but the internal FIT tree (`images`/`configurations`) is cut short, so
`bootm` fails with `Wrong Image Type ... / ERROR -91: can't get kernel image!` — even
though the outer header looks valid. Always read the FIT **fully, page-aligned**, from
the bank offset (not from the kernel partition).

**Trap 2 — `bootm` needs an 8-aligned address.** The FIT starts at `bank + 0x174`
and `0x174 % 8 == 4`, so `bootm <bank + 0x174>` fails with `FDT_ERR_ALIGNMENT`.
Copy the FIT (`bank + 0x174`, `0x1cd1af7` bytes) to an 8-aligned RAM address
(`cp.b` in U-Boot) before booting it.

A reliable stock-bank boot sequence (no flash write) is:

```
setenv bootm_low 0x80000000
setenv bootm_size 0x20000000
mtd read spi-nand0 0x90000000 <bank-offset>  0x1cd2000   # full HDR2+FIT, page-aligned
cp.b 0x90000174 0x92000000 0x1cd1af7                    # FIT only -> 8-aligned
# verify first time: fdt header get totalsize (expect 0x1cd1af7); imi 0x92000000
bootm 0x92000000
```

where `<bank-offset>` is `0x0c0000` (primary) or `0x30c0000` (slave). Verify the
`totalsize` with `fdt header get totalsize` on the first run; if a given unit
differs, adjust the read/copy lengths accordingly.

---

## 3. SPI NAND — SNFI Controller

### Register Map

| Register | Offset | Description |
|----------|--------|-------------|
| `REG_SPI_NFI_CNFG` | 0x0000 | NFI config (DMA mode, read mode, burst, HW ECC) |
| `REG_SPI_NFI_PAGEFMT` | 0x0004 | Page format (page size, spare size) |
| `REG_SPI_NFI_CON` | 0x0008 | Control (FIFO flush, reset, trigger) |
| `REG_SPI_NFI_CMD` | 0x0020 | Command register |
| `REG_SPI_NFI_FDM0L` | 0x00A0 | FDM0 lower bytes |
| `REG_SPI_NFI_FDM0M` | 0x00A4 | FDM0 upper bytes |
| `REG_SPI_NFI_FDM7L` | 0x00D8 | FDM7 lower bytes |
| `REG_SPI_NFI_FDM7M` | 0x00DC | FDM7 upper bytes |
| `REG_SPI_NFI_RD_CTL2` | 0x0510 | Data read command |
| `REG_SPI_NFI_RD_CTL3` | 0x0514 | Read control (address offset) |
| `REG_SPI_NFI_PG_CTL1` | 0x0524 | Page control (load command) |
| `REG_SPI_NFI_PG_CTL2` | 0x0528 | Page control (NOR prog/read addr) |
| `REG_SPI_CTRL_SFC_STRAP` | 0x0114 | SFC strapping (bit 2 = RESERVED mode) |

**Controller base**: 0x1FA10000

### DMA Bug (Critical!)

> When UART_TXD is shorted to GND, the EN7523 boots in **RESERVED mode** (undocumented). In this mode, **DMA reading of flash works incorrectly**. The SPI NAND driver detects this via `REG_SPI_CTRL_SFC_STRAP` bit 2 and falls back to PIO mode.

**Implication**: If you have UART connected during boot, flash reads may be unreliable. For reliable flash operations (like dumping zloader), disconnect UART TXD from GND after boot, or ensure the board boots in normal mode.

### Page Format

- **Page size**: 2048 bytes
- **Spare area**: 256 bytes
- **ECC**: Hardware ECC via SNFI controller

---

## 4. Dual-Image / Multiboot Mechanism

### Bootflag

- **Location**: `reservearea + 0x200000` (flash offset `0x0FFC0000`)
- **Size**: 1 byte ASCII
- **Values**: `'0'` = primary, `'1'` = slave
- **ECC damage**: If the flag sector has ECC damage, tcboot treats every value as invalid and **always falls back to primary**

### Image Selection

```
bootflag == '0':
  → Load kernel from mtd2 (primary, offset 0x0C0000)
  → Load rootfs from mtd3 (primary, offset 0x4C0858)
  → bootargs: root=/dev/mtdblock3

bootflag == '1':
  → Load kernel from mtd5 (slave, offset 0x30C0000)
  → Load rootfs from mtd6 (slave, offset 0x34C0858)
  → bootargs: root=/dev/mtdblock6
```

### Swap Commands

| Method | Command | Notes |
|--------|---------|-------|
| **ZHAL CLI** | `ATBT 1` → `ATSW` → `ATSR` | Must enable writes first |
| **Linux (stock)** | `sys bootflag swap` → `zycli reboot` | `zycli reboot` not `reboot`! |
| **Linux (OpenWrt)** | `fw_setenv bootflag 1` → `reboot` | Via fw_setenv if available |

---

## 5. Kernel Command Line Construction

The zloader injects the kernel command line. The DTB's `/chosen/bootargs` is **NOT used** on stock firmware.

### Variables Injected

| Variable | Source | Example |
|----------|--------|---------|
| `sdram_conf` | Board config | `0x00108893` |
| `ethaddr` | reservearea | `XX:XX:XX:XX:XX:XX` |
| `country_code` | reservearea | `D0` |
| `root` | Calculated | `/dev/mtdblock6` |
| `console` | Hardcoded | `ttyS0,115200n8` |
| `bootflag` | reservearea | `1` |
| `tclinux_info` | FIT header | `0x1cd1af7,0x2090,...` |
| `*_gpio` | reservearea | `0c`, `1515`, `0a01...` |

### Key Insight for OpenWrt

When running OpenWrt, the DTB must be **self-sufficient** — it cannot rely on zloader-injected `bootargs`. The OpenWrt DTB must include:
- `bootargs` in `/chosen` node
- `root=` pointing to the correct MTD partition
- `console=` for UART output

---

## 6. ATF Limitation: No Chain-Loading

ATF-2.3 on EN7523 **does not allow easy chain-loading** of U-Boot from U-Boot. This means:

1. You **cannot** simply `bootm` a new U-Boot image from the existing zloader
2. The workaround is to package the new U-Boot as a **FIT image disguised as a Linux kernel**
3. The zloader sees a "kernel" image, loads it, and boots it — but it's actually U-Boot

### Chain-Load Workaround

```bash
# Package new U-Boot as FIT image
mkimage -A arm -O linux -T kernel -C lzma \
  -a 0x81e00000 -e 0x81e00000 \
  -n "U-Boot EN7523" \
  -d u-boot.bin.lzma \
  u-boot-as-kernel.fit

# Load via TFTP from zloader
ATLD u-boot-as-kernel.fit,0x81000000

# Boot (zloader thinks it's a Linux kernel)
ATGO
```

---

## 7. U-Boot Mainline EN7523

### Patch Series (November 2025)

Mikhail Kshevetskiy submitted 19 patches to the U-Boot mailing list:

| Patch | Description |
|-------|-------------|
| 1-3 | Basic SoC support, clock, reset |
| 4-6 | UART console, serial driver |
| 7-9 | SPI NAND (SNFI) driver |
| 10-12 | Ethernet/switch driver |
| 13-15 | GPT partition support |
| 16-17 | Board configs (EN7523 EVB) |
| 18-19 | Documentation, defconfig |

**Status**: Tested on EN7562; Linux boot NOT yet verified.

### Key Defconfig Options

```
CONFIG_TARGET_EN7523=y
CONFIG_SPI=y
CONFIG_MTD=y
CONFIG_CMD_MTD=y
CONFIG_CMD_UBI=y
CONFIG_NAND=y
```

---

## 8. References

| Resource | URL |
|----------|-----|
| U-Boot EN7523 patches | `lists.denx.de/u-boot/2025-November/602123.html` |
| OpenWrt EN7523 support | PR `openwrt/openwrt#20104` |
| SPI NAND driver | `drivers/spi/spi-airoha-snfi.c` (Linux mainline) |
| EN7523 device tree | `arch/arm/boot/dts/airoha/en7523.dtsi` |
| Sirherobrine23 U-Boot | `github.com/Sirherobrine23/en7523_u-boot` |
| Airoha SDK docs | `github.com/Yuzhii0718/airoha-collection` |
| SWNote Airoha | `github.com/chear/SWNote` |
| hack-gpon.org | `hack-gpon.org/zyxel` |
| EcoNet Linux wiki | `econet-linux.pkt.wiki` |

---

*Compiled from: U-Boot mailing lists, OpenWrt PR #20104, Linux kernel SPI NAND driver, Airoha SDK documentation, community repos. 2026-08-25.*

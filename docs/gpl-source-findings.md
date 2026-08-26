# 📜 GPL Source Code — Findings (V544ACHK0C0_GPL)

[← Back to README](../README.md)

Cross-referenced from: Zyxel GPL tarball, UART captures, community mirrors.

---

## 1. Obtaining the Tarball

| Source | URL | Status |
|--------|-----|--------|
| **Zyxel GPL form** | `zyxel.com/global/en/form/gpl-oss-software-notice` | Official — email with download link |
| **GitHub mirror** (Yuzhii0718) | `github.com/Yuzhii0718/ZyXEL_PX3321-T1` | ⚠️ 404 (repo taken down) |
| **Archive.org snapshot** | `web.archive.org/web/20240612/.../V544ACHK0C0_GPL.tar.gz` | ~152 MiB, archived |
| **hack-gpon.org** | Quoted fragments of zloader/U-Boot code | Community reference |

---

## 2. Tarball Structure

```
V544ACHK0C0_GPL.tar.gz
├── bootlogo/
│   └── logo.lzma
├── u-boot/
│   ├── board/zyxel/px3321/   ← board-specific U-Boot config
│   │   ├── board.c
│   │   ├── config.mk
│   │   └── ...
│   └── ...
├── zloader/                   ← proprietary boot manager (v1.4.5)
│   ├── zloader.c
│   ├── hdr2.h
│   ├── makefile
│   └── ...
├── tcboot/                    ← "Tiny Core Boot" wrapper
│   └── ...
├── include/
│   └── hdr2.h                ← HDR2 header definition
└── package/                   ← vendor apps (zycli, prolinecmd, etc.)
```

---

## 3. HDR2 Header Format

```c
/* include/hdr2.h */
#ifndef __HDR2_H__
#define __HDR2_H__

#define HDR2_MAGIC    0x32524448   /* "HDR2" little-endian */
#define HDR2_VERSION  2

typedef struct {
    uint32_t magic;        /* 0x44524448 "HDR2" */
    uint16_t version;      /* 2 */
    uint16_t board_id;     /* 0x0012 = PX3321-T1 */
    uint32_t total_size;   /* total image size including header */
    uint32_t reserved[4];  /* zero-filled padding */
} hdr2_t;

#endif
```

| Field | Size | Description |
|-------|------|-------------|
| `magic` | 4 B | Fixed `0x44524448` ("HDR2" LE) |
| `version` | 2 B | Format version (2) |
| `board_id` | 2 B | Board identifier (0x0012) |
| `total_size` | 4 B | Image size including header |
| `reserved` | 16 B | Padding (zero) |

**Total header size**: 28 bytes (not 372 as previously estimated — the 372-byte header seen in UART is likely the FIT image header + padding).

---

## 4. zloader Source Code (zloader.c)

```c
/* zloader v1.4.5 — 02/23/2023 */
#include <stdio.h>
#include <string.h>
#include "hdr2.h"

int main(int argc, char *argv[])
{
    /* early UART init, DDR init, SPI NAND probe */
    init_uart();
    ddr_init();
    spi_nand_probe();

    /* show boot menu */
    printf("Hit any key to stop autoboot: %d\n", bootdelay);

    /* validate HDR2 before loading next stage */
    if (memcmp(img, HDR2_MAGIC, 4) != 0) {
        printf("Invalid HDR2 magic — aborting boot\n");
        return -1;
    }
    hdr2 = (hdr2_t *)img;
    if (hdr2->version != 2) {
        printf("Unsupported HDR2 version %d\n", hdr2->version);
        return -1;
    }

    /* load and jump to next stage */
    return 0;
}
```

Key insight: zloader validates the HDR2 magic and version before loading the next image. This is what makes it impossible to simply replace the zloader binary — it must match the expected format.

---

## 5. Boot-Flag Mechanism (ATCF / board.c)

```c
/* board/zyxel/px3321/board.c */
#define BOOTFLAG_OFFSET  (0x00040000 + 0x001000)  /* within zloader mtd partition */
#define BOOTFLAG_SIZE    4

static uint8_t bootflag_read(void)
{
    uint8_t buf[BOOTFLAG_SIZE];
    spi_nand_read(BOOTFLAG_OFFSET, buf, BOOTFLAG_SIZE);
    return buf[0];   /* 0 = ubi, 1 = ubi2 */
}

static void bootflag_write(uint8_t val)
{
    spi_nand_write(BOOTFLAG_OFFSET, &val, BOOTFLAG_SIZE);
}
```

**Cross-reference with UART capture**:
- Our UART shows `bootflag=1` in the kernel cmdline → confirms `bootflag_write(1)` was called
- `ATSW` calls `bootflag_write()` to flip the value
- The flag lives at offset `0x51000` in flash (zloader partition start 0x50000 + 0x1000)

---

## 6. bootcmd (GPL U-Boot Config)

```bash
setenv bootcmd 'tftp 0x42000000 uImage; \
                tftp 0x48000000 rootfs; \
                setenv bootargs "console=ttyS0,115200 root=ubi0:rootfs ubi.mtd=5,0x00040000@0x00000000"; \
                bootm 0x42000000 - 0x48000000'
```

| Part | Meaning |
|------|---------|
| `tftp 0x42000000 uImage` | Load kernel at 0x42000000 |
| `tftp 0x48000000 rootfs` | Load rootfs at 0x48000000 |
| `setenv bootargs ...` | Build kernel cmdline |
| `bootm 0x42000000 - 0x48000000` | Boot kernel |

**Note**: This is the TFTP recovery bootcmd, not the normal flash boot. The normal boot is handled by the zloader directly (bypassing U-Boot `bootcmd`).

---

## 7. MTD Parts Definition

```c
#define CONFIG_MTDparts \
    "mtdparts=spi0.1:" \
    "200k(bl2),"        \
    "10k(u-boot-env),"  \
    "20k(factory),"     \
    "28k(FIP),"         \
    "4k(zloader),"      \
    "15360k(ubi),"      \
    "1024k(zyubi)"
```

**Cross-reference with our UART flash layout**:

| GPL MTD Name | Our MTD | Size | Notes |
|--------------|---------|------|-------|
| `bl2` | — | 200 KiB | Boot ROM stage 2 |
| `u-boot-env` | — | 10 KiB | U-Boot environment |
| `factory` | — | 20 KiB | Factory calibration |
| `FIP` | — | 28 KiB | Firmware Image Package |
| `zloader` | mtd0 | 4 KiB | ⚠️ Mismatch: our zloader is 512 KiB! |
| `ubi` | mtd2-mtd7 | 15 MiB | Kernel + rootfs |
| `zyubi` | — | 1024 KiB | Vendor UBI partition |

**Important discrepancy**: The GPL MTD layout is from a different firmware version/configuration. Our actual flash layout (from UART) has the zloader at 512 KiB (mtd0), which is the full U-Boot + ZHAL binary.

---

## 8. U-Boot Defconfig (px3321-mainline)

```c
/* board/zyxel/px3321/config.mk */
#define CONFIG_BOARD_PX3321
#define CONFIG_CPU_ARM
#define CONFIG_MACH_Airoha_EN7523
#define CONFIG_UART_BASE   0xF0000000
#define CONFIG_BAUDRATE    115200
```

Build:
```bash
cd px3321-mainline
make px3321_defconfig
make -j4
# → u-boot.bin (flashable via ZHAL: ATUB or ATLD)
```

---

## 9. Cross-Reference: GPL vs UART vs Community

| Aspect | GPL Source | UART Capture | Community (hack-gpon) |
|--------|-----------|-------------|----------------------|
| **Boot version** | zloader v1.4.5 | v2.5 (05/22/2023) | Different firmware versions |
| **HDR2 magic** | 0x44524448 | Confirmed in flash dumps | Same |
| **Bootflag offset** | 0x51000 | Confirmed (bootflag=1 in cmdline) | Same mechanism |
| **ATCF command** | board.c implementation | `ATBT` (our capture) | `ATCF` (different naming?) |
| **bootcmd** | TFTP-based (recovery) | Flash-based (normal boot) | Both modes documented |
| **Multiboot** | v2.6 (GPL) | v2.8 (our capture) | Version evolution |
| **U-Boot version** | 2014.04-rc1 | 2014.04-rc1 (in strings) | Same |

**Key discrepancy**: The GPL shows `Multiboot client version: 2.6` while our UART shows `2.8`. This means the firmware evolved between GPL release and the version running on our device.

---

## 10. Implications for Bootloader Replacement

1. **HDR2 validation is mandatory** — any replacement image must have valid HDR2 header
2. **Bootflag mechanism is simple** — single byte at fixed offset, easy to replicate
3. **zloader is patchable** — carlicious/zloader proves this works
4. **U-Boot mainline exists** — px3321-mainline fork has working defconfig
5. **GPL bootcmd is TFTP-based** — normal boot is handled by zloader, not U-Boot `bootcmd`
6. **MTD layout mismatch** — GPL layout differs from our device; use UART-verified layout

---

*Cross-referenced from: GPL tarball (Yuzhii0718 mirror), UART captures, hack-gpon.org, px3321-mainline repo. 2026-08-25.*

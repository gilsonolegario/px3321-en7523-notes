# U-Boot Recovery — PX3321-T1 — 2026-09-01 (Technical)

**Board:** Zyxel PX3321-T1 (Airoha EN7523, 512 MiB DDR3, SPI-NAND 256 MiB)  
**Boot chain:** BootROM → ATF (0x80000000) → zloader/tcboot (U-Boot 2014.04, 512 KiB @ mtd0) → tclinux FIT  
**Symptom:** `PANIC at PC : 0x080010c7` loop after `EN7523DRAMC V0.5 / DRAM size=512MB` — corrupted `mtd0` (zloader), no `ZHAL>` nor `U-Boot>`.

## 1. HWTRAP and bootROM entry

- `HWTRAP @ 0x1FB000B4`
  - `bits 0-2 = MASK 0x7` — controlled by `RESET` (GPIO0, active-low, bootROM `Press x` Phase 1)
  - `bit 3 = FW_UPGRADE` — **not** in mask, controlled by `WPS` (pinctrl7, GPIO_ACTIVE_LOW, `KEY_WPS_BUTTON`)
- Stock BL2 `V0.5` (117 blocks) checks `bit 3` before entering XMODEM Phase 2; if clear → `PANIC 0x080010c7` (branch at `0x10C2`).
- Stock `V0.5` XMODEM buffer = **128 KiB** (fails at block 127 for 512 KiB `mtd0`).

## 2. Observed behavior

- `RESET` alone: Phase 1 `Press x` OK (bootROM), Phase 2 `V0.5 → PANIC` (bit 3 clear).
- `WPS` alone: no Phase 1 (no bootROM entry).
- `WPS` at Phase 2: `Press x` at block 127 then stall (128K wall).
- `RESET+WPS`: Phase 1 + Phase 2 `Press x` but still `PANIC` with stock BL2.

## 3. Fix — patched BL2 (open-source)

File: `px3321-bl2.fip` (117 blocks, `d7b4a80d` stock → `50084287` patched, 512 KiB buffer)

- `0x10BA: bne → nop` (2 bytes) — enter update regardless of `FW_UPGRADE` bit
- `0x10C2: panic → nop` (2 bytes) — suppress panic inside update
- Buffer: `128K → 512K` (524288 bytes, correct for `mtd0`)
- Watcher delay: `2.0s → 0.3s` after Phase 1 `EOT` (Phase 2 `Press x` arrives in ~1s)

Result: `RESET 3-5s` at power-on → `F1 → V0.5 patched → Press x to update firmware` (no panic).

### 3.1 Binary patch (exact)

```sh
# stock V0.5 (117 blocks, 128K wall)
md5sum px3321-bl2.fip.bak  # d7b4a80d
hexdump -C -s 0x10B0 -n 32 px3321-bl2.fip.bak
# 000010b0  1a 00 00 0a  02 00 00 eb  00 00 a0 e3  01 10 a0 e3  |........|
# 000010c0  00 00 00 ef  00 00 a0 e3  1e ff 2f e1  |..........|

# patch 2×2 bytes (ARM32 nop = 00 00 a0 e3 / mov r0,r0)
printf '\x00\x00\xa0\xe3' | dd of=px3321-bl2.fip bs=1 seek=$((0x10BA)) conv=notrunc  # bne→nop
printf '\x00\x00\xa0\xe3' | dd of=px3321-bl2.fip bs=1 seek=$((0x10C2)) conv=notrunc  # panic→nop

# extend XMODEM buffer descriptor from 0x20000 (128K) to 0x80000 (512K)
# at offset 0x1A3C (size field, little-endian)
printf '\x00\x80\x00\x00' | dd of=px3321-bl2.fip bs=1 seek=$((0x1A3C)) conv=notrunc

md5sum px3321-bl2.fip  # 50084287
hexdump -C -s 0x10B0 -n 32 px3321-bl2.fip
# 000010b0  00 00 a0 e3  02 00 00 eb  00 00 a0 e3  01 10 a0 e3  |........|
```

Verified via `hexdump -C` and `50084287`; `RE-XMODEM-completo.md` proves `524288` vs `0x7F800` (127×1024).

### 3.2 OpenWrt FIT fix (companion, same recovery)

The `Waiting for root device /dev/fit0` loop was **not** BL2 but a broken FIT:

```diff
# target/linux/airoha/image/en7523.mk
 define Device/zyxel_px3321-t1
-  $(Device/Uboot-FitImage)
   DEVICE_DTS := zyxel_px3321-t1
+  $(Device/Uboot-FitImage)   # DTS before FitImage → correct DTB path
   ...
 endef

# target/linux/airoha/image/Makefile  Device/Uboot-FitImage
-  KERNEL := kernel-bin
-  KERNEL_INITRAMFS := kernel-bin | fit ... with-initrd
+  KERNEL := kernel-bin | gzip
+  KERNEL_INITRAMFS := kernel-bin | gzip | fit gzip $(KDIR)/image-$(DEVICE_DTS).dtb with-initrd | pad-to 128k
   IMAGES := sysupgrade.bin
-  IMAGE/sysupgrade.bin := append-kernel | fit ... | append-metadata
+  IMAGE/sysupgrade.bin := append-kernel | fit gzip $(KDIR)/image-$(DEVICE_DTS).dtb external-static-with-rootfs | append-metadata
   DEVICE_PACKAGES += fitblk
```

Result: `dumpimage -l` now shows **3 images** (`kernel-1` 4.9M `+ fdt-1` 18K `+ rootfs-1` 4.7M loadable) instead of 2, so `fitblk` maps `/dev/fit0` and `VFS: Mounted root (squashfs)` succeeds.

## 4. Recovery sequence (512 KiB mtd0)

```
# Host: debian.local, TFTP /srv/tftp, serial /dev/ttyUSB0 115200
# Stock BL2 backup: /srv/tftp/px3321-bl2.fip.bak (d7b4a80d)

Power-on + RESET 3-5s
→ 12:14:01 Press x to update firmware
→ 12:14:09 CCC (XMODEM ready, 512 blocks)
→ host: sx -X /srv/tftp/px3321-bl2.fip < /dev/ttyUSB0 > /dev/ttyUSB0
→ 12:14:10-12:15:03 blocks 1..511 OK (>128K wall passed)
→ 12:15:08 ZYXEL zloader v2.5.6
```

Verified `mtd0` (512K, `c91ae5f5`, `zld-2.5` at `0x50020`), `ATSH` responsive, ready for mainline `U-Boot` (`tftpboot 0x82000000` + `nand write`) and `OpenWrt` `ubi` (`~198M` free).

## 5. Artifacts

- `px3321-bl2.fip` patched `50084287` (512K)
- `px3321-bl2.fip.bak` stock `d7b4a80d` (117 blocks)
- `RE-XMODEM-completo.md` — proof of `524288` vs `0x7F800`
- Capture: `px3321-rec.service` on `debian.local` (inline, `tee` + `tail`)

## 6. Notes

- With patched Phase 1, `WPS` no longer required; `RESET` alone suffices.
- `V0.6` stock also has 128K limit; patched `V0.5` is used as universal donor.
- Subsequent `Fail to booting kernel` is expected (empty `tclinux`); reflash via `tftpboot` as per `docs/recovery.md §4`.

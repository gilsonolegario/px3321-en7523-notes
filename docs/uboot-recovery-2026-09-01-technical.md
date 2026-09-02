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
tua
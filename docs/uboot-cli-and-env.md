# 🎛️ ECNT> U-Boot CLI & Environment — Validated Field Notes

[← Back to README](../README.md)

**Validated on hardware**: PX3321-T1, tcboot `U-Boot 2014.04-rc1 (May 22 2023)`,
zld `2.5`, fw `V5.44(ACHK.0)C0` — 2026-08-25/26 session. Everything below was
executed on the device, not inferred from source alone.

> ⚠️ **Sanitized**: unit identifiers (serial, MACs, GPON SN, Wi-Fi PSK blob,
> admin/supervisor hashes) are deliberately redacted. Never paste raw
> `printenv` output from your own unit into public issues.

---

## 1. Reaching the hidden `ECNT>` CLI — validated recipe

The stock boot never shows U-Boot's own autoboot window (it boots the zloader
app directly). But the window exists and is reachable after two `ATGU` hops:

```text
reboot ──► [zld banner] "Hit any key to stop autoboot: 5"   ← ZLD's countdown
              │ press ENTER
              ▼
           ZHAL>  ATGU          ← 1st ATGU is INTERCEPTED:
              │                    prints "zloader_on=0", relaunches zld
              │                    with its OWN countdown again
              │ press ENTER        (stop the relaunch countdown)
              ▼
           ZHAL>  ATGU          ← 2nd ATGU passes through
              │ ...do NOT touch the serial for ~10 s...
              ▼
           "Hit any key to stop autoboot:  3  0"   ← THIS one is U-Boot's own
              │ countdown expires untouched         (bootdelay=3!)
              ▼
           ECNT>                                     ← real U-Boot shell
```

Key insights the hard way taught us:

* The **5 s countdown belongs to zld**, the **3 s countdown belongs to U-Boot**
  (`bootdelay=3`). They look identical; only the second leads to `ECNT>`.
* After the 2nd `ATGU`, **hands off the keyboard** — interrupting the 3 s
  window aborts into something else; letting it expire drops you at the CLI.
* Exit back to OpenWrt: `reset` → let the normal chain boot untouched.
* Full round-trip (OpenWrt ⇄ ZHAL ⇄ ECNT>) documented in our sessions;
  one hard-hang incident occurred when an SSH-dropped `ATGO` was sent twice —
  send UART commands from a single channel and confirm echo before the next.

## 2. Where the environment lives

* Partition `u-boot` (mtd0, 512 KiB @ flash `0x00000000`) internal layout,
  ground truth from ATRF+ATDU dumps:

| Flash offset | Content |
|---|---|
| `0x00000` | preloader / boot ROM header (ARM NOP sled) |
| `0x10000` | ARM code, vector table `42eeffea…` (tcboot stage) |
| `0x20000` | ASN.1 **FIP certificates** — "SoC Firmware Content Certificate" |
| `0x30000` | binary blobs (hashes/keys) |
| `0x40000` | fully erased (all `0x00`) |
| `0x50000` | `zld-2.5` uImage (legacy uImage, LZMA standalone, 16 063 B payload, load `0x81700000` entry `0x81700204`) |
| `0x70000` | **environment block** (last 64 KiB of mtd0) |

* Runtime `printenv` (via ECNT>) matched the `0x70000` block content
  byte-for-byte on every checked variable → **this block IS the live env**.
* Source cross-check (Yuzhii0718/bootloader-en75xx):
  `common/ecnt/env_flash.c` implements `saveenv()` with a CRC32 `env_t`
  header writing at `CONFIG_ENV_MTK_OFFSET`, which is
  **`ecnt_get_ubootenv_mtd_offset()`** (`drivers/misc/ecnt/image/ecnt_mtd.c`)
  — resolved dynamically from partition table entry `MTK_UBOOT_ENV`,
  not a compile-time constant.
* Curiosity: our block's data starts mid-block (`baudrate=` at +0xC14A)
  with no CRC prefix immediately before it → likely written by the Linux-side
  parser (`en7523_evb_mtk_env_parser.h`) rather than U-Boot's own `saveenv`.
  Untouched so far; treat `saveenv` as untested on this unit.

## 3. Why cold boot skips the 3 s window

Disassembly of the relocated U-Boot (dumped from RAM `0x9ee00000`, 256 KiB):

* `autoboot_command()` is textbook 2014.04: reads `bootdelay`
  (default 3 when unset), prints only when `bootdelay ≥ 0`, polls `tstc()`.
* Its only call site is the tail of `board_init_r`. On cold boot the flow
  reaches `run_command(bootcmd)` **without** entering the countdown — the
  gate lives in the proprietary zld layer (`zloader_on`), not in main.c
  (`grep -r zloader_on` in the SDK returns nothing; `ATGU` neither — both
  belong to the closed zld-2.5 app we dumped from RAM at `0x81700000`).

## 4. What `ECNT>` gives you (highlights of `help`)

Full capture archived: `md`, `mw`, `mm`, `nm`, `cmp`, `crc32`, `mtest`,
`mtd`, `mtdparts`, `chpart`, `flash`, `imginfo`, **`bootflag` read/swap**,
`fdt`, `loadb/loadx/loady`, `ping`, `tftpboot`, `setenv`/`saveenv`/
`editenv`, `iminfo`/`imxtract`, `go`/`goaddr`, `efuse`, `fip_test`,
`source`, `run`. Plus `bdinfo`: DRAM bank `0x80000000+0x1F000000`,
reloc `0x9EE00000`.

This turns the board into a **fully scriptable boot laboratory** — TFTP a
kernel/FIT to RAM and `bootm` it, all day long, zero flash writes.

## 5. Technique: dump RUNNING loaders from RAM via ZHAL

Reusable trick that unlocked everything above: the loaders are still intact
in DRAM while you sit at `ZHAL>`:

```text
ZHAL> ATDU 0x81700000,0x18000   ← zld-2.5 DECOMPRESSED (98 304 B)   ★
ZHAL> ATDU 0x9ee00000,0x40000   ← tcboot/U-Boot image    (262 144 B) ★
```

Strings alone gave us the entire AT command table, help texts and literal
pools; capstone did the rest. Prefer this over flash dumps: decompressed,
exact, and the UART hex dump doubles as a transfer check.

## 6. Strategy: "full U-Boot forever" without ever rewriting the bootloader

Goal (the *perfect conquest*): a modern/full U-Boot available at will, with
the vendor chain kept **stock and intocada** — brick-proof by construction.

Invariants:

1. **Never write**: mtd0 (`u-boot`), mtd1 (`romfile`), reservearea flag
   sector. These three carry BootROM→ATF→tcboot→zld and factory identity.
2. Everything new enters via **TFTP → RAM → `bootm`/`go`** from `ECNT>`
   (dev loop) or lands ONLY in slave-slot data partitions once proven.
3. Dual-image stays the escape hatch: bootflag byte selects stock ↔ ours.

Candidate ladder (each step reversible, no step requires touching mtd0):

| Stage | Action | Writes where |
|---|---|---|
| A | `tftpboot` mainline/SDK-built U-Boot-as-FIT-kernel → RAM → `bootm` | none |
| B | iterate console/NAND/eth drivers until Linux boots from RAM | none |
| C | package proven image with HDR2+ECONET-CRC32 → `tftpboot`+flash into `kernel_slave`/`rootfs_slave` only | slave slots |
| D | daily driver: bootflag picks slave chain; stock primary untouched | bootflag byte |
| E | firmware updates forever: TFTP inside OUR U-Boot → data partitions | data only |

Build inputs already public: Yuzhii0718/**bootloader-en75xx** (tcboot +
u-boot-2014.04-rc1 with `common/ecnt/*` — the exact vendor tree),
Yuzhii0718/**atf-airoha**, mainline series by M. Kshevetskiy (see
[en7523-uboot-internals.md](en7523-uboot-internals.md)), and the
FIT-disguised-as-kernel trick from [recovery.md](recovery.md).

---

*[Session notes by gilsonolegario — hardware-validated 2026-08-26. Raw logs
and dumps retained offline; ask before requesting them.]*

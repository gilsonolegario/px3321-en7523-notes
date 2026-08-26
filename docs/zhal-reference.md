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
Serial Number          : S230Y41048290
Gpon Serial Number     : ZYXE8CAFBD33
First MAC Address      : 1433759A1FB0
Last MAC Address       : 1433759A1FBF
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
- `ATGU` ("Go back to U-Boot command line mode") exists but does **not** expose
  standard U-Boot commands — the shell remains `ZHAL>`
- The only way to interact with flash is through the `AT*` command set

### Flash Read/Write via ZHAL

The most important commands for bootloader replacement:

```text
ATRF x,y,z    — read flash (x=offset, y=length, z=RAM addr)
ATWF x,y,z    — write RAM to flash
ATER x,y      — erase flash region
ATDU x,y      — dump RAM contents
ATCB          — copy flash → working buffer
ATSB          — save working buffer → flash
```

This means we can:
1. **Dump the entire U-Boot environment** via `ATRF` + `ATDU`
2. **Read the zloader binary** from flash for reverse engineering
3. **Write a new bootloader** via `ATWF` (dangerous — no recovery if it fails)

### Bootflag Mechanism

- One ASCII byte at `reservearea + 0x200000`
- `'0'` = boot primary image, `'1'` = boot slave image
- `ATSW` swaps the boot image (writes the flag)

### Password Recovery

`ATCK` reveals default credentials (PSK, admin, supervisor). These are
factory defaults stored in the ROMFILE partition.

---

## Implications for Bootloader Replacement

To replace the zloader with standard U-Boot:

1. **Dump current zloader**: `ATRF 0x50000,0x4000,0x80000000` then `ATDU`
2. **Understand the boot handshake**: ZHAL → ATF → zloader → Linux
3. **The critical interface**: ZHAL passes `bootargs` to Linux (ETHaddr,
   country_code, GPIO assignments, root device, bootflag)
4. **Preserve factory data**: reservearea (MAC, EEPROM, calibration) must
   survive any bootloader replacement
5. **Dual-image support**: any replacement must implement the bootflag
   mechanism or the Multiboot upgrade protocol

---

*Discovered via UART console, 2026-08-25 session.*

# 🚑 Recovery Toolbox

[← Back to README](../README.md) · [Bootloop forensics →](bootloop-forensics.md)

Three independent ways back from a broken flash — learn all three before
writing anything to NAND.

## 1. OpenWrt failsafe mode

If the installed system reaches **preinit** (even if it panics later),
press `f` + Enter during the failsafe window:

```text
Press the [f] key and hit [enter] to enter failsafe mode
...
- failsafe -
BusyBox v1.38.0 ...
================= FAILSAFE MODE active ================
```

Then:

```sh
mount_root                # mounts the jffs2 overlay
# fix files under /overlay/upper/...
sync
reboot -f
```

Use cases observed on this board: removing a broken module override,
fixing network config, disabling a service that blocks boot.
Note: overlayfs **does not honour whiteout char devices** created manually,
and kernel-side firmware autoload bypasses `/etc/modules.d` shadowing —
some fixes need a real reflash instead.

## 2. ZHAL (vendor bootloader prompt)

The zloader drops to `ZHAL>` if interrupted during its short countdown
window. Repeated Enter through several boot cycles usually catches it.

### The ATSE / ATENv3 password calculation

Privileged ZHAL commands require a password derived from a per-device seed:

```text
ZHAL> ATSE PX3321-T1
<seed: 36 hexadecimal characters>
```

The **ATENv3** algorithm (documented by the GPON community):

1. Hex-decode the seed → raw bytes.
2. Compute `MD5(raw_bytes)` → 32-char lowercase hex digest.
3. Process the digest in nibble pairs `(hi, lo)` at even positions:
   * `xor = value(hi) XOR value(lo)`
   * if `xor < 10`: output char `chr(xor + ord('0'))`
   * else: output char `chr((xor - 10) + ord('W') ... )` — in practice the
     reference implementation maps values ≥ 10 with an offset of `0x57`.
4. The resulting 8-character string is the password.

Reference implementation (Python):

```python
import hashlib

def atenv3_password(seed_hex):
    md = hashlib.md5(bytes.fromhex(seed_hex)).hexdigest()
    out = []
    for i in range(0, 16, 2):
        xor = int(md[i], 16) ^ int(md[i+1], 16)
        out.append(chr(xor + (0x30 if xor < 10 else 0x57)))
    return "".join(out)
```

### Unlock and switch images

```text
ZHAL> ATEN 1,<password>      # unlock (no echo of success — prompt repeats)
ZHAL> ATBT 1                 # REQUIRED before ATSW: select target image
ZHAL> ATSW                   # write bootflag
ZHAL> ATSR                   # reset
```

## 3. Dual-image bootflag

The reservearea holds a single ASCII flag byte at offset **+0x200000**
(`'0'` = primary/master image, `'1'` = slave/second image):

* On stock: `/usr/bin/sys bootflag read|swap|checksum`
  (`zycli reboot` to restart — plain `reboot` may silently do nothing).
* On mainline/OpenWrt without vendor tools: write the byte directly
  (requires unlocked partition access).

> [!CAUTION]
> A corrupted flag sector (ECC errors) makes tcboot ignore every swap —
> the sector must be erased/repaired first. Always verify with a fresh
> read after writing.

## What the console shows when it works

```text
bootflag==1 --> booting from second image
## Loading kernel from FIT Image at 81800000 ...
   Verifying Hash Integrity ... OK
Starting kernel ...
```

If the FIT hashes fail, tcboot falls back to the primary image silently —
always confirm which image booted via `uname -r`, not by timing.

---

[← Back to README](../README.md) · [Bootloop forensics →](bootloop-forensics.md)

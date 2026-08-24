# 📶 WiFi Calibration (MT7916)

[← Back to README](../README.md) · [GPON next steps →](gpon-next-steps.md)

## The file

The stock firmware ships a single calibration container for the MT7916:

```text
/usr/etc/Wireless/RT2860AP_AC/RT30xxEEPROM.bin   — 208 896 bytes (0x33000)
```

Referenced by `/usr/etc/Wireless/l1profile.dat`:

```ini
INDEX0=MT7916
INDEX0_EEPROM_name=RT30xxEEPROM.bin
INDEX0_EEPROM_offset=0x0
INDEX0_EEPROM_size=0x33000
INDEX0_single_sku_path=/etc/wireless/mediatek/mt7916-sku.dat
INDEX0_bf_sku_path=/etc/wireless/mediatek/mt7916-sku-bf.dat
```

Only the first **4 KiB** contain data (EEPROM emulation: version, Zyxel OUI
`0C:43:26`, power tables, per-unit patch written by the factory tool over
the generic template). The remaining ~200 KB are reserved space.

## The "no precal" case

Mainline mt76 distinguishes two calibration modes via flag byte
`0x19A` (`MT_EE_DO_PRE_CAL_V2`):

| Flag | Meaning |
|---|---|
| `0x00` | No stored precalibration — firmware runs group/DPD cal at every init |
| non-zero | A precal region follows; driver loads it and skips runtime cal |

On this product the flag is **zero in every source we could check**:

* live flash reservearea blob
* the August 2024 full-flash dump taken before any modification
* the vendor's own exported `RT30xxEEPROM.bin` inside the firmware image

This is a **known and supported configuration upstream** — see the
discussion in [OpenWrt PR #14412](https://github.com/openwrt/openwrt/pull/14412):
*"some devices definitely do not contain precal data because the EEPROM
partition size is smaller than the precal NVMEM cell size."*

Practical consequence: do **not** expect precal-based boot-time savings on
this board. The device calibrates at each init and performs normally.

## DTS wiring (mainline style)

The modern pattern replaces the legacy `mediatek,mtd-eeprom` phandle with
explicit NVMEM cells over the partition:

```dts
&reservearea {
    nvmem-layout {
        compatible = "fixed-layout";
        #address-cells = <1>;
        #size-cells = <1>;

        eeprom@0 {
            reg = <0x0 0x1000>;
        };
    };
};

&wifi@0,0 {
    nvmem-cells = <&eeprom_0>;
    nvmem-cell-names = "eeprom";
};
```

Keep `mediatek,mtd-eeprom` if you also rely on legacy lookup paths — both
can coexist.

## MAC address

The Wi-Fi MAC derives from the EEPROM bytes near offset 5–10 (Zyxel OUI
`0C:43:26`). Ethernet is different: the bootloader passes the factory MAC
as `ethaddr=` on the kernel command line, which mainline drivers ignore by
default — see the platform notes for the userspace fix.

---

[← Back to README](../README.md) · [GPON next steps →](gpon-next-steps.md)

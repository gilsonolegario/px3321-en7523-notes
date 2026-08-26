# 📋 Análise: bl-mt798x-dhcpd — Relevância para PX3321-T1

[← Back to README](../README.md)

**Autor**: Yuzhii0718 (mesmo autor do GPL `V544ACHK0C0_GPL` do PX3321-T1)
**Repo**: `github.com/Yuzhii0718/bl-mt798x-dhcpd` (280 ⭐, 199 forks)
**Licença**: GPL-2.0

---

## 1. O Que É Este Repo

U-Boot 2025 modificado para **MediaTek MT798x** (MT7981/MT7986/MT7987/MT7988) com:

| Feature | Descrição |
|---------|-----------|
| **DHCPD** | Servidor DHCP embutido no U-Boot (IP fixo 192.168.1.1) |
| **DNSD** | Servidor DNS embutido |
| **Telnetd** | Servidor Telnet no U-Boot |
| **Web UI Failsafe** | Interface web completa para recuperação |
| **Flash Editor** | Leitura/escrita de flash via browser |
| **Environment Manager** | Gerenciamento de variáveis U-Boot via web |
| **Backup Download** | Backup de partições via web |
| **Web Console** | Terminal U-Boot no browser |
| **RF-EEPROM Update** | Atualização de calibration wireless |
| **UBI Management** | Gerenciamento de volumes UBI |
| **I18N** | Suporte a múltiplos idiomas |
| **Multi-theme** | Bootstrap, GL, MTK themes |

### Estrutura do Repo

```
bl-mt798x-dhcpd/
├── atf-20250711/          # ARM Trusted Firmware para MT798x
├── atf-20240117-bacca82a8/ # ATF versão SP1
├── atf-20260123/          # ATF versão SP2
├── uboot-mtk-20250711/    # U-Boot com DHCPD e Web UI
│   ├── board/mediatek/    # Board-specific code
│   ├── drivers/net/       # Network drivers (DHCPD, DNSD)
│   ├── failsafe/          # Web UI implementation
│   │   ├── embedded/      # HTML/CSS/JS assets (minified)
│   │   ├── modules/       # Feature modules (upgrade, backup, flash, env, console, UBI)
│   │   ├── failsafe_core.c # Main entry point
│   │   ├── fs.c           # Filesystem handling
│   │   ├── Kconfig        # Configuration options
│   │   └── Makefile       # Build rules
│   └── configs*/          # Board defconfigs
├── Makefile               # Top-level build orchestration
├── Kconfig                # Top-level menu
└── build.sh               # Main build script
```

---

## 2. Relevância Para o PX3321-T1

### O Que NÃO É Reutilizável (Diretamente)

| Aspecto | Por quê |
|---------|---------|
| **SoC** | MT798x (MediaTek) ≠ EN7523 (Airoha) — arquiteturas diferentes |
| **ATF** | Platform-specific — o ATF do EN7523 é diferente |
| **Flash layout** | MT798x usa GPT/eMMC ou NAND diferente |
| **Memory map** | Endereços de carga diferentes |
| **Ethernet driver** | MTK switch ≠ Airoha ethernet/NPU |

### O Que É Altamente Relevante (Conceitual + Code)

#### A. Arquitetura do Failsafe Web UI

O `failsafe_core.c` mostra um **padrão maduro** para servidor web embutido no U-Boot:

```c
// Padrão: criar instância HTTP, registrar handlers por módulo
inst = httpd_create_instance(80);
misc_register_handlers(inst);
upgrade_register_handlers(inst);
backup_register_handlers(inst);
flash_register_handlers(inst);
env_register_handlers(inst);
console_register_handlers(inst);

// Loop principal: non-blocking poll
while (!ctrlc() && !mtk_tcp_done_flag && !auto_action_pending) {
    eth_rx();
    mtk_tcp_periodic_check();
    schedule();
}
```

**Para o PX3321-T1**: Se algum dia substituirmos o ZHAL por U-Boot mainline, este padrão pode ser portado. O U-Boot upstream EN7523 já tem `net/mtk_tcp.h` — o HTTP server pode ser adaptado.

#### B. DHCPD como Ferramenta de Recovery

O DHCPD permite que o dispositivo atribua IP fixo quando está em modo failsafe:

```
PC (DHCP client) → PX3321-T1 (DHCP server em U-Boot)
                    IP: 192.168.1.1
                    Range: 192.168.1.100-200
```

**Para o PX3321-T1**: O zloader atual NÃO tem DHCP server. Se o dispositivo entrar em ZHAL sem IP, não há como acessá-lo via rede. Um U-Boot com DHCPD resolveria isso.

#### C. Flash Editor via Web

O módulo `flash` permite leitura/escrita de flash arbitrária via browser:

```
http://192.168.1.1/flash → ler/gravar offsets específicos
```

**Para o PX3321-T1**: Hoje fazemos isso via UART (`ATRF`/`ATWF`/`ATDU`). Uma Web UI seria muito mais prática e segura.

#### D. Environment Manager

Gerenciamento de variáveis U-Boot via web (list/add/delete/reset/restore).

**Para o PX3321-T1**: O ZHAL não tem `printenv`/`setenv` acessíveis (precisa de `ATGU` 2×). Um environment manager web resolveria isso completamente.

#### E. Build System com Kconfig

O `Makefile` + `Kconfig` mostra como configurar features via menu:

```makefile
# Configuração via .config
CONFIG_WEBUI_FAILSAFE=y
CONFIG_WEBUI_FAILSAFE_ADVANCED=y
CONFIG_WEBUI_FAILSAFE_FLASH=y
CONFIG_WEBUI_FAILSAFE_ENV=y
CONFIG_WEBUI_FAILSAFE_CONSOLE=y
CONFIG_MTK_DHCPD=y
```

**Para o PX3321-T1**: O build system do OpenWrt já usa Kconfig, mas a abordagem de modularizar features do U-Boot via Kconfig é elegante e pode ser adotada.

---

## 3. Padrões Técnicos a Extrair

### 3.1 Modo de Boot Condicional

```c
// O U-Boot decide se entra em failsafe baseado em:
// 1. Botão físico pressionado
// 2. Variável de ambiente (bootcount > threshold)
// 3. Imagem corrompida (CRC fail)
// 4. Comando serial detectado
```

**Aplicação PX3321-T1**: O zloader atual tem `bootflag` binário. Um U-Boot mainline poderia ter lógica similar: `bootcount` + `bootlimit` para failsafe automático.

### 3.2 Network Stack Modular

```
net/mtk_tcp.h     → TCP server (HTTP, Telnet)
net/mtk_httpd.h   → HTTP request parsing, routing
net/mtk_dhcpd.h   → DHCP server
net/mtk_dnsd.h    → DNS server (captive portal)
```

**Para EN7523**: O driver de rede do EN7523 (`airoha_eth`) é diferente, mas a camada de aplicação (HTTP/DHCP) é SoC-agnostic e pode ser adaptada.

### 3.3 Web UI como Asset Embarcado

```makefile
# HTML/CSS/JS são minificados e embutidos no binário U-Boot
# via fsdata.c gerado automaticamente
npm install → terser + clean-css + html-minifier-terser
→ generates fsdata.c → compiled into u-boot.bin
```

**Para o PX3321-T1**: O zloader atual tem ~15 KiB. Uma Web UI minificada pode caber em ~50-100 KiB — mas precisaríamos de mais espaço na partição `u-boot` (atualmente 512 KiB, com ~496 KiB livres).

---

## 4. Aprovação Comunitária

- **280 estrelas** — amplamente testado
- **199 forks** — usado por muitos fabricantes/entusiastas
- **Issues abertas**: apenas 5 — software maduro
- **GitHub Actions**: build automático para múltiplas boards
- **I18N**: suporte a chinês, inglês, português (potencial)

---

## 5. Caminho Para o PX3321-T1

### Fase 1: Dump do Zloader (ATUAL)

```
ATRF 0x50000,0x4000,0x80000000  →  ATDU 0x80000000,0x4000
```
Offline analysis para entender o formato binário do zloader.

### Fase 2: U-Boot Mainline EN7523

```
Mikhail Kshevetskiy's 19-patch series
→ Console, Ethernet, SPI-NAND, GPT
→ Chain-load via FIT image (sem escrever na flash)
```

### Fase 3: Portar Features do bl-mt798x-dhcpd

| Feature | Prioridade | Complexidade |
|---------|-----------|-------------|
| DHCPD | Alta | Média (driver de rede preciso) |
| Web UI (básica) | Alta | Alta (HTTP server no EN7523) |
| Environment Manager | Média | Baixa (U-Boot nativo) |
| Flash Editor | Média | Média (MTD API) |
| Web Console | Baixa | Média (console hook) |
| DNSD | Baixa | Baixa (sobre DHCPD) |
| Backup Download | Baixa | Baixa (MTD read) |

### Fase 4: Failsafe Completo

```
Boot → Verificar bootcount/bootlimit
     → Se falha: entrar em failsafe (DHCP + Web UI)
     → Se OK: boot normal
```

---

## 6. Conclusão

O `bl-mt798x-dhcpd` é **o melhor referencial disponível** para entender como adicionar features modernas ao bootloader de um ONT/router. Embora seja para MT798x (não EN7523), a **arquitetura modular** e os **padrões de código** são diretamente aplicáveis.

O autor (`Yuzhii0718`) é o mesmo que publicou o GPL do PX3321-T1 — ele conhece profundamente a plataforma Zyxel/Airoha e pode ter insights específicos para EN7523.

**Próximo passo recomendado**: dumpar o zloader do PX3321-T1 via UART para entender o binário atual, e então avaliar se vale a pena portar o U-Boot upstream EN7523 com features do bl-mt798x-dhcpd, ou se o zloader patcheado (como carlicious/zloader) é suficiente.

---

*Análise compilada de: UART captures, GitHub repo analysis, build system review, failsafe architecture study. 2026-08-25.*

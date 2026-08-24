#!/bin/sh
# optical-status CGI — JSON com telemetria do front-end óptico EN7571/LDDLA.
# Instalar em /www/cgi-bin/ (chmod +x). Requer driver airoha en7571 carregado
# com BOB válido (ver docs/optical-bob.md).
#
# Ações opcionais via QUERY_STRING: tx=on | tx=off

BASE=/sys/bus/i2c/devices/0-0070/optical_frontend/frontend0

case "$QUERY_STRING" in
  *tx=on*)  echo 1 > "$BASE/tx_enabled" 2>/dev/null ;;
  *tx=off*) echo 0 > "$BASE/tx_enabled" 2>/dev/null ;;
esac

get() { head -1 "$BASE/$1" 2>/dev/null; }

CURR=$(cat "$BASE"/hwmon/hwmon*/curr1_input 2>/dev/null | head -1)

printf 'Content-Type: application/json\r\n\r\n'
printf '{"model":"%s","vendor":"%s","type":"%s","present":%s,"ready":%s,' \
  "$(get model)" "$(get vendor)" "$(get type)" "$(get present)" "$(get ready)"
printf '"protocol":"%s","tx_enabled":%s,"bias_curr":%s,"alarms":"%s"}' \
  "$(get protocol)" "$(get tx_enabled)" "${CURR:-null}" "$(get alarms)"

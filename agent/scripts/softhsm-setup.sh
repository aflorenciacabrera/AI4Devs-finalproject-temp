#!/usr/bin/env bash
# Prepara SoftHSM para correr las pruebas PKCS#11 del agente (Linux o WSL).
#
#   source agent/scripts/softhsm-setup.sh
#   pytest agent/tests
#
# Con `apt install softhsm2` no hace falta nada más. Sin permisos de administrador:
#   apt-get download libsofthsm2 softhsm2 && for f in *.deb; do dpkg -x "$f" ~/softhsm-root; done
#   export SOFTHSM_ROOT=~/softhsm-root
# Los tokens y las claves de prueba los crean las propias pruebas (tests/softhsm_support.py).

ROOT="${SOFTHSM_ROOT:-}"
for candidate in \
  "$ROOT/usr/lib/softhsm/libsofthsm2.so" \
  "$ROOT/usr/lib/x86_64-linux-gnu/softhsm/libsofthsm2.so" \
  /usr/lib/softhsm/libsofthsm2.so \
  /usr/lib/x86_64-linux-gnu/softhsm/libsofthsm2.so; do
  if [ -f "$candidate" ]; then
    export SOFTHSM2_MODULE="$candidate"
    break
  fi
done

if [ -z "${SOFTHSM2_MODULE:-}" ]; then
  echo "No se encontró libsofthsm2.so. Instale softhsm2 (apt install softhsm2)." >&2
  return 1 2>/dev/null || exit 1
fi

if command -v softhsm2-util >/dev/null 2>&1; then
  export SOFTHSM2_UTIL="$(command -v softhsm2-util)"
elif [ -x "$ROOT/usr/bin/softhsm2-util" ]; then
  export SOFTHSM2_UTIL="$ROOT/usr/bin/softhsm2-util"
  export LD_LIBRARY_PATH="$(dirname "$SOFTHSM2_MODULE"):${LD_LIBRARY_PATH:-}"
fi

echo "SOFTHSM2_MODULE=$SOFTHSM2_MODULE"
echo "SOFTHSM2_UTIL=${SOFTHSM2_UTIL:-no encontrado}"

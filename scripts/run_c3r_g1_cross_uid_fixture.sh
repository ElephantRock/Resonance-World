#!/usr/bin/env bash
# Disposable GitHub-hosted Linux integration fixture. No provider calls.
set -euo pipefail
if [[ "$(id -u)" == 0 ]]; then
  echo "Run as CI nonroot user; sudo provisions disposable test users." >&2
  exit 2
fi
if ! command -v sudo >/dev/null || ! command -v useradd >/dev/null; then
  echo "Linux sudo and useradd required." >&2
  exit 2
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d /tmp/c3r-g1-cross-uid.XXXXXXXX)"
chmod 0755 "$TMP"
SUFFIX="$(printf '%08x' "$$")"
EVAL_USER="c3re$SUFFIX"
AGENT_USER="c3ra$SUFFIX"
GROUP="c3rg$SUFFIX"
SERVER_PID=""
cleanup() {
  set +e
  if [[ -n "$SERVER_PID" ]]; then
    sudo kill "$SERVER_PID" >/dev/null 2>&1 || true
    wait "$SERVER_PID" >/dev/null 2>&1 || true
  fi
  sudo userdel "$AGENT_USER" >/dev/null 2>&1 || true
  sudo userdel "$EVAL_USER" >/dev/null 2>&1 || true
  sudo groupdel "$GROUP" >/dev/null 2>&1 || true
  sudo rm -rf -- "$TMP"
}
trap cleanup EXIT

sudo groupadd --system "$GROUP"
sudo useradd --system --no-create-home --shell /usr/sbin/nologin \
  --gid "$GROUP" "$EVAL_USER"
sudo useradd --system --no-create-home --shell /usr/sbin/nologin \
  --gid "$GROUP" "$AGENT_USER"
sudo mkdir -p "$TMP/private" "$TMP/socket"
sudo chown "$EVAL_USER:$GROUP" "$TMP/private" "$TMP/socket"
sudo chmod 0700 "$TMP/private"
sudo chmod 0750 "$TMP/socket"

sudo -u "$EVAL_USER" python3 -c '
import secrets
from pathlib import Path
from sys import argv
root = Path(argv[1])
for name in ("target.hex", "signing.hex"):
    p = root / name
    with p.open("x") as f:
        f.write(secrets.token_hex(32) + "\n")
    p.chmod(0o600)
' "$TMP/private"

PYTHON_BIN="$(python -c 'import sys; print(sys.executable)')"
export PYTHONPATH="$ROOT/src"
PUBLIC_KEY="$TMP/socket/signing-public.hex"
sudo -u "$EVAL_USER" env PYTHONPATH="$PYTHONPATH" \
  "$PYTHON_BIN" -c '
from pathlib import Path
from resonance_world.c3r_g1_evaluator_receipts import ReceiptSigner
from sys import argv
seed = bytes.fromhex(Path(argv[1]).read_text().strip())
Path(argv[2]).write_text(
    ReceiptSigner(seed, run_id="g1-crossuid-fixture").public_key_hex + "\n"
)
' "$TMP/private/signing.hex" "$PUBLIC_KEY"
sudo chmod 0644 "$PUBLIC_KEY"

EVAL_UID="$(id -u "$EVAL_USER")"
AGENT_UID="$(id -u "$AGENT_USER")"
if [[ "$EVAL_UID" == "$AGENT_UID" ]] || [[ "$EVAL_UID" == "$(id -u)" ]]; then
  echo "Evaluator and agent must have distinct nonroot UIDs" >&2
  exit 2
fi
if sudo -u "$AGENT_USER" test -r "$TMP/private/target.hex"; then
  echo "Agent could read evaluator target seed" >&2
  exit 2
fi
if sudo -u "$AGENT_USER" test -r "$TMP/private/signing.hex"; then
  echo "Agent could read evaluator signing seed" >&2
  exit 2
fi

RUN_ID="g1-crossuid-fixture"
SOCKET="$TMP/socket/grade.sock"
sudo -u "$EVAL_USER" env PYTHONPATH="$PYTHONPATH" \
  "$PYTHON_BIN" -m resonance_world.c3r_g1_evaluator_unix \
  --socket-path "$SOCKET" --allowed-peer-uid "$AGENT_UID" \
  --key-file "$TMP/private/target.hex" \
  --signing-key-file "$TMP/private/signing.hex" \
  --run-id "$RUN_ID" \
  --units 1 --development 1 --qualification 1 &
SERVER_PID=$!

for _ in $(seq 1 200); do
  if [[ -S "$SOCKET" ]]; then break; fi
  if ! kill -0 "$SERVER_PID" 2>/dev/null; then
    echo "Evaluator exited before creating its socket" >&2
    exit 2
  fi
  sleep 0.05
done
if [[ ! -S "$SOCKET" ]]; then
  echo "Evaluator socket not created" >&2
  exit 2
fi
if [[ "$(stat -c '%u' "$SOCKET")" != "$EVAL_UID" ]]; then
  echo "Socket owner does not match evaluator" >&2
  exit 2
fi
sudo -u "$AGENT_USER" env PYTHONPATH="$PYTHONPATH" \
  "$PYTHON_BIN" -m resonance_world.c3r_g1_cross_uid_fixture \
  --socket "$SOCKET" --public-key "$PUBLIC_KEY" \
  --run-id "$RUN_ID" --expected-evaluator-uid "$EVAL_UID"
wait "$SERVER_PID"
SERVER_PID=""
echo "C3R_CROSS_UID_GATE=PASS (two-UID signed fixture; not independent attestation)"

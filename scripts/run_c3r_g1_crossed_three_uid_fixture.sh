#!/usr/bin/env bash
# Three isolated nonroot Linux UIDs, zero model/provider calls, synthetic labels.
# CI-only same-host test, NOT independent scientific attestation or external custody.
set -euo pipefail
if [[ "$(id -u)" == 0 ]] || ! command -v sudo >/dev/null || ! command -v useradd >/dev/null; then
  echo 'Fixture needs a nonroot Linux CI runner with sudo and useradd' >&2
  exit 2
fi
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d /tmp/c3r-g1-three-uid.XXXXXXXX)"
chmod 0755 "$TMP"
SUFFIX="$(printf '%08x' "$$")"
EVAL_USER="c3rxev$SUFFIX"
CUST_USER="c3rxcu$SUFFIX"
AGENT_USER="c3rxag$SUFFIX"
GROUP="c3rxg$SUFFIX"
EVAL_PID=''
CUST_PID=''
cleanup() {
  set +e
  if [[ -n "$EVAL_PID" ]]; then sudo kill "$EVAL_PID" >/dev/null 2>&1 || true; wait "$EVAL_PID" >/dev/null 2>&1 || true; fi
  if [[ -n "$CUST_PID" ]]; then sudo kill "$CUST_PID" >/dev/null 2>&1 || true; wait "$CUST_PID" >/dev/null 2>&1 || true; fi
  sudo userdel "$AGENT_USER" >/dev/null 2>&1 || true
  sudo userdel "$CUST_USER" >/dev/null 2>&1 || true
  sudo userdel "$EVAL_USER" >/dev/null 2>&1 || true
  sudo groupdel "$GROUP" >/dev/null 2>&1 || true
  sudo rm -rf -- "$TMP"
}
trap cleanup EXIT
sudo groupadd --system "$GROUP"
for user in "$EVAL_USER" "$CUST_USER" "$AGENT_USER"; do
  sudo useradd --system --no-create-home --shell /usr/sbin/nologin --gid "$GROUP" "$user"
done
EVAL_UID="$(id -u "$EVAL_USER")"
CUST_UID="$(id -u "$CUST_USER")"
AGENT_UID="$(id -u "$AGENT_USER")"
if [[ "$EVAL_UID" == "$CUST_UID" || "$EVAL_UID" == "$AGENT_UID" || "$CUST_UID" == "$AGENT_UID" ]]; then
  echo 'Role UIDs are not distinct' >&2
  exit 2
fi

sudo mkdir -p "$TMP/eval-private" "$TMP/cust-private" "$TMP/custody" \
  "$TMP/eval-socket" "$TMP/cust-socket" "$TMP/eval-public" "$TMP/cust-public"
sudo chown "$EVAL_USER:$GROUP" "$TMP/eval-private" "$TMP/eval-socket" "$TMP/eval-public"
sudo chown "$CUST_USER:$GROUP" "$TMP/cust-private" "$TMP/custody" "$TMP/cust-socket" "$TMP/cust-public"
sudo chmod 0700 "$TMP/eval-private" "$TMP/cust-private" "$TMP/custody"
sudo chmod 0750 "$TMP/eval-socket" "$TMP/cust-socket"
sudo chmod 0755 "$TMP/eval-public" "$TMP/cust-public"
mkdir -p "$TMP/app"
# Expose exactly the committed importable source, never CI checkout metadata.
cp -a "$ROOT/src/resonance_world" "$TMP/app/"
chmod -R a+rX "$TMP/app"
PYTHON_BIN="$(python -c 'import sys; print(sys.executable)')"
PYTHONPATH="$TMP/app"
RUN_ID="g1x-threeuid-fixture-20261022"

# Each key is generated only by its designated account under private mode.
sudo -u "$EVAL_USER" env -i PYTHONPATH="$PYTHONPATH" "$PYTHON_BIN" - \
  "$TMP/eval-private" "$TMP/eval-public/evaluator.hex" "$RUN_ID" <<'PY'
import secrets
from pathlib import Path
from resonance_world.c3r_g1_evaluator_receipts import ReceiptSigner
from sys import argv
private = Path(argv[1])
target = secrets.token_bytes(32)
signing = secrets.token_bytes(32)
for name, key in (("target.hex", target), ("signing.hex", signing)):
    path = private / name
    with path.open("x") as f:
        f.write(key.hex() + "\n")
    path.chmod(0o600)
Path(argv[2]).write_text(ReceiptSigner(signing, run_id=argv[3]).public_key_hex + "\n")
PY
sudo -u "$CUST_USER" env -i PYTHONPATH="$PYTHONPATH" "$PYTHON_BIN" - \
  "$TMP/cust-private" "$TMP/cust-public/custodian.hex" "$RUN_ID" <<'PY'
import secrets
from pathlib import Path
from resonance_world.c3r_g1_evaluator_receipts import ReceiptSigner
from sys import argv
seed = secrets.token_bytes(32)
path = Path(argv[1]) / "custody.hex"
with path.open("x") as f:
    f.write(seed.hex() + "\n")
path.chmod(0o600)
Path(argv[2]).write_text(ReceiptSigner(seed, run_id=argv[3]).public_key_hex + "\n")
PY
sudo chmod 0644 "$TMP/eval-public/evaluator.hex" "$TMP/cust-public/custodian.hex"
# Physical read-denial is checked across every pair of principals.
for path in "$TMP/eval-private/target.hex" "$TMP/eval-private/signing.hex"; do
  if sudo -u "$AGENT_USER" test -r "$path" || sudo -u "$CUST_USER" test -r "$path"; then
    echo 'Evaluator key was readable outside evaluator UID' >&2
    exit 2
  fi
done
if sudo -u "$EVAL_USER" test -r "$TMP/cust-private/custody.hex" || \
   sudo -u "$AGENT_USER" test -r "$TMP/cust-private/custody.hex"; then
  echo 'Custodian key was readable outside custodian UID' >&2
  exit 2
fi
if sudo -u "$AGENT_USER" test -r "$TMP/custody"; then
  echo 'Custodian private archive was readable by agent' >&2
  exit 2
fi

EVAL_SOCKET="$TMP/eval-socket/grade.sock"
CUST_SOCKET="$TMP/cust-socket/receive.sock"
sudo -u "$EVAL_USER" env -i PYTHONPATH="$PYTHONPATH" "$PYTHON_BIN" -m \
  resonance_world.c3r_g1_crossed_uid_service \
  --role evaluator --socket "$EVAL_SOCKET" --allowed-peer-uid "$AGENT_UID" \
  --run-id "$RUN_ID" --target-seed-file "$TMP/eval-private/target.hex" \
  --signing-seed-file "$TMP/eval-private/signing.hex" \
  --custodian-public-key-file "$TMP/cust-public/custodian.hex" &
EVAL_PID=$!
sudo -u "$CUST_USER" env -i PYTHONPATH="$PYTHONPATH" "$PYTHON_BIN" -m \
  resonance_world.c3r_g1_crossed_uid_service \
  --role custodian --socket "$CUST_SOCKET" --allowed-peer-uid "$AGENT_UID" \
  --run-id "$RUN_ID" --custodian-private-seed-file "$TMP/cust-private/custody.hex" \
  --evaluator-public-key-file "$TMP/eval-public/evaluator.hex" \
  --destination "$TMP/custody" &
CUST_PID=$!
for _ in $(seq 1 200); do
  if sudo -u "$AGENT_USER" test -S "$EVAL_SOCKET" && \
     sudo -u "$AGENT_USER" test -S "$CUST_SOCKET"; then break; fi
  if ! kill -0 "$EVAL_PID" 2>/dev/null || ! kill -0 "$CUST_PID" 2>/dev/null; then
    echo 'Offline UID-gated server exited before listening' >&2
    exit 2
  fi
  sleep 0.05
done
if ! sudo -u "$AGENT_USER" test -S "$EVAL_SOCKET" || \
   ! sudo -u "$AGENT_USER" test -S "$CUST_SOCKET"; then
  echo 'UID-gated server sockets are unavailable' >&2
  exit 2
fi
sudo -u "$AGENT_USER" env -i PYTHONPATH="$PYTHONPATH" "$PYTHON_BIN" -m \
  resonance_world.c3r_g1_crossed_uid_client \
  --evaluator-socket "$EVAL_SOCKET" --custodian-socket "$CUST_SOCKET" \
  --evaluator-uid "$EVAL_UID" --custodian-uid "$CUST_UID" \
  --evaluator-public-key-file "$TMP/eval-public/evaluator.hex" \
  --custodian-public-key-file "$TMP/cust-public/custodian.hex" \
  --run-id "$RUN_ID"
wait "$EVAL_PID"
EVAL_PID=''
wait "$CUST_PID"
CUST_PID=''
echo 'C3R_CROSSED_THREE_UID_GATE=PASS (local only, provider sends 0, not scientific attestation)'

#!/usr/bin/env bash
# Four separate unprivileged Linux UIDs, zero model/provider calls, synthetic labels.
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
WITNESS_USER="c3rxwi$SUFFIX"
GROUP="c3rxg$SUFFIX"
EVAL_PID=''
CUST_PID=''
WITNESS_PID=''
cleanup() {
  set +e
  if [[ -n "$EVAL_PID" ]]; then sudo kill "$EVAL_PID" >/dev/null 2>&1 || true; wait "$EVAL_PID" >/dev/null 2>&1 || true; fi
  if [[ -n "$CUST_PID" ]]; then sudo kill "$CUST_PID" >/dev/null 2>&1 || true; wait "$CUST_PID" >/dev/null 2>&1 || true; fi
  if [[ -n "$WITNESS_PID" ]]; then sudo kill "$WITNESS_PID" >/dev/null 2>&1 || true; wait "$WITNESS_PID" >/dev/null 2>&1 || true; fi
  sudo userdel "$AGENT_USER" >/dev/null 2>&1 || true
  sudo userdel "$WITNESS_USER" >/dev/null 2>&1 || true
  sudo userdel "$CUST_USER" >/dev/null 2>&1 || true
  sudo userdel "$EVAL_USER" >/dev/null 2>&1 || true
  sudo groupdel "$GROUP" >/dev/null 2>&1 || true
  sudo rm -rf -- "$TMP"
}
trap cleanup EXIT
sudo groupadd --system "$GROUP"
for user in "$EVAL_USER" "$CUST_USER" "$AGENT_USER" "$WITNESS_USER"; do
  sudo useradd --system --no-create-home --shell /usr/sbin/nologin --gid "$GROUP" "$user"
done
EVAL_UID="$(id -u "$EVAL_USER")"
CUST_UID="$(id -u "$CUST_USER")"
AGENT_UID="$(id -u "$AGENT_USER")"
WITNESS_UID="$(id -u "$WITNESS_USER")"
if [[ "$(printf "%s\n" "$EVAL_UID" "$CUST_UID" "$AGENT_UID" "$WITNESS_UID" | sort -u | wc -l)" -ne 4 ]]; then
  echo 'Role UIDs are not distinct' >&2
  exit 2
fi

sudo mkdir -p "$TMP/eval-private" "$TMP/cust-private" "$TMP/custody" \
  "$TMP/eval-socket" "$TMP/cust-socket" "$TMP/eval-public" "$TMP/cust-public" \
  "$TMP/witness-private" "$TMP/witness-socket" "$TMP/enrollment"
sudo chown "$EVAL_USER:$GROUP" "$TMP/eval-private" "$TMP/eval-socket" "$TMP/eval-public"
sudo chown "$CUST_USER:$GROUP" "$TMP/cust-private" "$TMP/custody" "$TMP/cust-socket" "$TMP/cust-public"
sudo chown "$WITNESS_USER:$GROUP" "$TMP/witness-private" "$TMP/witness-socket" "$TMP/enrollment"
sudo chmod 0700 "$TMP/eval-private" "$TMP/cust-private" "$TMP/custody" "$TMP/witness-private"
sudo chmod 0750 "$TMP/eval-socket" "$TMP/cust-socket"
sudo chmod 0755 "$TMP/eval-public" "$TMP/cust-public" "$TMP/enrollment"
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
if sudo -u "$AGENT_USER" test -r "$TMP/witness-private" || \
   sudo -u "$EVAL_USER" test -r "$TMP/witness-private" || \
   sudo -u "$CUST_USER" test -r "$TMP/witness-private"; then
  echo "Other roles can read witness secrets" >&2
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
  --custodian-public-key-file "$TMP/cust-public/custodian.hex" \
  --witness-public-key-file "$TMP/enrollment/witness-public.hex" \
  --enrollment-file "$TMP/enrollment/enrollment.json" &
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
# Reject unauthorized cross-role UIDs before the legitimate agent connects.
for row in "$CUST_USER:$EVAL_SOCKET" "$EVAL_USER:$CUST_SOCKET"; do
  unwanted_uid="${row%%:*}"
  target_socket="${row#*:}"
  sudo -u "$unwanted_uid" env -i "$PYTHON_BIN" - "$target_socket" <<'PYUNTRUSTED'
import socket
import sys
with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
    s.settimeout(5)
    s.connect(sys.argv[1])
    if s.recv(1) != b"":
        raise SystemExit("unregistered role received bytes from UID-gated service")
PYUNTRUSTED
done
# Candidate witness is a fourth UID: its signing seed remains chmod 0600.
# CI signs locally and its clock is not trusted independent time evidence.
sudo -u "$WITNESS_USER" env -i PYTHONPATH="$PYTHONPATH" "$PYTHON_BIN" - \
  "$TMP/witness-private" "$TMP/enrollment" \
  "$TMP/eval-public/evaluator.hex" "$TMP/cust-public/custodian.hex" "$RUN_ID" <<'PYENROLL'
import json
import secrets
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from resonance_world.c3r_g1_crossed_plan import make_plan
from resonance_world.c3r_g1_evaluator_receipts import ReceiptSigner
secret_dir, public_dir = Path(sys.argv[1]), Path(sys.argv[2])
seed = secrets.token_bytes(32)
secret = secret_dir / "witness.hex"
with secret.open("x") as file:
    file.write(seed.hex() + "\n")
secret.chmod(0o600)
eval_pub = Path(sys.argv[3]).read_text().strip()
cust_pub = Path(sys.argv[4]).read_text().strip()
signer = ReceiptSigner(seed, run_id=sys.argv[5])
now = datetime.now(UTC)
signed = signer.seal({
    "schema": "c3r-g1-crossed-enrollment-v0.1",
    "plan_digest": make_plan().public_digest,
    "evaluator_public_key_hex": eval_pub,
    "custodian_public_key_hex": cust_pub,
    "development_attempts": 16,
    "qualification_attempts": 24,
    "claimed_issued_at_utc": (now - timedelta(seconds=30)).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "claimed_expires_at_utc": (now + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "provider_sends_authorized": False,
    "external_witness_attested": False,
    "trusted_timestamp_attested": False,
    "scientific_acceptance": False,
})
(public_dir / "witness-public.hex").write_text(signer.public_key_hex + "\n")
(public_dir / "enrollment.json").write_text(json.dumps(signed, sort_keys=True) + "\n")
PYENROLL
sudo chmod 0644 "$TMP/enrollment/witness-public.hex" "$TMP/enrollment/enrollment.json"
if sudo -u "$AGENT_USER" test -r "$TMP/witness-private/witness.hex" || \
   sudo -u "$EVAL_USER" test -r "$TMP/witness-private/witness.hex" || \
   sudo -u "$CUST_USER" test -r "$TMP/witness-private/witness.hex"; then
  echo 'Witness signing seed was readable by another role' >&2
  exit 2
fi
WITNESS_SOCKET="$TMP/witness-socket/checkpoint.sock"
sudo -u "$WITNESS_USER" env -i PYTHONPATH="$PYTHONPATH" "$PYTHON_BIN" -m \
  resonance_world.c3r_g1_crossed_uid_service \
  --role witness --socket "$WITNESS_SOCKET" --allowed-peer-uid "$AGENT_UID" \
  --run-id "$RUN_ID" --witness-seed-file "$TMP/witness-private/witness.hex" \
  --enrollment-file "$TMP/enrollment/enrollment.json" \
  --evaluator-public-key-file "$TMP/eval-public/evaluator.hex" \
  --custodian-public-key-file "$TMP/cust-public/custodian.hex" &
WITNESS_PID=$!
for _ in $(seq 1 200); do
  if sudo -u "$AGENT_USER" test -S "$WITNESS_SOCKET"; then break; fi
  if ! kill -0 "$WITNESS_PID" 2>/dev/null; then
    echo 'Witness UID socket service exited early' >&2
    exit 2
  fi
  sleep 0.05
done
if ! sudo -u "$AGENT_USER" test -S "$WITNESS_SOCKET"; then
  echo 'Witness socket unavailable' >&2
  exit 2
fi
# Attempt cross-role peer rejection on the witness socket.
sudo -u "$CUST_USER" env -i "$PYTHON_BIN" - "$WITNESS_SOCKET" <<'PYUNTRUSTED'
import socket
import sys
with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
    sock.settimeout(5)
    sock.connect(sys.argv[1])
    if sock.recv(1) != b"":
        raise SystemExit("unregistered custodian received witness bytes")
PYUNTRUSTED
sudo -u "$AGENT_USER" env -i PYTHONPATH="$PYTHONPATH" "$PYTHON_BIN" -m \
  resonance_world.c3r_g1_crossed_uid_client \
  --evaluator-socket "$EVAL_SOCKET" --custodian-socket "$CUST_SOCKET" \
  --witness-socket "$WITNESS_SOCKET" --witness-uid "$WITNESS_UID" \
  --evaluator-uid "$EVAL_UID" --custodian-uid "$CUST_UID" \
  --evaluator-public-key-file "$TMP/eval-public/evaluator.hex" \
  --custodian-public-key-file "$TMP/cust-public/custodian.hex" \
  --run-id "$RUN_ID" \
  --witness-public-key-file "$TMP/enrollment/witness-public.hex" \
  --enrollment-file "$TMP/enrollment/enrollment.json"
wait "$EVAL_PID"
EVAL_PID=''
wait "$CUST_PID"
CUST_PID=''
wait "$WITNESS_PID"
WITNESS_PID=''
echo 'C3R_CROSSED_FOUR_UID_GATE=PASS (local only, no external witness or provider sends)'

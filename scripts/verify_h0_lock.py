#!/usr/bin/env python3
from __future__ import annotations
import argparse
import json
from pathlib import Path

def read(path: Path):
    return json.loads(path.read_text())

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument('--lock', type=Path, required=True)
    p.add_argument('--materialization', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    lock = read(a.lock)
    mat = read(a.materialization)
    checks = {}
    for name in ('plane_e', 'plane_k', 'meta'):
        e = lock['roots'][name]
        x = mat['roots'][name]
        checks[name] = int(e['file_count']) == int(x['file_count']) and str(e['manifest_root_sha256']) == str(x['manifest_root_sha256'])
    result = {
        'schema': 'h0-apparatus-lock-verification-v0.1',
        'base_revision': lock['base_revision'],
        'checks': checks,
        'all_match': all(checks.values())
    }
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, sort_keys=True, separators=(',', ':')) + '\n')
    return 0 if result['all_match'] else 1

if __name__ == '__main__':
    raise SystemExit(main())

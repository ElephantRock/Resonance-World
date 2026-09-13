#!/usr/bin/env python3
# ruff: noqa
"""Fail-closed sole-child authorization gate for #263."""
from __future__ import annotations
import subprocess, sys
from pathlib import Path

MARKER=Path('research/d2_top_level_projection/RUN_D2_TOP_LEVEL_PROJECTION')
AUTH='Autonomous_Operating_Charter_Amendment_A1_standing_execution_authority'
BASE='688dbd99fc0a8e73970ccbfc29cc1a1f8343cc96'
BLOBS={
'src/resonance_world/provider_send_guard.py':'4b8896235d8048523d007400d0acfe85470f628c',
'src/resonance_world/github_authorization_queries.py':'4fec4f0bfac06ae17a87a7c148dea6521736a97a',
'src/resonance_world/d2_terminal_adapter.py':'ba16d2eb4b7255437c8ab224e91d5ed093897990',
'src/resonance_world/d2_top_level_projection.py':'84ee0c1624f35ff0b8c68aad3721e48d134dea9e',
'scripts/d2_projection_spec.py':'e67c7ef40fd54b757278171426dbaf27cac12739',
'scripts/d2_projection_prompts.py':'d80d8e162ae96e22c50bdef817aa47162359f78a',
'scripts/d2_json_mode_contract.py':'4bff64e3806675d5fc90085182324820e159c9b9',
'scripts/d2_json_mode_transport.py':'001208db3b99e67717129ef481a2bb74c4d0a718',
'scripts/d2_json_mode_agent.py':'396eb6bd763554f8112f6f549889b4bf16bdb11f',
'scripts/d2_json_mode_probe.py':'a34b632a9bd1262b6220525e0f77a2aa9d6829dd',
'scripts/d2_json_mode_runtime.py':'3c6bb3021d1a11da3ca23d3879f24d14e163a527',
'scripts/qualify_d2_top_level_projection.py':'75fe45a57a0af64b583c64b7632c554ca793e1e4',
'scripts/d2_projection_verify_result.py':'87f4d78107a5d19e8d290c8c2accc3b5e2c6047e',
'tests/test_d2_top_level_projection.py':'6a3c20185ce1d68a6b044b4dc2b615244e2b0403',
'research/d2_top_level_projection/REQUEST_PLAN.json':'cf1491572c3910a7a73e2f9f8427ae9e995ec0d5',
'research/d2_top_level_projection/PROBES.json':'fe76a63adfb59922db9a9c9f490ca31bf067d198',
}
def run(*args:str)->str:return subprocess.check_output(args,text=True).strip()
def main()->int:
 if not MARKER.is_file(): raise SystemExit('marker absent')
 fields=dict(line.split('=',1) for line in MARKER.read_text().splitlines() if line)
 if set(fields)!={'candidate_sha','issue','authorization'} or fields['issue']!='263' or fields['authorization']!=AUTH: raise SystemExit('marker invalid')
 c=fields['candidate_sha']
 if run('git','rev-parse','HEAD^')!=c or run('git','diff','--name-only',c,'HEAD')!=str(MARKER): raise SystemExit('not sole-child activation')
 if subprocess.run(['git','cat-file','-e',f'{c}:{MARKER}'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0: raise SystemExit('candidate already marked')
 if run('git','log','--format=%H','--',str(MARKER)).splitlines()!=[run('git','rev-parse','HEAD')]: raise SystemExit('marker history invalid')
 repo=run('git','config','--get','remote.origin.url').removesuffix('.git').split('github.com/')[-1]
 rid=__import__('os').environ['GITHUB_RUN_ID']; py=sys.executable
 q=[py,'-m','resonance_world.github_authorization_queries']
 if int(run(*q,'workflow-runs','--repository',repo,'--workflow','d2-top-level-projection-qualification.yml','--exclude-run-id',rid))!=0: raise SystemExit('prior run exists')
 if int(run(*q,'reviews','--repository',repo,'--pull-request','266','--candidate-sha',c))<1: raise SystemExit('exact-head review absent')
 if int(run(*q,'threads','--repository',repo,'--pull-request','266'))!=0: raise SystemExit('unresolved review thread')
 subprocess.check_call(['git','merge-base','--is-ancestor',BASE,c])
 for path,expected in BLOBS.items():
  if run('git','rev-parse',f'{c}:{path}')!=expected: raise SystemExit(f'blob drift: {path}')
 print(c); return 0
if __name__=='__main__': raise SystemExit(main())

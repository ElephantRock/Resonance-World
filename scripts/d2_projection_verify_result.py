#!/usr/bin/env python3
# ruff: noqa
"""Bounded post-execution authority verifier for #263."""
import json,sys
from pathlib import Path
p=json.loads(Path('output/d2-top-level-projection-result.json').read_text())
assert p['schema']=='d2-top-level-projection-result-v0.1' and p['issue']==263 and p['candidate_sha']==sys.argv[1]
assert p['fresh_namespace']=='rw.d2-top-level-projection.v1'
assert p['request_intervention']=={'response_format':{'type':'json_object'}}
assert p['parser_intervention']=='ignore_unknown_top_level_keys_only'
assert p['terminal_adapter_git_blob_sha']=='ba16d2eb4b7255437c8ab224e91d5ed093897990'
assert p['projection_adapter_git_blob_sha']=='84ee0c1624f35ff0b8c68aad3721e48d134dea9e'
assert p['registered_probe_count']==p['attempted_probe_count']==72
assert 0<=p['effective_completed_count']<=72 and 0<=p['projection_used_probe_count']<=72
assert 0<=p['physical_provider_sends_observed_total']<=180
assert p['qualification_outcome'] in {'PASS','ADAPTER_PATH_NOT_EXERCISED','FAIL_STRUCTURED_CONTRACT','FAIL_JSON_MODE_COMPATIBILITY','FAIL_COMPLETION','APPARATUS_FAILURE'}
for k in ('scientific_scoring_performed','acceptance_action_authorized','production_historical_substrate_enabled','raw_credentials_persisted','raw_provider_response_body_persisted','raw_provider_error_body_or_message_persisted','raw_final_response_content_persisted','same_request_stream_rerun_allowed'):
 assert p[k] is False

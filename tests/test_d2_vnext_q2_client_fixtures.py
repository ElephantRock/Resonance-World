# ruff: noqa
# ruff: noqa: E501
from contextlib import contextmanager
from typing import Any
import d2_vnext_q2_hermes_client as q2
import pytest
class Ledger:
    def __init__(self):self.data={};self.attribution_mismatches=0
    def rows(self,i):return list(self.data.get(i,[]))
    def add(self,i):self.data.setdefault(i,[]).append({"origin_logical_index":i,"logical_index":i,"http_status":200,"transport_error_type":None})
class Budget:
    def __init__(self,l):self.l=l;self.blocked_unexpected=0;self.blocked_budget=0
    @contextmanager
    def logical_call(self,i):yield
    def sends_for_logical_call(self,i):return len(self.l.rows(i))
def attempt(*,length=0,parse=False,completed=False,reason="final_response_empty",api_calls=2,clean=True):
    return {"runtime_exception":False,"error_type":None,"error_sha256":None,"hermes_completed_flag_valid":True,"hermes_completed":completed,"hermes_failed":False,"hermes_partial":False,"hermes_interrupted":False,"hermes_error_present":False,"api_calls":api_calls,"final_response_length":length,"final_response_sha256":"f"*64 if length else None,"exact_structured_parse_valid":parse,"parse_diagnostic":"exact_valid" if parse else "json_decode_failure","placeholder_leak":False,"strategy_length":0,"strategy_sha256":None,"physical_provider_sends_observed":1,"attempts":[],"logical_attribution_integrity":clean,"exact_attributed_clean_transport":clean,"json_mode_compatibility_failure":False,"effective_completed":completed and parse,"terminal_iteration_override_used":False,"adapter_reason":reason}
def client():
    l=Ledger();b=Budget(l);c=q2.Client.__new__(q2.Client);c.budget=b;c.ledger=l;c.logical_calls_started=c.logical_calls_completed=c.logical_call_failures=c.retry_used_count=c.terminal_iteration_override_count=c._counter=0;return c,l,b
def install(monkeypatch,l,seq):
    it=iter(seq)
    def f(i,user,budget,ledger):l.add(i);return next(it)
    monkeypatch.setattr(q2.s2,"_invoke",f)
def call(c):return c.complete(phase="fresh/evaluation1",system="x",user="task",expected_actions=8,temperature=0.8)
def test_clean_empty_retry_can_rescue(monkeypatch):
    c,l,_=client();first=attempt();second=attempt(length=10,parse=True,completed=True,reason="completed");payload={"actions":["KAPPA"]*8,"strategy":None};install(monkeypatch,l,[(first,None),(second,payload)]);r=call(c);assert r["accepted_attempt_index"]==2 and r["retry_trigger_class"]==q2.CLEAN_EMPTY_TRIGGER and r["agent_invocation_count"]==2
def test_empty_unclean_not_retry_eligible(monkeypatch):
    c,l,_=client();first=attempt(clean=False);install(monkeypatch,l,[(first,None)])
    with pytest.raises(q2.Q2LogicalCallFailure) as e:
        call(c)
    assert e.value.evidence["retry_used"] is False
def test_parse_invalid_rule_preserved(monkeypatch):
    c,l,_=client();first=attempt(length=3,reason="structured_parse_invalid");second=attempt(length=10,parse=True,completed=True,reason="completed");payload={"actions":["MICA"]*8,"strategy":None};install(monkeypatch,l,[(first,None),(second,payload)]);r=call(c);assert r["retry_trigger_class"]==q2.PARSE_INVALID_TRIGGER
def test_failed_retry_has_no_third_invocation(monkeypatch):
    c,l,_=client();first=attempt();second=attempt();install(monkeypatch,l,[(first,None),(second,None)])
    with pytest.raises(q2.Q2LogicalCallFailure) as e:
        call(c)
    assert e.value.evidence["retry_used"] is True and len(l.rows(0))==2
    q2.assert_failure_evidence_has_no_raw_content(e.value.evidence)

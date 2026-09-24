# ruff: noqa: E501
"""Q2 supported-product client with one prospective clean-empty regeneration trigger."""
from __future__ import annotations

import hashlib
import os
import re
from typing import Any

import d2_vnext_s2_hermes_client as s2

BASE_URL=s2.BASE_URL
PROVIDER=s2.PROVIDER
API_MODE=s2.API_MODE
MODEL=s2.MODEL
TEMPERATURE=s2.TEMPERATURE
MAX_TOKENS=s2.MAX_TOKENS
MAX_ITERATIONS=s2.MAX_ITERATIONS
MAX_AGENT_INVOCATIONS=s2.MAX_AGENT_INVOCATIONS
MAX_LOGICAL_CALLS_PER_SHARD=s2.MAX_LOGICAL_CALLS_PER_SHARD
MAX_PHYSICAL_SENDS_PER_LOGICAL_CALL=s2.MAX_PHYSICAL_SENDS_PER_LOGICAL_CALL
MAX_PHYSICAL_SENDS_PER_SHARD=1152
TransportLedger=s2.TransportLedger
ProviderWorkerTracker=s2.ProviderWorkerTracker
guarded_shard_transport=s2.guarded_shard_transport

TERMINAL_FAILURE_MESSAGE="D2-vNext-Q2 logical call has no accepted exact completion"
TERMINAL_FAILURE_SHA256=hashlib.sha256(f"RuntimeError:{TERMINAL_FAILURE_MESSAGE}".encode()).hexdigest()
PARSE_INVALID_TRIGGER="clean_nonempty_exact_parser_invalid"
CLEAN_EMPTY_TRIGGER="clean_terminal_empty"

class Q2LogicalCallFailure(RuntimeError):
    def __init__(self,evidence:dict[str,Any])->None:
        super().__init__(TERMINAL_FAILURE_MESSAGE);self.evidence=evidence

def new_shard_budget()->s2.ProviderSendBudget:
    return s2.ProviderSendBudget(allowed_url_prefix=BASE_URL,maximum_logical_calls=MAX_LOGICAL_CALLS_PER_SHARD,maximum_sends_per_logical_call=MAX_PHYSICAL_SENDS_PER_LOGICAL_CALL,maximum_sends_total=MAX_PHYSICAL_SENDS_PER_SHARD)

def _bounded_attempt_view(attempt:dict[str,Any]|None)->dict[str,Any]|None:
    if attempt is None:return None
    return {
        "runtime_exception":bool(attempt["runtime_exception"]),"error_type":attempt["error_type"],"error_sha256":attempt["error_sha256"],
        "hermes_completed_flag_valid":bool(attempt["hermes_completed_flag_valid"]),"hermes_completed":bool(attempt["hermes_completed"]),
        "hermes_failed":bool(attempt["hermes_failed"]),"hermes_partial":bool(attempt["hermes_partial"]),"hermes_interrupted":bool(attempt["hermes_interrupted"]),"hermes_error_present":bool(attempt["hermes_error_present"]),
        "api_calls":int(attempt["api_calls"]),"exact_structured_parse_valid":bool(attempt["exact_structured_parse_valid"]),"parse_diagnostic":str(attempt["parse_diagnostic"]),
        "physical_provider_sends_observed":int(attempt["physical_provider_sends_observed"]),"exact_attributed_clean_transport":bool(attempt["exact_attributed_clean_transport"]),"logical_attribution_integrity":bool(attempt["logical_attribution_integrity"]),
        "effective_completed":bool(attempt["effective_completed"]),"terminal_iteration_override_used":bool(attempt["terminal_iteration_override_used"]),"adapter_reason":str(attempt["adapter_reason"]),
    }

def assert_failure_evidence_has_no_raw_content(value:Any)->None:
    forbidden={"raw_response_text","raw_first_response_text","raw_second_response_text","raw_provider_body","prompt_text","retry_prompt_text","final_response"}
    if isinstance(value,dict):
        overlap=forbidden&set(value)
        if overlap:raise AssertionError(f"raw-content field leaked into Q2 failure evidence: {sorted(overlap)}")
        for nested in value.values():assert_failure_evidence_has_no_raw_content(nested)
    elif isinstance(value,list):
        for nested in value:assert_failure_evidence_has_no_raw_content(nested)

def retry_trigger(first:dict[str,Any],budget:s2.ProviderSendBudget,ledger:TransportLedger)->str|None:
    if s2.retry_eligible(first,budget,ledger):return PARSE_INVALID_TRIGGER
    clean_empty=bool(
        not first["runtime_exception"] and first["final_response_length"]==0 and first["adapter_reason"]=="final_response_empty" and
        not first["exact_structured_parse_valid"] and first["hermes_completed_flag_valid"] and not first["hermes_completed"] and
        not first["hermes_failed"] and not first["hermes_partial"] and not first["hermes_interrupted"] and not first["hermes_error_present"] and
        int(first["api_calls"])==MAX_ITERATIONS and first["physical_provider_sends_observed"]>0 and first["exact_attributed_clean_transport"] and
        first["logical_attribution_integrity"] and not first["json_mode_compatibility_failure"] and budget.blocked_unexpected==0 and budget.blocked_budget==0 and ledger.attribution_mismatches==0
    )
    return CLEAN_EMPTY_TRIGGER if clean_empty else None

def retry_user_prompt(original_user:str,first:dict[str,Any],trigger:str)->str:
    if trigger==PARSE_INVALID_TRIGGER:return s2.retry_user_prompt(original_user,str(first["parse_diagnostic"]))
    if trigger!=CLEAN_EMPTY_TRIGGER:raise ValueError("unknown Q2 retry trigger")
    return original_user+"\n\nFormat-regeneration attempt: the prior invocation reached the bounded terminal iteration without a nonempty final response. Raw prior response content is unavailable and must not be inferred, reconstructed, or repaired. Generate a fresh independent answer for the original cases. Re-check the required positional JSON contract silently before emitting. Return JSON only."

def build_terminal_failure_evidence(*,phase:str,logical_index:int,first:dict[str,Any],trigger:str|None,second:dict[str,Any]|None)->dict[str,Any]:
    return {"arm":phase.split("/",1)[0],"phase":phase,"logical_call_index":logical_index,"first_attempt":_bounded_attempt_view(first),"retry_eligible":trigger is not None,"retry_trigger_class":trigger,"retry_used":second is not None,"second_attempt":_bounded_attempt_view(second),"accepted_exact_completion":False,"terminal_error_type":"RuntimeError","terminal_error_sha256":TERMINAL_FAILURE_SHA256}

class Client:
    def __init__(self,key:str,budget:s2.ProviderSendBudget,ledger:TransportLedger)->None:
        if not key.strip():raise RuntimeError("ZAI_API_KEY is required")
        if os.environ.get("GLM_BASE_URL","").rstrip("/")!=BASE_URL:raise RuntimeError("Coding Plan base URL drift")
        s2._runtime_versions()
        if s2.FORBIDDEN_EXEMPLAR in s2.SYSTEM_PROMPT:raise AssertionError("literal valid action exemplar prohibited")
        self.budget=budget;self.ledger=ledger;self.logical_calls_started=0;self.logical_calls_completed=0;self.logical_call_failures=0;self.retry_used_count=0;self.terminal_iteration_override_count=0;self._counter=0
    def complete(self,*,phase:str,system:str,user:str,expected_actions:int,temperature:float)->dict[str,Any]:
        del system
        if expected_actions!=8:raise AssertionError("D2-vNext-Q2 exact action count drift")
        if float(temperature)!=TEMPERATURE:raise AssertionError("D2-vNext-Q2 temperature drift")
        logical_index=self._counter;self._counter+=1
        if logical_index>=MAX_LOGICAL_CALLS_PER_SHARD:raise RuntimeError("registered logical-call topology exhausted")
        self.logical_calls_started+=1
        prompt_sha256=hashlib.sha256(s2.canonical_bytes({"system":s2.SYSTEM_PROMPT,"user":user})).hexdigest()
        second=None;second_payload=None;retry_prompt=None;first=None;trigger=None
        try:
            with self.budget.logical_call(logical_index):
                first,first_payload=s2._invoke(logical_index,user,self.budget,self.ledger)
                trigger=retry_trigger(first,self.budget,self.ledger)
                if trigger is not None:
                    retry_prompt=retry_user_prompt(user,first,trigger)
                    second,second_payload=s2._invoke(logical_index,retry_prompt,self.budget,self.ledger)
                    self.retry_used_count+=1
            if first["exact_structured_parse_valid"] and first["effective_completed"]:accepted_index=1;accepted=first;payload=first_payload
            elif second is not None and second["exact_structured_parse_valid"] and second["effective_completed"]:accepted_index=2;accepted=second;payload=second_payload
            else:
                self.logical_call_failures+=1
                evidence=build_terminal_failure_evidence(phase=phase,logical_index=logical_index,first=first,trigger=trigger,second=second)
                assert_failure_evidence_has_no_raw_content(evidence)
                raise Q2LogicalCallFailure(evidence)
            if payload is None:raise AssertionError("accepted exact response payload missing")
            if first["exact_structured_parse_valid"] and second is not None:raise AssertionError("valid first response was retried")
            if second is not None and trigger is None:raise AssertionError("format-regeneration retry was not eligible")
            if accepted["terminal_iteration_override_used"]:self.terminal_iteration_override_count+=1
            all_attempts=self.ledger.rows(logical_index)
            if len(all_attempts)!=self.budget.sends_for_logical_call(logical_index):raise AssertionError("provider-send ledger/accounting mismatch")
            self.logical_calls_completed+=1
            return {"actions":list(payload["actions"]),"strategy":payload.get("strategy"),"model":MODEL,"effective_model_identity_observed":False,"effective_model":None,"temperature":TEMPERATURE,"thinking":"disabled","request_id":f"d2-vnext-q2-{logical_index:04d}-{re.sub(r'[^a-zA-Z0-9_.-]+','-',phase)[-72:]}","prompt_sha256":prompt_sha256,"response_sha256":accepted["final_response_sha256"],"strategy_present":payload.get("strategy") is not None,"extra_key_count":0,"attempts":all_attempts,"usage":{},"total_latency_ms":None,"retry_used":second is not None,"retry_eligible_after_first":trigger is not None,"retry_trigger_class":trigger,"accepted_attempt_index":accepted_index,"agent_invocation_count":1+int(second is not None),"first_attempt_api_calls":int(first["api_calls"]),"first_attempt_parse_valid":first["exact_structured_parse_valid"],"first_attempt_parse_diagnostic":first["parse_diagnostic"],"first_attempt_final_response_length":first["final_response_length"],"first_attempt_final_response_sha256":first["final_response_sha256"],"second_attempt_api_calls":int(second["api_calls"]) if second is not None else None,"second_attempt_parse_valid":second["exact_structured_parse_valid"] if second is not None else None,"second_attempt_parse_diagnostic":second["parse_diagnostic"] if second is not None else None,"second_attempt_final_response_length":second["final_response_length"] if second is not None else None,"second_attempt_final_response_sha256":second["final_response_sha256"] if second is not None else None,"retry_prompt_sha256":s2.sha256_text(retry_prompt) if retry_prompt else None,"retry_raw_first_response_content_included":False,"hermes_completed":accepted["hermes_completed"],"terminal_iteration_override_used":accepted["terminal_iteration_override_used"],"adapter_reason":accepted["adapter_reason"],"json_mode_compatibility_failure":bool(first["json_mode_compatibility_failure"] or (second and second["json_mode_compatibility_failure"]))}
        except Q2LogicalCallFailure:raise
        except Exception:
            if self.logical_call_failures==0 or self.logical_calls_completed+self.logical_call_failures<self.logical_calls_started:self.logical_call_failures+=1
            raise

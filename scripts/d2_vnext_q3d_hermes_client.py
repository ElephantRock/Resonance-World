# ruff: noqa: E501
"""Q3-D structural observability wrapper preserving the frozen Q2 behavior."""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
from typing import Any, Callable

import d2_vnext_q2_hermes_client as q2
import d2_vnext_s2_hermes_client as s2
from resonance_world import d2_terminal_adapter as adapter

BASE_URL=q2.BASE_URL
PROVIDER=q2.PROVIDER
API_MODE=q2.API_MODE
MODEL=q2.MODEL
TEMPERATURE=q2.TEMPERATURE
MAX_TOKENS=q2.MAX_TOKENS
MAX_ITERATIONS=q2.MAX_ITERATIONS
MAX_AGENT_INVOCATIONS=q2.MAX_AGENT_INVOCATIONS
MAX_LOGICAL_CALLS_PER_SHARD=220
MAX_PHYSICAL_SENDS_PER_LOGICAL_CALL=q2.MAX_PHYSICAL_SENDS_PER_LOGICAL_CALL
MAX_PHYSICAL_SENDS_PER_SHARD=1152
TransportLedger=s2.TransportLedger
ProviderWorkerTracker=s2.ProviderWorkerTracker
guarded_shard_transport=s2.guarded_shard_transport
PARSE_INVALID_TRIGGER=q2.PARSE_INVALID_TRIGGER
CLEAN_EMPTY_TRIGGER=q2.CLEAN_EMPTY_TRIGGER
TERMINAL_FAILURE_MESSAGE="D2-vNext-Q3-D logical call has no accepted exact completion"
TERMINAL_FAILURE_SHA256=hashlib.sha256(f"RuntimeError:{TERMINAL_FAILURE_MESSAGE}".encode()).hexdigest()

FORBIDDEN_RAW_KEYS={"raw_response_text","raw_first_response_text","raw_second_response_text","raw_provider_body","prompt_text","retry_prompt_text","final_response","assistant_content","response_body","raw_content"}


def _sha_text(value:str)->str:
    return hashlib.sha256(value.encode()).hexdigest()


def _bounded_content_view(content:Any)->dict[str,Any]:
    if content is None:
        return {"assistant_content_present":False,"assistant_content_type":"null","assistant_content_length":0,"assistant_content_sha256":None}
    if isinstance(content,str):
        return {"assistant_content_present":bool(content),"assistant_content_type":"string","assistant_content_length":len(content),"assistant_content_sha256":_sha_text(content) if content else None}
    if isinstance(content,list):
        encoded=json.dumps(content,sort_keys=True,separators=(",",":"),default=str)
        return {"assistant_content_present":bool(content),"assistant_content_type":"list","assistant_content_length":len(content),"assistant_content_sha256":_sha_text(encoded) if content else None}
    encoded=str(content)
    return {"assistant_content_present":True,"assistant_content_type":type(content).__name__,"assistant_content_length":len(encoded),"assistant_content_sha256":_sha_text(encoded)}


def provider_completion_view(response:Any,*,agent_invocation_index:int,semantic_response_index:int)->dict[str,Any]:
    choices=list(getattr(response,"choices",[]) or [])
    first=choices[0] if choices else None
    message=getattr(first,"message",None) if first is not None else None
    content=getattr(message,"content",None) if message is not None else None
    content_view=_bounded_content_view(content)
    tool_calls=getattr(message,"tool_calls",None) if message is not None else None
    tool_count=len(tool_calls) if isinstance(tool_calls,(list,tuple)) else (1 if tool_calls else 0)
    usage=getattr(response,"usage",None)
    finish_reason=getattr(first,"finish_reason",None) if first is not None else None
    view={
        "agent_invocation_index":agent_invocation_index,
        "semantic_response_index":semantic_response_index,
        "effective_model_if_returned":str(getattr(response,"model",None)) if getattr(response,"model",None) is not None else None,
        "choice_count":len(choices),
        "finish_reason_present":finish_reason is not None,
        "finish_reason":str(finish_reason) if finish_reason is not None else None,
        "assistant_message_present":message is not None,
        **content_view,
        "tool_calls_present":tool_count>0,
        "tool_calls_count":tool_count,
        "usage_prompt_tokens":int(getattr(usage,"prompt_tokens",0)) if getattr(usage,"prompt_tokens",None) is not None else None,
        "usage_completion_tokens":int(getattr(usage,"completion_tokens",0)) if getattr(usage,"completion_tokens",None) is not None else None,
        "usage_total_tokens":int(getattr(usage,"total_tokens",0)) if getattr(usage,"total_tokens",None) is not None else None,
    }
    assert_no_raw_content(view)
    return view


class SemanticRecorder:
    def __init__(self)->None:
        self._lock=threading.Lock();self._rows:list[dict[str,Any]]=[]
    def append(self,row:dict[str,Any])->None:
        with self._lock:self._rows.append(dict(row))
    def rows(self)->list[dict[str,Any]]:
        with self._lock:return [dict(row) for row in self._rows]


def instrument_chat_completions(agent:Any,*,agent_invocation_index:int,recorder:SemanticRecorder)->Callable[...,Any]:
    """Wrap OpenAI semantic completion creation and return the exact original response object."""
    original=agent.client.chat.completions.create
    counter={"value":0}
    def wrapped(*args:Any,**kwargs:Any)->Any:
        response=original(*args,**kwargs)
        counter["value"]+=1
        recorder.append(provider_completion_view(response,agent_invocation_index=agent_invocation_index,semantic_response_index=counter["value"]))
        return response
    agent.client.chat.completions.create=wrapped
    return original


def bounded_termination_reason(*,runtime_exception:bool,result:dict[str,Any],api_calls:int,final_text:str)->str:
    if runtime_exception:return "runtime_exception"
    if result.get("failed") is True:return "hermes_failed"
    if result.get("partial") is True:return "hermes_partial"
    if result.get("interrupted") is True:return "hermes_interrupted"
    if bool(result.get("error")):return "hermes_error_present"
    if result.get("completed") is True:return "hermes_completed"
    if api_calls>=MAX_ITERATIONS:return "iteration_budget_exhausted"
    if final_text:return "terminal_response_uncompleted"
    return "terminal_empty_uncompleted"


def classify_boundary(*,runtime_exception:bool,provider_semantic:list[dict[str,Any]],candidate_present:bool,parse_valid:bool,effective_completed:bool)->str:
    if runtime_exception:return "runtime_or_transport_failure"
    last=provider_semantic[-1] if provider_semantic else None
    if last is None or not bool(last.get("assistant_content_present")):return "provider_content_absent"
    if not candidate_present:return "provider_content_present_hermes_terminal_absent"
    if candidate_present and not parse_valid:return "adapter_candidate_nonempty_parse_invalid"
    if parse_valid and effective_completed:return "accepted_exact_completion"
    return "unclassified_observability_defect"


def assert_no_raw_content(value:Any)->None:
    if isinstance(value,dict):
        overlap=FORBIDDEN_RAW_KEYS&set(value)
        if overlap:raise AssertionError(f"raw-content field leaked into Q3-D evidence: {sorted(overlap)}")
        for nested in value.values():assert_no_raw_content(nested)
    elif isinstance(value,list):
        for nested in value:assert_no_raw_content(nested)


def new_shard_budget()->s2.ProviderSendBudget:
    return s2.ProviderSendBudget(allowed_url_prefix=BASE_URL,maximum_logical_calls=MAX_LOGICAL_CALLS_PER_SHARD,maximum_sends_per_logical_call=MAX_PHYSICAL_SENDS_PER_LOGICAL_CALL,maximum_sends_total=MAX_PHYSICAL_SENDS_PER_SHARD)


def _invoke(logical_index:int,user:str,budget:s2.ProviderSendBudget,ledger:TransportLedger,*,agent_invocation_index:int)->tuple[dict[str,Any],dict[str,Any]|None]:
    before=len(ledger.rows(logical_index));agent=None;result:dict[str,Any]={};final_text="";runtime_exception=False;error_type=None;error_sha256=None;recorder=SemanticRecorder()
    try:
        agent=s2._new_agent(logical_index)
        instrument_chat_completions(agent,agent_invocation_index=agent_invocation_index,recorder=recorder)
        result=agent.run_conversation(user_message=user)
        final=result.get("final_response")
        final_text=final if isinstance(final,str) else ""
    except Exception as exc:
        runtime_exception=True;error_type=type(exc).__name__;error_sha256=_sha_text(f"{type(exc).__name__}:{str(exc)[:500]}")
    rows=ledger.rows(logical_index)[before:]
    api_calls=int(getattr(agent,"_api_call_count",0) if agent is not None else 0)
    completed=result.get("completed");completed_valid=isinstance(completed,bool)
    diagnostic=s2.bounded_parse_diagnostic(final_text)
    parse_valid,strategy=adapter.parse_response(final_text)
    if parse_valid!=(diagnostic=="exact_valid"):raise AssertionError("Q3-D exact parser/diagnostic divergence")
    logical_integrity=bool(rows) and all(row.get("origin_logical_index")==logical_index and row.get("logical_index")==logical_index for row in rows)
    view={"completed":completed if completed_valid else None,"failed":result.get("failed") is True or runtime_exception,"partial":result.get("partial") is True,"interrupted":result.get("interrupted") is True,"error":"bounded-error-present" if (bool(result.get("error")) or runtime_exception) else None,"api_calls":api_calls,"final_response":"bounded-nonempty-response-sentinel" if final_text.strip() else ""}
    decision=adapter.evaluate_terminal_completion(view,max_iterations=MAX_ITERATIONS,parse_valid=parse_valid,logical_attribution_integrity=logical_integrity,attempts=rows,physical_sends=len(rows),unexpected_outbound_blocks=budget.blocked_unexpected,provider_budget_blocks=budget.blocked_budget,attribution_mismatch_blocks=ledger.attribution_mismatches)
    compatibility=s2._compatibility_failure(runtime_exception,rows)
    payload=None
    if parse_valid:
        decoded=json.loads(final_text);payload={"actions":list(decoded["actions"]),"strategy":decoded.get("strategy")}
    semantic=recorder.rows()
    candidate_present=bool(final_text)
    bounded={
        "runtime_exception":runtime_exception,"error_type":error_type,"error_sha256":error_sha256,
        "hermes_completed_flag_valid":completed_valid,"hermes_completed":completed is True,"hermes_failed":result.get("failed") is True,"hermes_partial":result.get("partial") is True,"hermes_interrupted":result.get("interrupted") is True,"hermes_error_present":bool(result.get("error")),
        "agent_invocation_index":agent_invocation_index,"api_calls":api_calls,"loop_termination_reason":bounded_termination_reason(runtime_exception=runtime_exception,result=result,api_calls=api_calls,final_text=final_text),
        "final_response_length":len(final_text),"final_response_sha256":_sha_text(final_text) if final_text else None,"exact_structured_parse_valid":parse_valid,"parse_diagnostic":diagnostic,
        "physical_provider_sends_observed":len(rows),"attempts":rows,"logical_attribution_integrity":logical_integrity,"exact_attributed_clean_transport":s2._clean_attempts(rows),"json_mode_compatibility_failure":compatibility,
        "effective_completed":decision.effective_completed,"terminal_iteration_override_used":decision.terminal_iteration_override_used,"adapter_reason":decision.reason,
        "provider_semantic_completions":semantic,
        "terminal_adapter":{"candidate_source":"hermes_final_response","candidate_present":candidate_present,"candidate_type":"string" if isinstance(result.get("final_response"),str) else ("null" if result.get("final_response") is None else type(result.get("final_response")).__name__),"candidate_length":len(final_text),"candidate_sha256":_sha_text(final_text) if final_text else None,"adapter_reason":decision.reason,"parse_diagnostic":diagnostic,"exact_structured_parse_valid":parse_valid,"accepted_exact_completion":bool(parse_valid and decision.effective_completed)},
    }
    bounded["boundary_classification"]=classify_boundary(runtime_exception=runtime_exception,provider_semantic=semantic,candidate_present=candidate_present,parse_valid=parse_valid,effective_completed=decision.effective_completed)
    assert_no_raw_content({k:v for k,v in bounded.items() if k!="attempts"})
    return bounded,payload


def _bounded_attempt_view(attempt:dict[str,Any]|None)->dict[str,Any]|None:
    if attempt is None:return None
    fields=("runtime_exception","error_type","error_sha256","hermes_completed_flag_valid","hermes_completed","hermes_failed","hermes_partial","hermes_interrupted","hermes_error_present","agent_invocation_index","api_calls","loop_termination_reason","final_response_length","final_response_sha256","exact_structured_parse_valid","parse_diagnostic","physical_provider_sends_observed","logical_attribution_integrity","exact_attributed_clean_transport","json_mode_compatibility_failure","effective_completed","terminal_iteration_override_used","adapter_reason","provider_semantic_completions","terminal_adapter","boundary_classification")
    result={key:attempt.get(key) for key in fields};assert_no_raw_content(result);return result


class Q3DLogicalCallFailure(RuntimeError):
    def __init__(self,evidence:dict[str,Any])->None:
        super().__init__(TERMINAL_FAILURE_MESSAGE);self.evidence=evidence


class Client:
    def __init__(self,key:str,budget:s2.ProviderSendBudget,ledger:TransportLedger)->None:
        if not key.strip():raise RuntimeError("ZAI_API_KEY is required")
        if os.environ.get("GLM_BASE_URL","").rstrip("/")!=BASE_URL:raise RuntimeError("Coding Plan base URL drift")
        s2._runtime_versions()
        self.budget=budget;self.ledger=ledger;self.logical_calls_started=0;self.logical_calls_completed=0;self.logical_call_failures=0;self.retry_used_count=0;self.terminal_iteration_override_count=0;self._counter=0
    def complete(self,*,phase:str,system:str,user:str,expected_actions:int,temperature:float)->dict[str,Any]:
        del system
        if expected_actions!=8:raise AssertionError("D2-vNext-Q3-D exact action count drift")
        if float(temperature)!=TEMPERATURE:raise AssertionError("D2-vNext-Q3-D temperature drift")
        logical_index=self._counter;self._counter+=1
        if logical_index>=MAX_LOGICAL_CALLS_PER_SHARD:raise RuntimeError("registered logical-call topology exhausted")
        self.logical_calls_started+=1
        prompt_sha256=hashlib.sha256(s2.canonical_bytes({"system":s2.SYSTEM_PROMPT,"user":user})).hexdigest()
        second=None;second_payload=None;retry_prompt=None;trigger=None
        try:
            with self.budget.logical_call(logical_index):
                first,first_payload=_invoke(logical_index,user,self.budget,self.ledger,agent_invocation_index=1)
                trigger=q2.retry_trigger(first,self.budget,self.ledger)
                if trigger is not None:
                    retry_prompt=q2.retry_user_prompt(user,first,trigger)
                    second,second_payload=_invoke(logical_index,retry_prompt,self.budget,self.ledger,agent_invocation_index=2)
                    self.retry_used_count+=1
            if first["exact_structured_parse_valid"] and first["effective_completed"]:accepted_index=1;accepted=first;payload=first_payload
            elif second is not None and second["exact_structured_parse_valid"] and second["effective_completed"]:accepted_index=2;accepted=second;payload=second_payload
            else:
                self.logical_call_failures+=1
                evidence={"arm":phase.split("/",1)[0],"phase":phase,"logical_call_index":logical_index,"first_attempt":_bounded_attempt_view(first),"retry_eligible":trigger is not None,"retry_trigger_class":trigger,"retry_used":second is not None,"second_attempt":_bounded_attempt_view(second),"accepted_exact_completion":False,"terminal_error_type":"RuntimeError","terminal_error_sha256":TERMINAL_FAILURE_SHA256}
                assert_no_raw_content(evidence);raise Q3DLogicalCallFailure(evidence)
            if payload is None:raise AssertionError("accepted exact response payload missing")
            if first["exact_structured_parse_valid"] and second is not None:raise AssertionError("valid first response was retried")
            if second is not None and trigger is None:raise AssertionError("format-regeneration retry was not eligible")
            if accepted["terminal_iteration_override_used"]:self.terminal_iteration_override_count+=1
            all_attempts=self.ledger.rows(logical_index)
            if len(all_attempts)!=self.budget.sends_for_logical_call(logical_index):raise AssertionError("provider-send ledger/accounting mismatch")
            self.logical_calls_completed+=1
            return {"actions":list(payload["actions"]),"strategy":payload.get("strategy"),"model":MODEL,"effective_model_identity_observed":any(bool(x.get("effective_model_if_returned")) for x in accepted["provider_semantic_completions"]),"effective_model":next((x.get("effective_model_if_returned") for x in reversed(accepted["provider_semantic_completions"]) if x.get("effective_model_if_returned")),None),"temperature":TEMPERATURE,"thinking":"disabled","request_id":f"d2-vnext-q3d-{logical_index:04d}-{re.sub(r'[^a-zA-Z0-9_.-]+','-',phase)[-72:]}","prompt_sha256":prompt_sha256,"response_sha256":accepted["final_response_sha256"],"strategy_present":payload.get("strategy") is not None,"extra_key_count":0,"attempts":all_attempts,"usage":{},"total_latency_ms":None,"retry_used":second is not None,"retry_eligible_after_first":trigger is not None,"retry_trigger_class":trigger,"accepted_attempt_index":accepted_index,"agent_invocation_count":1+int(second is not None),"first_attempt_api_calls":int(first["api_calls"]),"first_attempt_parse_valid":first["exact_structured_parse_valid"],"first_attempt_parse_diagnostic":first["parse_diagnostic"],"first_attempt_final_response_length":first["final_response_length"],"first_attempt_final_response_sha256":first["final_response_sha256"],"second_attempt_api_calls":int(second["api_calls"]) if second is not None else None,"second_attempt_parse_valid":second["exact_structured_parse_valid"] if second is not None else None,"second_attempt_parse_diagnostic":second["parse_diagnostic"] if second is not None else None,"second_attempt_final_response_length":second["final_response_length"] if second is not None else None,"second_attempt_final_response_sha256":second["final_response_sha256"] if second is not None else None,"retry_prompt_sha256":s2.sha256_text(retry_prompt) if retry_prompt else None,"retry_raw_first_response_content_included":False,"hermes_completed":accepted["hermes_completed"],"terminal_iteration_override_used":accepted["terminal_iteration_override_used"],"adapter_reason":accepted["adapter_reason"],"json_mode_compatibility_failure":bool(first["json_mode_compatibility_failure"] or (second and second["json_mode_compatibility_failure"])),"q3d_observability":{"first_attempt":_bounded_attempt_view(first),"second_attempt":_bounded_attempt_view(second)}}
        except Q3DLogicalCallFailure:raise
        except Exception:
            if self.logical_calls_completed+self.logical_call_failures<self.logical_calls_started:self.logical_call_failures+=1
            raise

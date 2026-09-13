# ruff: noqa
"""Deterministic fresh probe prompts for #263."""
from __future__ import annotations
import json
from typing import Any
from resonance_world import d2_terminal_adapter as adapter
from d2_projection_spec import NAMESPACE

def cases(seed:int)->list[dict[str,int]]:
 return [{'case_id':seed*100+i,'f0':(seed+5*i)%13-6,'f1':(2*seed+7*i)%17-8,'f2':(3*seed+11*i)%19-9,'f3':(7*seed+13*i)%23-11} for i in range(8)]
def feedback(seed:int,budget:int)->list[dict[str,Any]]:
 return [{'case_id':r['case_id'],'chosen_action':adapter.ACTIONS[(seed+2*budget+3*i)%4],'correct':bool((seed+budget+2*i)%2),'bounded_feedback':'top-level projection engineering sentinel only'} for i,r in enumerate(cases(seed-2))]
def synthetic_strategy(seed:int,budget:int)->str:
 return f'projection-b{budget}-s{seed}; anchor-{adapter.ACTIONS[(seed+1)%4].lower()}; phase-{seed%3}; span-{(seed%19)+9}; exact-eight-action-json; no-provider-derived-strategy-propagation'
def system_prompt()->str:return adapter.system_prompt()
def user_prompt(probe:dict[str,Any])->str:
 shape=str(probe['call_shape']); seed=int(probe['seed']); budget=probe['development_budget']
 s=[f'Objective: engineering-only D2 top-level-projection sentinel; never scientifically scored.\nFresh namespace: {NAMESPACE}\nProbe: {probe["probe_id"]}\nCall shape: {shape}\nFresh seed: {seed}','Task ecology: synthetic integer cases; no hidden scientific policy or answer key.']
 if shape.startswith('developed_'):
  s += [f'Development budget shape: {budget}',f'Deterministic synthetic strategy context (never provider-derived):\n{synthetic_strategy(seed,int(budget))}',f'Synthetic engineering feedback:\n{json.dumps(feedback(seed,int(budget)),sort_keys=True,separators=(",",":"))}']
 s += [f'Cases to answer now:\n{json.dumps(cases(seed),sort_keys=True,separators=(",",":"))}','Return choices'+(' and, if useful, bounded private strategy' if shape=='developed_development' else '')+'. No response strategy propagates. Return JSON only.']
 return '\n\n'.join(s)

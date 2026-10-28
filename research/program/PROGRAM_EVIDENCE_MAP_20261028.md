# A. Program Evidence Map — Resonance World (2026-10-28)

Status: **realignment deliverable A**. Read-only review; zero sends;
zero budget; no historical record modified.

**Method.** Four parallel reviews covered (1) the D-line
(research/d1, d1b, d2*, d2_vnext*, evidence/d2_*, acceptance branches),
(2) the H-series + O + G1 v9 (research/h0–h8, o1, o2, KB g1v9 pages,
feature/g1-v9-integration), (3) the W-series (docs/w0–w9 on the working
tree), and (4) Piano Society (all 14 branches, fetched read-only from
origin; preregistrations + bound results + EXTRACTION_DECISION at
`52aa261`). Key claims were spot-verified against source documents.
Where evidence is unavailable, that is stated.

**Legend.** Outcome: positive / negative / mixed / did-not-meet-gate /
UNMEASURED. Strength: exploratory / confirmatory / replicated /
acceptance-judged. "Gate" = a frozen preregistered criterion.
Governance state per `mechanism-governance-v0.1`: nothing in the
program is integration-eligible; historical W/O/H results hold
`historical_record` only.

---

## 1. Model-baseline / model-interface layer (NOT architectural)

| claim | evidence | outcome | strength |
|---|---|---|---|
| Structured accumulating history improves decisions of fixed controllers and fresh stochastic successors (incl. live glm-5-turbo, complete turnover, 5 generations) | research/h1–h4 RESULTs; H4: 35/36 vs 19/36, Holm-corrected, 432/432 physical attempts | **positive** | confirmatory, replicated (H3 ×4) |
| Representation layers over raw history add nothing: History IR +1.04pp CI[−1.18,+2.93]; compiled semantic state 0.00pp; only role/chair synthesis +8.33pp survives Holm | research/h8/RESULT.md | **mixed** (limits) | confirmatory |
| Institutional mediation bundle (roles+authority+routine) over the same history: no superiority over equal-compute direct access | research/h5/RESULT.md | **negative** (for the bundle) | confirmatory |
| Relevance-gated/typed state: H6-P1 positive (+16.7pp) NOT replicated; H7 fresh-unit replication gave **−20.83pp** opposite direction | research/h6, h7 | **contradictory** | confirmatory ×2 |
| G1 v9 persistent behavioral memory A/B: one world, dense feedback — A−B=+0.01, controls honest (C→0.50, D 0.51); transport-error asymmetry contaminates arm A | KB g1v9 pages; PREREG/RESULT on feature/g1-v9-integration | **UNMEASURED** at confirmatory design (frozen 18-world/20pp protocol never run) | exploratory null |
| C3R-G1 model-interface line (2026-10-22→28): capsule validity vs natural text (50%↔75% ITT); stepwise granularity +1 paired (gate NOT met); wording causality +4 paired (gate MET); feedback acquisition UNMEASURABLE at three operating points (4096→empty; 16384/180s→kill; 16384/300s→kill at 300.2s); Learned-vs-Raw question never armed | research/c3r_g2/* RESULTs (this branch) | interface evidence only | exploratory |
| D-line transport walls: clean-terminal-empty boundary localized to SDK chat-completion object (Q3-D2); root cause unseparated (Q3-D3 frozen, unexecuted); model-identity drift documented (glm-5.3-flash answering glm-5-turbo) | research/d2d_diag, d2_vnext_q3d* | engineering, not scientific | — |

**Reading:** the strongest model-adjacent facts are (a) execution-style
requests are stable at the registered operating point, and (b)
induction-grade requests are not, at any permitted setting. These are
apparatus constants for architectural work — not research targets.

## 2. Models → Agents (does memory/experience add capability?)

| claim | evidence | outcome | strength |
|---|---|---|---|
| A frozen capability-production contract produces held-out capability in fresh destination Fields without private state transfer (deterministic substrate) | research/d1 (P0 +58.4pp, P2 non-inferior), d1b exact-replication (P0 +60.4pp); independent acceptance ACCEPT | **positive** | confirmatory + internal replication + acceptance |
| Same, stochastic model-mediated substrate (glm-5-turbo): development contract beats description-only and fresh controls; fidelity ≥100% | research/d2 D2-C2 (359 pairs; P0 +24.35pp, P1 +30.21pp), d2b (360/360; z=10.6/13.4); acceptance → `internally_replicated` | **positive** | confirmatory + replication + acceptance |
| Schema generalization of the above: FAILED on all 3 new schemas (closest missed by 0.44pp) | research/d2c | **negative** (valid) | confirmatory |
| Home general evidence predicts transfer of private acquired practice | docs/w1-status.md (+3.86/+2.52pp, ρ 0.52/0.45; 1/3 fields negative) | **positive** | confirmatory + replicated |
| Stable pair experience → partner-specific coordination capital, context-bound; intact-pair state preserved as a portable asset (PairModule) | docs/w4-status.md (DiD +7.36/+8.46pp); w5b-status.md (W5B-01 +14.06/+5.99; W5B-04 +14.97/+7.38) | **positive** (scope: intact membership) | confirmatory + replicated + byte-identical reproduction |
| Raw structured history as agent-usable memory: see H1–H4 above (positive, strongest thread) | research/h1–h4 | **positive** | confirmatory |
| Feedback-acquired procedural memory owned by the agent: never measured (operating-point wall) | research/c3r_g2 G1 v1/v2 RESULTs | **UNMEASURED** | — |

**Reading:** capability production contracts and raw-history channels
are the two replicated Model→Agent positives. Agent-owned learned
procedures remain unmeasured and are now decoupled from the
architectural program.

## 3. Agents → Organizations (does organization add capability?)

| claim | evidence | outcome | strength |
|---|---|---|---|
| Two-agent swarm beats best-member under explicit destination law | docs/w3-status.md (+10.0/+8.77pp) | **positive** | confirmatory + replicated |
| Relationship capital as an independent portable asset: gate FAILED (−0.37pp) | docs/w3-status.md W3-07 | **did-not-meet-gate** | confirmatory |
| Organizational memory representations (W5A routing stats/archives) help after turnover: NULL, replicated; the only active component (routing) was harmful | docs/w5-status.md (−1.17/+0.72pp; routing −2.44pp; intact-pair control +5.96pp) | **null** (replicated, representation-specific) | confirmatory + replicated |
| Cross-pair composition of modules: discovery +5.99pp, replication +2.00pp inside band → FAILED | docs/w5b-status.md W5B-03 | **did-not-meet-gate** | confirmatory |
| Competitive talent market benefit concentrated in 1/3 orgs → consistency FAILED; coopetition NEGATIVE replicated (−4.69/−5.21pp); source drain replicated | docs/w7-status.md | **mixed/negative** | confirmatory + replicated |
| Role/chair synthesis (two roles + chair over raw evidence): +8.33pp surviving Holm, shell-equivalence control | research/h8/RESULT.md | **positive** (single study) | confirmatory, unreplicated |
| Compiled organization procedure vs equal-information raw evidence (C3R-G2 four-arm A/B/C/D + removal): DESIGNED, reviewed, never run | docs/c3r-g2-construction.md | **UNMEASURED** | — |

**Reading:** organizations have two confirmed capability sources —
explicit destination-law swarm structure and intact-pair state — plus
one unreplicated synthesis positive. No owned-knowledge mechanism has
ever beaten members' direct use of the same evidence.

## 4. Organizations → Institutions (durability, regeneration)

| claim | evidence | outcome | strength |
|---|---|---|---|
| Raw structured history survives complete member replacement and accumulates across 5 generations (deterministic) and with live successor models | research/h2 (48/48 vs 16/48), h3 (×5 generations), h4 (live) | **positive** | confirmatory + replicated |
| Piano primitive 1 — execution acknowledgement eliminates outcome-report mismatch (65%→0%, p=3e-08); primitive 2 — controller-decision broadcast resolves channel conflict (p≈1e-10); primitive 3 — opaque attested authority eliminates role failure/spoof capture (29/60→0/60) after two invalidated designs | experiment/piano-society-{factorial, intention-stress, phase4c}; authority extracted to src/resonance_world/authority.py | **positive** (mechanism primitives) | confirmatory (4c passed corrected gate) |
| Piano institutional memory across 100% turnover: four consecutive attempts approached but did not pass the frozen +3pp materiality gate (5: +0.62; 5B: 0.0 by design; 5C: +2.54, p=0.0039, 0 harmful units; 5D: +2.96, p=1.2e-4, 14/14 non-negative); documented bottleneck = memory FORMATION QUALITY, not the controller; information curve non-monotonic | experiment/piano-society-phase5*, EXTRACTION_DECISION (52aa261) | **did-not-meet-gate** (directionally consistent) | confirmatory ×4 |
| Organizational succession via modules: NULL replicated (0.00/−0.95pp) | docs/w5b-status.md W5B-02 | **null** | confirmatory + replicated |
| Regulatory/economic regeneration: source-protection vs service tradeoff NOT solved (protection costs 11–13pp); every W9 mechanism (criticality allocation, leasing, surplus, coalition) failed jointly; selected system empty; MSC estimator calibration positive | docs/w8-status.md, w9-status.md, w9-closeout.md | **negative** (replicated regimes) | confirmatory + replicated + double reproduction |

**Reading:** turnover survival is proven for the RAW history channel
and for extracted institutional PRIMITIVES (acknowledgement, broadcast,
attested authority) — but not for any organization-owned memory or
regenerative economic mechanism at materiality.

## 5. Cross-cutting

| claim | evidence | outcome |
|---|---|---|
| Recruitment: frozen evidence-driven recruiter beats random, non-inferior to purpose-built (not superior to equal-development) | docs/w2-status.md | positive/replicated; bounded |
| Observer validity: O1 reconstruction (8160 claims), O2 longitudinal distinctions — flat log achieves parity | research/o1, o2 | positive (validity only) |
| W0 live non-interference gate | docs/w0-* | **UNMEASURED** (documented only) |
| D-line campaign-path transport stability on the current stack | d2d→Q3-D2 chain | unmeasured/unstable |

## 6. Availability notes (honest boundaries)

- Piano phase 1–4C numeric results exist as BOUND numbers in successor
  preregistrations and GitHub artifacts; per-branch RESULT files were
  not deposited. Phase 3-v2 details and phase-4B full numbers are
  artifact-only (not read locally beyond what documents bound).
- acceptance/* branches contain independent acceptance JUDGMENTS
  (review apparatus + verdicts), not re-executions of experiments.
- The G1-v9 confirmatory protocol, Q3-D3, and "model-backed
  replication" (Piano 5D exit) are frozen-but-never-run.
- Nothing anywhere measures cross-model generalization of any
  architectural effect (governance ladder G4 is empty).

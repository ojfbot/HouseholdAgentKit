# ADR-004 — Profile scope is (account, agent, served person), enforced on our side

Status: proposed (Fork F, 2026-11-19). Affects K07, K08, K12, K13, K17, K24.

## Context
Agent Profiles (CAP-02) are published as one profile per agent with a cap, approve-each, separate history and revoke; rollout is expected around late November. B's Care Profiles needs a profile per person cared for, with a pinned ship-to, scoped usuals and `requested_by` (CAP-21, proposed). Fork C generalized the same need to multi-address shoppers and org principals with two approvers (CAP-28, proposed). 17 run-0 families need it.

## Decision
- The scope key is `(account, agent, served_person_id)`. `profile_id` appears on Mandate@1, Ledger@0, PantryState and every usuals lookup.
- K07 is authoritative on our side: leakage, address integrity and blocked categories are checked before any Walmart call, whatever Walmart supports.
- The twin (K17) ships the announced behaviour as the default config and the care profile as a labeled proposal.
- Fallback when CAP-21 is absent: one agent instance and one Agent Profile per person cared for.
- Multi-address and org principal share the same scope key; for Dec 2 they are stubs.

## Consequences
- B's six eval rows become oracles of K07, K08 and K12.
- When Walmart's profile fields are published, only K24's mapping changes.

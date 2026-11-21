# ADR-002 — Event bus only at human and time seams; direct calls inside the planning path

Status: proposed (Fork F, 2026-11-19). Affects K09, K10, K12, K14, K23 and the LangGraph agent graph.

## Context
A designed taco night as an event-driven, time-boxed poll on SNS/SQS (LocalStack) with an in-process fallback. Fork C's triggers and B's `rule.changed` / `address.changed` events need the same transport. Putting every hop on the bus would make the planning path slow and hard to trace.

## Decision
- **Direct, synchronous calls** (LangGraph nodes and tools) for the planning path: K01 → K21 → K02 → K24 → K04 → K03 → K11. These are request/response, sub-second to seconds, one process.
- **Events over the bus (K23)** only where a human or a clock sits in the middle: triggers (K09, K14), polls and votes (K10), decisions, ledger appends (K12), rule and address changes (K06, K07).
- K23 has one interface with two transports: LocalStack SNS/SQS and in-process. The same message-log test runs on both. Trace context rides in message attributes (LangSmith headers + W3C traceparent).
- FIFO by `poll_id`; idempotency keys on every response; dead-letter after 3 failures, and every DLQ item becomes an eval case.

## Alternatives
- Everything on the bus: uniform, but adds latency and trace fan-out to the hello world's 3-minute budget. Rejected.
- No bus (in-process callbacks only): simplest, but loses the "room is the family" fan-out and A's AWS story. Kept only as the fallback transport.

## Consequences
- Episode boundaries are clear: a trigger or a request starts an episode; the bus carries only what waits on people or time.
- Demo-night failure of Docker or Wi-Fi switches K23 to in-process with no code change.

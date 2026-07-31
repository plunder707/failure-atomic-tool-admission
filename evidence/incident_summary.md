# Sanitized Incident Record

## Observed Event

A long-running tool-use turn completed 30 tool executions before the model
returned one malformed structured call. The response contained:

- 931 visible characters;
- 795 characters of internal reasoning;
- one tool-call argument truncated inside a quoted JSON value;
- exactly 12,000 generated output tokens;
- `finish_reason=length`.

The runtime appended the assistant response to history before parsing every
call. An unconditional JSON parse raised an uncaught exception and terminated
the turn.

## Ruled-Out Causes

The model context was not exhausted. The tool-iteration ceiling was not
reached. The backing inference and application services remained healthy. The
failure occurred at the structured admission boundary.

## Source-Backed Ordering

The affected runtime used this order:

1. append the complete assistant response to history;
2. parse each tool call;
3. dispatch each successfully parsed call.

The public repository does not distribute the private runtime. The minimal
reconstruction in `reference_runtime_ordering.py` preserves the relevant
ordering and is bound by SHA-256 in the released fault-injection result.

## Authority Boundary

This record motivates the study. The deterministic experiment establishes the
general valid-then-malformed counterexample. Neither one alone proves that the
candidate protocol improves end-to-end model performance.

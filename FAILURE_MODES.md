# Failure behavior

This document is the authoritative failure-mode contract for the deployed
AEGIS request path. It distinguishes a failure to make or enforce a security
decision from an optional telemetry or detector-backend degradation. It applies
to the gateway and agent-gate integration paths; callers that invoke an
internal service directly are responsible for preserving the same contract.

## Fail closed: security decisions and execution

| Failure | Runtime behavior | Security result |
|---|---|---|
| Input-defense, output-defense, or policy-engine is unavailable, times out, returns an error, or returns malformed JSON to the gateway | The gateway stops the pipeline and returns `502 Bad Gateway`. It never returns the model output. | The chat request is not released. |
| Model-router is unavailable or fails | The gateway returns the surfaced provider error and does not release a model response. Provider fallback, when configured inside model-router, is a normal routing attempt rather than a bypass of input/output checks: every returned response still passes output defense and output policy. | No unchecked model response is released. |
| Agent-gate cannot reach policy-engine, or policy evaluation fails | Agent-gate returns `502 Bad Gateway`; it does not return `APPROVED`. | The caller receives no authorization to execute the tool. |
| Invalid or missing gateway, agent service, or reviewer key | The protected endpoint returns `401 Unauthorized`. | The request, approval read, or approval decision is rejected. |
| Approval is pending, expired, missing after an agent-gate restart, or the reviewer decision fails | No automatic approval occurs. Only a successful decision using a reviewer key can produce `APPROVED`. | The tool remains unapproved. |
| Policy-engine cannot load its policy pack at startup | Policy-engine exits instead of serving without a policy pack. | Dependent gateway and agent-gate requests fail rather than being evaluated without policy. |

The policy engine evaluates the configured pack's `default_action` for a
successful evaluation (the shipped pack uses `allow`). That is a policy choice,
not an outage fallback. `shadow` and `dry_run` are deliberately non-enforcing
evaluation modes and must not be used on a production enforcement path.

Policy hot reload is atomic: a reload error leaves the previously loaded pack
in service. Operators must treat a reload error as a failed configuration
deployment and correct it before retrying. **Changing `policies/default.yaml`
on disk is not live until restart or a successful `/v1/reload`.**

## Explicitly fail open: observability and backend degradation

| Failure | Runtime behavior | Residual risk / operator action |
|---|---|---|
| Audit service is unavailable or rejects a receipt | Input/output defense await the write and log a warning; policy-engine and agent-gate emit asynchronously and log a warning. The underlying decision and request are not blocked. | The decision may have no durable signed receipt. Restore audit service and investigate warning logs; do not infer that a missing receipt means a request was allowed. |
| Optional output-defense router judge is unavailable | Each unavailable judge produces an `ESCALATE` vote when the pre-fused score is at least `0.45`, otherwise an `ALLOW` vote. | Below that threshold, the unavailable judge alone does not block output. Other detectors and output policy still run. |
| Optional output-defense backtranslation router is unavailable or yields a mock echo | The detector uses its local stub fallback and records the execution backend and fallback reason in detector metadata. | Detection quality can differ from the router-backed detector; monitor the returned metadata and restore the router-backed path. |
| Input/output policy returns `transform` or `escalate_to_judge` | The gateway stops only on `block`; these actions complete the request path. | They are not enforcement actions in the gateway today. Production packs must use `block` for any condition that must stop a response. |
| Tool policy returns an action other than `block` or `escalate_to_judge` | Agent-gate maps it to `APPROVED`, including `transform` or an unrecognized action value. | Policy packs are trusted configuration. Do not use those actions for tool rules; action validation and a default-deny mapping remain an open hardening item. |

## Enforcement invariants

- A model output is released only after input defense, input policy,
  model-router, output defense, and output policy complete successfully.
- A tool is executed only by the integrating caller after agent-gate returns
  `APPROVED`; `AWAITING_HUMAN_APPROVAL` and `DENIED` are not execution grants.
- Agent service keys cannot decide approvals. Approval decisions require the
  separate reviewer-key scope.
- Audit availability is intentionally not a security-decision dependency. This
  prevents telemetry outages from becoming a service-wide denial of service,
  at the cost of possible receipt loss.

## Verification

Run the component tests after changing any behavior described here:

```bash
make test-go
make test-python
```

For a running stack, stop one decision dependency at a time and confirm the
gateway or agent-gate request fails without returning an output or an
`APPROVED` tool decision. Then stop only audit and confirm the request still
completes while the service logs an audit-delivery warning.

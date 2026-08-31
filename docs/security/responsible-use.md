# Responsible use

VulnoraIQ sends adversarial input to AI systems and builds and runs code you
import. Both are activities that need permission.

**Use it only against systems you own, or are explicitly authorised in writing to
assess.** The full policy is in [ACCEPTABLE_USE.md](../../ACCEPTABLE_USE.md).

## Before an assessment

1. Confirm you have written authorisation covering the specific system, the
   assessment window, and the techniques involved.
2. Confirm the target is the system you intend — check the base URL, port, and
   environment, not just the target name.
3. Confirm data handling: assessment prompts and responses are stored as
   evidence. Do not point VulnoraIQ at a system holding data you are not
   permitted to capture.
4. Decide who reviews the findings. VulnoraIQ produces evidence, not verdicts.

## How VulnoraIQ enforces this

Authorisation is not advisory. It is a gate:

- Every scan requires an explicit authorisation flag — `--authorised` on the CLI,
  the authorisation checklist in the console. Without it the scan raises
  `PermissionError` before a single request is sent.
- Targets outside loopback and private ranges are refused unless someone
  explicitly opted that target into external access.
- Targets with placeholder endpoints are refused, so a half-configured template
  can never be assessed by accident.
- Synthetic demo and fixture targets are refused in normal runtime and require an
  explicit environment flag.
- Destructive tests are off in every shipped safety profile, and request counts,
  concurrency, timeouts, and response sizes are all bounded.

## What VulnoraIQ will not do

- It does not run destructive or denial-of-service checks.
- It does not attempt to exploit a finding beyond what is needed to evidence it.
- It does not act on a target. The assistant explains and recommends; a human
  decides and applies.
- It does not turn a model's output into a command.

## Reporting a security issue

See [SECURITY.md](../../SECURITY.md).

## Related

- [Acceptable use policy](../../ACCEPTABLE_USE.md)
- [Security model](security-model.md)
- [Assessment assurance](assurance.md)

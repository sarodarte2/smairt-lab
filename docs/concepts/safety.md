# Safety model

SMAIRT safety checks are experimental technical safeguards. They do not certify regulatory,
institutional, contractual, export-control, human-subject, clinical, or other compliance. A
private repository is collaboration infrastructure, not proof of compliance. Controlled material
is explicitly unsupported as a compliance claim in this research preview.

## Classification and mode are separate

Classification describes the material:

- `public` — intended for open distribution; secrets remain prohibited.
- `unpublished` — ordinary prepublication research.
- `private` — confidential or proprietary work requiring private collaboration.
- `controlled` — regulated, contractual, export-controlled, human-subject, or similarly restricted
  material for which SMAIRT refuses to imply sufficient compliance.

Safety mode describes how aggressively SMAIRT responds:

| Behavior | Standard | Strict |
| --- | --- | --- |
| Intended use | Normal research collaboration | Sensitive or tightly restricted work |
| Unknown repository visibility | Warn where ordinary work can continue | Fail sharing and release gates closed |
| Secrets and private keys | Block in staged or tracked content | Same block |
| Raw protected data | Block protected paths and formats from Git | Same block with stronger local-only defaults |
| Protected summaries | Require an attested private repository | Keep local unless explicitly shareable and redaction-confirmed |
| Remote metadata | Explicit command; protected queries require `--confirm-remote` | Protected queries denied unless `--confirm-remote` |
| Release | Check files, history, secrets, visibility, and provenance | Add fresh private visibility and protected-summary checks |
| Compliance claim | None | None |

## Offline and remote behavior

`status`, `validate`, `doctor`, and terminal refreshes are offline. They do not hide a network
lookup. Refresh repository visibility explicitly:

```bash
smairt safety status --refresh-visibility --json
```

Remote literature queries, PDF downloads, GitHub visibility, HPC submission, and provider tests
are similarly explicit. A result from a remote metadata provider remains attributed input rather
than verified scientific evidence.

## Enforcement maturity

- SMAIRT CLI validation, immutable-run rules, mutation locks, transaction journals, Git checks,
  and publication gates are local controls within their documented scope.
- Harness hooks and permissions depend on client trust and configuration. They supplement rather
  than replace SMAIRT validation.
- Agent instructions and adversarial reviewers depend on model behavior. Review findings are
  advisory and cannot accept evidence or approve claims.
- Secret patterns and history scans are defense in depth, not comprehensive data-loss prevention.

The local process has the researcher's permissions. A malicious local user with equivalent access
can bypass or alter project files. Use institutional security, data-governance, and compliance
processes appropriate to the research.

## Before sharing

```bash
smairt doctor --json
smairt validate --staged
smairt safety status --refresh-visibility --json
smairt safety release-check --json
```

Review errors and warnings in context. A passing technical gate is not a substitute for scientific,
legal, ethical, or institutional review.

# Contributing to AEGIS

## Pull requests (Track A — production)

`main` is protected. Changes ship via PR only.

### Merge gate (safe self-merge)

Hamid is **not** required to click Merge on every PR. Auto-merge is enabled when **all** of the following are true:

1. **CI is green** — required status checks on `main` (core CI jobs; see branch protection).
2. **CodeRabbit has approved** the current head — CodeRabbit runs with `reviews.request_changes_workflow: true` (see `.coderabbit.yaml`). If CodeRabbit requests changes or leaves unresolved blocking comments, auto-merge does **not** proceed until those are fixed or Hamid explicitly overrides.

Arm auto-merge on an eligible PR (CI running / green, awaiting CodeRabbit):

```bash
gh pr merge --auto --squash <n>
```

Or rely on `.github/workflows/arm-auto-merge.yml`, which arms squash auto-merge for non-draft PRs targeting `main` once the workflow can see the PR.

### What still needs a human

- CodeRabbit **CHANGES_REQUESTED** or unresolved blocking threads → fix or get Hamid’s explicit call.
- Branch-protection admin bypass is not the normal path; prefer fixing the gate.
- Secrets, production credential changes, and irreversible infra still need Hamid’s judgment even if CI+CodeRabbit are green.

### CodeRabbit App

If reviews are missing on new PRs, install/enable: https://github.com/apps/coderabbitai for `hamidmatiny/aegis`.

<!-- probe: required_approving_review_count gate check; close without merging -->

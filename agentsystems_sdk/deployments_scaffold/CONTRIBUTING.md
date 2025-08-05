# Contributing to `agent-platform-deployments`

This repository contains the Docker-Compose deployment template for running the Agent Platform locally or in CI.  Keeping it tidy ensures every downstream project spins up reliably.

---
## Dev environment setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pre-commit install
pre-commit run --all-files   # first run auto-fixes
```

The hooks enforce **ruff**, **black**, **shellcheck**, and **hadolint** so commits stay consistent across AgentSystems repos.

---
## Continuous Integration (GitHub Actions)

All pull requests trigger `ci.yml`, which spins up the entire compose stack, polls the Gateway `/health` endpoint, and tears everything down.  If you break the stack, CI fails and the PR cannot be merged.

## Contribution guidelines

1. One logical change per pull-request.
2. Prefer declarative Compose overrides over ad-hoc shell scripts.
3. Update `README.md` if you change environment variables or service names.
4. Ensure `pre-commit run --all-files` passes before pushing.

Thanks for contributing! 🚀

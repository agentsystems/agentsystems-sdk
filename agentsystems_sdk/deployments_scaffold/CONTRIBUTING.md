# Contributing to Your AgentSystems Deployment

This directory contains the Docker Compose deployment configuration for running the AgentSystems platform locally. Keeping it well-maintained ensures your deployment runs reliably.

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
## Testing Your Deployment

You can verify your deployment is working correctly by:
1. Running `make up` to start the stack
2. Checking health endpoints: `curl http://localhost:18080/health`
3. Running `make ps` to see all services are healthy
4. Reviewing logs with `make logs`

## Contribution guidelines

1. One logical change per pull-request.
2. Prefer declarative Compose overrides over ad-hoc shell scripts.
3. Update `README.md` if you change environment variables or service names.
4. Ensure `pre-commit run --all-files` passes before pushing.

Thanks for contributing! 🚀

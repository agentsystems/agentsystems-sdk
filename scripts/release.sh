#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# scripts/release.sh – build & (optionally) publish agentsystems-sdk
# Mimics agent-template's build_and_release.sh semantics for Python / PyPI.
# ---------------------------------------------------------------------------
# Usage examples:
#   ./scripts/release.sh --version 0.3.0                         # build & lint only (dry run)
#   ./scripts/release.sh --version 0.3.0 --test                  # publish to Test PyPI
#   ./scripts/release.sh --version 0.3.0 --prod                  # publish to real PyPI
#   ./scripts/release.sh --version 0.3.0 --test --dry-run        # full checks, no upload
#
# Flags:
#   --version <semver>  : Desired package version (defaults to env VERSION or git describe)
#   --test              : Publish to Test PyPI (repository "testpypi")
#   --prod              : Publish to real PyPI  (repository "pypi")
#   --dry-run           : Run all checks/build but skip upload & git push
#   -h | --help         : Display this help
# ---------------------------------------------------------------------------
set -euo pipefail

function usage() {
  grep '^#' "$0" | sed -E 's/^# ?//'
  exit 0
}

VERSION="${VERSION:-}"
REPO="dry-run"   # options: dry-run, testpypi, pypi
DRY_RUN=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --version) VERSION="$2"; shift 2;;
    --test)    REPO="testpypi"; shift;;
    --prod)    REPO="pypi"; shift;;
        --dry-run) DRY_RUN=true; shift;;
    -h|--help) usage;;
    *) echo "Unknown arg: $1"; usage;;
  esac
done

# ----------------------------------------------------------------------------
# determine publish mode & tag creation
# ----------------------------------------------------------------------------
PUBLISH=false
if [[ "$REPO" != "dry-run" ]]; then
  PUBLISH=true
fi

CREATE_GIT_TAG=false
if [[ "$PUBLISH" == true && "$DRY_RUN" == false ]]; then
  CREATE_GIT_TAG=true
fi

# -------- version resolution ------------------------------------------------
# Fetch remote tags early so existence check includes them
if git rev-parse --is-inside-work-tree &>/dev/null; then
  git fetch --tags --quiet || true
fi
semver_regex='^([0-9]+)\.([0-9]+)\.([0-9]+)([A-Za-z0-9.-]*)?$'

if [[ -z "$VERSION" ]]; then
  if git rev-parse --is-inside-work-tree &>/dev/null; then
    VERSION="$(git describe --tags --abbrev=0 2>/dev/null | sed 's/^v//')"
    if [[ -z "$VERSION" ]]; then
      echo "No existing tags found – defaulting to 0.1.0"; VERSION="0.1.0";
    else
      IFS='.' read -r major minor patch <<< "$VERSION"
      PATCH=$((patch+1))
      VERSION="${major}.${minor}.${PATCH}"
    fi
  else
    echo "Not in a git repo and --version not provided"; exit 1;
  fi
fi

if ! [[ "$VERSION" =~ $semver_regex ]]; then
  echo "Invalid semantic version: $VERSION"; exit 1;
fi

GIT_TAG="v$VERSION"
if git rev-parse "$GIT_TAG" &>/dev/null; then
  echo "Git tag $GIT_TAG already exists – aborting."; exit 1;
fi

# -------- PyPI/TestPyPI version existence check -----------------------------
if [[ "$PUBLISH" == true ]]; then
  API_BASE="https://pypi.org/pypi"
  if [[ "$REPO" == "testpypi" ]]; then
    API_BASE="https://test.pypi.org/pypi"
  fi
  if command -v curl &>/dev/null && curl -sf -o /dev/null "$API_BASE/agentsystems-sdk/$VERSION/json"; then
    echo "Package version $VERSION already exists on $API_BASE – aborting." >&2
    exit 1
  fi
fi

echo "# ---------------------------"
echo "Version        : $VERSION"
echo "Repository     : $REPO"
echo "Git tag        : $GIT_TAG (create: $CREATE_GIT_TAG)"
echo "Dry-run        : $DRY_RUN"
echo "# ---------------------------"

# -------- verify version matches pyproject.toml -----------------------------
PY_FOR_VERSION=$(command -v python3 || command -v python)
if [[ -z "$PY_FOR_VERSION" ]]; then echo "Python interpreter not found"; exit 1; fi
FILE_VER=$("$PY_FOR_VERSION" - "$VERSION" <<'PY'
import sys, pathlib
try:
    import tomllib as _toml
except ModuleNotFoundError:
    try:
        import tomli as _toml  # type: ignore
    except ModuleNotFoundError:
        print("tomli is required for Python < 3.11", file=sys.stderr)
        sys.exit(1)
wanted = sys.argv[1]
text = pathlib.Path("pyproject.toml").read_text()
info = _toml.loads(text)
print(info["project"]["version"])
PY
)
if [[ "$FILE_VER" != "$VERSION" ]]; then
  echo "pyproject.toml declares version $FILE_VER but --version was $VERSION" >&2
  echo "Update pyproject.toml before releasing." >&2
  exit 1
fi

# -------- build -------------------------------------------------------------
if [[ "$DRY_RUN" == true ]]; then
  echo "[dry-run] Skipping build step. Would run: python -m build --sdist --wheel";
else
  # choose python interpreter (prefer 'python3', fallback to 'python')
  if command -v python3 &>/dev/null; then PY=python3; elif command -v python &>/dev/null; then PY=python; else echo "No python interpreter found"; exit 1; fi
  "$PY" -m build --sdist --wheel
  echo "Built distributions in dist/"
fi

# -------- twine publish -----------------------------------------------------
if [[ "$PUBLISH" == true ]]; then
  if [[ "$DRY_RUN" == true ]]; then
    echo "Would run: TWINE_REPOSITORY=$REPO twine upload -r $REPO dist/*";
  else
    TWINE_REPOSITORY="$REPO" twine upload -r "$REPO" dist/*
  fi
fi

# -------- commit & tag ------------------------------------------------------
if [[ "$CREATE_GIT_TAG" == true && "$DRY_RUN" == false ]]; then
  git tag -a "$GIT_TAG" -m "Release $GIT_TAG"
  git push origin "$GIT_TAG"
fi

echo "Done."

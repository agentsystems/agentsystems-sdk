#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# scripts/release.sh – build & (optionally) publish agentsystems-sdk
# Mimics agent-template's build_and_release.sh semantics for Python / PyPI.
# ---------------------------------------------------------------------------
# Usage examples:
#   ./scripts/release.sh --version 0.2.0          # bump/commit/tag/build wheel
#   ./scripts/release.sh --publish                # derive version from git tag & upload
#   VERSION=0.3.1 ./scripts/release.sh --publish  # env override + publish
#   ./scripts/release.sh --help                   # show help
#
# Flags:
#   --version <semver>  : Desired package version (defaults to env VERSION or git describe)
#   --publish           : After building wheel, upload to PyPI via twine (twine must be configured)
#   --git-tag           : Create and push git tag (vX.Y.Z) after successful build
#   --dry-run           : Validate & build only – do not commit, tag, or publish
#   -h | --help         : Display this help
# ---------------------------------------------------------------------------
set -euo pipefail

function usage() {
  grep '^#' "$0" | sed -E 's/^# ?//'
  exit 0
}

VERSION="${VERSION:-}"
PUBLISH=false
CREATE_GIT_TAG=false
DRY_RUN=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --version) VERSION="$2"; shift 2;;
    --publish) PUBLISH=true; shift;;
    --git-tag) CREATE_GIT_TAG=true; shift;;
    --dry-run) DRY_RUN=true; shift;;
    -h|--help) usage;;
    *) echo "Unknown arg: $1"; usage;;
  esac
done

# -------- version resolution ------------------------------------------------
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

echo "# ---------------------------"
echo "Version       : $VERSION"
echo "Git tag       : $GIT_TAG (create: $CREATE_GIT_TAG)"
echo "Publish to PyPI: $PUBLISH"
echo "Dry-run       : $DRY_RUN"
echo "# ---------------------------"

# -------- bump version in pyproject.toml ------------------------------------
if [[ "$DRY_RUN" == false ]]; then
  sed -i.bak -E "0,/^version = \".*\"/s//version = \"$VERSION\"/" pyproject.toml
  rm pyproject.toml.bak
  git add pyproject.toml
  git commit -m "release: $VERSION"
fi

# -------- build -------------------------------------------------------------
python -m build --sdist --wheel

echo "Built distributions in dist/"

# -------- twine publish -----------------------------------------------------
if [[ "$PUBLISH" == true ]]; then
  if [[ "$DRY_RUN" == true ]]; then
    echo "Would run: twine upload dist/*";
  else
    twine upload dist/*
  fi
fi

# -------- commit & tag ------------------------------------------------------
if [[ "$CREATE_GIT_TAG" == true && "$DRY_RUN" == false ]]; then
  git tag -a "$GIT_TAG" -m "Release $GIT_TAG"
  git push origin "$GIT_TAG"
fi

echo "Done."

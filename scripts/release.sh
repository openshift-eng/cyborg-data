#!/usr/bin/env bash
#
# release.sh — cut a tag-driven release of the Python package (orgdatacore).
#
# Pushing a `python-v<version>` tag to the canonical repo triggers
# .github/workflows/release.yml, which builds, gates (ruff + mypy + pytest) and:
#   final      (python-v0.2.0)    -> PyPI     (pauses for a required-reviewer approval)
#   prerelease (python-v0.2.0rc1) -> TestPyPI (no approval)
# The tag is the single source of truth for the version (hatch-vcs).
#
# This wrapper runs the safety checks a raw `git tag && git push` skips, then
# creates a signed (or annotated) tag and pushes it. See python/RELEASING.md.

set -euo pipefail

CANONICAL="openshift-eng/cyborg-data"
PREFIX="python-v"

usage() {
  cat >&2 <<'EOF'
Cut a tag-driven release of orgdatacore (the Python package).

Usage: scripts/release.sh [options] <version>

Examples:
  scripts/release.sh 0.1.0             final      -> PyPI (after approval)
  scripts/release.sh 0.2.0rc1          prerelease -> TestPyPI
  scripts/release.sh --dry-run 0.2.0   run every check, create/push nothing

Options:
  --ref <commit>     Commit to tag (default: tip of <remote>/main). Must be on
                     <remote>/main unless --allow-unmerged.
  --allow-unmerged   Skip the "commit is on <remote>/main" guard.
  --no-sign          Create an annotated (-a) tag instead of a signed (-s) one.
  --dry-run          Do everything except create and push the tag.
  -y, --yes          Do not prompt for confirmation.
  -h, --help         Show this help.

Environment:
  REMOTE   Git remote pointing at openshift-eng/cyborg-data
           (default: autodetected by URL, else "upstream").

Versioning: while on 0.x the API is unstable — breaking changes bump the MINOR
(0.1.0 -> 0.2.0) until it is frozen at 1.0.0.
EOF
}

die()  { printf 'release: %s\n' "$1" >&2; exit "${2:-1}"; }
step() { printf '==> %s\n' "$*" >&2; }
note() { printf '    %s\n' "$*" >&2; }

REF=""
ALLOW_UNMERGED=0
SIGN=1
DRY_RUN=0
YES=0
VERSION=""

while [ $# -gt 0 ]; do
  case "$1" in
    --ref)            REF="${2:-}"; [ -n "$REF" ] || die "--ref needs a value" 2; shift 2 ;;
    --allow-unmerged) ALLOW_UNMERGED=1; shift ;;
    --no-sign)        SIGN=0; shift ;;
    --dry-run)        DRY_RUN=1; shift ;;
    -y|--yes)         YES=1; shift ;;
    -h|--help)        usage; exit 0 ;;
    -*)               die "unknown option: $1 (try --help)" 2 ;;
    *)                [ -z "$VERSION" ] || die "unexpected extra argument: $1" 2; VERSION="$1"; shift ;;
  esac
done

[ -n "$VERSION" ] || die "missing <version> — e.g. 0.1.0 or 0.2.0rc1 (try --help)" 2

# Accept and strip a leading 'python-v' or 'v'.
VERSION="${VERSION#python-}"
VERSION="${VERSION#v}"

# Validate X.Y.Z with optional pre-release aN/bN/rcN. The workflow is the source
# of truth (PEP 440 via `packaging`); this is a fast local guard.
if ! printf '%s' "$VERSION" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+((a|b|rc)[0-9]+)?$'; then
  die "version '$VERSION' must be X.Y.Z or X.Y.Z{a,b,rc}N (e.g. 0.1.0, 0.2.0rc1)" 2
fi

TAG="${PREFIX}${VERSION}"
if printf '%s' "$VERSION" | grep -Eq '(a|b|rc)[0-9]+$'; then
  PRERELEASE=1
  TARGET="TestPyPI (pre-release; no approval gate)"
else
  PRERELEASE=0
  TARGET="PyPI (final; pauses for a required-reviewer approval)"
fi

cd "$(git rev-parse --show-toplevel)"

# Locate the remote that points at the canonical repo.
if [ -z "${REMOTE:-}" ]; then
  REMOTE="upstream"
  for r in $(git remote); do
    if git remote get-url "$r" 2>/dev/null | grep -q "$CANONICAL"; then
      REMOTE="$r"
      break
    fi
  done
fi
git remote get-url "$REMOTE" >/dev/null 2>&1 \
  || die "remote '$REMOTE' not found — set REMOTE=<name> pointing at $CANONICAL"

step "Fetching $REMOTE (branches + tags)"
git fetch --quiet --tags "$REMOTE" || die "git fetch $REMOTE failed"

# Working tree must be clean.
git diff --quiet && git diff --cached --quiet \
  || die "working tree is dirty — commit or stash before releasing"

# Resolve the commit to tag; default to the tip of <remote>/main.
[ -n "$REF" ] || REF="${REMOTE}/main"
COMMIT="$(git rev-parse --verify --quiet "${REF}^{commit}")" \
  || die "cannot resolve ref '$REF'"

# Releases come from a green main unless explicitly overridden.
if [ "$ALLOW_UNMERGED" -eq 0 ] && ! git merge-base --is-ancestor "$COMMIT" "${REMOTE}/main"; then
  die "commit ${COMMIT:0:12} is not on ${REMOTE}/main — merge first, or pass --allow-unmerged
    (releases must come from a green main; see python/RELEASING.md)"
fi

# The tag must be new (locally and on the remote).
if git rev-parse -q --verify "refs/tags/${TAG}" >/dev/null 2>&1; then
  die "tag ${TAG} already exists locally"
fi
if git ls-remote --tags --exit-code "$REMOTE" "refs/tags/${TAG}" >/dev/null 2>&1; then
  die "tag ${TAG} already exists on ${REMOTE}"
fi

# Changelog sanity for final releases: expect a '## [X.Y.Z]' heading.
CHANGELOG="python/CHANGELOG.md"
if [ "$PRERELEASE" -eq 0 ] && [ -f "$CHANGELOG" ] \
   && ! grep -Eq "^##[[:space:]]+\[${VERSION}\]" "$CHANGELOG"; then
  note "⚠ $CHANGELOG has no '## [${VERSION}]' section — rename [Unreleased] to"
  note "  [${VERSION}] with today's date first (see RELEASING.md). Continuing."
fi

# Prefer a signed tag when signing is configured; else annotated.
TAG_FLAG="-a"
if [ "$SIGN" -eq 1 ]; then
  if git config --get user.signingkey >/dev/null 2>&1 \
     || [ "$(git config --get tag.gpgSign 2>/dev/null || true)" = "true" ]; then
    TAG_FLAG="-s"
  else
    note "⚠ no signing key configured — creating an annotated (unsigned) tag"
    note "  (release.yml does not verify signatures; --no-sign silences this)"
  fi
fi

step "Release plan"
note "tag:       ${TAG}"
note "commit:    $(git show -s --format='%h %s' "$COMMIT")"
note "remote:    ${REMOTE} ($(git remote get-url "$REMOTE"))"
note "publishes: ${TARGET}"
note "tag type:  $([ "$TAG_FLAG" = "-s" ] && echo signed || echo 'annotated (unsigned)')"

if [ "$DRY_RUN" -eq 1 ]; then
  step "Dry run — nothing created or pushed."
  exit 0
fi

if [ "$YES" -eq 0 ]; then
  printf 'Create and push %s to %s? [y/N] ' "$TAG" "$REMOTE" >&2
  read -r ans || ans=""
  case "$ans" in
    y|Y|yes|YES) ;;
    *) die "aborted" ;;
  esac
fi

git tag "$TAG_FLAG" "$TAG" "$COMMIT" -m "$TAG"
step "Created ${TAG} at ${COMMIT:0:12}"
git push "$REMOTE" "refs/tags/${TAG}"
step "Pushed ${TAG} to ${REMOTE}"

printf '\n' >&2
step "Release workflow: https://github.com/${CANONICAL}/actions/workflows/release.yml"
if [ "$PRERELEASE" -eq 0 ]; then
  note "Approve the 'pypi' deployment (Actions -> the run -> Review deployments)"
  note "with a reviewer who is NOT the tag author. Nothing publishes until then;"
  note "the GitHub Release is created automatically after publish."
else
  note "Publishes to TestPyPI only. Smoke-test:"
  note "  pip install --index-url https://test.pypi.org/simple/ \\"
  note "    --extra-index-url https://pypi.org/simple/ 'orgdatacore==${VERSION}'"
fi

#!/usr/bin/env bash
# Create a JobOps repo from this plan bundle, ready for OmO.
#   ./omo-kit/setup-repo.sh ~/src/jobops
set -euo pipefail
KIT="$(cd "$(dirname "$0")" && pwd)"
PLAN_SRC="$(dirname "$KIT")"
DEST="${1:?usage: setup-repo.sh <target-dir>}"
[ -e "$DEST/plan" ] && { echo "refusing: $DEST/plan already exists" >&2; exit 1; }
mkdir -p "$DEST/plan/tools/tests"
# plan content (everything except the kit itself)
for item in PLAN.md 00-INDEX.md epics stories _source checkpoints.yaml; do
  cp -R "$PLAN_SRC/$item" "$DEST/plan/"
done
cp "$KIT/tools/build_state.py" "$DEST/plan/tools/"
cp "$KIT/tests/test_build_state.py" "$DEST/plan/tools/tests/"
cp "$KIT/AGENTS.md" "$DEST/"
cp -R "$KIT/.omo" "$DEST/"
cp -R "$KIT/prompts" "$DEST/plan/prompts"
cp "$KIT/BUILD-WITH-OMO.md" "$DEST/plan/"
[ -f "$DEST/plan/DOC-INBOX.md" ] || printf '# Doc inbox\n\nThings the build needs from Doc. Clear a checkpoint with:\n\n    python plan/tools/build_state.py clear <story>\n\n## Open\n\n## Done\n' > "$DEST/plan/DOC-INBOX.md"
python3 "$DEST/plan/tools/build_state.py" --plan "$DEST/plan" report > /dev/null
echo "JobOps repo ready at $DEST — next: cd $DEST && omo, then paste plan/prompts/01-bootstrap.md"

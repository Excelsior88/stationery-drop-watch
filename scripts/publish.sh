#!/usr/bin/env bash
# One-time publish to GitHub. Requires `gh auth login` (as Excelsior88) on this machine first.
set -euo pipefail
OWNER=Excelsior88
NAME=${1:-stationery-drop-watch}
cd "$(dirname "$0")/.."
gh repo view "$OWNER/$NAME" >/dev/null 2>&1 && { echo "$OWNER/$NAME already exists; pass another name"; exit 1; }
gh repo create "$OWNER/$NAME" --public --description "Restock tracker for limited journaling planners (Hobonichi Techo 2027 first)" --source . --remote origin --push
# Enable Pages with GitHub Actions as the source
gh api -X POST "repos/$OWNER/$NAME/pages" -f build_type=workflow || gh api -X PUT "repos/$OWNER/$NAME/pages" -f build_type=workflow
gh workflow enable check-and-deploy.yml -R "$OWNER/$NAME" || true
gh workflow run check-and-deploy.yml -R "$OWNER/$NAME" --ref main
echo "Repo:  https://github.com/$OWNER/$NAME"
echo "Site:  https://$(echo $OWNER | tr A-Z a-z).github.io/$NAME/"

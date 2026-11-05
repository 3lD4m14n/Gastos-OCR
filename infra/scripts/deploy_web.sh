#!/usr/bin/env bash
# Compila la web con las salidas de GastosProd y la publica en Amplify Hosting.
set -euo pipefail

STACK=GastosProd
REGION=us-east-2
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

output() {
  aws cloudformation describe-stacks --region "$REGION" --stack-name "$STACK" \
    --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text
}

APP_ID="$(output AmplifyAppId)"
BRANCH="$(output AmplifyBranch)"

cd "$ROOT/web"
# Las variables de entorno tienen prioridad sobre web/.env.local, que apunta a desarrollo.
VITE_API_URL="$(output ApiUrl)" \
VITE_COGNITO_AUTHORITY="$(output Issuer)" \
VITE_COGNITO_CLIENT_ID="$(output WebClientId)" \
VITE_COGNITO_DOMAIN="$(output LoginDomain)" \
  npm run build

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
(cd dist && python3 -m zipfile -c "$WORK/web.zip" ./*)

read -r JOB_ID UPLOAD_URL < <(
  aws amplify create-deployment --region "$REGION" --app-id "$APP_ID" --branch-name "$BRANCH" \
    --query '[jobId, zipUploadUrl]' --output text
)
curl --fail --silent --show-error --upload-file "$WORK/web.zip" "$UPLOAD_URL"
aws amplify start-deployment --region "$REGION" --app-id "$APP_ID" --branch-name "$BRANCH" \
  --job-id "$JOB_ID" --query 'jobSummary.status' --output text

for _ in $(seq 1 60); do
  STATUS="$(aws amplify get-job --region "$REGION" --app-id "$APP_ID" --branch-name "$BRANCH" \
    --job-id "$JOB_ID" --query 'job.summary.status' --output text)"
  case "$STATUS" in
    SUCCEED) echo "Publicada en $(output WebUrl)"; exit 0 ;;
    FAILED | CANCELLED) echo "La publicación terminó en $STATUS" >&2; exit 1 ;;
  esac
  sleep 5
done
echo "La publicación sigue en curso tras 5 minutos (job $JOB_ID)" >&2
exit 1

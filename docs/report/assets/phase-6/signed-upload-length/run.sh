#!/usr/bin/env bash
#
# Chrome -> nginx (TLS, HTTP/2, the production snippets/media.conf) -> the
# dev stack's RustFS, with upload URLs signed the way the app now signs them:
# the declared size included. The question is whether a real browser's
# upload still carries the length all the way to the bucket -- if nginx
# turned it into a chunked body, every upload on the VPS would be a 403.
#
#   docs/report/assets/phase-6/signed-upload-length/run.sh
#
# Needs: the dev stack up (its `storage`, its network, its backend container
# to sign with), 127.0.0.1:443 free, Chrome, and frontend/node_modules. Run
# from the repository root. Everything it starts and uploads is removed.
set -euo pipefail
export MSYS_NO_PATHCONV=1

here="$(cd "$(dirname "$0")" && pwd)"
repo="$(cd "${here}/../../../../.." && pwd)"
work="$(mktemp -d)"
run="$(date +%s)"

# Docker Desktop and Node on Windows want Windows paths.
native() { if command -v cygpath > /dev/null; then cygpath -w "$1"; else echo "$1"; fi; }
compose=(docker compose -f "$(native "${repo}/infra/docker-compose.yml")")

cleanup() {
    docker rm -f upload-front > /dev/null 2>&1 || true
    rm -rf "${work}"
}
trap cleanup EXIT
cleanup
mkdir -p "${work}/certs"

docker run --rm \
    -v "$(native "${repo}/docs/report/assets/phase-6/storage-decision"):/spike:ro" \
    -v "$(native "${work}/certs"):/out" \
    devpath-backend:dev python /spike/make_cert.py /out devpath.localhost

docker run -d --name upload-front --network devpath_default -p 127.0.0.1:443:443 \
    -v "$(native "${here}/nginx.conf"):/etc/nginx/nginx.conf:ro" \
    -v "$(native "${repo}/infra/nginx/snippets"):/etc/nginx/snippets:ro" \
    -v "$(native "${work}/certs"):/certs:ro" \
    nginx:1.27-alpine > /dev/null
for _ in $(seq 30); do
    curl -sfk --resolve devpath.localhost:443:127.0.0.1 https://devpath.localhost/ > /dev/null && break
    sleep 1
done
echo "== nginx $(docker exec upload-front nginx -v 2>&1 | sed 's/.*\///'), media.conf from infra/nginx/snippets"

"${compose[@]}" exec -T backend python - sign "${run}" < "${here}/tickets.py" > "${work}/cases.json"

status=0
echo "== Chrome, XHR PUT as frontend/lib/api/storage.ts does it"
NODE_PATH="$(native "${repo}/frontend/node_modules")" \
    node "$(native "${here}/h2-upload.cjs")" "$(native "${work}/cases.json")" || status=$?

echo "== what the bucket holds afterwards (then deleted)"
"${compose[@]}" exec -T backend python - check "${run}" < "${here}/tickets.py" || status=$?

echo "== what nginx received from Chrome (access log, query string left out)"
docker logs upload-front 2>/dev/null | grep -E '^(PUT|GET) /devpath-media' || true
exit "${status}"

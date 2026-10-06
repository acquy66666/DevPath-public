#!/usr/bin/env bash
#
# One self-hosted S3 server, behind nginx, driven by the app's own storage
# adapter (spike.py). Run from the repository root:
#
#   docs/report/assets/phase-6/storage-decision/run.sh seaweedfs|rustfs
#
# Needs the dev backend image (devpath-backend:dev) for the adapter and boto3
# as locked. Everything it starts is removed on exit; the result is printed.
set -euo pipefail
export MSYS_NO_PATHCONV=1

candidate="${1:?seaweedfs or rustfs}"
here="$(cd "$(dirname "$0")" && pwd)"
backend="$(cd "${here}/../../../../../backend" && pwd)"
work="$(mktemp -d)"
net=s3spike

# Docker Desktop on Windows wants Windows paths for bind mounts.
native() { if command -v cygpath > /dev/null; then cygpath -w "$1"; else echo "$1"; fi; }

cleanup() {
    docker rm -f spike-s3 spike-front > /dev/null 2>&1 || true
    docker network rm "${net}" > /dev/null 2>&1 || true
    rm -rf "${work}"
}
trap cleanup EXIT
cleanup
mkdir -p "${work}/certs"
docker network create "${net}" > /dev/null

case "${candidate}" in
    seaweedfs)
        image=chrislusf/seaweedfs:latest
        docker run -d --name spike-s3 --network "${net}" \
            -v "$(native "${here}/seaweedfs-s3.json"):/etc/seaweedfs/s3.json:ro" \
            "${image}" server -s3 -s3.config=/etc/seaweedfs/s3.json -dir=/data > /dev/null
        port=8333
        ;;
    rustfs)
        # The version and digest the compose files run (since 05/10/2026).
        image=rustfs/rustfs:1.0.1@sha256:1803faef57627e2d9c2e7d89d655d712ddded5389040054987163043fecb6a3c
        docker run -d --name spike-s3 --network "${net}" \
            -e RUSTFS_ACCESS_KEY=spikeaccess \
            -e RUSTFS_SECRET_KEY=spike-secret-0123456789 \
            "${image}" > /dev/null
        port=9000
        ;;
    *)
        echo "unknown candidate ${candidate}" >&2
        exit 2
        ;;
esac

docker run --rm -v "$(native "${here}"):/spike:ro" -v "$(native "${work}/certs"):/out" \
    devpath-backend:dev python /spike/make_cert.py /out

sed "s/UPSTREAM/spike-s3:${port}/g" "${here}/nginx.conf" > "${work}/nginx.conf"
# NO_HOST_HEADER=1 is the control: without Host passed through, the server
# checks each signature against its own name and every presigned URL fails.
if [[ "${NO_HOST_HEADER:-0}" == 1 ]]; then
    grep -v 'proxy_set_header Host' "${here}/s3_proxy.conf" > "${work}/s3_proxy.conf"
else
    cp "${here}/s3_proxy.conf" "${work}/s3_proxy.conf"
fi
docker run -d --name spike-front --network "${net}" --network-alias spike-front \
    -v "$(native "${work}/nginx.conf"):/etc/nginx/nginx.conf:ro" \
    -v "$(native "${work}/s3_proxy.conf"):/etc/nginx/s3_proxy.conf:ro" \
    -v "$(native "${work}/certs"):/certs:ro" \
    nginx:1.27-alpine > /dev/null

echo "== ${candidate}: $(docker image inspect "${image}" --format '{{index .RepoDigests 0}}')"
status=0
docker run --rm --network "${net}" \
    -v "$(native "${backend}"):/app:ro" \
    -v "$(native "${here}"):/spike:ro" \
    -v "$(native "${work}/certs"):/certs:ro" \
    -e CANDIDATE="${candidate}" \
    -e ADMIN_ENDPOINT="http://spike-s3:${port}" \
    -e AWS_CA_BUNDLE=/certs/cert.pem \
    -e PYTHONDONTWRITEBYTECODE=1 \
    -w /app devpath-backend:dev python /spike/spike.py || status=$?

echo "== memory after the run: $(docker stats --no-stream --format '{{.MemUsage}}' spike-s3)"
exit "${status}"

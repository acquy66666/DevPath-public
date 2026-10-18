#!/usr/bin/env bash
# D1: an upload the way a visitor's browser makes one on https://<DOMAIN>.
#
#   docs/report/assets/phase-6/named-tunnel/tunnel_upload.sh devpath-01.me
#
# The API calls (sign-up, ticket, confirm) go to the stack on this machine
# (--resolve to 127.0.0.1; nginx's self-signed certificate, hence -k). Every
# PUT to the presigned URL and the anonymous GET go by the public name:
# DNS -> Cloudflare's edge -> the named tunnel -> nginx -> the bucket. The
# account is a throwaway @e2e.devpath.example one; scripts.purge_e2e removes it.
set -euo pipefail

domain="$1"
site="https://${domain}"
local_api=(--resolve "${domain}:443:127.0.0.1" -k -sS)
work="$(mktemp -d)"
trap 'rm -rf "${work}"' EXIT

json() { python -c "import json,sys; print(json.load(sys.stdin)$1)"; }

email="tunnel-upload-$(openssl rand -hex 5)@e2e.devpath.example"
token="$(curl "${local_api[@]}" -X POST "${site}/api/v1/auth/register" \
    -H 'Content-Type: application/json' \
    -d "{\"email\":\"${email}\",\"password\":\"$(openssl rand -hex 12)\",\"full_name\":\"Tunnel Upload\"}" \
    | json '["access_token"]')"
auth=(-H "Authorization: Bearer ${token}")
echo "account: ${email}"

ticket() {  # size -> writes upload_url and storage_key
    curl "${local_api[@]}" -X POST "${site}/api/v1/users/me/avatar" "${auth[@]}" \
        -H 'Content-Type: application/json' \
        -d "{\"filename\":\"me.png\",\"content_type\":\"image/png\",\"size_bytes\":$1}" > "${work}/ticket.json"
    json '["upload_url"]' < "${work}/ticket.json" > "${work}/url"
    json '["storage_key"]' < "${work}/ticket.json" > "${work}/key"
}

put() {  # file -> "status server" of a PUT through Cloudflare
    curl -sS -o "${work}/put-body" -w '%{http_code} %header{server}' --max-time 300 \
        --expect100-timeout 30 -H 'Content-Type: image/png' -T "$1" "$(cat "${work}/url")"
}

head -c 1048576 /dev/urandom > "${work}/1mb"
ticket 1048576
echo "ticket host: $(cut -d/ -f3 < "${work}/url")"
echo "PUT 1 MiB, declared 1 MiB, through the tunnel: $(put "${work}/1mb")"

ticket 1048576
head -c 1048577 /dev/urandom > "${work}/1mb+1"
echo "PUT 1 MiB + 1 byte, declared 1 MiB, through the tunnel: $(put "${work}/1mb+1")"

# Cloudflare Free refuses a request body over 100 MB at its edge. Expect:
# 100-continue lets it say so before curl sends the body.
truncate -s 105906176 "${work}/101mib"
echo "PUT 101 MiB through the tunnel: $(put "${work}/101mib")"

ticket 1048576
put "${work}/1mb" > /dev/null
avatar="$(curl "${local_api[@]}" -X POST "${site}/api/v1/users/me/avatar/complete" "${auth[@]}" \
    -H 'Content-Type: application/json' -d "{\"storage_key\":\"$(cat "${work}/key")\"}" | json '["avatar_url"]')"
echo "avatar: ${avatar}"
curl -sS -o "${work}/got" -w 'anonymous GET through the tunnel: %{http_code} %header{server} %header{content-type}\n' "${avatar}"
if cmp -s "${work}/1mb" "${work}/got"; then echo "bytes read back: identical"; else echo "bytes read back: DIFFERENT"; fi

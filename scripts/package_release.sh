#!/usr/bin/env bash
set -euo pipefail

version="${1:-0.1.0}"
output_root="${2:-dist}"
platform="${3:-linux/amd64}"
image="ops-agent-core:${version}"
base_image="ops-agent-runtime-base:${version}"
toxiproxy_image="ghcr.io/shopify/toxiproxy:2.12.0"
bundle="${output_root}/ops-agent-core-${version}"

if [[ -e "${bundle}" || -e "${bundle}.tar.gz" ]]; then
  echo "Release output already exists: ${bundle}" >&2
  exit 1
fi

docker buildx build \
  --platform "${platform}" \
  --load \
  --file Dockerfile.base \
  --tag "${base_image}" \
  .
docker buildx build \
  --platform "${platform}" \
  --load \
  --build-arg "OPS_AGENT_BASE_IMAGE=${base_image}" \
  --tag "${image}" \
  .
docker pull --platform "${platform}" "${toxiproxy_image}"

mkdir -p "${bundle}/docs/deployment" "${bundle}/product-skills"
docker save "${base_image}" "${image}" "${toxiproxy_image}" \
  | gzip -9 > "${bundle}/ops-agent-offline-images-${version}.tar.gz"
cp Dockerfile Dockerfile.base .dockerignore pyproject.toml docker-compose.yml .env.example "${bundle}/"
printf 'OPS_AGENT_IMAGE=%s\nOPS_AGENT_BASE_IMAGE=%s\nOPS_AGENT_TOXIPROXY_IMAGE=%s\n' \
  "${image}" "${base_image}" "${toxiproxy_image}" > "${bundle}/.env.release"
cp docs/deployment/01-skill-installation.md "${bundle}/docs/deployment/"
cp docs/deployment/02-docker-deployment.md "${bundle}/docs/deployment/"
cp runtime-data/product-skills/README.md "${bundle}/product-skills/README.md"
tar -C "${output_root}" -czf "${bundle}.tar.gz" "ops-agent-core-${version}"

echo "Created ${bundle}.tar.gz"

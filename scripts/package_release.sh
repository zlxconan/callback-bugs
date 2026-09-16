#!/usr/bin/env bash
set -euo pipefail

version="${1:-0.1.0}"
output_root="${2:-dist}"
image="ops-agent-core:${version}"
bundle="${output_root}/ops-agent-core-${version}"

if [[ -e "${bundle}" || -e "${bundle}.tar.gz" ]]; then
  echo "Release output already exists: ${bundle}" >&2
  exit 1
fi

docker build --tag "${image}" .

mkdir -p "${bundle}/docs/deployment" "${bundle}/product-skills"
docker save "${image}" | gzip -9 > "${bundle}/ops-agent-core-${version}.image.tar.gz"
cp docker-compose.yml .env.example "${bundle}/"
printf 'OPS_AGENT_IMAGE=%s\n' "${image}" > "${bundle}/.env.release"
cp docs/deployment/01-skill-installation.md "${bundle}/docs/deployment/"
cp docs/deployment/02-docker-deployment.md "${bundle}/docs/deployment/"
cp runtime-data/product-skills/README.md "${bundle}/product-skills/README.md"
tar -C "${output_root}" -czf "${bundle}.tar.gz" "ops-agent-core-${version}"

echo "Created ${bundle}.tar.gz"

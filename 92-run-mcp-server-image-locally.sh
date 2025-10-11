#!/bin/bash
# -*- mode:shell-script; coding:utf-8; -*-

set -e

imagename=products-mcp-service

if [[ ! -f .image-timestamp ]]; then
    echo "File .image-timestamp not found. Please run ./91-build-image-for-local-execution.sh first." >&2
    exit 1
fi

timestamp=$(cat .image-timestamp)

if ! podman image exists "${imagename}:${timestamp}" >/dev/null 2>&1; then
    echo "Image '${imagename}:${timestamp}' not found locally." >&2
    echo "Please run ./91-build-image-for-local-execution.sh to build it." >&2
    exit 1
fi

echo "using Image ${imagename}:${timestamp}" >&2
podman run -it -e "PORT=8088"   --env-file .env -p 5055:8088 --init "${imagename}":"${timestamp}"

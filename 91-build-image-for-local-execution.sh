#!/bin/bash
# -*- mode:shell-script; coding:utf-8; -*-

set -e

#source ./lib/utils.sh

# check_shell_variables GOOGLE_CLOUD_PROJECT
timestamp=$(date '+%Y%m%d-%H%M%S')
echo "${timestamp}" > .image-timestamp

cd mcp-server
imagename=products-mcp-service

podman build -t "${imagename}":"${timestamp}" -f Dockerfile


#!/bin/bash
# -*- mode:shell-script; coding:utf-8; -*-

set -e
service_name=products-mcp-service

source ./lib/utils.sh

check_shell_variables CLOUDRUN_PROJECT_ID CLOUDRUN_REGION

cd mcp-server
gcloud run deploy "$service_name" \
  --source . \
  --project $CLOUDRUN_PROJECT_ID \
  --region $CLOUDRUN_REGION \
  --cpu 1 \
  --memory '512Mi' \
  --min-instances 0 \
  --max-instances 1 \
  --no-use-http2 \
  --allow-unauthenticated

  # --service-account "$sa_email" \
  # --update-secrets=TOMTOM_APIKEY=tomtom-apikey:latest \
  # --update-secrets=GMAPS_APIKEY=gmaps-apikey:latest \
  # --set-env-vars="GOOGLE_CLOUD_PROJECT=${GOOGLE_CLOUD_PROJECT}" \

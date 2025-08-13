#!/bin/bash
# -*- mode:shell-script; coding:utf-8; -*-

set -e

source ./lib/utils.sh

printf "\nThis script signs you in, and grants permissions to read and write sheets to\n"
printf "any application that can read Application Default Credentials.\n\n"

check_shell_variables CLOUDRUN_PROJECT_ID 
check_required_commands gcloud

needed_scopes=(openid
  https://www.googleapis.com/auth/userinfo.email
  https://www.googleapis.com/auth/cloud-platform
  https://www.googleapis.com/auth/spreadsheets
  https://www.googleapis.com/auth/drive)

# Join the array elements with a comma
joined_scope_string=$(
  IFS=,
  echo "${needed_scopes[*]}"
)

gcloud auth application-default login --scopes "$joined_scope_string"
#gcloud auth application-default set-quota-project "$CLOUDRUN_PROJECT_ID"

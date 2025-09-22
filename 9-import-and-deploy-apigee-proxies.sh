#!/bin/bash
# -*- mode:shell-script; coding:utf-8; -*-

# Copyright © 2024,2025 Google LLC.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

PROXY_NAME="mcp-access-control"
service_name="products-mcp-service"
need_wait=0

source ./lib/utils.sh

import_and_deploy_apiproxy() {
  local proxy_name dir project env rev files name dirpath
  proxy_name=$1
  dir=$2
  project=$3
  env=$4

  dirpath="${dir}/apiproxy"
  files=("$dirpath/*.xml")
  if [[ ${#files[@]} -eq 1 ]]; then
    name="${files[0]}"
    name=$(basename "${name%.*}")
    # import only if the dir has changed
      printf "Importing %s into %s...\n" "$proxy_name" "${project}"
      rev=$(apigeecli apis create bundle -f "${dirpath}" -n "$proxy_name" --org "$project" --token "$TOKEN" --disable-check | jq ."revision" -r)
      printf "Deploying proxy %s revision %s into %s/%s...\n" "$proxy_name" "$rev" "$project" "$env"
      apigeecli apis deploy --wait --name "$proxy_name" --ovr --rev "$rev" --org "$project" --env "$env" --token "$TOKEN" --disable-check &
      need_wait=1
  else
    printf "could not determine name of proxy to import\n"
  fi
}

get_element_text() {
  local element_name=$1
  local file_name=$2
  # -P: Use Perl-compatible regex for lookarounds
  # -o: Only print the matched part of the line
  # (?<=<tag>): Positive lookbehind, asserts that the opening tag is before our match
  # .*: Matches the content (the text you want)
  # (?=</tag>): Positive lookahead, asserts that the closing tag is after our match
  grep -oP "(?<=<${element_name}>).*(?=</${element_name}>)" "$file_name"
}

replace_element_text() {
  local element_name=$1
  local contents=$2
  local file_name=$3
  local match_pattern="<${element_name}>.\\+</${element_name}>"
  local replace_pattern="<${element_name}>${contents}</${element_name}>"
  local sed_script="s#${match_pattern}#${replace_pattern}#"
  #  in-place editing
  local SEDOPTION="-i"
  if [[ "$OSTYPE" == "darwin"* ]]; then
    SEDOPTION='-i \x27\x27'
  fi
  sed "$SEDOPTION" -e "${sed_script}" "${file_name}"
}

replace_property_value() {
  local property_name=$1
  local new_value=$2
  local file_name=$3
  local match_pattern="^${property_name} *= *.\\+"
  local replace_pattern="${property_name} = ${new_value}"
  local sed_script="s#${match_pattern}#${replace_pattern}#"
  #printf "sed script: %s\n" "$sed_script"
  #  in-place editing
  local SEDOPTION="-i"
  if [[ "$OSTYPE" == "darwin"* ]]; then
    SEDOPTION='-i \x27\x27'
  fi
  sed "$SEDOPTION" -e "${sed_script}" "${file_name}"
}


# ====================================================================
check_shell_variables CLOUDRUN_SERVICE_NAME CLOUDRUN_PROJECT_ID \
  APIGEE_PROJECT_ID APIGEE_ENV APIGEE_HOST OIDC_SERVER

check_required_commands gcloud jq

if [[ ! -d "$HOME/.apigeecli/bin" ]]; then
  printf "apigeecli is not installed in the default location (%s).\n" "$HOME/.apigeecli/bin" >&2
  printf "Please install it from https://github.com/apigee/apigeecli\n" >&2
  exit 1
fi
export PATH=$PATH:$HOME/.apigeecli/bin

if ! gcloud run services describe "${service_name}" \
  --project "$CLOUDRUN_PROJECT_ID" --format='value(status.url)' 2>&1 >>/dev/null; then
  printf "The %s service is not deployed to cloud run. Please deploy it.\n" "$service_name"
  exit 1
fi

service_url=$(gcloud run services describe "${service_name}" \
  --project "$CLOUDRUN_PROJECT_ID" --format='value(status.url)')

tmpdir=$(mktemp -d)
printf "Temporary directory: %s\n" "$tmpdir"
cp -r ./apis "$tmpdir"

printf "The URL for the Backend Service in the proxy should be %s...\n" "${service_url}"
TARGET_1="$tmpdir/apis/${PROXY_NAME}/apiproxy/targets/target1.xml"
if [[ ! -f "$TARGET_1" ]]; then
  printf "Missing the target in the API Proxy. %s\n" "$TARGET_1"
  exit 1
fi

cur_url=$(get_element_text "URL" "${TARGET_1}")
if [[ ! "x${cur_url}" = "x${service_url}" ]]; then
  printf "Replacing the target URL in the API Proxy...\n"
  replace_element_text "URL" "${service_url}" "${TARGET_1}"
else
  printf "The target URL for the API Proxy is unchanged...\n"
fi


replace_property_value "oidc_server_issuer" "${OIDC_SERVER}" \
                       "$tmpdir/apis/${PROXY_NAME}/apiproxy/resources/properties/settings.properties"

replace_property_value "oidc_server_jwks" "${OIDC_SERVER}.well-known/jwks.json" \
                       "$tmpdir/apis/${PROXY_NAME}/apiproxy/resources/properties/settings.properties"

replace_property_value "oidc_server" "$OIDC_SERVER" \
                       "$tmpdir/apis/well-known-endpoints/apiproxy/resources/properties/settings.properties"


TOKEN=$(gcloud auth print-access-token)
import_and_deploy_apiproxy "$PROXY_NAME" "$tmpdir/apis/${PROXY_NAME}" "${APIGEE_PROJECT_ID}" "$APIGEE_ENV"
import_and_deploy_apiproxy "well-known-endpoints" "$tmpdir/apis/well-known-endpoints" "${APIGEE_PROJECT_ID}" "$APIGEE_ENV"

if [[ $need_wait -eq 1 ]]; then
  printf "Waiting...\n"
  wait
fi

rm -fr $tmpdir

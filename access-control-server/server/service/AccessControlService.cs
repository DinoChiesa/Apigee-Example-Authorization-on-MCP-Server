// Copyright © 2025 Google LLC.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     https://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.
//

using System;
using System.Collections.Generic;
using System.Net.Http;
using System.Text.Json;
using System.Text.RegularExpressions;
using System.Threading.Tasks;
using Apigee.ExternalCallout;
using Grpc.Core;
using Microsoft.Extensions.Caching.Memory;
using Microsoft.Extensions.Logging;

namespace Server
{
    public class AccessControlService : ExternalCalloutService.ExternalCalloutServiceBase
    {
        private readonly ILogger _logger;
        private readonly IMemoryCache _memoryCache;
        private readonly RemoteDataService _rds;
        private readonly String buildTime;

        public AccessControlService(
            ILoggerFactory loggerFactory,
            IMemoryCache memoryCache,
            IHttpClientFactory httpClientFactory
        )
        {
            _logger = loggerFactory.CreateLogger<AccessControlService>();
            _memoryCache = memoryCache;
            _rds = new RemoteDataService(_memoryCache, httpClientFactory);
            buildTime = cmdwtf.BuildTimestamp.BuildTimeUtc.ToString(
                "o",
                System.Globalization.CultureInfo.InvariantCulture
            );
        }

        private Func<List<string>, string, bool?> GetRuleChecker(
            List<string> groups,
            string httpVerb,
            string mcpMethod,
            string toolName
        )
        {
            _logger.LogInformation(
                $"GetRuleChecker:  Verb={httpVerb} method={mcpMethod} tool={toolName} groups=[{string.Join(",", groups)}]."
            );
            return (rule, logContext) =>
            {
                if (rule != null && rule.Count >= 5)
                {
                    // rule[0] = group, rule[1] = httpVerb, rule[2] = mcpMethod, rule[3] = toolName, rule[4] = permission
                    _logger.LogInformation(
                        $"CheckRule: group({rule[0]}|[{string.Join(",", groups)}]) verb({rule[1]}|{httpVerb}) method({rule[2]}|{mcpMethod}) tool({rule[3]}|{toolName})"
                    );
                    bool ruleApplies = false;
                    bool groupMatch = groups.Contains(rule[0].Trim());
                    if (groupMatch)
                    {
                        bool isGet = string.Equals(httpVerb, "GET", StringComparison.Ordinal);
                        if (isGet)
                        {
                            ruleApplies = string.Equals(
                                rule[1].Trim(),
                                httpVerb,
                                StringComparison.Ordinal
                            );

                            _logger.LogInformation(
                                $"CheckRule: {logContext}. Verb='{httpVerb}'. Rule='[{string.Join(",", rule)}]'."
                            );
                        }
                        else
                        {
                            bool isToolCall = string.Equals(
                                "tools/call",
                                mcpMethod,
                                StringComparison.Ordinal
                            );
                            if (isToolCall)
                            {
                                ruleApplies =
                                    string.Equals(
                                        rule[2].Trim(),
                                        mcpMethod,
                                        StringComparison.Ordinal
                                    )
                                    && string.Equals(
                                        rule[3].Trim(),
                                        toolName,
                                        StringComparison.Ordinal
                                    );

                                _logger.LogInformation(
                                    $"CheckRule: {logContext}. Method='{mcpMethod}', Tool='{toolName}'. Rule='[{string.Join(",", rule)}]'."
                                );
                            }
                            else
                            {
                                ruleApplies = string.Equals(
                                    rule[2].Trim(),
                                    mcpMethod,
                                    StringComparison.Ordinal
                                );

                                _logger.LogInformation(
                                    $"CheckRule: {logContext}. Method='{mcpMethod}'. Rule='[{string.Join(",", rule)}]'."
                                );
                            }
                        }
                    }
                    else
                    {
                        _logger.LogInformation($"CheckRule: no group match");
                    }
                    return ruleApplies
                        ? string.Equals(rule[4], "ALLOW", StringComparison.OrdinalIgnoreCase)
                        : null;
                }
                return null;
            };
        }

        private async Task<Boolean> EvaluateAccess(
            Dictionary<string, object> token,
            string verb,
            string method,
            string toolName
        )
        {
            GsheetData rules = await _rds.GetAccessControlRules();
            if (rules?.Values != null)
            {
                // initialize to default value
                List<string> groups = new List<string> { "none" };
                // Extract the value for the "az_groups" key. The value comes out as an 'object'.
                if (
                    token.TryGetValue("az_groups", out object groupsObject)
                    && groupsObject is JsonElement groupsElement
                )
                {
                    try
                    {
                        groups = groupsElement.Deserialize<List<string>>();
                    }
                    catch (JsonException) { }
                }
                // groups will now contain either the default list or the extracted list.

                // pass 1: check for a match on the groups associated to the user
                var ruleChecker = GetRuleChecker(groups, verb, method, toolName);
                foreach (var ruleEntry in rules.Values)
                {
                    bool? allowed = ruleChecker(ruleEntry, $"Specific rule match");
                    if (allowed.HasValue)
                    {
                        _logger.LogInformation(
                            $"EvaluateAccess: allowed={allowed.Value}  method={method}, tool={toolName}"
                        );
                        return allowed.Value;
                    }
                }

                // pass 2: check for "any"
                var anyRuleChecker = GetRuleChecker(
                    new List<string> { "any" },
                    verb,
                    method,
                    toolName
                );
                foreach (var ruleEntry in rules.Values)
                {
                    bool? allowed = anyRuleChecker(ruleEntry, $"Rule(any) match");
                    if (allowed.HasValue)
                    {
                        _logger.LogInformation(
                            $"EvaluateAccess: allowed (method={method}, tool={toolName})"
                        );
                        return allowed.Value;
                    }
                }

                _logger.LogInformation(
                    $"EvaluateAccess: No matching rule found. ({string.Join(",", groups)}, {method}, {toolName}). Denying access."
                );
            }
            else
            {
                _logger.LogInformation(
                    $"EvaluateAccess: No rules found. Configuration error? Denying access."
                );
            }
            return false;
        }

        public override async Task<MessageContext> ProcessMessage(
            MessageContext msgCtxt,
            ServerCallContext context
        )
        {
            _logger.LogInformation($"> ProcessMessage");

            if (msgCtxt.Request != null)
            {
                // ====================================================================
                // Diagnostics
                // Inject a header with the current date, and the buildTime of this service.
                msgCtxt.Request.Headers["x-extcallout-id"] = new Strings
                {
                    Strings_ = { $"now {DateTime.UtcNow.ToString("o")} build {buildTime}" },
                };

                // Also inject a header showing the count of AdditionalFlowVariables
                msgCtxt.Request.Headers["x-extcallout-variable-count"] = new Strings
                {
                    Strings_ = { $"{msgCtxt.AdditionalFlowVariables.Keys.Count}" },
                };
                // ====================================================================

                // retrieve the data provided by the API Proxy
                var jwt_payload = msgCtxt
                    .AdditionalFlowVariables["accesscontrol.jwt_payload"]
                    .String;
                var tokenPayload = JsonSerializer.Deserialize<Dictionary<string, object>>(
                    jwt_payload
                );

                var http_verb = msgCtxt.AdditionalFlowVariables["accesscontrol.http_verb"].String;
                var mcp_method = msgCtxt.AdditionalFlowVariables["accesscontrol.mcp_method"].String;
                var toolName = msgCtxt.AdditionalFlowVariables["accesscontrol.mcp_tool"].String;
                bool isAllowed = await EvaluateAccess(
                    tokenPayload,
                    http_verb,
                    mcp_method,
                    toolName
                );
                msgCtxt.AdditionalFlowVariables.Add("accesscontrol.result", new FlowVariable());
                msgCtxt.AdditionalFlowVariables["accesscontrol.result"].String = isAllowed
                    ? "ALLOW"
                    : "DENY";
            }
            return msgCtxt;
        }
    }
}

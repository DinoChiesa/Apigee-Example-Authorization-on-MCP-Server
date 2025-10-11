function doFilter(jsonString, allowList) {
  const json = JSON.parse(jsonString);
  if (json.result.tools) {
    json.result.tools = json.result.tools.filter(
      (t) => allowList.indexOf(t.name) !== -1,
    );
    return JSON.stringify(json);
  }
  return null;
}

function processString(inputString, allowList) {
  const ssePrefix = "event: message";
  const dataPrefix = "data: ";

  if (inputString.startsWith(ssePrefix)) {
    const dataIndex = inputString.indexOf(dataPrefix);
    if (dataIndex !== -1) {
      const jsonString = inputString.substring(dataIndex + dataPrefix.length);
      const frame = inputString.substring(0, dataIndex + dataPrefix.length);
      const filtered = doFilter(jsonString, allowList);
      return filtered ? frame + filtered : null;
    } else {
      context.setVariable("js-error", "could not find data: frame");
      return null;
    }
  }
  return doFilter(inputString, allowList);
}

try {
  // get list of tools from API Product variable
  const v = properties["allow-list-var"];
  if (v) {
    const payload = context.getVariable(properties["content-var"]);
    if (payload) {
      const allowList = JSON.parse(context.getVariable(v));
      const processed = processString(payload, allowList);
      if (processed) {
        context.setVariable(properties["content-var"], processed);
      } else {
        context.setVariable("js-result", "empty result from filtering attempt");
      }
    } else {
      context.setVariable("js-result", "empty json string");
    }
  } else {
    context.setVariable("js-error", "allow-list-var is not present");
  }
} catch (exc1) {
  context.setVariable("js-error", "exception while filtering: " + exc1);
  context.setVariable("js-error-stack", "" + exc1.stack);
}

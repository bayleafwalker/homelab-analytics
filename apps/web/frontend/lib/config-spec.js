const VERSION_ID_RE = /^(.*?)([_-]v)(\d+)$/i;

export function parseColumnsSpec(spec) {
  return String(spec || "")
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line && !line.startsWith("#"))
    .map((line) => {
      const [namePart, typePart, requiredPart] = line.split(",").map((part) => part.trim());
      if (!namePart || !typePart) {
        throw new Error("Each dataset column line must include name,type[,required].");
      }
      const requiredValue = String(requiredPart || "required").toLowerCase();
      if (!["required", "optional", "true", "false"].includes(requiredValue)) {
        throw new Error(
          `Unknown required flag '${requiredPart}' for column '${namePart}'. Use required or optional.`
        );
      }
      return {
        name: namePart,
        type: typePart,
        required: requiredValue === "required" || requiredValue === "true"
      };
    });
}

export function formatColumnsSpec(columns = []) {
  return columns
    .map((column) => `${column.name},${column.type},${column.required ? "required" : "optional"}`)
    .join("\n");
}

export function parseRulesSpec(spec) {
  return String(spec || "")
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line && !line.startsWith("#"))
    .map((line) => {
      const [targetPart, sourcePart, defaultPart, functionPart] = line
        .split(",")
        .map((part) => part.trim());
      if (!targetPart) {
        throw new Error(
          "Each mapping rule line must include target_column[,source_column,default_value,function_key]."
        );
      }
      return {
        target_column: targetPart,
        source_column: sourcePart || null,
        default_value: defaultPart || null,
        function_key: functionPart || null
      };
    });
}

export function formatRulesSpec(rules = []) {
  return rules
    .map((rule) => {
      const cells = [
        rule.target_column,
        rule.source_column || "",
        rule.default_value || "",
        rule.function_key || ""
      ];
      while (cells.length > 1 && !cells[cells.length - 1]) {
        cells.pop();
      }
      return cells.join(",");
    })
    .join("\n");
}

export function suggestVersionId(recordId, nextVersion) {
  const match = VERSION_ID_RE.exec(String(recordId || ""));
  if (!match) {
    return `${recordId}_v${nextVersion}`;
  }
  return `${match[1]}${match[2]}${nextVersion}`;
}

"use client";

import React, { useState } from "react";

import { PolicyForm } from "@/components/policy-form";
import { POLICY_TEMPLATES, TEMPLATE_EXCLUSIONS } from "@/lib/policy-templates";

/**
 * Start a policy from a template, or from a blank form.
 *
 * A template prefills only what it can state truthfully. Anything it cannot
 * decide for the operator — a spending limit, which source matters, how stale
 * is too stale — is left empty and marked required, and the form refuses to
 * submit until it is supplied. That is the whole of the template discipline:
 * a disabled template is parameterized, never misleading.
 */
export function PolicyAuthoringPanel({ publications, ruleSchemaVersion }) {
  const [selectedId, setSelectedId] = useState(null);
  const selected = POLICY_TEMPLATES.find((template) => template.id === selectedId);

  return (
    <div className="stack">
      <div className="entityList">
        {POLICY_TEMPLATES.map((template) => (
          <article className="entityCard" key={template.id}>
            <div className="entityHeader">
              <div>
                <strong>{template.name}</strong>
                <div className="muted">{template.summary}</div>
              </div>
              <span
                className="pill"
                data-tone={selectedId === template.id ? "accent" : "neutral"}
              >
                template
              </span>
            </div>
            <div className="specBlock">
              <div className="muted">Reads</div>
              <div>{template.reads}</div>
            </div>
            {template.requiredInputs.length > 0 ? (
              <div className="muted">
                You must supply: {template.requiredInputs.join(", ")}. Until then
                this policy cannot be created or enabled.
              </div>
            ) : (
              <div className="muted">
                Needs no further input beyond a name.
              </div>
            )}
            <div className="buttonRow">
              <button
                className="ghostButton"
                type="button"
                onClick={() =>
                  setSelectedId(selectedId === template.id ? null : template.id)
                }
              >
                {selectedId === template.id ? "Clear template" : "Use this template"}
              </button>
            </div>
          </article>
        ))}
      </div>

      <details>
        <summary>Templates deliberately not offered</summary>
        <div className="compactStack">
          {TEMPLATE_EXCLUSIONS.map((exclusion) => (
            <p className="muted" key={exclusion.id}>
              <strong>{exclusion.id}</strong> — {exclusion.reason}
            </p>
          ))}
        </div>
      </details>

      <PolicyForm
        key={selectedId || "blank"}
        publications={publications}
        ruleSchemaVersion={ruleSchemaVersion}
        template={selected || null}
        action="/control/policies/create"
      />
    </div>
  );
}

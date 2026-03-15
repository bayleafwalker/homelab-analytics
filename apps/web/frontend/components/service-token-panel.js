"use client";

import { useState } from "react";

const SCOPE_OPTIONS = [
  { value: "reports:read", label: "reports:read" },
  { value: "runs:read", label: "runs:read" },
  { value: "ingest:write", label: "ingest:write" },
  { value: "admin:write", label: "admin:write" }
];

function defaultScopesForRole(role) {
  if (role === "admin") {
    return ["admin:write", "ingest:write", "runs:read", "reports:read"];
  }
  if (role === "operator") {
    return ["ingest:write", "runs:read", "reports:read"];
  }
  return ["reports:read"];
}

export function ServiceTokenPanel({ initialTokens }) {
  const [tokens, setTokens] = useState(initialTokens);
  const [tokenName, setTokenName] = useState("");
  const [role, setRole] = useState("reader");
  const [scopes, setScopes] = useState(defaultScopesForRole("reader"));
  const [expiresAt, setExpiresAt] = useState("");
  const [revealedToken, setRevealedToken] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [revokingTokenId, setRevokingTokenId] = useState("");

  async function createToken(event) {
    event.preventDefault();
    setIsSubmitting(true);
    setError("");
    setSuccess("");
    setRevealedToken("");
    try {
      const response = await fetch("/control/service-tokens", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          token_name: tokenName,
          role,
          scopes,
          expires_at: expiresAt ? new Date(expiresAt).toISOString() : null
        })
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.detail || payload.error || "Could not create service token.");
      }
      setTokens((current) => [...current, payload.service_token]);
      setRevealedToken(payload.token_value || "");
      setSuccess("Service token created. Copy it now; it will not be shown again.");
      setTokenName("");
      setExpiresAt("");
      setRole("reader");
      setScopes(defaultScopesForRole("reader"));
    } catch (requestError) {
      setError(requestError.message || "Could not create service token.");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function revokeToken(tokenId) {
    setRevokingTokenId(tokenId);
    setError("");
    setSuccess("");
    try {
      const response = await fetch(`/control/service-tokens/${tokenId}/revoke`, {
        method: "POST"
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.detail || payload.error || "Could not revoke service token.");
      }
      setTokens((current) =>
        current.map((token) =>
          token.token_id === tokenId ? payload.service_token : token
        )
      );
      setSuccess("Service token revoked.");
      if (revealedToken.startsWith(`hst_${tokenId}.`)) {
        setRevealedToken("");
      }
    } catch (requestError) {
      setError(requestError.message || "Could not revoke service token.");
    } finally {
      setRevokingTokenId("");
    }
  }

  return (
    <div className="stack compactStack">
      <form className="adminFormGrid" onSubmit={createToken}>
        <div className="field">
          <label htmlFor="service-token-name">Token name</label>
          <input
            id="service-token-name"
            value={tokenName}
            onChange={(event) => setTokenName(event.target.value)}
            placeholder="home-assistant"
            required
          />
        </div>
        <div className="field">
          <label htmlFor="service-token-role">Role</label>
          <select
            id="service-token-role"
            value={role}
            onChange={(event) => {
              const nextRole = event.target.value;
              setRole(nextRole);
              setScopes(defaultScopesForRole(nextRole));
            }}
          >
            <option value="reader">reader</option>
            <option value="operator">operator</option>
            <option value="admin">admin</option>
          </select>
        </div>
        <div className="field">
          <label htmlFor="service-token-expiry">Expires at</label>
          <input
            id="service-token-expiry"
            value={expiresAt}
            onChange={(event) => setExpiresAt(event.target.value)}
            type="datetime-local"
          />
        </div>
        <div className="field spanThree">
          <label>Scopes</label>
          <div className="choiceGrid">
            {SCOPE_OPTIONS.map((scopeOption) => (
              <label className="checkboxRow" key={scopeOption.value}>
                <input
                  checked={scopes.includes(scopeOption.value)}
                  onChange={(event) => {
                    setScopes((current) => {
                      if (event.target.checked) {
                        return Array.from(new Set([...current, scopeOption.value]));
                      }
                      return current.filter((value) => value !== scopeOption.value);
                    });
                  }}
                  type="checkbox"
                />
                <span>{scopeOption.label}</span>
              </label>
            ))}
          </div>
        </div>
        <button className="primaryButton inlineButton" disabled={isSubmitting} type="submit">
          {isSubmitting ? "Creating..." : "Create service token"}
        </button>
      </form>

      {error ? <div className="errorBanner">{error}</div> : null}
      {success ? <div className="successBanner">{success}</div> : null}
      {revealedToken ? (
        <div className="tokenReveal">
          <div className="metricLabel">Copy once</div>
          <code>{revealedToken}</code>
        </div>
      ) : null}

      {tokens.length === 0 ? (
        <div className="empty">No service tokens created yet.</div>
      ) : (
        <div className="stack compactStack">
          {tokens.map((token) => (
            <section className="adminCard" key={token.token_id}>
              <div className="adminCardHeader">
                <div>
                  <div className="metricLabel">{token.token_name}</div>
                  <div className="muted">
                    {token.token_id} / created {token.created_at}
                  </div>
                </div>
                <span className="userBadge">
                  {token.role} / {token.revoked ? "revoked" : token.expired ? "expired" : "active"}
                </span>
              </div>
              <div className="metaGrid">
                <div className="metaItem">
                  <div className="metricLabel">Scopes</div>
                  <div className="muted">{token.scopes.join(", ") || "n/a"}</div>
                </div>
                <div className="metaItem">
                  <div className="metricLabel">Last used</div>
                  <div>{token.last_used_at || "never"}</div>
                </div>
                <div className="metaItem">
                  <div className="metricLabel">Expires</div>
                  <div>{token.expires_at || "never"}</div>
                </div>
              </div>
              {!token.revoked ? (
                <div className="buttonRow">
                  <button
                    className="ghostButton inlineButton"
                    disabled={revokingTokenId === token.token_id}
                    onClick={() => revokeToken(token.token_id)}
                    type="button"
                  >
                    {revokingTokenId === token.token_id ? "Revoking..." : "Revoke token"}
                  </button>
                </div>
              ) : null}
            </section>
          ))}
        </div>
      )}
    </div>
  );
}

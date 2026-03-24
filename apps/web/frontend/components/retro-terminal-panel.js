"use client";

import { useMemo, useState } from "react";

function fallbackExecution(commandLine, message) {
  return {
    command_name: "client-error",
    normalized_command: commandLine.trim(),
    status: "failed",
    mutating: false,
    exit_code: 70,
    stdout_lines: [],
    stderr_lines: [message],
    result: { message }
  };
}

function statusLabel(status) {
  if (status === "succeeded") {
    return "OK";
  }
  if (status === "rejected") {
    return "REJECTED";
  }
  return "FAILED";
}

export function RetroTerminalPanel({ initialCommands }) {
  const [commandLine, setCommandLine] = useState("status");
  const [history, setHistory] = useState([]);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const quickLaunch = useMemo(
    () => initialCommands.map((command) => command.usage),
    [initialCommands]
  );

  async function runCommand(event) {
    event.preventDefault();
    const nextCommand = commandLine.trim();
    if (!nextCommand) {
      return;
    }
    setIsSubmitting(true);
    try {
      const response = await fetch("/retro/terminal/execute", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ command_line: nextCommand })
      });
      const payload = await response.json().catch(() => ({}));
      const execution = payload.execution || fallbackExecution(nextCommand, "No execution payload returned.");
      setHistory((current) => [execution, ...current]);
    } catch (error) {
      setHistory((current) => [
        fallbackExecution(nextCommand, error?.message || "Command request failed."),
        ...current
      ]);
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <section className="retroTerminal retroPanel">
      <div className="retroSectionHeader">
        <div>
          <div className="retroEyebrow">Admin Terminal</div>
          <h2>Allowlisted command entry</h2>
        </div>
        <span className="retroTag">SYNC / NO SHELL ACCESS</span>
      </div>

      <div className="retroHintRow">
        {quickLaunch.map((usage) => (
          <button
            key={usage}
            className="retroHintButton"
            type="button"
            onClick={() => setCommandLine(usage)}
          >
            {usage}
          </button>
        ))}
      </div>

      <form className="retroPromptRow" onSubmit={runCommand}>
        <label className="retroPromptLabel" htmlFor="retro-terminal-command">
          ops@crt&gt;
        </label>
        <input
          id="retro-terminal-command"
          className="retroCommandInput"
          value={commandLine}
          onChange={(event) => setCommandLine(event.target.value)}
          autoComplete="off"
          spellCheck="false"
        />
        <button className="retroActionButton" type="submit" disabled={isSubmitting}>
          {isSubmitting ? "Running" : "Execute"}
        </button>
      </form>

      <div className="retroCommandCatalog retroStackCompact">
        {initialCommands.map((command) => (
          <div key={command.name} className="retroCatalogRow">
            <div>
              <div className="retroMonoStrong">{command.usage}</div>
              <div className="retroMuted">{command.description}</div>
            </div>
            <span className="retroTag" data-variant={command.mutating ? "warn" : "neutral"}>
              {command.mutating ? "MUTATING" : "READ-ONLY"}
            </span>
          </div>
        ))}
      </div>

      <div className="retroHistory retroStackCompact">
        {history.length === 0 ? (
          <div className="retroEmptyState">Run a command to populate the terminal transcript.</div>
        ) : (
          history.map((entry, index) => (
            <article key={`${entry.normalized_command}-${index}`} className="retroHistoryEntry">
              <div className="retroHistoryHeader">
                <div className="retroMonoStrong">&gt; {entry.normalized_command || "(empty)"}</div>
                <span className="retroTag" data-variant={entry.status === "succeeded" ? "ok" : "warn"}>
                  {statusLabel(entry.status)} / {entry.exit_code}
                </span>
              </div>
              {entry.stdout_lines?.length > 0 ? (
                <pre className="retroTranscript">{entry.stdout_lines.join("\n")}</pre>
              ) : null}
              {entry.stderr_lines?.length > 0 ? (
                <pre className="retroTranscript retroTranscriptError">{entry.stderr_lines.join("\n")}</pre>
              ) : null}
            </article>
          ))
        )}
      </div>
    </section>
  );
}

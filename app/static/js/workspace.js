"use strict";

(() => {
  const root = document.getElementById("coding-workspace");
  if (!root) return;

  const languageSelect = document.getElementById("workspace-language");
  const textarea = document.getElementById("workspace-code");
  const output = document.getElementById("workspace-output");
  const diagnosticDetail = document.getElementById("diagnostic-detail");
  const editorStatus = document.getElementById("editor-status");
  const buddyResponse = document.getElementById("workspace-buddy-response");
  const csrfToken = root.dataset.csrfToken;
  const samples = {
    python: 'def greet(name):\n    print(f"Hello, {name}!")\n\ngreet("world")',
    javascript: 'function greet(name) {\n  console.log(`Hello, ${name}!`);\n}\n\ngreet("world");',
    c: '#include <stdio.h>\n\nint main(void) {\n    printf("Hello, world!\\n");\n    return 0;\n}',
    cpp: '#include <iostream>\n\nint main() {\n    std::cout << "Hello, world!\\n";\n    return 0;\n}',
  };
  const modeForLanguage = {
    python: "python",
    javascript: "javascript",
    c: "text/x-csrc",
    cpp: "text/x-c++src",
  };
  let editor = null;
  let latestDiagnostic = null;
  let buddyBusy = false;

  if (window.CodeMirror) {
    editor = window.CodeMirror.fromTextArea(textarea, {
      mode: modeForLanguage.python,
      lineNumbers: true,
      indentUnit: 4,
      tabSize: 4,
      lineWrapping: false,
      viewportMargin: 20,
    });
    editor.setSize("100%", 420);
    editorStatus.textContent = "Syntax highlighting ready. Changes stay in this tab until you request a check or share with Buddy.";
  } else {
    textarea.classList.add("editor-fallback");
    editorStatus.textContent = "Syntax-highlighting library unavailable; plain-text editor is ready. Check your connection to load CodeMirror.";
  }

  function getCode() {
    return editor ? editor.getValue() : textarea.value;
  }

  function setCode(code) {
    if (editor) editor.setValue(code);
    else textarea.value = code;
    latestDiagnostic = null;
    diagnosticDetail.hidden = true;
  }

  function languageName() {
    return languageSelect.options[languageSelect.selectedIndex].text;
  }

  function displayDiagnostic(diagnostic) {
    latestDiagnostic = diagnostic;
    diagnosticDetail.replaceChildren();
    if (!diagnostic) {
      diagnosticDetail.hidden = true;
      return;
    }
    const heading = document.createElement("strong");
    heading.textContent = `${languageName()} · ${diagnostic.error}`;
    const location = document.createElement("span");
    location.textContent = diagnostic.line
      ? `Line ${diagnostic.line}${diagnostic.column ? `, column ${diagnostic.column}` : ""}`
      : "Location unavailable";
    const code = document.createElement("code");
    code.textContent = diagnostic.code || "";
    diagnosticDetail.append(heading, location, code);
    diagnosticDetail.hidden = false;
  }

  async function checkSyntax() {
    output.textContent = "Checking syntax only. No code will be executed.";
    try {
      const response = await fetch("/api/workspace/diagnostics", {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken,
        },
        credentials: "same-origin",
        body: JSON.stringify({ language: languageSelect.value, code: getCode() }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error?.message || "Syntax check failed.");
      if (!result.available) {
        latestDiagnostic = null;
        displayDiagnostic(null);
        output.textContent = result.message;
        return result;
      }
      displayDiagnostic(result.diagnostic);
      output.textContent = result.diagnostic
        ? `${result.language} syntax error: ${result.diagnostic.error}`
        : result.message;
      return result;
    } catch (error) {
      output.textContent = `Diagnostics unavailable: ${error.message}`;
      return null;
    }
  }

  function redactedCode(source) {
    return source
      .replace(/^([^\n]*(?:api[_-]?key|secret|password|token|credential)[^\n]*?\s*[:=]\s*).+$/gim, "$1[redacted]")
      .replace(/\bAIza[0-9A-Za-z_-]{30,}\b/g, "[redacted-key]")
      .replace(/\b(?:sk-[A-Za-z0-9_-]{16,}|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b/g, "[redacted-token]")
      .replace(/\b(Bearer\s+)[A-Za-z0-9._~+\/-]+=*/gi, "$1[redacted]");
  }

  function buddyPrompt(action, code, diagnostic) {
    const requests = {
      explain: "Explain the actual diagnostic below in beginner-friendly language. Point to the relevant line and give one small next step; do not claim the program was run.",
      hint: "Give one progressive hint about this code and diagnostic. Do not reveal the complete fix unless I ask for it.",
      debug: "Debug this code using the diagnostic as observed evidence. Separate evidence from hypotheses and suggest the smallest next check. Do not claim execution.",
    };
    const errorText = diagnostic
      ? `${diagnostic.error}${diagnostic.line ? ` at line ${diagnostic.line}${diagnostic.column ? `, column ${diagnostic.column}` : ""}` : ""}\nRelevant code: ${diagnostic.code || "not provided"}`
      : "No syntax diagnostic is available. No program output or runtime error exists because execution is unavailable.";
    return `${requests[action]}\n\nSelected language: ${languageSelect.value}\nActual diagnostic: ${errorText}\nExecution status: unavailable; the code was not run.\n\nEditor code (secret-like values redacted):\n\`\`\`${languageSelect.value}\n${code}\n\`\`\``;
  }

  async function askBuddy(action, button) {
    if (buddyBusy) return;
    const code = redactedCode(getCode()).slice(0, 8_000);
    buddyBusy = true;
    button.disabled = true;
    buddyResponse.hidden = false;
    buddyResponse.textContent = "Buddy is thinking…";
    window.setBuddyExpression?.("thinking");
    try {
      const response = await fetch("/api/buddy/respond", {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken,
        },
        credentials: "same-origin",
        body: JSON.stringify({
          message: buddyPrompt(action, code, latestDiagnostic),
          language: languageSelect.value,
          workspace_context: true,
        }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error?.message || `Buddy request failed (${response.status}).`);
      const label = result.response.is_mock ? "MOCK · simulated reply" : "GEMINI · Google AI";
      buddyResponse.textContent = `${label}: ${result.response.content}`;
      window.setBuddyExpression?.("encouraging");
    } catch (error) {
      buddyResponse.textContent = `Buddy could not respond: ${error.message}. No fallback response was generated.`;
      window.setBuddyExpression?.("confused");
    } finally {
      buddyBusy = false;
      button.disabled = false;
    }
  }

  languageSelect.addEventListener("change", () => {
    if (editor) editor.setOption("mode", modeForLanguage[languageSelect.value]);
    document.getElementById("editor-filename").textContent = `scratch.${{ python: "py", javascript: "js", c: "c", cpp: "cpp" }[languageSelect.value]}`;
    latestDiagnostic = null;
    displayDiagnostic(null);
    output.textContent = `${languageName()} selected. Static syntax diagnostics are available for Python only; execution is unavailable.`;
  });

  document.getElementById("load-sample").addEventListener("click", () => {
    setCode(samples[languageSelect.value]);
    output.textContent = `${languageName()} sample loaded. No program has run.`;
  });
  document.getElementById("reset-code").addEventListener("click", () => {
    setCode(samples[languageSelect.value]);
    output.textContent = "Editor reset to the selected language's sample. No program has run.";
  });
  document.getElementById("check-syntax").addEventListener("click", checkSyntax);
  document.getElementById("run-code").addEventListener("click", async () => {
    await checkSyntax();
    output.textContent = `${output.textContent}\nExecution unavailable: no isolated runner is configured. No program has run.`;
  });

  const brokenMission = "def average(values):\n    total = 0\n    for value in values:\n        total += value\n    return total / len(value)\n\nprint(average([2, 4, 6]))";
  document.getElementById("mission-load").addEventListener("click", () => {
    languageSelect.value = "python";
    languageSelect.dispatchEvent(new Event("change"));
    setCode(brokenMission);
    output.textContent = "Mission code loaded. The displayed TypeError is part of the challenge; this program has not run.";
  });
  document.getElementById("mission-verify").addEventListener("click", async () => {
    const resultElement = document.getElementById("mission-result");
    if (languageSelect.value !== "python") {
      resultElement.textContent = "Select Python before verifying this mission.";
      return;
    }
    try {
      const response = await fetch("/api/workspace/missions/average/verify", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
        credentials: "same-origin",
        body: JSON.stringify({ language: "python", code: getCode() }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error?.message || "Mission verification failed.");
      resultElement.textContent = `${result.message}${result.xp_awarded ? ` +${result.xp_awarded} XP` : ""}`;
      document.getElementById("mission-total").textContent = `Verified mission XP: ${result.total_xp}`;
      if (result.passed) window.setBuddyExpression?.("celebrating");
      else window.setBuddyExpression?.("encouraging");
    } catch (error) {
      resultElement.textContent = `Mission verifier unavailable: ${error.message}. No XP was awarded.`;
    }
  });

  document.querySelectorAll("[data-buddy-action]").forEach((button) => {
    button.addEventListener("click", () => askBuddy(button.dataset.buddyAction, button));
  });
})();
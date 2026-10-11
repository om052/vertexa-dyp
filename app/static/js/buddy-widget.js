"use strict";

(() => {
  const widget = document.getElementById("buddy-float");
  if (!widget) return;

  const launcher = document.getElementById("buddy-float-launcher");
  const panel = document.getElementById("buddy-float-panel");
  const greeting = document.getElementById("buddy-float-greeting");
  const greetings = [
    "Tiny steps still count. Want a hint?",
    "Ready when you are, legend.",
    "Debugging together beats debugging alone.",
  ];
  greeting.textContent = greetings[Math.floor(Math.random() * greetings.length)];
  window.setTimeout(() => {
    greeting.hidden = true;
  }, 6500);

  function setExpression(expression) {
    const allowed = ["idle", "thinking", "playful", "encouraging", "celebrating"];
    widget.dataset.expression = allowed.includes(expression) ? expression : "idle";
    document.documentElement.dataset.buddyExpression = widget.dataset.expression;
  }

  function setOpen(open) {
    panel.hidden = !open;
    launcher.setAttribute("aria-expanded", String(open));
    launcher.setAttribute(
      "aria-label",
      open ? "Close Buddy quick actions" : "Open Buddy quick actions",
    );
    if (open) {
      setExpression("playful");
      panel.querySelector("a")?.focus();
    } else {
      setExpression("idle");
      launcher.focus();
    }
  }

  launcher.addEventListener("click", () => setOpen(panel.hidden));
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !panel.hidden) setOpen(false);
  });

  window.setBuddyExpression = setExpression;
  setExpression("idle");
})();

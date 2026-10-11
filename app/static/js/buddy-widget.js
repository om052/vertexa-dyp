"use strict";

(() => {
  const widget = document.getElementById("buddy-float");
  if (!widget) return;

  const launcher = document.getElementById("buddy-float-launcher");
  const panel = document.getElementById("buddy-float-panel");
  const greeting = document.getElementById("buddy-float-greeting");
  const modelStage = document.getElementById("buddy-float-model-stage");
  const modelStatus = document.getElementById("buddy-float-model-status");
  const greetings = [
    "Tiny steps still count. Want a hint?",
    "Ready when you are, legend.",
    "Debugging together beats debugging alone.",
  ];
  let modelViewer = null;
  let modelRequested = false;
  let modelReady = false;
  const animations = {
    idle: "Idle_A",
    thinking: "Idle_A",
    explaining: "Idle_A",
    debugging: "Idle_A",
    playful: "Greeting",
    confused: "Confused",
    encouraging: "Yes",
    celebrating: "Cheering_Two_Hands",
  };
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  greeting.textContent = greetings[Math.floor(Math.random() * greetings.length)];
  window.setTimeout(() => {
    greeting.hidden = true;
  }, 6500);

  function setExpression(expression) {
    const allowed = Object.keys(animations);
    widget.dataset.expression = allowed.includes(expression) ? expression : "idle";
    document.documentElement.dataset.buddyExpression = widget.dataset.expression;
    if (!modelReady) return;

    const animation = animations[widget.dataset.expression];
    if (!modelViewer.availableAnimations.includes(animation)) {
      modelStatus.textContent = "3D Buddy is ready; this animation is unavailable.";
      return;
    }
    modelViewer.animationName = animation;
    modelViewer.currentTime = 0;
    modelViewer.loop = widget.dataset.expression === "idle" ||
      widget.dataset.expression === "thinking";
    if (reducedMotion.matches) modelViewer.pause();
    else modelViewer.play();
  }

  function loadModel() {
    if (modelRequested || !modelStage || !modelStatus) return;
    modelRequested = true;
    modelStatus.textContent = "Loading Buddy's 3D character…";

    const viewer = document.createElement("model-viewer");
    modelViewer = viewer;
    viewer.className = "buddy-float-model-viewer";
    viewer.setAttribute("src", modelStage.dataset.modelSrc);
    viewer.setAttribute("alt", "Buddy, a friendly 3D robot");
    viewer.setAttribute("camera-controls", "");
    viewer.setAttribute("disable-pan", "");
    viewer.setAttribute("interaction-prompt", "none");
    viewer.setAttribute("environment-image", "neutral");
    viewer.setAttribute("shadow-intensity", "0.7");
    viewer.setAttribute("aria-hidden", "true");
    viewer.addEventListener("load", () => {
      modelReady = true;
      viewer.setAttribute("aria-hidden", "false");
      viewer.classList.add("is-ready");
      modelStatus.textContent = "Buddy's 3D character is ready.";
      modelStage.querySelector(".buddy-float-model-fallback").hidden = true;
      setExpression(widget.dataset.expression || "idle");
    }, { once: true });
    viewer.addEventListener("error", () => {
      modelStatus.textContent =
        "3D character unavailable. Buddy's illustrated face is still available.";
    }, { once: true });
    modelStage.prepend(viewer);
    modelStatus.textContent = "Loading Buddy's 3D character…";

    if (window.customElements?.get("model-viewer")) return;
    const script = document.createElement("script");
    script.type = "module";
    script.src = "https://ajax.googleapis.com/ajax/libs/model-viewer/4.1.0/model-viewer.min.js";
    script.addEventListener("error", () => {
      modelStatus.textContent =
        "3D renderer unavailable. Buddy's illustrated face is still available.";
    }, { once: true });
    document.head.append(script);
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
      loadModel();
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
  reducedMotion.addEventListener("change", () => {
    if (reducedMotion.matches) modelViewer?.pause();
    else if (modelReady) setExpression(widget.dataset.expression || "idle");
  });

  window.setBuddyExpression = setExpression;
  setExpression("idle");
})();

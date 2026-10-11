"use strict";

(() => {
  const widget = document.getElementById("buddy-float");
  if (!widget) return;

  const launcher = document.getElementById("buddy-float-launcher");
  const panel = document.getElementById("buddy-float-panel");
  const greeting = document.getElementById("buddy-float-greeting");
  const modelStage = document.getElementById("buddy-float-model-stage");
  const modelStatus = document.getElementById("buddy-float-model-status");
  const page = document.body?.dataset.page;
  const isWelcomePage = page === "home" || page === "dashboard";

  let modelViewer = null;
  let modelRequested = false;
  let modelReady = false;

  // Real, verified animation clip names in greetings.glb
  const animations = {
    welcome: "Greeting",
    idle: "Idle_A",
    thinking: "Idle Listening",
    explaining: "Idle_Talking",
    debugging: "Idle Listening",
    playful: "Greeting",
    confused: "Confused",
    encouraging: "Yes",
    celebrating: "Cheering_Two_Hands",
  };
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

  if (isWelcomePage) {
    greeting.textContent = "Welcome back! I'm Buddy. Ready to code or tackle a quest?";
  } else {
    greeting.textContent = "Tiny steps still count. Need a hint? I'm right here.";
  }

  function setBuddyMessage(text) {
    if (!greeting) return;
    greeting.textContent = text;
    greeting.hidden = false;
    const floatCopy = panel?.querySelector(".buddy-float-copy");
    if (floatCopy && !panel.hidden) {
      floatCopy.textContent = text;
    }
  }

  function setExpression(expression) {
    const allowed = Object.keys(animations);
    widget.dataset.expression = allowed.includes(expression) ? expression : "idle";
    document.documentElement.dataset.buddyExpression = widget.dataset.expression;
    if (!modelReady || !modelViewer) return;

    let animation = animations[widget.dataset.expression] || animations.idle;
    if (!modelViewer.availableAnimations?.includes(animation)) {
      modelStatus.textContent = "3D Buddy is ready; this animation is unavailable.";
      animation = animations.idle;
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
      const fallback = modelStage.querySelector(".buddy-float-model-fallback");
      if (fallback) fallback.hidden = true;
      setExpression(widget.dataset.expression || (isWelcomePage ? "welcome" : "idle"));
    }, { once: true });
    viewer.addEventListener("error", () => {
      modelReady = false;
      modelStatus.textContent =
        "3D character unavailable. Buddy's illustrated face is still available.";
      const fallback = modelStage.querySelector(".buddy-float-model-fallback");
      if (fallback) fallback.hidden = false;
    }, { once: true });
    modelStage.prepend(viewer);

    if (window.customElements?.get("model-viewer")) return;
    const script = document.createElement("script");
    script.type = "module";
    script.src = "https://ajax.googleapis.com/ajax/libs/model-viewer/4.1.0/model-viewer.min.js";
    script.addEventListener("error", () => {
      modelReady = false;
      modelStatus.textContent =
        "3D renderer unavailable. Buddy's illustrated face is still available.";
      const fallback = modelStage.querySelector(".buddy-float-model-fallback");
      if (fallback) fallback.hidden = false;
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
      const current = widget.dataset.expression;
      if (current && current !== "idle") {
        setExpression(current);
      } else if (isWelcomePage) {
        setExpression("welcome");
      } else {
        setExpression("encouraging");
      }
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

  // Seamlessly wire float quick actions to workspace when on the workspace page
  panel.querySelectorAll(".buddy-float-actions a").forEach((link) => {
    link.addEventListener("click", (event) => {
      const href = link.getAttribute("href") || "";
      const match = href.match(/[?&]quick=(\w+)/);
      if (match && document.getElementById("coding-workspace")) {
        const action = match[1];
        const workspaceBtn = document.querySelector(`[data-buddy-action="${action}"]`);
        if (workspaceBtn) {
          event.preventDefault();
          workspaceBtn.click();
          workspaceBtn.scrollIntoView({ behavior: "smooth", block: "center" });
        }
      }
    });
  });

  window.setBuddyExpression = setExpression;
  window.setBuddyMessage = setBuddyMessage;
  setExpression(isWelcomePage ? "welcome" : "idle");
})();

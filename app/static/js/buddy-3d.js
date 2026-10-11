"use strict";

(() => {
  const viewer = document.getElementById("buddy-model-viewer");
  const fallback = document.getElementById("buddy-model-fallback");
  const status = document.getElementById("buddy-model-status");
  const rendererScript = document.getElementById("buddy-model-viewer-script");
  if (!viewer || !fallback || !status) return;

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
  let ready = false;

  function setExpression(expression) {
    if (!ready) return;
    const animationName = animations[expression] || animations.idle;
    if (!viewer.availableAnimations.includes(animationName)) {
      status.textContent = "3D animation unavailable · using Buddy face";
      return;
    }

    viewer.animationName = animationName;
    viewer.currentTime = 0;
    viewer.loop = expression === "idle" || expression === "thinking";
    if (reducedMotion.matches) {
      viewer.pause();
      return;
    }
    viewer.play();
  }

  viewer.addEventListener("load", () => {
    ready = true;
    viewer.classList.add("is-ready");
    viewer.setAttribute("aria-hidden", "false");
    fallback.hidden = true;
    status.hidden = true;
    setExpression(document.documentElement.dataset.buddyExpression || "idle");
  }, { once: true });

  viewer.addEventListener("error", () => {
    status.textContent = "3D unavailable · showing Buddy face";
  }, { once: true });

  rendererScript?.addEventListener("error", () => {
    status.textContent = "3D renderer unavailable · showing Buddy face";
  }, { once: true });

  reducedMotion.addEventListener("change", () => {
    if (!ready) return;
    if (reducedMotion.matches) viewer.pause();
    else setExpression(document.documentElement.dataset.buddyExpression || "idle");
  });

  window.setBuddyModelExpression = setExpression;

  if (!window.customElements) {
    status.textContent = "3D unavailable · showing Buddy face";
    return;
  }
  window.setTimeout(() => {
    if (!ready && !window.customElements.get("model-viewer")) {
      status.textContent = "3D renderer unavailable · showing Buddy face";
    }
  }, 15_000);
})();

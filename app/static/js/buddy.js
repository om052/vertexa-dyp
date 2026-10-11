"use strict";

(() => {
  const root = document.getElementById("buddy-app");
  if (!root) return;

  const csrfToken = root.querySelector('meta[name="csrf-token"]')?.content || "";
  const transcript = document.getElementById("buddy-transcript");
  const composer = document.getElementById("buddy-composer");
  const messageInput = document.getElementById("buddy-message");
  const sendButton = document.getElementById("buddy-send");
  const composeError = document.getElementById("buddy-compose-error");
  const historyActions = document.getElementById("buddy-consent-actions");
  const historyEnable = document.getElementById("buddy-history-enable");
  const historyDecline = document.getElementById("buddy-history-decline");
  const historyRevoke = document.getElementById("buddy-history-revoke");
  const historyNewChat = document.getElementById("buddy-new-chat");
  const historyDescription = document.getElementById("buddy-history-description");
  const conversationList = document.getElementById("buddy-conversations");
  const languageSelect = document.getElementById("buddy-language");
  const memoryStatus = document.getElementById("buddy-memory-status");
  const memoryToggle = document.getElementById("buddy-memory-toggle");
  const memoryAdd = document.getElementById("buddy-memory-add");
  const memoryWarning = document.getElementById("buddy-memory-warning");
  const memoryList = document.getElementById("buddy-memory-list");
  const memoryEditor = document.getElementById("buddy-memory-editor");
  const memoryEditorTitle = document.getElementById("buddy-memory-editor-title");
  const memoryCategory = document.getElementById("buddy-memory-category");
  const memoryContent = document.getElementById("buddy-memory-content");
  const memoryApproval = document.getElementById("buddy-memory-approval");
  const memoryCancel = document.getElementById("buddy-memory-cancel");
  const quickActions = {
    hint: "Give me one small hint for the coding problem I'm working on without giving away the full solution.",
    explain: "Please explain the coding concept or snippet I'm working on. Ask me to share it if you need more context.",
    debug: "Help me debug a coding problem. Ask me to share the error message and relevant code, and guide me through it step by step.",
  };

  const state = {
    historyConsent: false,
    historyPromptDismissed: false,
    selectedConversationId: null,
    memoryEnabled: false,
    memoryItems: [],
    editingMemoryId: null,
    busy: false,
    ready: false,
    expressionResetTimer: null,
  };

  function element(tag, className, text) {
    const result = document.createElement(tag);
    if (className) result.className = className;
    if (text !== undefined) result.textContent = text;
    return result;
  }

  function setBuddyExpression(expression) {
    if (state.expressionResetTimer) {
      window.clearTimeout(state.expressionResetTimer);
      state.expressionResetTimer = null;
    }
    const allowed = ["idle", "thinking", "playful", "encouraging", "celebrating"];
    const value = allowed.includes(expression) ? expression : "idle";
    document.documentElement.dataset.buddyExpression = value;
    window.setBuddyExpression?.(value);
  }

  function errorMessage(status, serverMessage) {
    if (status === 401) return "Your session has ended. Sign in again to use Buddy.";
    if (status === 400) return "Please check your request and approval choices, then try again.";
    if (status === 404) return "That saved conversation or memory is no longer available.";
    if (status === 413) return "That request is too large. Shorten it and try again.";
    if (status === 429) return "Buddy is receiving requests too quickly. Wait a moment before trying again.";
    if (status >= 500) return "Buddy could not complete that request. Check saved history before resending.";
    return serverMessage || "Buddy could not complete that request.";
  }

  async function api(path, options = {}) {
    const method = options.method || "GET";
    const headers = { Accept: "application/json" };
    if (options.body !== undefined) {
      headers["Content-Type"] = "application/json";
      headers["X-CSRFToken"] = csrfToken;
    }
    const response = await fetch(`/api/buddy${path}`, {
      method,
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      credentials: "same-origin",
    });
    let payload;
    try {
      payload = await response.json();
    } catch {
      payload = null;
    }
    if (!response.ok) {
      const serverMessage = payload?.error?.message;
      throw Object.assign(
        new Error(errorMessage(response.status, serverMessage)),
        { status: response.status },
      );
    }
    return payload;
  }

  function showInlineError(container, message, retry) {
    container.replaceChildren();
    container.hidden = false;
    container.append(element("p", "", message));
    if (retry) {
      const button = element("button", "button button-outline button-small", "Refresh saved chats");
      button.type = "button";
      button.addEventListener("click", retry);
      container.append(button);
    }
  }

  function appendMessage(role, content) {
    const assistant = role === "assistant";
    const row = element(
      "article",
      `buddy-message ${assistant ? "buddy-message-assistant" : "buddy-message-learner"}`,
    );
    const avatar = element(
      "span",
      "buddy-message-avatar",
      assistant ? "B" : "Y",
    );
    avatar.setAttribute("aria-hidden", "true");
    const body = element("div", "buddy-message-body");
    const author = element(
      "p",
      "buddy-message-author",
      assistant ? "Buddy" : "You",
    );
    if (assistant) author.append(element("span", "", "MOCK"));
    body.append(author);
    const blocks = String(content).split(/```(?:[a-zA-Z0-9_+-]+)?\r?\n([\s\S]*?)```/g);
    for (let index = 0; index < blocks.length; index += 1) {
      const part = blocks[index];
      if (index % 2 === 1) {
        const pre = element("pre", "buddy-code-block");
        pre.append(element("code", "", part));
        body.append(pre);
      } else {
        part.split(/\n{2,}/).forEach((paragraph) => {
          if (!paragraph) return;
          const text = element("p", "buddy-message-text");
          text.textContent = paragraph;
          body.append(text);
        });
      }
    }
    row.append(avatar, body);
    transcript.append(row);
    transcript.scrollTop = transcript.scrollHeight;
  }

  function clearTranscript() {
    transcript.replaceChildren();
  }

  function updateConsentControls() {
    historyActions.hidden = state.historyConsent;
    historyDecline.hidden = state.historyPromptDismissed;
    historyRevoke.hidden = !state.historyConsent;
    historyRevoke.disabled = false;
    historyNewChat.hidden = !state.historyConsent;
    historyNewChat.disabled = false;
    if (state.historyConsent) {
      historyDescription.textContent =
        "New Buddy exchanges are saved to your account and expire after 90 days without activity. History consent lasts for this signed-in session and may remain enabled after reload until logout or session expiry. Turning saving off does not delete conversations already saved.";
    } else {
      historyDescription.textContent =
        "Saved history is off until you opt in. Without it, exchanges stay only in this tab and are cleared on reload. Choosing Not now applies to this page; the prompt may return later. Declining does not delete conversations already saved.";
    }
  }

  function renderConversationList(conversations) {
    conversationList.replaceChildren();
    if (!state.historyConsent) {
      conversationList.append(
        element("p", "buddy-muted", "Enable saved history to view saved conversations."),
      );
      return;
    }
    if (!conversations.length) {
      conversationList.append(element("p", "buddy-muted", "No saved conversations yet."));
      return;
    }
    conversations.forEach((conversation, index) => {
      const row = element(
        "div",
        `buddy-conversation-row${state.selectedConversationId === conversation.id ? " is-selected" : ""}`,
      );
      const selectButton = element(
        "button",
        "buddy-conversation-select",
        `Conversation ${index + 1} · ${new Date(conversation.last_meaningful_at).toLocaleDateString()}`,
      );
      selectButton.type = "button";
      selectButton.setAttribute(
        "aria-pressed",
        String(state.selectedConversationId === conversation.id),
      );
      selectButton.addEventListener("click", () => loadConversation(conversation.id));
      const deleteButton = element("button", "buddy-icon-button", "Delete");
      deleteButton.type = "button";
      deleteButton.setAttribute("aria-label", `Delete conversation ${index + 1}`);
      deleteButton.addEventListener("click", () => removeConversation(conversation.id));
      row.append(selectButton, deleteButton);
      conversationList.append(row);
    });
  }

  async function loadConversations() {
    try {
      const result = await api("/conversations");
      renderConversationList(result.conversations);
    } catch (error) {
      showInlineError(conversationList, error.message);
    }
  }

  async function loadConversation(id) {
    try {
      const result = await api(`/conversations/${encodeURIComponent(id)}`);
      state.selectedConversationId = result.conversation.id;
      clearTranscript();
      result.messages.forEach((message) => appendMessage(message.role, message.content));
      renderConversationList(
        (await api("/conversations")).conversations,
      );
      messageInput.focus();
      composeError.hidden = true;
    } catch (error) {
      showInlineError(conversationList, error.message, loadConversations);
    }
  }

  async function removeConversation(id) {
    if (!window.confirm("Delete this saved conversation and its messages? This cannot be undone.")) {
      return;
    }
    try {
      await api(`/conversations/${encodeURIComponent(id)}`, { method: "DELETE", body: {} });
      if (state.selectedConversationId === id) {
        state.selectedConversationId = null;
        clearTranscript();
        appendMessage("assistant", "This saved conversation was deleted. What would you like to explore next?");
      }
      await loadConversations();
    } catch (error) {
      showInlineError(conversationList, error.message, loadConversations);
    }
  }

  function setBusy(busy) {
    state.busy = busy;
    messageInput.disabled = busy;
    languageSelect.disabled = busy;
    sendButton.disabled = busy;
    document.querySelectorAll("[data-buddy-quick]").forEach((button) => {
      button.disabled = busy || !state.ready;
    });
    sendButton.querySelector("span:first-child").textContent = busy ? "Thinking…" : "Send";
    composer.setAttribute("aria-busy", String(busy));
  }

  async function sendMessage(message) {
    return submitMessage(message, false);
  }

  async function submitMessage(message, retry) {
    if (state.busy) return;
    setBusy(true);
    setBuddyExpression("thinking");
    composeError.hidden = true;
    composeError.replaceChildren();
    if (!retry) appendMessage("user", message);
    try {
      const payload = { message };
      if (state.historyConsent && state.selectedConversationId) {
        payload.conversation_id = state.selectedConversationId;
      }
      if (languageSelect.value) payload.language = languageSelect.value;
      const result = await api("/respond", { method: "POST", body: payload });
      if (result.response.is_mock !== true) {
        throw new Error("Buddy returned a response that could not be verified as mock output.");
      }
      if (typeof result.response.content !== "string" || !result.response.content) {
        throw new Error("Buddy returned an invalid response.");
      }
      appendMessage("assistant", result.response.content);
      setBuddyExpression("celebrating");
      state.expressionResetTimer = window.setTimeout(
        () => setBuddyExpression("idle"),
        2200,
      );
      if (result.saved && result.conversation?.id) {
        state.selectedConversationId = result.conversation.id;
        await loadConversations();
      }
      messageInput.value = "";
    } catch (error) {
      setBuddyExpression("encouraging");
      showInlineError(
        composeError,
        `${error.message} A send request may already have been processed; it was not retried automatically.`,
      );
      const retryButton = element(
        "button",
        "button button-outline button-small",
        "Resend anyway (may duplicate)",
      );
      retryButton.type = "button";
      retryButton.addEventListener("click", () => {
        if (window.confirm(
          "The request may already have been processed. Resending can create a duplicate saved exchange. Continue?",
        )) {
          submitMessage(message, true);
        }
      });
      composeError.append(retryButton);
      if (state.historyConsent) {
        const refreshButton = element(
          "button",
          "button button-outline button-small",
          "Refresh saved chats",
        );
        refreshButton.type = "button";
        refreshButton.addEventListener("click", loadConversations);
        composeError.append(refreshButton);
      }
    } finally {
      setBusy(false);
      messageInput.focus();
    }
  }

  async function chooseHistoryConsent(consent) {
    historyEnable.disabled = true;
    historyDecline.disabled = true;
    const wasConsented = state.historyConsent;
    try {
      await api("/history-consent", {
        method: "POST",
        body: { consent },
      });
      state.historyConsent = consent;
      state.historyPromptDismissed = !consent;
      state.selectedConversationId = null;
      if (wasConsented && !consent) clearTranscript();
      if (!consent) {
        if (wasConsented) {
          appendMessage(
            "assistant",
            "Future exchanges will not be saved. Existing saved conversations are unchanged.",
          );
        }
      } else {
        appendMessage(
          "assistant",
          "Saved history is enabled for future exchanges. Messages from before you opted in were not saved.",
        );
      }
      updateConsentControls();
      await loadConversations();
    } catch (error) {
      showInlineError(composeError, error.message);
    } finally {
      historyEnable.disabled = false;
      historyDecline.disabled = false;
    }
  }

  async function revokeHistoryConsent() {
    if (!window.confirm("Turn off saving future exchanges? Previously saved conversations will remain in your account.")) {
      return;
    }
    await chooseHistoryConsent(false);
  }

  function renderMemoryItems() {
    memoryList.replaceChildren();
    state.memoryItems.forEach((item) => {
      const row = element("article", "buddy-memory-item");
      const text = element("div", "buddy-memory-item-content");
      text.append(
        element("span", "buddy-memory-category", item.category.replaceAll("_", " ")),
        element("p", "", item.content),
      );
      const actions = element("div", "buddy-memory-item-actions");
      const edit = element("button", "buddy-text-button", "Edit");
      edit.type = "button";
      edit.addEventListener("click", () => beginMemoryEdit(item));
      const remove = element("button", "buddy-text-button buddy-text-danger", "Delete");
      remove.type = "button";
      remove.addEventListener("click", () => removeMemory(item.id));
      actions.append(edit, remove);
      row.append(text, actions);
      memoryList.append(row);
    });
    memoryAdd.hidden = !state.memoryEnabled;
    memoryAdd.disabled = !state.memoryEnabled;
    memoryWarning.hidden = !state.memoryEnabled || state.memoryItems.length === 0;
  }

  async function loadMemory() {
    const [privacy, memory] = await Promise.all([
      api("/privacy"),
      api("/memory"),
    ]);
    state.memoryEnabled = privacy.privacy.memory_enabled;
    state.memoryItems = memory.items;
    memoryStatus.textContent = state.memoryEnabled
      ? "On — only items you approve are stored. Memory is separate from conversation history."
      : "Off — Buddy does not send or store persistent learning memory.";
    memoryToggle.textContent = state.memoryEnabled ? "Turn memory off" : "Enable memory";
    memoryToggle.disabled = false;
    renderMemoryItems();
  }

  async function toggleMemory() {
    const enabling = !state.memoryEnabled;
    if (!enabling && state.memoryItems.length > 0 &&
      !window.confirm("Disable Buddy memory and delete all saved memory items? This does not delete conversations.")) {
      return;
    }
    memoryToggle.disabled = true;
    try {
      const result = await api("/privacy", {
        method: "PATCH",
        body: {
          memory_enabled: enabling,
          ...(!enabling && state.memoryItems.length
            ? { confirm_delete_existing: true }
            : {}),
        },
      });
      state.memoryEnabled = result.privacy.memory_enabled;
      memoryToggle.textContent = state.memoryEnabled ? "Turn memory off" : "Enable memory";
      memoryStatus.textContent = state.memoryEnabled
        ? "On — only items you approve are stored. Memory is separate from conversation history."
        : "Off — Buddy does not send or store persistent learning memory.";
      if (!state.memoryEnabled) {
        closeMemoryEditor();
        if (state.memoryItems.length) {
          state.memoryItems = [];
        }
      }
      renderMemoryItems();
      try {
        await loadMemory();
      } catch (error) {
        memoryStatus.textContent = `Setting saved, but the memory list could not refresh: ${error.message}`;
      }
    } catch (error) {
      memoryStatus.textContent = error.message;
    } finally {
      memoryToggle.disabled = false;
    }
  }

  function beginMemoryEdit(item) {
    state.editingMemoryId = item.id;
    memoryEditorTitle.textContent = "Edit approved learning memory";
    memoryCategory.value = item.category;
    memoryContent.value = item.content;
    memoryApproval.checked = false;
    memoryEditor.hidden = false;
    memoryContent.focus();
  }

  function openMemoryCreate() {
    state.editingMemoryId = null;
    memoryEditorTitle.textContent = "Add a learning memory";
    memoryCategory.value = "learning_goal";
    memoryContent.value = "";
    memoryApproval.checked = false;
    memoryEditor.hidden = false;
    memoryContent.focus();
  }

  function closeMemoryEditor() {
    state.editingMemoryId = null;
    memoryEditor.reset();
    memoryEditor.hidden = true;
  }

  async function saveMemory(event) {
    event.preventDefault();
    if (!memoryApproval.checked) {
      memoryApproval.focus();
      return;
    }
    const editingId = state.editingMemoryId;
    const path = editingId ? `/memory/${encodeURIComponent(editingId)}` : "/memory";
    try {
      await api(path, {
        method: editingId ? "PATCH" : "POST",
        body: {
          category: memoryCategory.value,
          content: memoryContent.value,
          learner_approved: true,
        },
      });
      closeMemoryEditor();
      await loadMemory();
    } catch (error) {
      memoryStatus.textContent = error.message;
    }
  }

  async function removeMemory(id) {
    if (!window.confirm("Delete this approved learning memory?")) return;
    try {
      await api(`/memory/${encodeURIComponent(id)}`, { method: "DELETE", body: {} });
      await loadMemory();
    } catch (error) {
      memoryStatus.textContent = error.message;
    }
  }

  async function initialize() {
    try {
      const status = await api("/status");
      state.historyConsent = status.history.consent;
      messageInput.disabled = false;
      sendButton.disabled = false;
      historyEnable.disabled = false;
      historyDecline.disabled = false;
      updateConsentControls();
      await loadConversations();
      await loadMemory();
      if (!status.provider.is_mock) {
        throw new Error("The configured Buddy response mode could not be verified.");
      }
      state.ready = true;
      document.querySelectorAll("[data-buddy-quick]").forEach((button) => {
        button.disabled = false;
      });
      const params = new URLSearchParams(window.location.search);
      const quickAction = params.get("quick");
      if (quickAction && Object.prototype.hasOwnProperty.call(quickActions, quickAction)) {
        window.history.replaceState({}, "", window.location.pathname);
        messageInput.value = "";
        await sendMessage(quickActions[quickAction]);
      }
    } catch (error) {
      showInlineError(composeError, error.message);
      memoryStatus.textContent = "Privacy settings could not be loaded. Please refresh and try again.";
    }
  }

  composer.addEventListener("submit", (event) => {
    event.preventDefault();
    const message = messageInput.value.trim();
    if (message) sendMessage(message);
  });

  messageInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      composer.requestSubmit();
    }
  });

  historyEnable.addEventListener("click", () => chooseHistoryConsent(true));
  historyDecline.addEventListener("click", () => chooseHistoryConsent(false));
  historyRevoke.addEventListener("click", revokeHistoryConsent);
  historyNewChat.addEventListener("click", () => {
    state.selectedConversationId = null;
    clearTranscript();
    appendMessage("assistant", "A fresh conversation is ready. What would you like to work on?");
    loadConversations();
    messageInput.focus();
  });
  memoryToggle.addEventListener("click", toggleMemory);
  memoryAdd.addEventListener("click", openMemoryCreate);
  memoryCancel.addEventListener("click", closeMemoryEditor);
  memoryEditor.addEventListener("submit", saveMemory);
  document.querySelectorAll("[data-buddy-quick]").forEach((button) => {
    button.addEventListener("click", () => {
      const message = quickActions[button.dataset.buddyQuick];
      if (message) sendMessage(message);
    });
  });

  initialize();
})();

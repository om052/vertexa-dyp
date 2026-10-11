"use strict";

const icons = ["⌘", "◎", "◈", "⌁"];

function node(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined) element.textContent = text;
  return element;
}

function showError(container, message) {
  container.replaceChildren();
  const box = node("div", "empty-state error-state");
  box.append(node("span", "empty-icon", "!"), node("h3", "", "We couldn't load this content"));
  box.append(node("p", "", message));
  const retry = node("button", "button button-outline", "Try again");
  retry.type = "button";
  retry.addEventListener("click", () => window.location.reload());
  box.append(retry);
  container.append(box);
}

async function getJson(url) {
  const response = await fetch(url, { headers: { Accept: "application/json" } });
  if (!response.ok) throw new Error(response.status === 404 ? "This curriculum item was not found." : "Please check your connection and try again.");
  return response.json();
}

function appendInlineText(container, text) {
  const inlineCode = /`([^`]+)`/g;
  let start = 0;
  for (const match of text.matchAll(inlineCode)) {
    container.append(document.createTextNode(text.slice(start, match.index)));
    container.append(node("code", "lesson-inline-code", match[1]));
    start = match.index + match[0].length;
  }
  container.append(document.createTextNode(text.slice(start)));
}

function renderLanguageCards(container, languages) {
  container.replaceChildren();
  if (!languages.length) {
    const empty = node("div", "empty-state");
    empty.append(node("span", "empty-icon", "⌘"), node("h3", "", "Learning paths are being prepared"), node("p", "", "There are no published language paths yet. Please check back soon."));
    container.append(empty);
    return;
  }
  languages.forEach((language, index) => {
    const card = node("a", `language-card language-tone-${index % 4}`);
    card.href = `/learn/${encodeURIComponent(language.slug)}`;
    card.setAttribute("aria-label", `Explore ${language.name} learning path`);
    const top = node("div", "language-card-top");
    top.append(node("span", "language-icon", icons[index % icons.length]), node("span", "card-arrow", "↗"));
    const details = node("div", "language-card-details");
    details.append(node("h3", "", language.name), node("p", "", language.description));
    const footer = node("div", "language-card-footer");
    const counts = node("span", "card-count", `${language.topic_count} ${language.topic_count === 1 ? "topic" : "topics"}`);
    counts.append(document.createTextNode(" · "));
    counts.append(document.createTextNode(`${language.lesson_count} ${language.lesson_count === 1 ? "lesson" : "lessons"}`));
    footer.append(counts, node("span", "card-link", "Explore path →"));
    card.append(top, details, footer);
    container.append(card);
  });
}

async function loadLanguages() {
  const containers = document.querySelectorAll("[data-api='/api/languages']");
  for (const container of containers) {
    try {
      const result = await getJson(container.dataset.api);
      if (!Array.isArray(result.languages)) throw new Error("The learning path response was invalid.");
      renderLanguageCards(container, result.languages);
    } catch (error) {
      showError(container, error.message);
    }
  }
}

function renderRoadmapTopics(container, language) {
  container.replaceChildren();
  if (!language.topics.length) {
    const empty = node("div", "empty-state");
    empty.append(node("span", "empty-icon", "↗"), node("h3", "", "This roadmap is ready for its first topic"), node("p", "", "Topics will appear here when curriculum content is published."));
    container.append(empty);
    return;
  }
  language.topics.forEach((topic, index) => {
    const item = node("article", "roadmap-card");
    const marker = node("div", "roadmap-marker", String(index + 1).padStart(2, "0"));
    marker.setAttribute("aria-hidden", "true");
    const content = node("div", "roadmap-card-content");
    const meta = node("div", "roadmap-meta");
    meta.append(node("span", "difficulty-tag", topic.difficulty), node("span", "meta-dot", "·"), node("span", "", `${topic.lesson_count} ${topic.lesson_count === 1 ? "lesson" : "lessons"}`));
    content.append(meta, node("h3", "", topic.title), node("p", "", topic.description));
    const link = node("a", "button button-outline button-small", "View topic");
    link.href = `/learn/${encodeURIComponent(language.slug)}/topics/${encodeURIComponent(topic.slug)}`;
    item.append(marker, content, link);
    container.append(item);
  });
}

async function loadRoadmap() {
  const header = document.getElementById("roadmap-header");
  if (!header) return;
  const list = document.getElementById("roadmap-topics");
  try {
    const result = await getJson(header.dataset.api);
    const language = result.language;
    if (!language || !Array.isArray(language.topics)) throw new Error("The roadmap response was invalid.");
    header.replaceChildren();
    const heading = node("h1");
    heading.append(document.createTextNode(`${language.name} `));
    const accent = node("span", "text-gradient", "roadmap.");
    heading.append(accent);
    header.append(heading);
    header.append(node("p", "page-hero-description", language.description));
    const counts = node("div", "hero-meta");
    counts.append(node("span", "", `${language.topic_count} topics`), node("span", "meta-divider", "·"), node("span", "", `${language.lesson_count} lessons`));
    header.append(counts);
    document.getElementById("roadmap-breadcrumb").textContent = language.name;
    document.title = `${language.name} Roadmap — CodeQuest AI`;
    renderRoadmapTopics(list, language);
  } catch (error) {
    showError(header, error.message);
    list.replaceChildren();
  }
}

function renderLessons(container, topic, languageCode) {
  container.replaceChildren();
  if (!topic.lessons.length) {
    const empty = node("div", "empty-state");
    empty.append(node("span", "empty-icon", "✧"), node("h3", "", "Lessons are on their way"), node("p", "", "This topic does not have any published lessons yet."));
    container.append(empty);
    return;
  }
  topic.lessons.forEach((lesson, index) => {
    const card = node("a", "lesson-card");
    card.href = `/learn/${encodeURIComponent(languageCode)}/topics/${encodeURIComponent(topic.slug)}/lessons/${encodeURIComponent(lesson.slug)}`;
    const number = node("span", "lesson-number", String(index + 1).padStart(2, "0"));
    const body = node("span", "lesson-card-body");
    body.append(node("strong", "", lesson.title), node("span", "", lesson.description));
    card.append(number, body, node("span", "card-arrow", "↗"));
    container.append(card);
  });
}

async function loadTopic() {
  const header = document.getElementById("topic-header");
  if (!header) return;
  try {
    const result = await getJson(header.dataset.api);
    const topic = result.topic;
    if (!topic || !Array.isArray(topic.lessons)) throw new Error("The topic response was invalid.");
    header.replaceChildren();
    header.append(node("p", "eyebrow", `${topic.language.name.toUpperCase()} · TOPIC ${String(topic.position + 1).padStart(2, "0")}`));
    header.append(node("h1", "", topic.title));
    header.append(node("p", "page-hero-description", topic.description));
    const meta = node("div", "hero-meta");
    meta.append(node("span", "difficulty-tag", topic.difficulty), node("span", "meta-divider", "·"), node("span", "", `${topic.lessons.length} ${topic.lessons.length === 1 ? "lesson" : "lessons"}`));
    header.append(meta);
    document.getElementById("topic-roadmap-link").textContent = topic.language.name;
    document.title = `${topic.title} — CodeQuest AI`;
    renderLessons(document.getElementById("topic-lessons"), topic, topic.language.slug);
  } catch (error) {
    showError(header, error.message);
    document.getElementById("topic-lessons").replaceChildren();
  }
}

function appendLessonBody(container, content) {
  container.replaceChildren();
  const lines = content.split(/\r?\n/);
  let paragraph = [];
  let codeLines = null;
  const flushParagraph = () => {
    if (!paragraph.length) return;
    const element = node("p", "lesson-paragraph");
    appendInlineText(element, paragraph.join(" "));
    container.append(element);
    paragraph = [];
  };
  for (const line of lines) {
    if (line.trim().startsWith("```")) {
      flushParagraph();
      if (codeLines) {
        const pre = node("pre", "lesson-code");
        const code = node("code", "", codeLines.join("\n"));
        pre.append(code);
        container.append(pre);
        codeLines = null;
      } else {
        codeLines = [];
      }
      continue;
    }
    if (codeLines) {
      codeLines.push(line);
      continue;
    }
    const heading = line.match(/^(#{1,3})\s+(.+)$/);
    if (heading) {
      flushParagraph();
      const level = heading[1].length;
      container.append(node(`h${level + 1}`, "lesson-subheading", heading[2]));
    } else if (!line.trim()) {
      flushParagraph();
    } else {
      paragraph.push(line.trim());
    }
  }
  if (codeLines) {
    const pre = node("pre", "lesson-code");
    pre.append(node("code", "", codeLines.join("\n")));
    container.append(pre);
  }
  flushParagraph();
}

async function loadLesson() {
  const header = document.getElementById("lesson-header");
  if (!header) return;
  try {
    const result = await getJson(header.dataset.api);
    const lesson = result.lesson;
    if (!lesson || typeof lesson.content !== "string") throw new Error("The lesson response was invalid.");
    header.replaceChildren();
    header.append(node("p", "eyebrow", `LESSON ${String(lesson.position + 1).padStart(2, "0")}`));
    header.append(node("h1", "", lesson.title));
    header.append(node("p", "page-hero-description", lesson.description));
    document.getElementById("lesson-topic-link").textContent = lesson.topic_slug.replaceAll("-", " ");
    document.getElementById("lesson-roadmap-link").textContent = lesson.language_slug;
    document.title = `${lesson.title} — CodeQuest AI`;
    appendLessonBody(document.getElementById("lesson-content"), lesson.content);
    const pager = document.getElementById("lesson-pager");
    const previous = lesson.prerequisites[0];
    if (previous) {
      const link = node("a", "button button-outline", "← Previous lesson");
      link.href = `/learn/${encodeURIComponent(lesson.language_slug)}/topics/${encodeURIComponent(previous.topic_slug)}/lessons/${encodeURIComponent(previous.lesson_slug)}`;
      pager.append(link);
    } else {
      pager.append(node("span", "pager-placeholder", "Start of this topic"));
    }
    const next = node("a", "button button-primary", "Back to topic");
    next.href = `/learn/${encodeURIComponent(lesson.language_slug)}/topics/${encodeURIComponent(lesson.topic_slug)}`;
    pager.append(next);
  } catch (error) {
    showError(header, error.message);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  loadLanguages();
  loadRoadmap();
  loadTopic();
  loadLesson();
});

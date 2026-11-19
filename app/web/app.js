"use strict";
const $ = (id) => document.getElementById(id);
const topics = {
  BACKEND: "Бэкенд",
  FRONTEND: "Фронтенд",
  AI_DATA: "ИИ и данные",
  SECURITY: "Информационная безопасность",
  RESEARCH: "Исследования",
};
const types = {
  internship: "Стажировка",
  junior_job: "Вакансия",
  hackathon: "Хакатон",
  grant: "Грант",
  event: "Мероприятие",
  learning: "Обучение",
};
const formats = {
  online: "Онлайн",
  onsite: "Очно",
  hybrid: "Гибридный формат",
  unknown: "Формат уточняется",
};
let registering = false,
  faculties = [],
  view = "personalized",
  offset = 0,
  requestId = 0;
const form = $("profileForm").elements;
function screen(name) {
  for (const id of ["auth", "profile", "feed"]) $(id).hidden = id !== name;
  $("nav").hidden = name === "auth";
  $("edit").hidden = name === "profile";
}
function logout() {
  requestId++;
  sessionStorage.removeItem("token");
  setRegistration(false);
  $("authForm").reset();
  screen("auth");
}
function errorText(message) {
  $("error").textContent = message;
  $("error").hidden = !message;
}
async function api(path, method = "GET", body) {
  const headers = {};
  if (body) headers["Content-Type"] = "application/json";
  if (sessionStorage.token)
    headers.Authorization = "Bearer " + sessionStorage.token;
  const response = await fetch("/api/v1" + path, {
    method,
    headers,
    body: body && JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok) {
    if (response.status === 401 && !path.startsWith("/auth")) logout();
    const detail =
      typeof data.detail === "string"
        ? data.detail
        : "Проверьте введённые данные";
    throw Error(
      {
        401: "Войдите снова или проверьте почту и пароль",
        409: "Эта почта уже зарегистрирована",
      }[response.status] || detail,
    );
  }
  return data;
}
function on(id, event, handler) {
  $(id).addEventListener(event, async (e) => {
    e.preventDefault();
    const button =
      e.submitter ||
      (e.currentTarget.tagName === "BUTTON" ? e.currentTarget : null);
    if (button) button.disabled = true;
    errorText("");
    try {
      await handler(e);
    } catch (err) {
      errorText(err.message);
    } finally {
      if (button) button.disabled = false;
    }
  });
}
function text(tag, value, css) {
  const node = document.createElement(tag);
  node.textContent = value;
  if (css) node.className = css;
  return node;
}
function checks(id, entries, selected) {
  $(id).replaceChildren(
    ...entries.map(([value, title]) => {
      const label = document.createElement("label"),
        input = document.createElement("input");
      input.type = "checkbox";
      input.value = value;
      input.checked = selected.includes(value);
      label.append(input, title);
      return label;
    }),
  );
}
function fillPrograms(selected) {
  const faculty = faculties.find((f) => f.id === Number(form.faculty.value));
  form.program.replaceChildren(
    ...(faculty?.programs || []).map((p) => new Option(p.name, p.id)),
  );
  if (selected) form.program.value = selected;
}
async function profile(user) {
  const [universities, tags] = await Promise.all([
    api("/universities"),
    api("/tags"),
  ]);
  faculties =
    universities.find((u) => u.name.includes("Донской"))?.faculties || [];
  if (!faculties.length)
    throw Error("Справочник ДГТУ пуст. Обратитесь к организатору показа.");
  const p = user.profile;
  form.faculty.replaceChildren(
    ...faculties.map((f) => new Option(f.name, f.id)),
  );
  if (p.faculty_id) form.faculty.value = p.faculty_id;
  fillPrograms(p.study_program_id);
  form.course.value = p.course || "";
  checks(
    "topics",
    tags.filter((t) => topics[t.code]).map((t) => [t.id, topics[t.code]]),
    p.interest_ids || [],
  );
  checks("types", Object.entries(types), p.preferred_types || []);
  screen("profile");
}
function link(label, url) {
  if (!url) return null;
  try {
    const u = new URL(url);
    if (!["https:", "http:"].includes(u.protocol)) return null;
    const a = text("a", label);
    a.href = u.href;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    return a;
  } catch {
    return null;
  }
}
function card(c) {
  const article = document.createElement("article");
  article.append(
    text(
      "div",
      [types[c.type], formats[c.format], c.city].filter(Boolean).join(" · "),
      "meta",
    ),
    text("h2", c.title),
    text("p", c.summary),
  );
  if (c.deadline)
    article.append(
      text(
        "p",
        "Приём заявок до " +
          new Intl.DateTimeFormat("ru-RU", {
            dateStyle: "long",
            timeStyle: "short",
            timeZone: "Europe/Moscow",
          }).format(new Date(c.deadline)) +
          " МСК",
        "meta",
      ),
    );
  if (c.match_reasons.length)
    article.append(
      text(
        "p",
        c.match_reasons
          .map((r) =>
            r.replace(
              /По интересу (\w+)/,
              (_, t) => "По интересу «" + (topics[t] || t) + "»",
            ),
          )
          .join(" · "),
        "reason",
      ),
    );
  if (c.conditions) article.append(text("p", c.conditions));
  if (c.contact) article.append(text("p", c.contact));
  const source = link("Открыть источник ↗", c.source_url);
  if (source) article.append(source);
  if (c.action_url && c.action_url !== c.source_url) {
    const action = link("Перейти к участию ↗", c.action_url);
    if (action) article.append(" · ", action);
  }
  return article;
}
async function feed(next = view, append = false) {
  const id = ++requestId,
    start = append ? offset : 0;
  const data = await api(
    "/opportunities?view=" + next + "&limit=20&offset=" + start,
  );
  if (id !== requestId) return;
  view = next;
  offset = start + data.items.length;
  if (!append) $("cards").replaceChildren();
  $("cards").append(...data.items.map(card));
  $("count").textContent = offset
    ? "Показано: " + offset
    : "Пока нет актуальных предложений. Попробуйте общий каталог или измените интересы.";
  $("more").hidden = data.items.length < 20;
  for (const mode of ["all", "personalized"])
    $(mode).setAttribute("aria-pressed", String(view === mode));
  screen("feed");
}
async function enter() {
  const user = await api("/profile/me");
  if (user.role !== "student") {
    logout();
    throw Error("Для студенческой ленты войдите под аккаунтом студента.");
  }
  if (
    user.profile.interest_ids?.length &&
    (user.profile.study_program_id || user.profile.study_group_id)
  )
    await feed("personalized");
  else await profile(user);
}
function setRegistration(enabled) {
  registering = enabled;
  $("nameLabel").hidden = !registering;
  $("authForm").elements.full_name.required = registering;
  $("authForm").elements.password.autocomplete = registering
    ? "new-password"
    : "current-password";
  $("authTitle").textContent = registering ? "Регистрация" : "Вход";
  $("submitAuth").textContent = registering ? "Зарегистрироваться" : "Войти";
  $("toggleAuth").textContent = registering
    ? "Уже есть аккаунт"
    : "Создать аккаунт";
}
on("toggleAuth", "click", () => setRegistration(!registering));
on("authForm", "submit", async (e) => {
  const { email, password, full_name } = Object.fromEntries(
    new FormData(e.target),
  );
  if (registering)
    await api("/auth/register", "POST", {
      email,
      password,
      full_name,
      role: "student",
    });
  const result = await api("/auth/login", "POST", { email, password });
  sessionStorage.setItem("token", result.access_token);
  e.target.reset();
  await enter();
});
on("profileForm", "submit", async () => {
  const chosen = (id) =>
    Array.from($(id).querySelectorAll(":checked"), (c) => c.value);
  const interests = chosen("topics").map(Number);
  if (!interests.length) throw Error("Выберите хотя бы один интерес");
  await api("/profile/student", "PUT", {
    faculty_id: Number(form.faculty.value),
    study_program_id: Number(form.program.value),
    course: Number(form.course.value) || null,
    interest_ids: interests,
    preferred_types: chosen("types"),
  });
  await feed("personalized");
});
form.faculty.addEventListener("change", () => fillPrograms());
on("edit", "click", async () => profile(await api("/profile/me")));
on("logout", "click", logout);
on("all", "click", () => feed("all"));
on("personalized", "click", () => feed("personalized"));
on("more", "click", () => feed(view, true));
if (sessionStorage.token) enter().catch((err) => errorText(err.message));

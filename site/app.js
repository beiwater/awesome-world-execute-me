"use strict";

// Fallback when the page is not served from <owner>.github.io/<repo>/.
const DEFAULT_REPO = "beiwater/awesome-world-execute-me";

const FORMS = {
  web: "WEB 网页",
  terminal: "TERMINAL 终端",
  video: "VIDEO 视频PV",
  code: "CODE 代码实现",
};
const MAKERS = { ai: "AI", human: "手写", unknown: "未标注" };
const SORTS = { stars: "★stars", newest: "newest", pushed: "updated" };
const NEW_DAYS = 7;

const $ = (sel) => document.querySelector(sel);
const state = { form: "", maker: "", model: "", q: "", sort: "stars" };
let works = [];
let generated = null;

// ---------- helpers ----------
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const span = (cls, text) => `<span class="${cls}">${esc(text)}</span>`;
const daysBetween = (a, b) => (new Date(b) - new Date(a)) / 864e5;

function repoSlug() {
  const host = location.hostname;
  if (host.endsWith(".github.io")) {
    const owner = host.slice(0, -".github.io".length);
    const repo = location.pathname.split("/").filter(Boolean)[0];
    return `${owner}/${repo || host}`;
  }
  return DEFAULT_REPO;
}

function readState() {
  const p = new URLSearchParams(location.search);
  for (const k of Object.keys(state)) if (p.has(k)) state[k] = p.get(k);
  if (!SORTS[state.sort]) state.sort = "stars";
}

function writeState() {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(state)) if (v && !(k === "sort" && v === "stars")) p.set(k, v);
  const qs = p.toString();
  history.replaceState(null, "", location.pathname + (qs ? "?" + qs : "") + location.hash);
}

// ---------- boot ----------
function boot(total) {
  const el = $("#boot");
  const log = $("#boot-log");
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (sessionStorage.getItem("booted") || reduced) { el.classList.add("done"); return; }
  sessionStorage.setItem("booted", "1");

  const lines = [
    ["", "> Switch on the power line"],
    ["ok", "[ OK ] mounting /world ..................... done"],
    ["ok", `[ OK ] loading ${total} objects from GitHub ......... done`],
    ["ok", "[ OK ] allocating memory for me ............ done"],
    ["hl", "> world.execute(me);"],
  ];
  let i = 0, j = 0, timer;
  const finish = () => {
    clearTimeout(timer);
    el.classList.add("done");
    removeEventListener("keydown", finish);
    el.removeEventListener("click", finish);
  };
  addEventListener("keydown", finish);
  el.addEventListener("click", finish);
  const tick = () => {
    if (i >= lines.length) { timer = setTimeout(finish, 450); return; }
    const [cls, text] = lines[i];
    j += cls === "ok" ? 6 : 1;
    const done = lines.slice(0, i).map(([c, t]) => `<span class="${c}">${esc(t)}</span>`).join("\n");
    log.innerHTML = (done ? done + "\n" : "") + `<span class="${cls}">${esc(text.slice(0, j))}</span><span class="caret"></span>`;
    if (j >= text.length) { i++; j = 0; timer = setTimeout(tick, 140); }
    else timer = setTimeout(tick, cls === "ok" ? 8 : 34);
  };
  tick();
}

// ---------- arena ----------
// Arena and model filter work on vendor families ("Claude", "DeepSeek", …); cards show exact versions.
function familyCounts(list) {
  const m = new Map();
  for (const w of list) for (const fam of w.families || []) m.set(fam, (m.get(fam) || 0) + 1);
  return [...m.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
}

function renderArena() {
  const counts = familyCounts(works);
  const top = counts.slice(0, 12);
  const max = top.length ? top[0][1] : 1;
  const bars = $("#arena-bars");
  bars.innerHTML = top.map(([label, n]) => `
    <li><button class="bar${state.model === label ? " active" : ""}" type="button" data-model="${esc(label)}">
      <span class="bar-label str">"${esc(label)}"</span>
      <span class="bar-track"><span class="bar-fill" data-w="${(n / max) * 100}"></span></span>
      <span class="bar-num">${n}</span>
    </button></li>`).join("") || `<li class="cm">// 暂无标注模型的作品</li>`;
  requestAnimationFrame(() => requestAnimationFrame(() => {
    for (const f of bars.querySelectorAll(".bar-fill")) f.style.width = f.dataset.w + "%";
  }));
  bars.onclick = (e) => {
    const b = e.target.closest(".bar");
    if (!b) return;
    state.model = state.model === b.dataset.model ? "" : b.dataset.model;
    update(true);
  };

  const by = (key) => works.reduce((acc, w) => ((acc[w[key]] = (acc[w[key]] || 0) + 1), acc), {});
  const forms = by("form"), makers = by("maker");
  $("#form-stats").innerHTML =
    Object.keys(FORMS).map((k) => `<span>${esc(k)}: <b>${forms[k] || 0}</b></span>`).join("") +
    `<span class="cm">//</span>` +
    Object.keys(MAKERS).map((k) => `<span>${esc(MAKERS[k])}: <b>${makers[k] || 0}</b></span>`).join("");
}

// ---------- filters ----------
function chips(el, options, key, counts) {
  el.innerHTML = Object.entries(options).map(([value, label]) => {
    const n = counts ? `<span class="n">${counts[value] || 0}</span>` : "";
    return `<button class="chip" type="button" data-v="${esc(value)}" aria-pressed="${state[key] === value}">${esc(label)}${n}</button>`;
  }).join("");
  el.onclick = (e) => {
    const c = e.target.closest(".chip");
    if (!c) return;
    state[key] = key !== "sort" && state[key] === c.dataset.v ? "" : c.dataset.v;
    update(true);
  };
}

function renderFilters() {
  const count = (key) => works.reduce((a, w) => ((a[w[key]] = (a[w[key]] || 0) + 1), a), {});
  chips($("#f-form"), { "": "ALL", ...Object.fromEntries(Object.entries(FORMS).map(([k, v]) => [k, v.split(" ")[0]])) }, "form", { "": works.length, ...count("form") });
  chips($("#f-maker"), { "": "ALL", ...MAKERS }, "maker", { "": works.length, ...count("maker") });
  chips($("#f-sort"), SORTS, "sort");

  const sel = $("#f-model");
  sel.innerHTML = `<option value="">ALL</option>` +
    familyCounts(works).map(([m, n]) => `<option value="${esc(m)}">"${esc(m)}" (${n})</option>`).join("");
  sel.value = state.model;
  sel.onchange = () => { state.model = sel.value; update(true); };

  const q = $("#f-q");
  q.value = state.q;
  q.oninput = () => { state.q = q.value.trim(); update(false); };
}

function filtered() {
  const q = state.q.toLowerCase();
  const list = works.filter((w) =>
    (!state.form || w.form === state.form) &&
    (!state.maker || w.maker === state.maker) &&
    (!state.model || (w.families || []).includes(state.model)) &&
    (!q || [w.repo, w.description, w.language, ...(w.models || [])].join(" ").toLowerCase().includes(q)));
  const key = { stars: (w) => -w.stars, newest: (w) => -Date.parse(w.created), pushed: (w) => -Date.parse(w.pushed) }[state.sort];
  return list.sort((a, b) => key(a) - key(b) || b.stars - a.stars);
}

// ---------- cards ----------
function objectCode(w) {
  const lines = [
    `${span("kw", "new")} ${span("ty", "Work")}(${span("str name", `"${w.name}"`)}) {`,
    `  author = ${span("str", `"${w.owner}"`)};`,
    `  stars  = ${span("num", w.stars)};`,
    `  form   = ${span("ty", w.form.toUpperCase())};`,
  ];
  if (w.models && w.models.length) lines.push(`  model  = ${span("str", `"${w.models.join('", "')}"`)};`);
  else lines.push(`  model  = ${span("kw", "null")}; ${span("cm", `// ${MAKERS[w.maker]}`)}`);
  lines.push(`  lang   = ${w.language ? span("str", `"${w.language}"`) : span("kw", "null")};`);
  lines.push(`  since  = ${span("num", w.created)};`);
  lines.push("}");
  return lines.join("\n");
}

function card(w, tpl) {
  const node = tpl.content.firstElementChild.cloneNode(true);
  node.id = "w-" + w.repo.replace(/[^\w-]/g, "_");
  const thumb = node.querySelector(".thumb");
  thumb.href = w.demo || w.url;
  const img = node.querySelector("img");
  const sources = [w.preview, w.og].filter(Boolean);
  img.alt = w.repo;
  img.referrerPolicy = "no-referrer";
  const setSrc = () => {
    img.src = sources[0];
    img.classList.toggle("og", sources[0] === w.og);
  };
  img.onerror = () => {
    sources.shift();
    if (sources.length) setSrc();
    else img.replaceWith(Object.assign(document.createElement("span"), { className: "ph", textContent: `// ${w.repo}\n// preview not found` }));
  };
  setSrc();

  const badges = [];
  if (generated && daysBetween(w.created, generated) <= NEW_DAYS) badges.push(`<span class="badge new">NEW</span>`);
  if (w.maker === "ai") badges.push(`<span class="badge ai">AI</span>`);
  if (w.demo) badges.push(`<span class="badge">▶ 在线</span>`);
  node.querySelector(".badges").innerHTML = badges.join("");

  node.querySelector(".obj code").innerHTML = objectCode(w);
  const desc = node.querySelector(".desc");
  if (w.description) desc.textContent = "// " + w.description;
  else desc.remove();

  const acts = [];
  if (w.demo) acts.push(`<a class="run" href="${esc(w.demo)}" target="_blank" rel="noopener">run()</a>`);
  acts.push(`<a href="${esc(w.url)}" target="_blank" rel="noopener">source()</a>`);
  for (const bv of w.bilibili || []) acts.push(`<a href="https://www.bilibili.com/video/${esc(bv)}" target="_blank" rel="noopener">bilibili("${esc(bv.slice(0, 6))}…")</a>`);
  for (const yt of w.youtube || []) acts.push(`<a href="https://www.youtube.com/watch?v=${esc(yt)}" target="_blank" rel="noopener">youtube()</a>`);
  node.querySelector(".actions").innerHTML = acts.join("");
  return node;
}

function renderGrid(list) {
  const grid = $("#grid");
  const tpl = $("#card-tpl");
  const frag = document.createDocumentFragment();
  list.forEach((w, i) => {
    const c = card(w, tpl);
    c.style.animationDelay = Math.min(i, 24) * 18 + "ms";
    frag.appendChild(c);
  });
  grid.replaceChildren(frag);
  $("#result-count").textContent = list.length;
  $("#empty").hidden = list.length > 0;
}

// ---------- main ----------
function update(rerenderControls) {
  writeState();
  if (rerenderControls) { renderFilters(); renderArena(); }
  renderGrid(filtered());
}

function resetAll() {
  Object.assign(state, { form: "", maker: "", model: "", q: "", sort: "stars" });
  update(true);
}

function executeRandom() {
  const cards = [...document.querySelectorAll("#grid .card")];
  if (!cards.length) return;
  const c = cards[Math.floor(Math.random() * cards.length)];
  c.classList.remove("flash");
  void c.offsetWidth;
  c.classList.add("flash");
  c.scrollIntoView({ behavior: "smooth", block: "center" });
}

async function main() {
  const slug = repoSlug();
  $("#repo-link").href = `https://github.com/${slug}`;
  $("#submit-link").href = `https://github.com/${slug}/issues/new?template=submit-work.yml`;

  let data;
  try {
    const res = await fetch("data/works.json", { cache: "no-cache" });
    data = await res.json();
  } catch (err) {
    $("#boot").classList.add("done");
    $("#grid").innerHTML = `<p class="empty"><span class="err">IOException</span>: 无法加载 data/works.json（${esc(err.message)}）。本地预览请用 <code>python3 -m http.server</code>。</p>`;
    return;
  }
  works = data.works;
  generated = data.generated;
  $("#hero-count").textContent = works.length;
  $("#hero-date").textContent = generated.slice(0, 10);
  document.title = `world.execute(gallery); · ${works.length} 个 Mili world.execute(me); 二创`;

  boot(works.length);
  readState();
  update(true);
  $("#random").onclick = executeRandom;
  $("#reset").onclick = resetAll;
  document.querySelector("[data-reset]").onclick = resetAll;
}

main();

"use strict";

/* ------------------------------------------------------------------ bridge
 * pywebview exposes window.pywebview.api; the developer server answers
 * POST /api/<name> with a JSON array of arguments. */
const api = new Proxy({}, {
  get: (_, name) => async (...args) => {
    if (window.pywebview && window.pywebview.api) return window.pywebview.api[name](...args);
    const r = await fetch("/api/" + name, { method: "POST", body: JSON.stringify(args) });
    const j = await r.json();
    if (!j.ok) throw new Error(j.error);
    return j.result;
  },
});

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const h = (html) => { const t = document.createElement("template"); t.innerHTML = html.trim(); return t.content.firstElementChild; };
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const fileLabel = (p) => {
  const i = Math.max(p.lastIndexOf("/"), p.lastIndexOf("\\"));
  return `<strong>${esc(p.slice(i + 1))}</strong><br><span title="${esc(p)}">${esc(p.slice(0, i))}</span>`;
};
const gem = (cls = "slot-gem") => `<svg class="${cls}" aria-hidden="true"><use href="#gem"/></svg>`;

const num = (x) => Number(x).toLocaleString(LANG, { maximumFractionDigits: 1 });
/* Backend message code -> text in the current language. */
function msgText(code, args, fallback) {
  if (!code) return fallback || "";
  const key = code.startsWith("msg.") || code.startsWith("err.") || code.startsWith("d.") ? code : "msg." + code;
  return tt(key, args || {}, fallback || code);
}
function jobLine(j) {
  const stage = t("stage." + j.stage) || "";
  const detail = j.detail ? msgText(j.detail, j.detail_args) : "";
  return detail && detail !== stage ? `${stage} – ${detail}` : stage;
}

const S = {
  state: null,
  view: "library",
  active: 0,
  sheetGame: null,
  picks: {},          // game_id -> DiscCheck
  include: {},        // game_id -> bool
  step: 1,
  wasRunning: false,
};

/* ------------------------------------------------------------------ boot */
let wired = false;
async function boot() {
  const prefs = (await api.get_prefs()) || {};
  setLang(pickLang(prefs.lang), false);
  if (!wired) { wireStatic(); wired = true; }
  await refresh();
  const any = S.state.games.some((g) => g.installed);
  show(any ? "library" : "library");
  setInterval(tick, 700);
  pollGamepad();
  updateInit();
}

async function refresh() {
  S.state = await api.get_state();
  if (S.view === "library") renderLibrary();
  if (S.view === "setup") renderSetup();
}

async function tick() {
  try {
    const st = await api.get_state();
    const running = st.build.running;
    S.state = st;
    if (S.view === "setup" && (running || S.wasRunning)) {
      if (running && S.step !== 2) gotoStep(2);
      renderJobs();
      if (!running && S.wasRunning) finishBuild();
    }
    if (S.view === "library") updateLibraryStatus();
    if (U.s && (["downloading", "verifying", "applying"].includes(U.s.phase) || U.s.phase === "ready")) {
      U.s = await api.update_state();
      renderUpdate();
    }
    S.wasRunning = running;
  } catch (e) { /* window closing */ }
}

function show(view) {
  if (!S.state) return;
  S.view = view;
  $$(".view").forEach((v) => (v.hidden = v.id !== "view-" + view));
  $$(".navbtn").forEach((b) => b.toggleAttribute("aria-current", b.dataset.view === view));
  $$(".navbtn").forEach((b) => b.dataset.view === view ? b.setAttribute("aria-current", "page") : b.removeAttribute("aria-current"));
  if (view === "library") renderLibrary();
  if (view === "setup") {
    if (S.state.build.running) gotoStep(2);
    else if (S.step === 2) gotoStep(1);
    renderSetup();
  }
}

/* ------------------------------------------------------------------ library */
function renderLibrary() {
  const box = $("#worlds");
  const games = S.state.games;
  if (!games.some((g) => g.installed)) {
    box.innerHTML = "";
    box.append(h(`
      <div class="empty">
        <div>
          <div class="gems">
            <svg style="--g1:#ffe3a3;--g2:#f5b82e;--g3:#c26a14"><use href="#gem"/></svg>
            <svg style="--g1:#b8ffe8;--g2:#33c9a0;--g3:#137a68"><use href="#gem"/></svg>
            <svg style="--g1:#eadcff;--g2:#b086ff;--g3:#5d38b0"><use href="#gem"/></svg>
          </div>
          <h1>${esc(t("lib.empty.title"))}</h1>
          <p>${esc(t("lib.empty.text"))}</p>
          <button class="btn btn-gold btn-lg" data-go-setup>${esc(t("lib.empty.start"))}</button>
        </div>
      </div>`));
    $("[data-go-setup]", box).onclick = () => show("setup");
    $("#pad-hint").hidden = true;
    return;
  }
  $("#pad-hint").hidden = false;
  box.innerHTML = "";
  games.forEach((g, i) => {
    const el = h(`
      <article class="world" data-game="${g.id}" tabindex="0" aria-label="${esc(g.title)}">
        ${g.id === "spyro3" ? '<span class="moon" aria-hidden="true"></span>' : ""}
        <span class="numeral" aria-hidden="true">${g.number}</span>
        <div class="gem">${gem("")}</div>
        <h2>${esc(g.title)}</h2>
        <p class="meta">${esc(tt("game." + g.id + ".sub", {}, g.subtitle))}, ${g.year}</p>
        <div class="row"></div>
      </article>`);
    el.addEventListener("mouseenter", () => setActive(i));
    el.addEventListener("focus", () => setActive(i));
    el.addEventListener("click", (ev) => { if (!ev.target.closest("button")) setActive(i); });
    box.append(el);
  });
  setActive(Math.min(S.active, games.length - 1));
  updateLibraryStatus();
}

function updateLibraryStatus() {
  $$(".world").forEach((el) => {
    const g = S.state.games.find((x) => x.id === el.dataset.game);
    const row = $(".row", el);
    const key = JSON.stringify([g.installed, g.running, g.disc_missing, g.outdated, S.state.build.running, LANG]);
    if (row.dataset.key === key) return;
    row.dataset.key = key;
    row.innerHTML = "";
    if (!g.installed) {
      const b = h(`<button class="btn btn-ghost">${esc(t("lib.setup"))}</button>`);
      b.onclick = () => { show("setup"); };
      row.append(b, h(`<span class="status">${esc(t("lib.not_installed"))}</span>`));
      row.querySelector(".btn").style.display = "inline-block";
      return;
    }
    const play = h(`<button class="btn btn-gold btn-lg">${esc(t(g.running ? "lib.running" : "lib.play"))}</button>`);
    play.disabled = g.running;
    play.onclick = () => launch(g.id);
    const set = h(`<button class="btn btn-ghost">${esc(t("lib.settings"))}</button>`);
    set.onclick = () => openSheet(g.id);
    row.append(play, set);
    if (g.disc_missing) row.append(h(`<span class="status warn">${esc(t("lib.disc_missing"))}</span>`));
    else if (g.outdated) {
      const up = h(`<button class="btn btn-text update">${esc(t("lib.update"))}</button>`);
      up.title = t("lib.update_tip");
      up.onclick = () => show("setup");
      row.append(up);
    }
  });
}

function setActive(i) {
  S.active = i;
  $$(".world").forEach((el, j) => el.classList.toggle("is-active", j === i));
}

async function launch(id) {
  const r = await api.launch(id);
  if (!r.ok) return toast(tt(r.code, {}, r.message || r.code));
  toast(t("lib.launched"));
  setTimeout(refresh, 600);
}

/* ------------------------------------------------------------------ setup */
function gotoStep(n) {
  S.step = n;
  $$(".step-panel").forEach((p) => (p.hidden = Number(p.dataset.panel) !== n));
  $$(".steps li").forEach((li) => {
    const k = Number(li.dataset.step);
    li.classList.toggle("is-current", k === n);
    li.classList.toggle("is-done", k < n);
  });
}

async function prefillInstalled() {
  /* Installed games: offer their known image so a rebuild is one checkbox away. */
  for (const g of S.state.games) {
    if (!g.installed || S.picks[g.id] || !g.info || !g.info.cue) continue;
    try {
      const c = await api.identify(g.info.cue);
      if (c.game_id === g.id) { S.picks[g.id] = c; S.include[g.id] = !!g.outdated; }
    } catch (e) { /* image moved: leave the slot empty */ }
  }
  if (S.step === 1) renderSlots();
}

function renderSetup() {
  if (S.step === 1) { renderSlots(); prefillInstalled(); }
  if (S.step === 2) renderJobs();
}

function renderSlots() {
  const box = $("#slots");
  box.innerHTML = "";
  for (const g of S.state.games) {
    const pick = S.picks[g.id];
    let check = "", ready = false;
    if (pick) {
      if (!pick.ok) check = `<p class="check bad">${esc(msgText(pick.code, pick.args, pick.message))}</p>`;
      else if (pick.sbi === "missing") check = `<p class="check bad">${esc(t("slot.sbi_missing"))}</p>`;
      else if (pick.sbi === "invalid") check = `<p class="check bad">${esc(t("slot.sbi_invalid"))}</p>`;
      else { check = `<p class="check ok">${esc(t(pick.sbi === "ok" ? "slot.detected_sbi" : "slot.detected", pick))}</p>`; ready = true; }
    } else if (g.installed) {
      check = `<p class="check info">${esc(t("slot.installed"))}</p>`;
    } else {
      check = `<p class="check info">${esc(t("slot.none"))}</p>`;
    }
    if (!ready) S.include[g.id] = false;
    else if (S.include[g.id] === undefined) S.include[g.id] = !g.installed;
    const el = h(`
      <div class="slot ${ready ? (S.include[g.id] ? "is-ready" : "") : "is-empty"}" data-game="${g.id}">
        ${gem()}
        <h3>${esc(g.title)}</h3>
        <p class="file">${pick ? fileLabel(pick.path) : ""}</p>
        ${check}
        <label class="include"><input type="checkbox" ${S.include[g.id] ? "checked" : ""} ${ready ? "" : "disabled"}>
          ${esc(t(g.installed ? "slot.rebuild" : "slot.build"))}</label>
      </div>`);
    $("input", el).onchange = (e) => { S.include[g.id] = e.target.checked; renderSlots(); };
    box.append(el);
  }
  const n = Object.values(S.include).filter(Boolean).length;
  const btn = $("#btn-build");
  btn.disabled = n === 0 || S.state.build.running;
  btn.textContent = t(n > 1 ? "setup.build_n" : n === 1 ? "setup.build_1" : "setup.build_0", { n });
  const need = n * 1.2;
  $("#space-note").textContent = n
    ? t("setup.space", { need: num(need), free: num(S.state.free_gb) })
    : t("setup.first_tools");
}

function addPicks(list) {
  let added = 0, unknown = 0;
  for (const c of list) {
    if (c.game_id) { S.picks[c.game_id] = c; S.include[c.game_id] = c.ok && c.sbi !== "missing" && c.sbi !== "invalid"; added++; }
    else unknown++;
  }
  renderSlots();
  if (!list.length) toast(t("setup.none_found"));
  else if (unknown && !added) toast(msgText(list[0].code, list[0].args, list[0].message));
}

async function startBuild() {
  const sel = {};
  for (const [id, on] of Object.entries(S.include)) if (on && S.picks[id]) sel[id] = S.picks[id].path;
  const ok = await api.start_build(sel);
  if (!ok) return toast(t("err.generic", { detail: "start_build" }));
  S.wasRunning = true;
  gotoStep(2);
  $("#jobs").innerHTML = "";
  renderJobs();
}

function renderJobs() {
  const b = S.state.build;
  $("#tools-label").textContent = b.tools.code ? tt(b.tools.code, b.tools.args, "") : "";
  $("#tools-bar").style.width = (b.tools.progress * 100).toFixed(1) + "%";
  $("#tools-progress").hidden = b.tools.progress >= 1;
  const box = $("#jobs");
  for (const j of b.jobs) {
    const g = S.state.games.find((x) => x.id === j.game_id);
    let el = $(`.job[data-game="${j.game_id}"]`, box);
    if (!el) {
      el = h(`
        <div class="job" data-game="${j.game_id}">
          ${gem()}
          <h3>${esc(g.title)}</h3><span class="pct"></span>
          <div class="bar"><i></i></div>
          <p class="detail small"></p>
          <details><summary>${esc(t("build.log"))}</summary><pre></pre></details>
        </div>`);
      box.append(el);
    }
    el.classList.toggle("is-error", j.status === "error");
    el.classList.toggle("is-done", j.status === "done");
    const pct = Math.round(j.progress * 100);
    $(".pct", el).textContent = j.status === "running" ? pct + " %" : t("job." + j.status) || pct + " %";
    $(".bar i", el).style.width = (j.status === "done" ? 100 : pct) + "%";
    $(".detail", el).textContent = j.status === "error" ? msgText(j.error, j.error_args)
      : j.status === "running" ? jobLine(j) : "";
    const pre = $("pre", el);
    if ($("details", el).open) pre.textContent = j.log_tail.join("\n");
  }
  $("#btn-cancel").disabled = !b.running;
}

function finishBuild() {
  finishBuildTexts();
  S.picks = {}; S.include = {};
  gotoStep(3);
}
function finishBuildTexts() {
  const jobs = S.state.build.jobs;
  const okN = jobs.filter((j) => j.status === "done").length;
  $("#done-title").textContent = t(okN === jobs.length ? (okN === 1 ? "done.all_1" : "done.all_n")
    : okN ? "done.some" : "done.none");
  const box = $("#done-list");
  box.innerHTML = "";
  for (const j of jobs) {
    const g = S.state.games.find((x) => x.id === j.game_id);
    box.append(h(`
      <div class="done-item job" data-game="${j.game_id}" style="display:flex">
        ${gem()}
        <div><p><strong>${esc(g.title)}</strong></p>
        ${j.status === "done" ? `<p class="small">${esc(t("done.ok"))}</p>`
          : `<p class="err">${esc(j.error ? msgText(j.error, j.error_args) : t(j.status === "cancelled" ? "done.cancelled" : "done.skipped"))}</p>`}</div>
      </div>`));
  }
}

/* ------------------------------------------------------------------ settings sheet */
async function openSheet(id) {
  const g = S.state.games.find((x) => x.id === id);
  S.sheetGame = id;
  $("#sheet .sheet-body").dataset.game = id;
  $("#sheet-title").textContent = g.title;
  $("#sheet-sub").textContent = g.info ? t("sheet.sub", g.info) : "";
  S.tab = S.tab || "game";
  await showTab(S.tab);
  $("#sheet").hidden = false;
  $("#sheet .iconbtn").focus();
}

function renderSettings(values) {
  const box = $("#sheet-content");
  box.innerHTML = "";
  let group = null;
  for (const s of S.state.settings_schema) {
    if (s.group !== group) { group = s.group; box.append(h(`<h3>${esc(tt("grp." + group, {}, group))}</h3>`)); }
    const v = values[s.id];
    const fid = "set-" + s.id;
    let control;
    if (s.kind === "choice") {
      control = h(`<select id="${fid}">${s.choices.map(([val, lab]) =>
        `<option value="${esc(val)}" ${String(val) === String(v) ? "selected" : ""}>${esc(tt(`set.${s.id}.${val}`, {}, lab))}</option>`).join("")}</select>`);
      control.onchange = () => save(s.id, control.value);
    } else if (s.kind === "bool") {
      control = h(`<span class="toggle"><input type="checkbox" id="${fid}" ${v ? "checked" : ""}><span></span></span>`);
      $("input", control).onchange = (e) => save(s.id, e.target.checked);
    } else {
      control = h(`<span class="range"><input type="range" id="${fid}" min="${s.min}" max="${s.max}" step="${s.step}" value="${v}"><output>${v}</output></span>`);
      const inp = $("input", control);
      inp.oninput = () => ($("output", control).textContent = inp.value);
      inp.onchange = () => save(s.id, Number(inp.value));
    }
    const help = tt(`set.${s.id}.help`, {}, s.help);
    const row = h(`<div class="setting"><div class="setting-top"><label for="${fid}">${esc(tt("set." + s.id, {}, s.label))}</label></div>
                   ${help ? `<p class="help">${esc(help)}</p>` : ""}</div>`);
    $(".setting-top", row).append(control);
    box.append(row);
  }
}

async function save(id, value) {
  try {
    await api.set_setting(S.sheetGame, id, value);
    const g = S.state.games.find((x) => x.id === S.sheetGame);
    toast(t(g.running ? "sheet.saved_running" : "sheet.saved"));
  } catch (e) { toast(e.message); }
}

function closeSheet() { stopListening(); $("#sheet").hidden = true; S.sheetGame = null; }

async function showTab(tab) {
  S.tab = tab;
  stopListening();
  $$(".tabs [data-tab]").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.tab === tab)));
  $$(".sheet-foot [data-for]").forEach((el) => (el.hidden = el.dataset.for !== tab));
  if (tab === "game") renderSettings(await api.get_settings(S.sheetGame));
  else renderControls(await api.get_controls(S.sheetGame));
}

/* ------------------------------------------------------------------ controls */
const BUTTONS = ["up", "down", "left", "right", "cross", "circle", "square", "triangle",
                 "l1", "r1", "l2", "r2", "start", "select", "l3", "r3"];
const PS_GLYPH = { cross: "✕", circle: "○", square: "□", triangle: "△", up: "↑", down: "↓", left: "←", right: "→",
                   l1: "L1", r1: "R1", l2: "L2", r2: "R2", l3: "L3", r3: "R3", start: "▶", select: "■" };
/* KeyboardEvent.code -> SDL key name (what keybinds.ini expects) */
function sdlKey(e) {
  const c = e.code;
  if (/^Key[A-Z]$/.test(c)) return c.slice(3);
  if (/^Digit\d$/.test(c)) return c.slice(5);
  if (/^F\d{1,2}$/.test(c)) return c;
  if (/^Numpad\d$/.test(c)) return "Keypad " + c.slice(6);
  const map = {
    ArrowUp: "Up", ArrowDown: "Down", ArrowLeft: "Left", ArrowRight: "Right", Enter: "Return", NumpadEnter: "Keypad Enter",
    Space: "Space", Tab: "Tab", ShiftLeft: "Left Shift", ShiftRight: "Right Shift", ControlLeft: "Left Ctrl",
    ControlRight: "Right Ctrl", AltLeft: "Left Alt", AltRight: "Right Alt", Backquote: "`", Minus: "-", Equal: "=",
    BracketLeft: "[", BracketRight: "]", Backslash: "\\", Semicolon: ";", Quote: "'", Comma: ",", Period: ".",
    Slash: "/", Insert: "Insert", Home: "Home", End: "End", PageUp: "PageUp", PageDown: "PageDown", CapsLock: "CapsLock",
    NumpadAdd: "Keypad +", NumpadSubtract: "Keypad -", NumpadMultiply: "Keypad *", NumpadDivide: "Keypad /",
  };
  return map[c] || null;
}
const PAD_BUTTON = ["a", "b", "x", "y", "leftshoulder", "rightshoulder", "lefttrigger", "righttrigger",
                    "back", "start", "leftstick", "rightstick", "dpup", "dpdown", "dpleft", "dpright"];
const PAD_AXIS = [["leftx-", "leftx+"], ["lefty-", "lefty+"], ["rightx-", "rightx+"], ["righty-", "righty+"]];
function padLabel(v) {
  const names = { a: "A", b: "B", x: "X", y: "Y", leftshoulder: "LB", rightshoulder: "RB", lefttrigger: "LT",
    righttrigger: "RT", back: "View", start: "Menu", leftstick: "LS", rightstick: "RS",
    dpup: "✛ ↑", dpdown: "✛ ↓", dpleft: "✛ ←", dpright: "✛ →",
    "leftx-": "LS ←", "leftx+": "LS →", "lefty-": "LS ↑", "lefty+": "LS ↓",
    "rightx-": "RS ←", "rightx+": "RS →", "righty-": "RS ↑", "righty+": "RS ↓" };
  return v.split(",").map((p) => p.trim()).map((p) => names[p] || names[p.replace(/[+-]$/, "")] || p).join(", ");
}
function keyLabel(v) {
  const de = LANG === "de";
  const names = { Return: "Enter", Up: "↑", Down: "↓", Left: "←", Right: "→",
    "Right Shift": de ? "Shift rechts" : "Right Shift", "Left Shift": de ? "Shift links" : "Left Shift",
    "Left Ctrl": de ? "Strg links" : "Left Ctrl", "Right Ctrl": de ? "Strg rechts" : "Right Ctrl",
    Space: de ? "Leertaste" : "Space" };
  return v.split(",").map((p) => p.trim()).map((p) => names[p] || p).join(", ");
}

function renderControls(binds) {
  const box = $("#sheet-content");
  box.innerHTML = `<p class="ctl-intro">${esc(t("ctl.intro"))}</p>
    <table class="ctl-table"><thead><tr><th>${esc(t("ctl.button"))}</th><th>${esc(t("ctl.keyboard"))}</th>
    <th>${esc(t("ctl.controller"))}</th></tr></thead><tbody></tbody></table>`;
  const body = $("tbody", box);
  for (const b of BUTTONS) {
    const k = binds.keys[b] || "None", p = binds.pad[b] || "None";
    const act = t("act." + b);
    const cell = (dev, v) => {
      const none = !v || v === "None";
      return `<button class="bind ${none ? "is-none" : ""}" data-dev="${dev}" data-btn="${b}">${esc(none ? t("ctl.none") : dev === "keys" ? keyLabel(v) : padLabel(v))}</button>`;
    };
    body.append(h(`<tr><td><div class="ctl-name"><span class="ps ps-${b}">${PS_GLYPH[b]}</span>
      <span>${esc(t("btn." + b))}${act ? `<small>${esc(act)}</small>` : ""}</span></div></td>
      <td>${cell("keys", k)}</td><td>${cell("pad", p)}</td></tr>`));
  }
  $$(".bind", body).forEach((el) => (el.onclick = () => listen(el)));
}

let listening = null;
function stopListening() {
  if (!listening) return;
  window.removeEventListener("keydown", listening.onKey, true);
  cancelAnimationFrame(listening.raf);
  listening = null;
}
function listen(el) {
  stopListening();
  const dev = el.dataset.dev, btn = el.dataset.btn;
  el.classList.add("is-listening");
  el.textContent = t(dev === "keys" ? "ctl.press_key" : "ctl.press_pad");
  const finish = async (value) => {
    stopListening();
    if (value === undefined) return renderControls(await api.get_controls(S.sheetGame));
    try {
      renderControls(await api.set_control(S.sheetGame, dev, btn, value));
      toast(t("ctl.saved"));
    } catch (e) { toast(t("err.generic", { detail: e.message || e })); }
  };
  const onKey = (e) => {
    e.preventDefault(); e.stopPropagation();
    if (e.code === "Escape") return finish(undefined);
    if (e.code === "Delete" || e.code === "Backspace") return finish("None");
    if (dev === "keys") { const k = sdlKey(e); if (k) finish(k); }
  };
  window.addEventListener("keydown", onKey, true);
  const baseline = snapshotPad();
  const poll = () => {
    if (dev === "pad") {
      const v = newPadInput(baseline);
      if (v) return finish(v);
    }
    listening.raf = requestAnimationFrame(poll);
  };
  listening = { onKey, raf: requestAnimationFrame(poll) };
}
function snapshotPad() {
  const pad = navigator.getGamepads ? [...navigator.getGamepads()].find(Boolean) : null;
  return pad ? pad.buttons.map((b) => b.pressed) : [];
}
function newPadInput(baseline) {
  const pad = navigator.getGamepads ? [...navigator.getGamepads()].find(Boolean) : null;
  if (!pad) return null;
  for (let i = 0; i < PAD_BUTTON.length; i++)
    if (pad.buttons[i] && pad.buttons[i].pressed && !baseline[i]) return PAD_BUTTON[i];
  for (let a = 0; a < 4; a++) {
    const v = pad.axes[a] || 0;
    if (Math.abs(v) > 0.7) return PAD_AXIS[a][v < 0 ? 0 : 1];
  }
  return null;
}

/* ------------------------------------------------------------------ dialogs */
function confirmBox(title, text, yes) {
  return new Promise((resolve) => {
    $("#modal-title").textContent = title;
    $("#modal-text").textContent = text;
    $("#modal-yes").textContent = yes;
    $("#modal").hidden = false;
    $("#modal-no").focus();
    const done = (v) => { $("#modal").hidden = true; resolve(v); };
    $("#modal-yes").onclick = () => done(true);
    $("#modal-no").onclick = () => done(false);
  });
}

let toastTimer;
function toast(msg) {
  const t = $("#toast");
  t.textContent = msg;
  t.classList.add("is-on");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove("is-on"), 3200);
}

/* ------------------------------------------------------------------ wiring */
function wireStatic() {
  $$(".navbtn").forEach((b) => (b.onclick = () => show(b.dataset.view)));
  $("#lang").onchange = (e) => setLang(e.target.value);
  renderHint();
  const guard = (fn) => async () => { try { await fn(); } catch (e) { toast(t("err.generic", { detail: e.message || e })); } };
  $("#btn-pick").onclick = guard(async () => { const l = await api.pick_images(); if (l.length) addPicks(l); });
  $("#btn-scan").onclick = guard(async () => addPicks(await api.pick_folder()));
  $("#pathform").onsubmit = async (e) => {
    e.preventDefault();
    const p = $("#pathinput").value.trim().replace(/^"|"$/g, "");
    if (!p) return;
    const list = p.toLowerCase().endsWith(".cue") ? [await api.identify(p)] : await api.scan(p);
    addPicks(list);
    $("#pathinput").value = "";
  };
  $("#btn-build").onclick = startBuild;
  $("#btn-cancel").onclick = async () => {
    if (await confirmBox(t("build.cancel_q"), t("build.cancel_text"), t("build.cancel"))) api.cancel_build();
  };
  $("#btn-to-library").onclick = () => { gotoStep(1); show("library"); };
  $("#btn-again").onclick = () => { gotoStep(1); renderSetup(); };

  $$("#sheet [data-close]").forEach((b) => (b.onclick = closeSheet));
  $$(".tabs [data-tab]").forEach((b) => (b.onclick = () => showTab(b.dataset.tab)));
  $("#btn-ctl-all").onclick = async () => { await api.controls_to_all(S.sheetGame); toast(t("ctl.all_done")); };
  $("#btn-ctl-reset").onclick = async () => { renderControls(await api.reset_controls(S.sheetGame)); toast(t("ctl.reset_done")); };
  $("#btn-saves").onclick = () => api.open_saves(S.sheetGame);
  $("#btn-all").onclick = async () => { await api.apply_to_all(S.sheetGame); toast(t("sheet.applied_all")); };
  $("#btn-reset").onclick = async () => { renderSettings(await api.reset_settings(S.sheetGame)); toast(t("sheet.reset_done")); };
  $("#btn-rebuild").onclick = () => { closeSheet(); show("setup"); toast(t("sheet.rebuild_hint")); };
  $("#btn-remove").onclick = async () => {
    const g = S.state.games.find((x) => x.id === S.sheetGame);
    if (!(await confirmBox(t("sheet.remove_q", g), t("sheet.remove_text"), t("sheet.remove")))) return;
    if (await api.uninstall(S.sheetGame)) { closeSheet(); toast(t("sheet.removed")); refresh(); }
    else toast(t("sheet.quit_first"));
  };

  document.addEventListener("keydown", (e) => {
    if (!$("#modal").hidden) { if (e.key === "Escape") $("#modal-no").click(); return; }
    if (!$("#sheet").hidden) { if (e.key === "Escape" && !listening) closeSheet(); return; }
    if (S.view !== "library" || e.target.matches("input, select")) return;
    const n = $$(".world").length;
    if (!n) return;
    if (e.key === "ArrowRight") { setActive((S.active + 1) % n); $$(".world")[S.active].focus(); }
    if (e.key === "ArrowLeft") { setActive((S.active + n - 1) % n); $$(".world")[S.active].focus(); }
    if (e.key === "Enter" && !e.target.matches("button")) activeAction("play");
    if (e.key.toLowerCase() === "e") activeAction("settings");
  });
}

function activeAction(what) {
  const g = S.state.games[S.active];
  if (!g || !g.installed) return;
  if (what === "play" && !g.running) launch(g.id);
  if (what === "settings") openSheet(g.id);
}

/* ------------------------------------------------------------------ language */
function setLang(lang, save = true) {
  LANG = lang;
  applyStaticI18n();
  const sel = $("#lang");
  sel.innerHTML = Object.entries(LANGS).map(([k, v]) => `<option value="${k}" ${k === LANG ? "selected" : ""}>${v}</option>`).join("");
  if (save) api.set_pref("lang", lang);
  if (!S.state) return;
  renderHint();
  if (S.view === "library") renderLibrary();
  if (S.view === "setup") { renderSetup(); if (S.step === 3) finishBuildTexts(); }
  if (S.sheetGame) openSheet(S.sheetGame);
  renderUpdate();
}

/* ------------------------------------------------------------------ hint line
 * Shows the controls of the device used last (keyboard/mouse or controller). */
let lastInput = "keys";
function setInput(kind) {
  if (kind === lastInput) return;
  lastInput = kind;
  renderHint();
}
const DPAD = `<svg class="dpad" viewBox="0 0 24 24" aria-hidden="true">
  <path class="dpad-v" d="M9 2h6v7h-6zM9 15h6v7h-6z"/>
  <path class="dpad-h" d="M2 9h7v6h-7zM15 9h7v6h-7z"/>
  <rect class="dpad-c" x="9" y="9" width="6" height="6"/></svg>`;
function renderHint() {
  const el = $("#pad-hint");
  if (!el) return;
  if (lastInput === "pad") {
    el.innerHTML = `<span>${DPAD} ${esc(t("hint.choose"))}</span>`
      + `<span><kbd class="pad-a">A</kbd><kbd class="pad-x">✕</kbd> ${esc(t("hint.play"))}</span>`
      + `<span><kbd class="pad-y">Y</kbd><kbd class="pad-t">△</kbd> ${esc(t("hint.settings"))}</span>`;
  } else {
    el.innerHTML = `<span><kbd>←</kbd><kbd>→</kbd> ${esc(t("hint.choose"))}</span>`
      + `<span><kbd>Enter</kbd> ${esc(t("hint.play"))}</span><span><kbd>E</kbd> ${esc(t("hint.settings"))}</span>`;
  }
}
window.addEventListener("keydown", () => setInput("keys"), true);
window.addEventListener("mousedown", () => setInput("keys"), true);
window.addEventListener("wheel", () => setInput("keys"), { passive: true, capture: true });
let lastMouse = null;
window.addEventListener("mousemove", (e) => {
  // ignore tiny jitter; a real move switches back to keyboard/mouse hints
  if (lastMouse && Math.hypot(e.clientX - lastMouse[0], e.clientY - lastMouse[1]) > 24) setInput("keys");
  lastMouse = [e.clientX, e.clientY];
}, true);

/* ------------------------------------------------------------------ gamepad */
function pollGamepad() {
  const prev = {};
  const press = (pad, i) => pad.buttons[i] && pad.buttons[i].pressed;
  function frame() {
    const pads = navigator.getGamepads ? [...navigator.getGamepads()].filter(Boolean) : [];
    for (const pad of pads) {
      const now = {
        left: press(pad, 14) || pad.axes[0] < -0.6, right: press(pad, 15) || pad.axes[0] > 0.6,
        a: press(pad, 0), b: press(pad, 1), y: press(pad, 3),
      };
      const was = prev[pad.index] || {};
      const edge = (k) => now[k] && !was[k];
      const anyPressed = pad.buttons.some((b) => b && b.pressed) || pad.axes.some((a) => Math.abs(a) > 0.5);
      if (anyPressed && document.hasFocus()) setInput("pad");
      if (document.hasFocus()) {
        if (!$("#sheet").hidden) { if (edge("b") && !listening) closeSheet(); }
        else if (S.view === "library") {
          const n = $$(".world").length;
          if (n && edge("right")) setActive((S.active + 1) % n);
          if (n && edge("left")) setActive((S.active + n - 1) % n);
          if (edge("a")) activeAction("play");
          if (edge("y")) activeAction("settings");
        }
      }
      prev[pad.index] = now;
    }
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
}

/* pywebview creates window.pywebview before its api methods exist; start only
 * once get_state is really callable, and retry for a few seconds. */
let booted = false;
async function startWhenReady(attempt = 0) {
  if (booted) return;
  const native = !location.protocol.startsWith("http");
  const ready = !native || (window.pywebview && window.pywebview.api && window.pywebview.api.get_state);
  if (ready) {
    try {
      booted = true;
      await boot();
      return;
    } catch (e) {
      booted = false;
      if (attempt > 40) { toast(t("err.start", { detail: e.message || e })); return; }
    }
  }
  setTimeout(() => startWhenReady(attempt + 1), 150);
}
window.addEventListener("pywebviewready", () => startWhenReady());
startWhenReady();


/* ------------------------------------------------------------------ updates
 * The backend asks GitHub for the latest release; the banner offers it,
 * downloads it (checksum-verified) and restarts into the new version. */
var U = { s: null };   // var: renderUpdate may run before this line (language switch)

async function updateInit() {
  $("#btn-update-go").onclick = updateGo;
  $("#btn-update-notes").onclick = openNotes;
  $("#update-later").onclick = () => ($("#update-modal").hidden = true);
  $("#update-now").onclick = () => { $("#update-modal").hidden = true; updateGo(); };
  $("#btn-update-check").onclick = () => updateCheck(true);
  $("#update-auto").onchange = (e) => api.set_pref("update_check", e.target.checked);
  try {
    U.s = await api.update_state();
    $("#update-auto").checked = U.s.auto;
    renderUpdate();
    if (U.s.auto) await updateCheck(false);
  } catch (e) { /* updates are optional */ }
}

async function updateCheck(manual) {
  const btn = $("#btn-update-check");
  btn.disabled = true;
  try {
    U.s = await api.update_check();
    renderUpdate();
    if (manual && !U.s.available)
      toast(U.s.error ? t("update.check_failed") : t("update.latest", { v: U.s.current }));
  } finally { btn.disabled = false; }
}

async function updateGo() {
  if (!U.s) return;
  if (U.s.phase === "ready") {
    if (S.state && S.state.build.running) { toast(t("update.wait_build")); return; }
    const ok = await api.update_apply();
    if (!ok) toast(t("update.e.apply"));
    U.s = await api.update_state();
  } else {
    U.s = await api.update_install();
  }
  renderUpdate();
}

function renderUpdate() {
  const s = U ? U.s : null;
  if (!s) return;
  $("#app-version").textContent = t("update.version", { v: s.current });
  const banner = $("#update-banner");
  const v = s.info ? s.info.version : "";
  const busy = s.phase === "downloading" || s.phase === "verifying";
  const failed = s.phase === "error";
  banner.hidden = !(s.available || busy || failed || s.phase === "ready" || s.phase === "applying");
  if (banner.hidden) return;
  banner.toggleAttribute("data-error", failed);
  const go = $("#btn-update-go");
  const bar = $("#update-bar");
  bar.hidden = !busy;
  bar.firstElementChild.style.width = `${Math.round((s.progress || 0) * 100)}%`;
  go.hidden = false;
  go.disabled = busy || s.phase === "applying";
  $("#btn-update-notes").hidden = !s.info || !s.info.notes;
  let title, sub;
  if (busy) {
    title = t("update.loading", { v }); sub = t("update.loading_sub"); go.textContent = t("update.install");
  } else if (s.phase === "ready" && s.error === "update.dev") {
    title = t("update.ready", { v }); sub = t("update.e.dev"); go.hidden = true;
  } else if (s.phase === "ready") {
    title = t("update.ready", { v }); sub = t("update.ready_sub"); go.textContent = t("update.restart");
  } else if (s.phase === "applying") {
    title = t("update.applying"); sub = t("update.applying_sub"); go.textContent = t("update.restart");
  } else if (failed) {
    title = t("update.failed"); sub = t(s.error.replace("update.", "update.e.")) || t("update.e.download_failed");
    go.textContent = t("update.retry");
  } else {
    title = t("update.available", { v }); sub = t("update.available_sub", { cur: s.current });
    go.textContent = t("update.install");
    if (!s.can_install) { sub = t("update.e.dev"); go.hidden = true; }
  }
  $("#update-title").textContent = title;
  $("#update-sub").textContent = sub;
}

/* Release notes: a small, safe subset of Markdown (headings, lists, bold, code). */
function mdLite(src) {
  const inline = (s) => esc(s).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/`([^`]+)`/g, "<code>$1</code>");
  let html = "", list = false;
  for (const raw of String(src || "").split(/\r?\n/)) {
    const line = raw.trim();
    const li = line.match(/^[-*] (.*)$/);
    if (li) { if (!list) { html += "<ul>"; list = true; } html += `<li>${inline(li[1])}</li>`; continue; }
    if (list) { html += "</ul>"; list = false; }
    const hd = line.match(/^#{1,6} (.*)$/);
    if (hd) html += `<h4>${inline(hd[1])}</h4>`;
    else if (line) html += `<p>${inline(line)}</p>`;
  }
  return html + (list ? "</ul>" : "");
}

function openNotes() {
  const s = U.s;
  if (!s || !s.info) return;
  $("#update-modal-title").textContent = t("update.notes_title", { v: s.info.version });
  $("#update-notes").innerHTML = mdLite(s.info.notes);
  const now = $("#update-now");
  now.textContent = s.phase === "ready" ? t("update.restart") : t("update.install");
  now.hidden = !s.can_install || s.phase === "downloading" || s.phase === "verifying" || s.phase === "applying";
  $("#update-modal").hidden = false;
}

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
    const key = JSON.stringify([g.installed, g.running, g.disc_missing, S.state.build.running, LANG]);
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

function renderSetup() {
  if (S.step === 1) renderSlots();
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
    else if (S.include[g.id] === undefined) S.include[g.id] = true;
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
    if (c.game_id) { S.picks[c.game_id] = c; S.include[c.game_id] = undefined; added++; }
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
  const values = await api.get_settings(id);
  renderSettings(values);
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

function closeSheet() { $("#sheet").hidden = true; S.sheetGame = null; }

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
  $("#btn-advanced").onclick = async () => {
    const r = await api.open_advanced(S.sheetGame);
    toast(t(r.ok ? "sheet.advanced_open" : "sheet.quit_first"));
  };
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
    if (!$("#sheet").hidden) { if (e.key === "Escape") closeSheet(); return; }
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
}

/* ------------------------------------------------------------------ hint line */
function padConnected() {
  return navigator.getGamepads && [...navigator.getGamepads()].some(Boolean);
}
function renderHint() {
  const el = $("#pad-hint");
  if (!el) return;
  if (padConnected()) {
    el.innerHTML = `<span><kbd>✛</kbd> ${esc(t("hint.choose"))}</span>`
      + `<span><kbd class="pad-a">A</kbd><kbd class="pad-x">✕</kbd> ${esc(t("hint.play"))}</span>`
      + `<span><kbd class="pad-y">Y</kbd><kbd class="pad-t">△</kbd> ${esc(t("hint.settings"))}</span>`;
  } else {
    el.innerHTML = `<span><kbd>←</kbd><kbd>→</kbd> ${esc(t("hint.choose"))}</span>`
      + `<span><kbd>Enter</kbd> ${esc(t("hint.play"))}</span><span><kbd>E</kbd> ${esc(t("hint.settings"))}</span>`;
  }
}
window.addEventListener("gamepadconnected", renderHint);
window.addEventListener("gamepaddisconnected", renderHint);

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
      if (document.hasFocus()) {
        if (!$("#sheet").hidden) { if (edge("b")) closeSheet(); }
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

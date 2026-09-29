"use strict";

/* ───────────────────────── utilities ───────────────────────── */
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const DAY_MS = 86400000;
const pad = (n) => String(n).padStart(2, "0");
const ymd = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
const parseYmd = (s) => {
  const [y, m, d] = String(s).split("-").map(Number);
  return new Date(y, (m || 1) - 1, d || 1);
};
const isYmd = (s) => /^\d{4}-\d{2}-\d{2}$/.test(String(s || ""));
const todayYmd = () => ymd(new Date());
const daysBetween = (a, b) => Math.round((parseYmd(b) - parseYmd(a)) / DAY_MS);
const addDays = (s, n) => {
  const d = parseYmd(s);
  d.setDate(d.getDate() + n);
  return ymd(d);
};
const fmtDate = (s, opts) =>
  parseYmd(s).toLocaleDateString("en-ZA", opts || { weekday: "short", day: "numeric", month: "short" });
const dec = (x, n = 0) => Number(x).toFixed(n).replace(".", ",");
const pct = (score, total = 150) => Math.round((score / total) * 100);
const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`;
const hm = (min) => {
  const h = Math.floor(min / 60);
  const m = min % 60;
  return h ? `${h} h${m ? ` ${m} min` : ""}` : `${m} min`;
};
const clockText = (ms) => {
  const t = Math.max(0, Math.round(ms / 1000));
  const h = Math.floor(t / 3600);
  const m = Math.floor((t % 3600) / 60);
  const s = t % 60;
  return h ? `${h}:${pad(m)}:${pad(s)}` : `${pad(m)}:${pad(s)}`;
};
const ytWatch = (id) => `https://www.youtube.com/watch?v=${id}`;
const ytSearch = (q) => `https://www.youtube.com/results?search_query=${encodeURIComponent(q)}`;

/* ───────────────────────── icons ───────────────────────── */
const ICON = {
  today: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
  plan: '<rect x="3" y="4" width="18" height="17" rx="2"/><path d="M3 9h18M8 2v4M16 2v4M8 13h.01M12 13h.01M16 13h.01M8 17h.01M12 17h.01"/>',
  learn: '<path d="M2 5c3-1.5 7-1.5 10 1 3-2.5 7-2.5 10-1v14c-3-1.5-7-1.5-10 1-3-2.5-7-2.5-10-1z"/><path d="M12 6v14"/>',
  papers: '<path d="M7 2h7l5 5v13a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2z"/><path d="M14 2v5h5M9 13h6M9 17h6"/>',
  cards: '<rect x="7" y="3" width="14" height="16" rx="2"/><path d="M3 7v11a3 3 0 0 0 3 3h9"/>',
  sheets: '<path d="M18 4H6l6 8-6 8h12"/>',
  strategy: '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/>',
  focus: '<circle cx="12" cy="13" r="8"/><path d="M12 9v4l2.5 2M9 2h6"/>',
  settings: '<path d="M4 6h9M17 6h3M4 12h3M11 12h9M4 18h11M19 18h1"/><circle cx="15" cy="6" r="2"/><circle cx="9" cy="12" r="2"/><circle cx="17" cy="18" r="2"/>',
  more: '<circle cx="5" cy="12" r="1.3"/><circle cx="12" cy="12" r="1.3"/><circle cx="19" cy="12" r="1.3"/>',
};
const icon = (k) =>
  `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICON[k]}</svg>`;
const PLAY = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5v14l11-7z"/></svg>';

function blossom(cx, cy, r, cls = "") {
  let petals = "";
  for (let i = 0; i < 5; i++) {
    const a = (Math.PI * 2 * i) / 5 - Math.PI / 2;
    petals += `<circle class="petal" cx="${(cx + Math.cos(a) * r * 0.62).toFixed(1)}" cy="${(cy + Math.sin(a) * r * 0.62).toFixed(1)}" r="${(r * 0.52).toFixed(1)}"/>`;
  }
  return `<g class="${cls}">${petals}<circle class="eye" cx="${cx}" cy="${cy}" r="${(r * 0.26).toFixed(1)}"/></g>`;
}
const BRAND_SVG = `<svg width="30" height="30" viewBox="0 0 30 30" aria-hidden="true">${(() => {
  let s = "";
  for (let i = 0; i < 5; i++) {
    const a = (Math.PI * 2 * i) / 5 - Math.PI / 2;
    s += `<circle cx="${(15 + Math.cos(a) * 7.5).toFixed(1)}" cy="${(15 + Math.sin(a) * 7.5).toFixed(1)}" r="6.4" fill="var(--jac)" opacity="0.9"/>`;
  }
  return s + '<circle cx="15" cy="15" r="3.4" fill="var(--card)"/>';
})()}</svg>`;

/* ───────────────────────── state ───────────────────────── */
const STORE_KEY = "matric-hq-v1";
const LOCAL_KEY = "matric-hq-local-v1";
const DEFAULT_EXAM = "2026-10-24";
const PLAN_LEN = 25;

function freshState() {
  return {
    v: 1,
    examDate: DEFAULT_EXAM,
    examConfirmed: false,
    name: "",
    paperDates: { "maths.1": "", "maths.2": "", "phys.1": "", "phys.2": "" },
    tasks: {},
    topics: {},
    practice: {},
    videos: {},
    attempts: [],
    cards: {},
    minutes: {},
    updatedAt: 0,
  };
}
function normalize(x) {
  const f = freshState();
  if (!x || typeof x !== "object") return f;
  const s = { ...f, ...x, paperDates: { ...f.paperDates, ...(x.paperDates || {}) } };
  if (!isYmd(s.examDate)) s.examDate = DEFAULT_EXAM;
  for (const k of ["tasks", "topics", "practice", "videos", "cards", "minutes"]) if (!s[k] || typeof s[k] !== "object") s[k] = {};
  if (!Array.isArray(s.attempts)) s.attempts = [];
  return s;
}
function readJSON(k) {
  try {
    const s = localStorage.getItem(k);
    return s ? JSON.parse(s) : null;
  } catch {
    return null;
  }
}
function writeJSON(k, v) {
  try {
    localStorage.setItem(k, JSON.stringify(v));
  } catch {
    /* private window or storage blocked: the page still works for this visit */
  }
}

let S = normalize(readJSON(STORE_KEY));
let L = Object.assign(
  { learnTab: "maths", pSubj: "all", pSess: "nov", sheet: "maths", focus: null, exam: null, focusSubj: "maths", focusLen: 25, logOpen: null },
  readJSON(LOCAL_KEY) || {}
);

function commit() {
  S.updatedAt = Date.now();
  writeJSON(STORE_KEY, S);
  Sync.schedule();
}
function saveLocal() {
  writeJSON(LOCAL_KEY, L);
}

/* Progress follows the learner between devices when the page is opened
   inside Claude (private per-person store). Anywhere else it stays in this
   browser, with a backup code in Settings. */
const Sync = {
  ref: null,
  status: "local",
  busy: false,
  again: false,
  timer: 0,
  async init() {
    const c = window.claude;
    if (!c || typeof c.use !== "function") return;
    try {
      const [db, user] = await Promise.all([c.use("db"), c.use("user")]);
      if (!db || !user) return;
      const uid = await user.id();
      if (!uid) return;
      this.ref = db.doc(`data/users/${uid}/progress`);
      await this.pull(true);
      if (this.ref) this.status = "synced";
      paintSync();
      document.addEventListener("visibilitychange", () => {
        if (document.visibilityState === "visible") this.pull(false);
      });
    } catch {
      this.ref = null;
      this.status = "local";
    }
  },
  async pull(first) {
    if (!this.ref || this.busy) return;
    try {
      const snap = await this.ref.get();
      const d = snap.exists ? snap.data() : null;
      let remote = null;
      try {
        remote = d && typeof d.json === "string" ? JSON.parse(d.json) : null;
      } catch {
        remote = null;
      }
      const rT = remote ? Number(remote.updatedAt) || 0 : 0;
      if (remote && rT > S.updatedAt) {
        S = normalize(remote);
        writeJSON(STORE_KEY, S);
        render(true);
      } else if (S.updatedAt > rT && (first || S.updatedAt - rT > 0)) {
        this.schedule(0);
      }
    } catch {
      /* stay on local data */
    }
  },
  schedule(delay = 1500) {
    if (!this.ref) return;
    clearTimeout(this.timer);
    this.timer = setTimeout(() => this.push(), delay);
  },
  async push() {
    if (!this.ref) return;
    if (this.busy) {
      this.again = true;
      return;
    }
    this.busy = true;
    try {
      await this.ref.set({ json: JSON.stringify(S), updatedAt: S.updatedAt });
      this.status = "synced";
    } catch (e) {
      if (e && e.code === "invalid_argument") {
        this.ref = null;
        this.status = "local";
      } else this.status = "retry";
    }
    this.busy = false;
    paintSync();
    if (this.again) {
      this.again = false;
      this.schedule(400);
    } else if (this.status === "retry") this.schedule(8000);
  },
};
function syncLabel() {
  if (Sync.status === "synced") return "Progress saved to your Claude account";
  if (Sync.status === "retry") return "Saved on this device, syncing when possible";
  return "Progress saved on this device";
}
function paintSync() {
  $$("[data-sync]").forEach((el) => (el.textContent = syncLabel()));
}

/* ───────────────────────── plan maths ───────────────────────── */
const startDate = () => addDays(S.examDate, -PLAN_LEN);
const dayDate = (n) => addDays(startDate(), n - 1);
const todayIndex = () => daysBetween(startDate(), todayYmd()) + 1;
const daysToExam = () => daysBetween(todayYmd(), S.examDate);
const taskId = (n, i) => `d${n}.${i}`;
function dayProgress(n) {
  const d = PLAN[n - 1];
  const done = d.tasks.filter((_, i) => S.tasks[taskId(n, i)]).length;
  return { done, total: d.tasks.length, left: d.tasks.reduce((m, t, i) => m + (S.tasks[taskId(n, i)] ? 0 : t.min), 0) };
}
function allTaskStats() {
  let done = 0,
    total = 0;
  PLAN.forEach((d) => d.tasks.forEach((_, i) => {
    total++;
    if (S.tasks[taskId(d.n, i)]) done++;
  }));
  return { done, total };
}
const phaseOf = (n) => PHASES.find((p) => n >= p.days[0] && n <= p.days[1]);

/* ───────────────────────── papers ───────────────────────── */
const SESS = Object.fromEntries(PAPERS.map((s) => [s.key, s]));
const pKey = (sess, subj, p) => `${sess}.${subj}.${p}`;
const paperName = (subj, p) => (subj === "maths" ? `Maths P${p}` : p === 1 ? "Physics P1" : "Chemistry P2");
function links(sess, subj, p) {
  const s = SESS[sess];
  if (!s) return null;
  const d = s[subj] || {};
  return { qp: d["p" + p] || null, memo: d["m" + p] || null, ab: subj === "maths" && p === 2 ? d.ab || null : null, page: s.page, label: s.label };
}
function attemptsFor(key) {
  return S.attempts.filter((a) => a.key === key).sort((a, b) => (a.date < b.date ? -1 : a.date > b.date ? 1 : a.id - b.id));
}
function paperButtons(sess, subj, p, small = true) {
  const l = links(sess, subj, p);
  if (!l) return "";
  const cls = `btn ghost${small ? " sm" : ""}`;
  const out = [];
  out.push(l.qp ? `<a class="${cls} ext" href="${esc(l.qp)}" target="_blank" rel="noopener">Question paper</a>` : `<a class="${cls} ext" href="${esc(l.page)}" target="_blank" rel="noopener">Find paper on DBE site</a>`);
  if (l.memo) out.push(`<a class="${cls} ext" href="${esc(l.memo)}" target="_blank" rel="noopener">Memo</a>`);
  else if (l.qp) out.push(`<a class="${cls} ext" href="${esc(l.page)}" target="_blank" rel="noopener">Memo (DBE page)</a>`);
  if (l.ab) out.push(`<a class="${cls} ext" href="${esc(l.ab)}" target="_blank" rel="noopener">Answer book</a>`);
  return out.join("");
}

/* ───────────────────────── rendering core ───────────────────────── */
const NAV = [
  ["today", "Today", "today"],
  ["plan", "25-day plan", "plan"],
  ["learn", "Learn", "learn"],
  ["papers", "Past papers", "papers"],
  ["cards", "Drill", "cards"],
  ["sheets", "Formula sheets", "sheets"],
  ["strategy", "Exam game plan", "strategy"],
  ["focus", "Focus timer", "focus"],
  ["settings", "Settings", "settings"],
];
const TABS = [
  ["today", "Today"],
  ["plan", "Plan"],
  ["learn", "Learn"],
  ["papers", "Papers"],
  ["more", "More"],
];
const ROUTE_NAV = { day: "plan", t: "learn", pp: "papers", deck: "cards" };

function parseHash() {
  let h = "";
  try {
    h = decodeURIComponent(location.hash.slice(1));
  } catch {
    h = location.hash.slice(1);
  }
  h = h || "today";
  const i = h.indexOf(".");
  return i < 0 ? { name: h, arg: "" } : { name: h.slice(0, i), arg: h.slice(i + 1) };
}
function go(hash) {
  if (location.hash === "#" + hash) render();
  else location.hash = hash;
}

function shell() {
  const rail = NAV.map(
    ([k, label, ic], i) =>
      (i === 4 ? '<div class="nav-sep" role="presentation"></div>' : "") +
      `<a class="nav-a" href="#${k}" data-nav="${k}">${icon(ic)}<span>${label}</span></a>`
  ).join("");
  const tabs = TABS.map(([k, label]) => `<a href="#${k}" data-nav="${k}">${icon(k === "more" ? "more" : k)}<span>${label}</span></a>`).join("");
  document.getElementById("app").innerHTML = `
    <nav class="rail" aria-label="Main">
      <a class="brand" href="#today">${BRAND_SVG}<div><b>Matric Rewrite HQ</b><span>Maths · Physical Sciences</span></div></a>
      ${rail}
      <div class="rail-foot"><div id="rail-chip"></div><p data-sync>${syncLabel()}</p></div>
    </nav>
    <div class="main">
      <header class="topbar">
        <a class="brand" href="#today">${BRAND_SVG}<div><b>Matric Rewrite HQ</b></div></a>
        <div id="top-chip"></div>
      </header>
      <main id="view" class="page" tabindex="-1"></main>
    </div>
    <nav class="tabbar" aria-label="Main">${tabs}</nav>
    <div id="overlay-root"></div>
    <div id="toast-root" aria-live="polite"></div>`;
}

const VIEWS = {};
let lastRoute = "";
function render(keepScroll) {
  const r = parseHash();
  const view = VIEWS[r.name] ? r : { name: "today", arg: "" };
  const key = view.name + "." + view.arg;
  const same = key === lastRoute;
  const y = window.scrollY;
  const focusId = document.activeElement && document.activeElement.id;
  const el = document.getElementById("view");
  if (!same && view.name === "pp") enterPaperRow(view.arg);
  el.innerHTML = VIEWS[view.name](view.arg);
  el.classList.toggle("phys-page", view.name === "t" && TOPIC[view.arg] && TOPIC[view.arg].subj === "phys");
  const navKey = ROUTE_NAV[view.name] || view.name;
  const moreKeys = ["cards", "sheets", "strategy", "focus", "settings", "more"];
  $$("[data-nav]").forEach((a) => {
    const k = a.dataset.nav;
    const cur = k === navKey || (k === "more" && a.closest(".tabbar") && moreKeys.includes(navKey));
    if (cur) a.setAttribute("aria-current", "page");
    else a.removeAttribute("aria-current");
  });
  if (keepScroll || same) {
    window.scrollTo(0, y);
    if (focusId) {
      const f = document.getElementById(focusId);
      if (f) f.focus({ preventScroll: true });
    }
  } else {
    window.scrollTo(0, 0);
  }
  lastRoute = key;
  after(view, same);
  tick();
}
function rerender() {
  render(true);
}
function after(view, same) {
  $$(".mini").forEach(wireMini);
  if (view.name === "pp" && !same) {
    const row = document.getElementById("row-" + view.arg.replace(/\./g, "-"));
    if (row) {
      row.scrollIntoView({ block: "center" });
      row.classList.add("flash");
      setTimeout(() => row.classList.remove("flash"), 2200);
    }
  }
}
function toast(msg, ms = 4200) {
  const root = document.getElementById("toast-root");
  root.innerHTML = `<div class="toast" role="status">${msg}</div>`;
  clearTimeout(toast.t);
  toast.t = setTimeout(() => (root.innerHTML = ""), ms);
}

/* ───────────────────────── Today ───────────────────────── */
function branchSvg() {
  const W = 720,
    H = 150;
  const P = (t) => {
    // gentle rising curve: cubic Bézier from bottom-left to top-right
    const p0 = [18, 118],
      p1 = [220, 150],
      p2 = [470, 20],
      p3 = [704, 44];
    const u = 1 - t;
    return [
      u * u * u * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t * t * t * p3[0],
      u * u * u * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t * t * t * p3[1],
    ];
  };
  const today = todayIndex();
  let twigs = "",
    blooms = "";
  for (let n = 1; n <= PLAN_LEN; n++) {
    const t = 0.03 + ((n - 1) / (PLAN_LEN - 1)) * 0.94;
    const [x, y] = P(t);
    const side = n % 2 ? -1 : 1;
    const bx = x + side * 4;
    const by = y + side * 24;
    twigs += `<path class="twig" d="M${x.toFixed(1)} ${y.toFixed(1)} Q ${(x + side * 6).toFixed(1)} ${(y + side * 10).toFixed(1)} ${bx.toFixed(1)} ${by.toFixed(1)}"/>`;
    const pr = dayProgress(n);
    const st = pr.done === pr.total ? "done" : pr.done ? "part" : "none";
    const lab = `Day ${n}, ${fmtDate(dayDate(n))}: ${pr.done} of ${pr.total} tasks done${n === today ? " (today)" : ""}`;
    blooms += `<g class="bl ${st}${n === today ? " today" : ""}" role="link" tabindex="0" aria-label="${esc(lab)}" data-act="open-day" data-day="${n}"><title>${esc(lab)}</title><circle cx="${bx.toFixed(1)}" cy="${by.toFixed(1)}" r="18" fill="transparent"/>${n === today ? `<circle class="ring" cx="${bx.toFixed(1)}" cy="${by.toFixed(1)}" r="17"/>` : ""}${blossom(+bx.toFixed(1), +by.toFixed(1), 11, "")}</g>`;
  }
  return `<svg class="branch" viewBox="0 0 ${W} ${H + 10}" role="group" aria-label="Your 25 days as jacaranda blossoms">
    <path class="stem" d="M18 118 C 220 150, 470 20, 704 44"/>${twigs}${blooms}</svg>`;
}

function taskRow(n, i, t) {
  const id = taskId(n, i);
  const done = !!S.tasks[id];
  let go = "";
  let meta = `<span class="chip ${t.s}">${t.s === "maths" ? "Maths" : t.s === "phys" ? "Physical Sciences" : "Both"}</span>`;
  if (t.min) meta += `<span>${hm(t.min)}</span>`;
  if (t.topic) go = `<a class="btn quiet sm" href="#t.${t.topic}">Open topic</a>`;
  else if (t.deck) go = `<a class="btn quiet sm" href="#deck.${t.deck}">Open deck</a>`;
  else if (t.go) go = `<a class="btn quiet sm" href="#${t.go}">Open</a>`;
  let extra = "";
  if (t.paper) {
    const [sess, subj, p] = t.paper;
    const l = links(sess, subj, p);
    meta += `<span>${paperName(subj, p)} · ${l ? l.label : sess}</span>`;
    extra = `<div class="paper-links">${paperButtons(sess, subj, p)}${
      t.exam ? `<button class="btn sm" data-act="exam-start" data-key="${pKey(sess, subj, p)}">Start 3-hour timer</button>` : `<a class="btn quiet sm" href="#pp.${pKey(sess, subj, p)}">Log score</a>`
    }</div>`;
  }
  return `<li class="task${done ? " done" : ""}">
    <input type="checkbox" class="check" id="c-${id.replace(".", "-")}" data-act="task" data-id="${id}" data-day="${n}" ${done ? "checked" : ""} aria-label="Done: ${esc(t.t)}">
    <div class="t-body"><label class="t-text" for="c-${id.replace(".", "-")}">${esc(t.t)}</label><div class="t-meta">${meta}</div>${extra}</div>
    <div class="t-go">${go}</div>
  </li>`;
}

function meter(label, done, total, cls = "") {
  const w = total ? Math.round((done / total) * 100) : 0;
  return `<div class="meter ${cls}"><div class="m-top"><span>${label}</span><b class="num">${done} / ${total}</b></div>
    <div class="bar" role="progressbar" aria-valuemin="0" aria-valuemax="${total}" aria-valuenow="${done}" aria-label="${esc(label)}"><i style="width:${w}%"></i></div></div>`;
}

function scoreMini(subj, p) {
  const all = S.attempts.filter((a) => a.key.endsWith(`.${subj}.${p}`)).sort((a, b) => (a.date < b.date ? -1 : a.date > b.date ? 1 : a.id - b.id));
  const data = all.slice(-8);
  const colour = subj === "maths" ? "var(--jac)" : "var(--sci)";
  const name = paperName(subj, p);
  if (!data.length)
    return `<div class="mini"><h4>${name}</h4><div class="big muted">–</div><p class="small muted">No scores yet. Log one on the Past papers page.</p></div>`;
  const W = 200,
    H = 118,
    x0 = 30,
    x1 = 194,
    yTop = 16,
    yBot = 96;
  const yOf = (v) => yBot - (v / 100) * (yBot - yTop);
  const band = (x1 - x0) / Math.max(data.length, 4);
  const bw = Math.min(24, band * 0.62);
  let grid = "";
  [0, 50, 100].forEach((v) => {
    grid += `<line class="grid-l" x1="${x0}" x2="${x1}" y1="${yOf(v)}" y2="${yOf(v)}"/><text class="ax" x="${x0 - 6}" y="${yOf(v) + 3}" text-anchor="end">${v}%</text>`;
  });
  let cols = "";
  data.forEach((a, i) => {
    const v = pct(a.score, a.total || 150);
    const cx = x0 + band * i + band / 2;
    const x = cx - bw / 2;
    const y = yOf(Math.max(v, 1));
    const h = yBot - y;
    const r = Math.min(4, h, bw / 2);
    const path = `M${x} ${yBot} L${x} ${y + r} Q${x} ${y} ${x + r} ${y} L${x + bw - r} ${y} Q${x + bw} ${y} ${x + bw} ${y + r} L${x + bw} ${yBot} Z`;
    const sess = a.key.split(".")[0];
    const tipText = `${SESS[sess] ? SESS[sess].label : sess} · ${a.score}/${a.total || 150} (${v}%) · ${fmtDate(a.date, { day: "numeric", month: "short" })}`;
    cols += `<g class="col" tabindex="0" data-tip="${esc(tipText)}" data-x="${cx}" data-y="${y}"><rect class="hit" x="${cx - band / 2}" y="${yTop}" width="${band}" height="${yBot - yTop}"/><path class="m" d="${path}" fill="${colour}"/></g>`;
    if (i === data.length - 1) cols += `<text class="val" x="${cx}" y="${y - 5}" text-anchor="middle">${v}%</text>`;
  });
  const last = data[data.length - 1];
  const lastPct = pct(last.score, last.total || 150);
  const status = lastPct >= 40 ? '<span class="chip good">Above your 40% target</span>' : lastPct >= 30 ? '<span class="chip warn">Passing, aim for 40%</span>' : '<span class="chip bad">Below 30%, keep going</span>';
  return `<div class="mini"><h4>${name}</h4><div class="row between"><div class="big">${lastPct}%</div>${status}</div>
    <svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(name)} scores: ${data.map((a) => pct(a.score, a.total || 150) + "%").join(", ")}">
      ${grid}<line class="pass-l" x1="${x0}" x2="${x1}" y1="${yOf(30)}" y2="${yOf(30)}"/><text class="ax" x="${x1}" y="${yOf(30) - 4}" text-anchor="end">30% pass</text>${cols}
      <text class="ax" x="${x0}" y="${H - 6}">${plural(all.length, "attempt", "attempts")}</text>
    </svg></div>`;
}
function wireMini(box) {
  let tip = null;
  const show = (g) => {
    if (!tip) {
      tip = document.createElement("div");
      tip.className = "tip";
      box.appendChild(tip);
    }
    const svg = box.querySelector("svg");
    const vb = svg.viewBox.baseVal;
    const rect = svg.getBoundingClientRect();
    const bx = box.getBoundingClientRect();
    const sx = rect.width / vb.width;
    tip.textContent = g.dataset.tip;
    tip.style.left = rect.left - bx.left + Number(g.dataset.x) * sx + "px";
    tip.style.top = rect.top - bx.top + Number(g.dataset.y) * sx + "px";
  };
  const hide = () => {
    if (tip) tip.remove();
    tip = null;
  };
  $$(".col", box).forEach((g) => {
    g.addEventListener("pointerenter", () => show(g));
    g.addEventListener("pointerleave", hide);
    g.addEventListener("focus", () => show(g));
    g.addEventListener("blur", hide);
  });
}

VIEWS.today = () => {
  const n = todayIndex();
  const toExam = daysToExam();
  const planDay = Math.min(Math.max(n, 1), PLAN_LEN);
  const d = PLAN[planDay - 1];
  const pr = dayProgress(planDay);
  const greet = (() => {
    const h = new Date().getHours();
    const g = h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening";
    return S.name ? `${g}, ${esc(S.name)}` : g;
  })();

  let top;
  if (n < 1)
    top = `<div class="eyebrow">${greet} · ${fmtDate(todayYmd(), { weekday: "long", day: "numeric", month: "long" })}</div>
      <div class="day-of">${toExam} <small>days to go</small></div>
      <p class="lead">The plan officially starts on ${fmtDate(startDate(), { weekday: "long", day: "numeric", month: "long" })}. Starting early is only good: here is Day 1.</p>`;
  else if (n > PLAN_LEN)
    top = `<div class="eyebrow">${greet} · ${fmtDate(todayYmd(), { weekday: "long", day: "numeric", month: "long" })}</div>
      <div class="day-of">Exam time</div>
      <p class="lead">${toExam === 0 ? "Your first exam is today. Breathe, start with the question you know best, and write something for every question." : "The 25-day plan is finished. Keep sharp with one past paper a day until your last Maths or Physical Sciences paper."}</p>`;
  else
    top = `<div class="eyebrow">${greet} · ${fmtDate(todayYmd(), { weekday: "long", day: "numeric", month: "long" })} · ${plural(toExam, "day", "days")} to your first exam</div>
      <div class="day-of">Day ${n}<small>of ${PLAN_LEN}</small></div>
      <p class="lead">${esc(d.title)}</p>
      <p class="small muted">Phase ${phaseOf(n).n} of 4, ${esc(phaseOf(n).name.toLowerCase())}. ${esc(phaseOf(n).blurb)}</p>`;

  const confirm = !S.examConfirmed
    ? `<div class="callout"><b>Is your first exam on ${fmtDate(S.examDate, { weekday: "long", day: "numeric", month: "long" })}?</b>
        <p class="small">The plan counts 25 days back from your first exam. Set the real date from your timetable or admission letter so every day lines up.</p>
        <form class="row" data-form="exam-date"><label class="sr" for="first-exam">First exam date</label><input class="input" type="date" id="first-exam" value="${S.examDate}" required>
        <button class="btn sm" type="submit">Save date</button><button class="btn ghost sm" type="button" data-act="exam-ok">Yes, that's right</button></form></div>`
    : "";

  const paperCountdown = Object.entries(S.paperDates)
    .filter(([, v]) => isYmd(v) && daysBetween(todayYmd(), v) >= 0)
    .sort((a, b) => (a[1] < b[1] ? -1 : 1))
    .map(([k, v]) => {
      const [subj, p] = k.split(".");
      const dd = daysBetween(todayYmd(), v);
      return `<span class="chip ${subj}">${paperName(subj, +p)}: ${dd === 0 ? "today" : "in " + plural(dd, "day", "days")}</span>`;
    })
    .join("");

  let mission;
  if (n > PLAN_LEN) {
    const next = BONUS.find(([sess, subj, p]) => !attemptsFor(pKey(sess, subj, p)).length);
    mission = `<section class="card stack"><div class="sec-head"><h2>Today's mission</h2></div>
      ${next ? `<p>Write <b>${paperName(next[1], next[2])} ${esc(SESS[next[0]].label)}</b> under exam conditions, mark it with the memo and log your score.</p>
      <div class="paper-links">${paperButtons(...next)}<button class="btn sm" data-act="exam-start" data-key="${pKey(...next)}">Start 3-hour timer</button></div>` : "<p>You've written every bonus paper. Pick any year on the Past papers page.</p>"}
      <p class="small muted">Then 20 minutes of flashcards: <a href="#deck.phys-defs">Physics definitions</a> · <a href="#deck.maths-must">Maths must-knows</a>.</p></section>`;
  } else {
    mission = `<section class="card stack" aria-labelledby="mission-h">
      <div class="sec-head"><h2 id="mission-h">Today's mission${n < 1 ? " (Day 1)" : ""}</h2>
        <span class="small muted num">${pr.done} of ${pr.total} done${pr.left ? ` · about ${hm(pr.left)} left` : " · day complete"}</span></div>
      <ul class="tasks">${d.tasks.map((t, i) => taskRow(planDay, i, t)).join("")}</ul>
      <div class="row"><a class="btn ghost sm" href="#day.${planDay}">Open Day ${planDay}</a><button class="btn ghost sm" data-act="focus-quick">Start a 25-minute focus session</button></div>
    </section>`;
  }

  // Unfinished tasks from earlier days
  let behind = [];
  for (let k = 1; k < Math.min(n, PLAN_LEN + 1); k++) {
    const p = dayProgress(k);
    if (p.done < p.total) behind.push(k);
  }
  const catchUp = behind.length
    ? `<section class="callout warn"><b>${plural(behind.length, "earlier day has", "earlier days have")} unfinished tasks</b>
       <p class="small">Don't try to do everything twice. Do the <i>past paper</i> tasks first; they carry the most marks.</p>
       <div class="row">${behind.slice(-6).map((k) => `<a class="btn ghost sm" href="#day.${k}">Day ${k}</a>`).join("")}</div></section>`
    : "";

  const t = allTaskStats();
  const conf = (subj) => TOPICS.filter((x) => x.subj === subj && S.topics[x.id] === "confident").length;
  const nm = TOPICS.filter((x) => x.subj === "maths").length;
  const np = TOPICS.filter((x) => x.subj === "phys").length;
  const known = DECKS.reduce((m, dk) => m + dk.cards.filter((_, i) => (S.cards[dk.id] || {})[i] >= 2).length, 0);
  const cardsTotal = DECKS.reduce((m, dk) => m + dk.cards.length, 0);
  const mins = S.minutes[todayYmd()] || {};

  return `
  <header class="hero">${top}
    <div class="branch-wrap">${branchSvg()}</div>
    <div class="legend-row" aria-hidden="true"><span><i class="done"></i>Day done</span><span><i class="part"></i>Started</span><span><i class="none"></i>Not started</span><span>Day 1 on the left, Day 25 on the right. Tap a blossom to open that day</span></div>
    ${paperCountdown ? `<div class="row">${paperCountdown}</div>` : ""}
  </header>
  ${confirm}
  ${mission}
  ${catchUp}
  <section class="grid-2">
    <div class="card stack-lg"><div class="sec-head"><h2>Where you stand</h2><span class="small muted" data-sync>${syncLabel()}</span></div>
      ${meter("Plan tasks done", t.done, t.total, "good")}
      ${meter("Maths topics you feel confident in", conf("maths"), nm)}
      ${meter("Physical Sciences topics you feel confident in", conf("phys"), np, "phys")}
      ${meter("Flashcards you know", known, cardsTotal, "good")}
      <p class="small muted">Studied today: ${hm(mins.maths || 0)} Maths, ${hm(mins.phys || 0)} Physical Sciences (from the focus timer).</p>
    </div>
    <div class="card stack"><div class="sec-head"><h2>Past paper scores</h2><a class="small" href="#papers">Log a score</a></div>
      <div class="minis">${scoreMini("maths", 1)}${scoreMini("maths", 2)}${scoreMini("phys", 1)}${scoreMini("phys", 2)}</div>
      <p class="small muted">Red line = 30% pass mark. Your target is 40% per paper, so a bad question can't sink you.</p>
    </div>
  </section>
  <section class="quick" aria-label="Shortcuts">
    <a class="qlink" href="#focus">${icon("focus")}<b>Focus timer</b><span>25 minutes on, 5 off</span></a>
    <a class="qlink" href="#cards">${icon("cards")}<b>Drill</b><span>Definitions & must-knows</span></a>
    <a class="qlink" href="#sheets">${icon("sheets")}<b>Formula sheets</b><span>What the exam gives you</span></a>
    <a class="qlink" href="#strategy">${icon("strategy")}<b>Exam game plan</b><span>How you'll pass</span></a>
  </section>`;
};

/* ───────────────────────── Plan & Day ───────────────────────── */
VIEWS.plan = () => {
  const today = todayIndex();
  const phases = PHASES.map((ph) => {
    let tiles = "";
    for (let n = ph.days[0]; n <= ph.days[1]; n++) {
      const d = PLAN[n - 1];
      const p = dayProgress(n);
      const st = p.done === p.total ? "done" : n === today ? "today" : "";
      const chip = p.done === p.total ? '<span class="chip good">Done</span>' : n === today ? '<span class="chip maths">Today</span>' : n < today && p.done < p.total ? '<span class="chip warn">Unfinished</span>' : `<span class="small muted num">${p.done}/${p.total}</span>`;
      tiles += `<a class="dtile ${st}" href="#day.${n}"><div class="d-top"><span class="d-n">${n}</span><span class="d-date">${fmtDate(dayDate(n))}</span></div><div class="d-title">${esc(d.title)}</div><div>${chip}</div></a>`;
    }
    return `<section class="section"><div class="sec-head"><h2>Phase ${ph.n}: ${esc(ph.name)}</h2><span class="small muted">Days ${ph.days[0]}${ph.days[1] !== ph.days[0] ? "–" + ph.days[1] : ""}</span></div>
      <p class="muted">${esc(ph.blurb)}</p><div class="day-tiles">${tiles}</div></section>`;
  }).join("");
  const t = allTaskStats();
  return `<header class="stack"><h1>Your 25-day plan</h1>
    <p class="lead">Every day mixes Maths and Physical Sciences, about 3½ to 5 hours of work. Topics that give the most marks for the least effort come first; full timed papers come last. Day 25 is ${fmtDate(dayDate(25), { weekday: "long", day: "numeric", month: "long" })}, the day before your first exam.</p>
    ${meter("Tasks done", t.done, t.total, "good")}</header>${phases}
    <section class="callout"><b>If your Maths or Physical Sciences papers are after Day 25</b><p class="small">Keep going with one full past paper per day. The Today page will suggest the next unseen paper and set it up with the timer.</p></section>`;
};

VIEWS.day = (arg) => {
  const n = Math.min(Math.max(parseInt(arg, 10) || 1, 1), PLAN_LEN);
  const d = PLAN[n - 1];
  const p = dayProgress(n);
  const ph = phaseOf(n);
  return `<nav class="crumbs"><a href="#plan">25-day plan</a><span>›</span><span>Day ${n}</span></nav>
    <header class="stack"><div class="eyebrow">Phase ${ph.n} · ${esc(ph.name)} · ${fmtDate(dayDate(n), { weekday: "long", day: "numeric", month: "long" })}</div>
    <h1>Day ${n}: ${esc(d.title)}</h1>
    <p class="muted num">${p.done} of ${p.total} tasks done${p.left ? ` · about ${hm(p.left)} of work left` : ""}</p></header>
    <section class="card"><ul class="tasks">${d.tasks.map((t, i) => taskRow(n, i, t)).join("")}</ul></section>
    <nav class="row between">${n > 1 ? `<a class="btn ghost" href="#day.${n - 1}">← Day ${n - 1}</a>` : "<span></span>"}${n < PLAN_LEN ? `<a class="btn ghost" href="#day.${n + 1}">Day ${n + 1} →</a>` : ""}</nav>`;
};

/* ───────────────────────── Learn ───────────────────────── */
const STATUS = { none: "Not started", learning: "Learning", confident: "Confident" };
function practiceScore(t) {
  const marks = t.practice.map((_, i) => S.practice[`${t.id}.${i}`]);
  return { right: marks.filter((m) => m === "right").length, tried: marks.filter(Boolean).length, total: t.practice.length };
}
function topicCard(t) {
  const st = S.topics[t.id] || "none";
  const ps = practiceScore(t);
  const stChip = st === "confident" ? '<span class="chip good">Confident</span>' : st === "learning" ? `<span class="chip ${t.subj}">Learning</span>` : '<span class="chip plain">Not started</span>';
  return `<a class="tcard ${t.subj}" href="#t.${t.id}">
    <div class="row between"><span class="eyebrow">${t.subj === "maths" ? "Maths" : t.paper === 1 ? "Physics" : "Chemistry"} · P${t.paper}</span>${t.level === "gold" ? '<span class="chip gold">Start here</span>' : ""}</div>
    <h3>${esc(t.name)}</h3>
    <div class="tc-meta">${t.marks} marks · ${esc(t.where.replace(/^Paper \d · /, ""))}</div>
    <div class="tc-foot">${stChip}<span class="small muted">${plural(t.videos.length, "video", "videos")} · practice ${ps.right}/${ps.total}</span></div>
  </a>`;
}
VIEWS.learn = () => {
  const tab = L.learnTab === "phys" ? "phys" : "maths";
  const groups = [1, 2]
    .map((p) => {
      const list = TOPICS.filter((t) => t.subj === tab && t.paper === p);
      const title = tab === "maths" ? `Paper ${p}` : p === 1 ? "Paper 1 · Physics" : "Paper 2 · Chemistry";
      return `<section class="section"><div class="sec-head"><h2>${title}</h2><span class="small muted">${plural(list.length, "topic", "topics")}</span></div><div class="tcards">${list.map(topicCard).join("")}</div></section>`;
    })
    .join("");
  return `<header class="stack"><h1>Learn</h1>
    <p class="lead">Every exam topic in one place: 2–4 short videos that get to the point, the method in plain words, worked examples marked like a memo, and practice with answers. Topics marked <b>Start here</b> give the most marks for the least effort.</p>
    <div class="seg" role="group" aria-label="Subject"><button data-act="ltab" data-v="maths" aria-pressed="${tab === "maths"}">Mathematics</button><button data-act="ltab" data-v="phys" aria-pressed="${tab === "phys"}">Physical Sciences</button></div></header>${groups}`;
};

function proofFig(kind) {
  const C = '<circle class="c" cx="100" cy="100" r="70"/>';
  const pt = (x, y) => `<circle class="pt" cx="${x}" cy="${y}" r="2.6"/>`;
  if (kind === "chord")
    return `<svg viewBox="0 0 200 200" role="img" aria-label="Circle with centre O, chord AB and OM perpendicular to AB">${C}
      <line class="l" x1="42.6" y1="140" x2="157.4" y2="140"/><line class="l" x1="100" y1="100" x2="100" y2="140"/>
      <line class="k" x1="100" y1="100" x2="42.6" y2="140"/><line class="k" x1="100" y1="100" x2="157.4" y2="140"/>
      <path class="l" d="M100 132 H108 V140" style="stroke-width:1.2"/>${pt(100, 100)}
      <text x="106" y="96">O</text><text x="28" y="152">A</text><text x="161" y="152">B</text><text x="95" y="157">M</text></svg>`;
  if (kind === "centre")
    return `<svg viewBox="0 0 200 200" role="img" aria-label="Circle with centre O; A, B and C on the circle; CO extended to D">${C}
      <line class="l" x1="100" y1="30" x2="39.4" y2="135"/><line class="l" x1="100" y1="30" x2="160.6" y2="135"/>
      <line class="l" x1="100" y1="100" x2="39.4" y2="135"/><line class="l" x1="100" y1="100" x2="160.6" y2="135"/>
      <line class="k" x1="100" y1="30" x2="100" y2="170"/>${pt(100, 100)}
      <text x="95" y="22">C</text><text x="24" y="143">A</text><text x="165" y="143">B</text><text x="80" y="100">O</text><text x="95" y="186">D</text>
      <text class="n" x="90" y="54">1</text><text class="n" x="104" y="54">2</text><text class="n" x="89" y="125">1</text><text class="n" x="105" y="125">2</text></svg>`;
  return `<svg viewBox="0 0 200 200" role="img" aria-label="Cyclic quadrilateral ABCD in a circle with centre O">${C}
    <path class="l" d="M39.4 65 L123.9 34.2 L160.6 135 L65 160.6 Z"/>
    <line class="k" x1="100" y1="100" x2="123.9" y2="34.2"/><line class="k" x1="100" y1="100" x2="65" y2="160.6"/>${pt(100, 100)}
    <text x="24" y="64">A</text><text x="124" y="26">B</text><text x="166" y="146">C</text><text x="52" y="178">D</text><text x="83" y="100">O</text>
    <text class="n" x="109" y="113">1</text><text class="n" x="89" y="89">2</text></svg>`;
}

VIEWS.t = (id) => {
  const t = TOPIC[id];
  if (!t) return VIEWS.learn();
  const st = S.topics[t.id] || "none";
  const subjName = t.subj === "maths" ? "Mathematics" : "Physical Sciences";
  const vids = t.videos
    .map(
      (v, i) => `<a class="video${S.videos[v.id] ? " seen" : ""}" href="${ytWatch(v.id)}" target="_blank" rel="noopener" data-act="video" data-vid="${v.id}">
      <span class="play">${PLAY}</span>
      <span class="stack" style="gap:2px"><span class="v-title">${i + 1}. ${esc(v.title)}</span><span class="v-note">${v.note}${v.kind === "exam" ? " · Past-paper walkthrough" : v.kind === "calc" ? " · Calculator skills" : ""}${S.videos[v.id] ? " · Watched" : ""}</span></span>
      <span class="v-cta">Watch on YouTube ↗</span></a>`
    )
    .join("");
  const defs = t.defs
    ? `<section class="section"><h2>Definitions to learn word for word <span class="count">${t.defs.length}</span></h2>
       <div class="defs">${t.defs.map(([k, v]) => `<div class="def"><b>${k}</b>${v}</div>`).join("")}</div>
       <a class="btn ghost sm" href="#deck.${t.paper === 1 ? "phys-defs" : "chem-defs"}" style="justify-self:start">Drill these as flashcards</a></section>`
    : "";
  const formulas = `<section class="section"><h2>Formulas</h2><div class="formulas">${t.formulas
    .map((f) => `<div class="frow"><div class="f-label">${f.label}</div><div class="f-math">${f.f}</div><div>${f.sheet ? '<span class="chip good">On the sheet</span>' : '<span class="chip warn">Memorise</span>'}</div></div>`)
    .join("")}</div></section>`;
  const calc = t.calc ? `<section class="section"><h2>Calculator steps</h2><div class="calc">${t.calc.map((c) => `<p>${c}</p>`).join("")}</div></section>` : "";
  const examples = `<section class="section"><h2>Worked examples, marked like a memo</h2>
    <p class="memo-note">Each <span class="tk">✓</span> is one mark, the way the memo gives them. Notice how many marks come from just writing the formula and substituting.</p>
    ${t.examples.map((e, i) => `<div class="memo"><span class="q-no">${i + 1}</span><div class="q">${e.q}</div><div class="lines">${e.lines.map((l) => `<div>${l}</div>`).join("")}</div></div>`).join("")}</section>`;
  const proofs = t.proofs
    ? `<section class="section"><h2>Theorem proofs you can be asked to write <span class="count">3 of 6</span></h2>
      <p class="muted">These three are shown here. The other three (tan-chord, proportionality, similarity) are in the videos above and the DBE Mind the Gap guide linked below.</p>
      ${t.proofs.map((p) => `<div class="card proof">${proofFig(p.fig)}<div class="stack"><h3>${esc(p.name)}</h3>
        <p class="small"><b>Given:</b> ${p.given}<br><b>Required to prove:</b> ${p.rtp}<br><b>Construction:</b> ${p.construction}</p>
        <table class="sr-table"><tbody>${p.steps.map(([a, b]) => `<tr><td>${a}</td><td>${b ? "(" + b + ")" : ""}</td></tr>`).join("")}</tbody></table></div></div>`).join("")}</section>`
    : "";
  const practice = `<section class="section"><div class="sec-head"><h2>Practice</h2><span class="small muted num">${practiceScore(t).right} of ${t.practice.length} right</span></div>
    <p class="muted small">Try each one on paper first. Then show the answer and be honest with yourself.</p>
    ${t.practice
      .map((q, i) => {
        const m = S.practice[`${t.id}.${i}`];
        return `<div class="pq ${m || ""}"><div class="pq-q">${i + 1}. ${q.q}</div>
        <div class="pq-a" id="ans-${t.id}-${i}" ${m ? "" : "hidden"}>${q.a}</div>
        <div class="row">${m ? "" : `<button class="btn ghost sm" data-act="reveal" data-target="ans-${t.id}-${i}">Show answer</button>`}
          <button class="btn ${m === "right" ? "" : "ghost"} sm" data-act="pq" data-k="${t.id}.${i}" data-v="right" aria-pressed="${m === "right"}">I got it</button>
          <button class="btn ${m === "wrong" ? "danger" : "ghost"} sm" data-act="pq" data-k="${t.id}.${i}" data-v="wrong" aria-pressed="${m === "wrong"}">I got it wrong</button></div></div>`;
      })
      .join("")}</section>`;
  const drillSessions = ["2023-nov", "2022-nov", "2021-nov", "2024-jun", "2023-jun"];
  const pastPapers = `<section class="section"><h2>Find it in past papers</h2>
    <p class="muted">${esc(t.where)}. Open a paper, find the ${esc(t.name.toLowerCase())} question, answer it, then mark it with the memo. (Save November 2025 and 2024 for your full practice papers on Days 18–24.)</p>
    <div class="stack">${drillSessions
      .map((k) => `<div class="prow ${t.subj}"><div class="p-name"><i></i>${paperName(t.subj, t.paper)}</div><div class="small muted">${esc(SESS[k].label)}</div><div class="p-actions">${paperButtons(k, t.subj, t.paper)}</div></div>`)
      .join("")}</div></section>`;
  const guide = t.guide ? `<p><a class="ext" href="${esc(t.guide.url)}" target="_blank" rel="noopener">${esc(t.guide.label)}</a></p>` : "";
  const siblings = TOPICS.filter((x) => x.subj === t.subj);
  const idx = siblings.indexOf(t);
  const prev = siblings[idx - 1],
    next = siblings[idx + 1];
  return `<nav class="crumbs"><a href="#learn" data-act="ltab-go" data-v="${t.subj}">Learn</a><span>›</span><span>${subjName}</span><span>›</span><span>Paper ${t.paper}</span></nav>
  <header class="topic-head">
    <h1>${esc(t.name)}</h1>
    <div class="meta"><span class="chip ${t.subj}">${t.marks} marks</span><span class="small muted">${esc(t.where)}</span>${t.level === "gold" ? '<span class="chip gold">Start here</span>' : ""}</div>
    <p class="lead">${t.hook}</p>
    <div class="seg status" role="group" aria-label="How well do you know this topic?">${Object.entries(STATUS)
      .map(([k, v]) => `<button data-act="status" data-id="${t.id}" data-v="${k}" aria-pressed="${st === k}">${v}</button>`)
      .join("")}</div>
  </header>
  <section class="section"><h2>Watch <span class="count">${t.videos.length} short videos</span></h2>
    <p class="muted small">Watch the first one now. Pause and copy the examples; don't just watch. Videos open on YouTube.</p>
    <div class="videos">${vids}</div>
    <a class="small ext" href="${ytSearch(t.yt)}" target="_blank" rel="noopener">A video isn't loading? Search YouTube for more on this topic</a></section>
  <section class="section"><h2>The idea in plain words</h2><ul class="ideas">${t.ideas.map((x) => `<li>${x}</li>`).join("")}</ul></section>
  ${defs}${formulas}${calc}
  <section class="section"><h2>How to answer the exam question</h2><ol class="steps">${t.method.map((x) => `<li><span>${x}</span></li>`).join("")}</ol></section>
  ${examples}${proofs}
  <section class="section"><h2>Mistakes that cost marks</h2><ul class="mistakes">${t.mistakes.map((x) => `<li><span>${x}</span></li>`).join("")}</ul></section>
  ${practice}${pastPapers}${guide}
  <nav class="row between">${prev ? `<a class="btn ghost" href="#t.${prev.id}">← ${esc(prev.name)}</a>` : "<span></span>"}${next ? `<a class="btn ghost" href="#t.${next.id}">${esc(next.name)} →</a>` : ""}</nav>`;
};

/* ───────────────────────── Papers ───────────────────────── */
function paperRow(s, subj, p) {
  const key = pKey(s.key, subj, p);
  const at = attemptsFor(key);
  const best = at.length ? Math.max(...at.map((a) => a.score)) : null;
  const status = best === null ? '<span class="small muted">Not written yet</span>' : `<span class="chip ${pct(best) >= 30 ? "good" : "bad"}">Best ${best}/150 · ${pct(best)}%</span>`;
  const open = L.logOpen === key;
  const form = open
    ? `<form class="logform" data-form="log" data-key="${key}">
      <label class="lbl">Your mark out of 150<input class="input n3" type="number" inputmode="numeric" min="0" max="150" step="1" id="score-${key.replace(/\./g, "-")}" required></label>
      <label class="lbl">Date written<input class="input" type="date" id="date-${key.replace(/\./g, "-")}" value="${todayYmd()}" max="${todayYmd()}" required></label>
      <div class="row" style="align-self:end"><button class="btn sm" type="submit">Save score</button><button class="btn ghost sm" type="button" data-act="log-close">Cancel</button></div></form>`
    : "";
  return `<div class="prow ${subj}" id="row-${key.replace(/\./g, "-")}">
    <div class="p-name"><i></i>${paperName(subj, p)}</div>
    <div>${status}</div>
    <div class="p-actions">${paperButtons(s.key, subj, p)}<button class="btn ghost sm" data-act="exam-start" data-key="${key}">Timed attempt</button><button class="btn quiet sm" data-act="log-open" data-key="${key}">Log score</button></div>
    ${form}</div>`;
}
VIEWS.papers = () => {
  const subjF = L.pSubj,
    sessF = L.pSess;
  const list = PAPERS.filter((s) => sessF === "all" || s.session === sessF);
  const subjects = subjF === "all" ? ["maths", "phys"] : [subjF];
  const blocks = list
    .map((s) => {
      const rows = [];
      subjects.forEach((subj) => [1, 2].forEach((p) => rows.push(paperRow(s, subj, p))));
      const note =
        s.key === "2017-nov"
          ? '<p class="small muted">Only the Physics P1 link could be confirmed for November 2017. The other papers and memos are on the official DBE page for that year.</p>'
          : s.key === "2026-jun"
          ? '<p class="small muted">For May/June 2026 Physical Sciences, open the papers from the official DBE page.</p>'
          : "";
      return `<section class="session"><div class="session-head"><h2>${esc(s.label)}</h2><a class="small ext" href="${esc(s.page)}" target="_blank" rel="noopener">Official DBE page</a></div>${note}${rows.join("")}</section>`;
    })
    .join("");
  const f = (k, v, label) => `<button data-act="pf" data-k="${k}" data-v="${v}" aria-pressed="${L[k] === v}">${label}</button>`;
  const rowsAll = [...S.attempts].sort((a, b) => (a.date < b.date ? 1 : a.date > b.date ? -1 : b.id - a.id));
  const table = rowsAll.length
    ? `<div class="table-wrap"><table class="data"><thead><tr><th>Date</th><th>Paper</th><th>Session</th><th>Score</th><th>%</th><th></th></tr></thead><tbody>${rowsAll
        .map((a) => {
          const [sess, subj, p] = a.key.split(".");
          return `<tr><td>${fmtDate(a.date, { day: "numeric", month: "short" })}</td><td>${paperName(subj, +p)}</td><td>${esc(SESS[sess] ? SESS[sess].label : sess)}</td><td>${a.score}/${a.total || 150}</td><td>${pct(a.score, a.total || 150)}%</td>
          <td><button class="btn quiet sm" data-act="del-attempt" data-id="${a.id}">${L.confirmDel === a.id ? "Tap again to delete" : "Delete"}</button></td></tr>`;
        })
        .join("")}</tbody></table></div>`
    : '<p class="muted">Nothing logged yet. After you mark a paper with its memo, press <b>Log score</b> on that paper.</p>';
  return `<header class="stack"><h1>Past papers</h1>
    <p class="lead">Every November paper from 2017 to 2025, plus the May/June rewrite papers, each with its memo. The links open the official PDFs from the Department of Basic Education. Question papers are in English; memos are bilingual (English and Afrikaans).</p></header>
    <section class="callout"><b>How to mark yourself</b><p class="small">Mark strictly: give yourself a mark only where the memo shows a ✓. If an earlier answer was wrong but you used it correctly later, the memo usually still gives the later marks (CA, consistent accuracy). Write down every question where you lost marks and redo it two days later.</p></section>
    <div class="filters" role="group" aria-label="Filter papers">
      <div class="seg" role="group" aria-label="Subject">${f("pSubj", "all", "Both subjects")}${f("pSubj", "maths", "Maths")}${f("pSubj", "phys", "Physical Sciences")}</div>
      <div class="seg" role="group" aria-label="Session">${f("pSess", "all", "All sessions")}${f("pSess", "nov", "November")}${f("pSess", "jun", "May/June")}${f("pSess", "mar", "Feb/March")}</div>
    </div>
    ${blocks}
    <section class="section"><h2>Your scores</h2>${table}</section>
    <p class="small muted">Paper links come from the DBE's own listings (index updated ${esc(PAPERS_SOURCE.slice(0, 10))}). If a link ever stops working, the “Official DBE page” link on that session always lists the papers.</p>`;
};
VIEWS.pp = () => VIEWS.papers();
// Runs once when a "#pp.<session>.<subject>.<paper>" link is opened: make sure
// the row is visible under the current filters and open its score form.
function enterPaperRow(arg) {
  const [sess, subj] = arg.split(".");
  if (!SESS[sess]) return;
  if (L.pSess !== "all" && L.pSess !== SESS[sess].session) L.pSess = "all";
  if (L.pSubj !== "all" && L.pSubj !== subj) L.pSubj = "all";
  L.logOpen = arg;
  saveLocal();
}

/* ───────────────────────── Drill (flashcards) ───────────────────────── */
let CS = null; // current card session
function deckKnown(dk) {
  const b = S.cards[dk.id] || {};
  return dk.cards.filter((_, i) => b[i] >= 2).length;
}
VIEWS.cards = () => {
  const card = (dk) => `<a class="tcard ${dk.subj}" href="#deck.${dk.id}"><div class="row between"><span class="eyebrow">${dk.subj === "maths" ? "Maths" : "Physical Sciences"}</span><span class="small muted num">${dk.cards.length} cards</span></div>
    <h3>${esc(dk.name)}</h3><p class="small muted">${esc(dk.blurb)}</p>${meter("Known", deckKnown(dk), dk.cards.length, dk.subj === "phys" ? "phys" : "")}</a>`;
  return `<header class="stack"><h1>Drill</h1><p class="lead">Definitions and must-know facts are free marks: no calculation, just recall. Ten minutes a day is enough if you do it every day.</p></header>
    <div class="tcards">${DECKS.map(card).join("")}</div>
    <p class="small muted">How it works: say the answer out loud, flip the card, then be honest. Cards you get wrong come back first next time.</p>`;
};
function startDeck(id) {
  const dk = DECK[id];
  const b = S.cards[id] || {};
  const order = dk.cards.map((_, i) => i).sort((a, c) => (b[a] || 0) - (b[c] || 0) || Math.random() - 0.5);
  CS = { id, order, pos: 0, flipped: false, got: 0, again: 0 };
}
VIEWS.deck = (id) => {
  const dk = DECK[id];
  if (!dk) return VIEWS.cards();
  if (!CS || CS.id !== id) startDeck(id);
  const b = S.cards[id] || {};
  const head = `<nav class="crumbs"><a href="#cards">Drill</a><span>›</span><span>${esc(dk.name)}</span></nav>
    <header class="stack"><h1>${esc(dk.name)}</h1>${meter("Known", deckKnown(dk), dk.cards.length, dk.subj === "phys" ? "phys" : "good")}</header>`;
  if (CS.pos >= CS.order.length) {
    return `${head}<section class="card stack-lg" style="text-align:center;justify-items:center"><h2>Round done</h2>
      <p class="lead">${CS.got} got it · ${CS.again} to practise again</p>
      <div class="row"><button class="btn" data-act="deck-again">Go again</button><a class="btn ghost" href="#cards">All decks</a></div></section>`;
  }
  const i = CS.order[CS.pos];
  const c = dk.cards[i];
  const box = b[i] || 0;
  const topic = c.topic ? TOPIC[c.topic] : null;
  return `${head}
  <p class="small muted num">Card ${CS.pos + 1} of ${CS.order.length}</p>
  <div class="flash" data-act="flip" role="button" tabindex="0" aria-label="Flip card" id="flashcard">
    ${CS.flipped ? `<span class="side">Answer</span><div class="front" style="font-size:1.05rem">${c.f}</div><div class="back">${c.b}</div>` : `<span class="side">${dk.id.endsWith("defs") ? "Define" : "Question"}</span><div class="front">${c.f}</div><span class="small muted">Tap or press space to flip</span>`}
    <div class="boxes" aria-label="Known level ${box} of 3"><i class="${box >= 1 ? "on" : ""}"></i><i class="${box >= 2 ? "on" : ""}"></i><i class="${box >= 3 ? "on" : ""}"></i></div>
  </div>
  <div class="row" style="justify-content:center">${
    CS.flipped
      ? `<button class="btn danger" data-act="card" data-v="again">Again (1)</button><button class="btn" data-act="card" data-v="got" style="background:var(--tick)">Got it (2)</button>`
      : `<button class="btn" data-act="flip">Show answer</button>`
  }</div>
  ${topic ? `<p class="small muted" style="text-align:center">From <a href="#t.${topic.id}">${esc(topic.name)}</a></p>` : ""}
  <details><summary class="small">See the whole deck as a list</summary><div class="defs" style="margin-top:12px">${dk.cards.map((x) => `<div class="def"><b>${x.f}</b>${x.b}</div>`).join("")}</div></details>`;
};

/* ───────────────────────── Formula sheets ───────────────────────── */
VIEWS.sheets = (arg) => {
  const id = SHEETS.find((s) => s.id === arg) ? arg : L.sheet;
  const sh = SHEETS.find((s) => s.id === id) || SHEETS[0];
  const tabs = SHEETS.map((s) => `<button data-act="sheet" data-v="${s.id}" aria-pressed="${s.id === sh.id}">${s.id === "maths" ? "Maths" : s.id === "p1" ? "Physics P1" : "Chemistry P2"}</button>`).join("");
  const consts = sh.constants
    ? `<section class="section"><h2>Constants</h2><div class="table-wrap"><table class="sheet-tbl"><thead><tr><th>Name</th><th>Symbol</th><th>Value</th></tr></thead><tbody>${sh.constants
        .map(([a, b, c]) => `<tr><td class="lab">${a}</td><td class="fm">${b}</td><td class="num">${c}</td></tr>`)
        .join("")}</tbody></table></div></section>`
    : "";
  const groups = sh.groups
    .map((g) => `<section class="section"><h2>${g.name}</h2><div class="table-wrap"><table class="sheet-tbl"><tbody>${g.rows.map(([a, b]) => `<tr><td class="lab">${a}</td><td class="fm">${b}</td></tr>`).join("")}</tbody></table></div></section>`)
    .join("");
  return `<header class="stack"><h1>Formula sheets</h1><p class="lead">What the exam gives you, and what it doesn't. Knowing exactly what's on the sheet means you only memorise the rest.</p>
    <div class="seg" role="group" aria-label="Sheet">${tabs}</div></header>
    <section class="callout"><b>${esc(sh.name)}</b><p class="small">${esc(sh.note)}</p></section>
    ${consts}${groups}
    <section class="callout warn"><b>Not on the sheet: memorise these</b><ul class="small">${sh.memorise.map((m) => `<li>${m}</li>`).join("")}</ul></section>`;
};

/* ───────────────────────── Exam game plan ───────────────────────── */
VIEWS.strategy = () => {
  const tgt = (key, title) => {
    const rows = TARGETS[key];
    const sumT = rows.reduce((m, r) => m + r[1], 0);
    const sumA = rows.reduce((m, r) => m + r[2], 0);
    return `<div class="stack"><h3>${title}</h3><div class="table-wrap"><table class="data"><thead><tr><th>Where the marks are</th><th>About</th><th>Your target</th></tr></thead><tbody>${rows
      .map((r) => `<tr><td>${r[3] ? `<a href="#t.${r[3]}">${esc(r[0])}</a>` : esc(r[0])}</td><td>${r[1]}</td><td><b>${r[2]}</b></td></tr>`)
      .join("")}<tr><td><b>Total</b></td><td>≈ ${sumT}</td><td><b>${sumA} / 150 = ${pct(sumA)}%</b></td></tr></tbody></table></div></div>`;
  };
  return `<header class="stack"><h1>Exam game plan</h1>
    <p class="lead">You don't need to know everything. You need to collect enough marks, on purpose. This page is how.</p></header>
    <section class="section"><h2>What passing takes</h2>
      <p style="max-width:70ch">The pass mark is 30% for each subject. Both papers together are out of 300, so you need about <b>90 marks across both papers</b>. Aim for <b>60 out of 150 (40%) on each paper</b>; that gives you room for a bad question or a hard paper. Last time you had 15% in Maths and 26% in Physical Sciences. Physical Sciences needs about 20 more marks per paper. Maths needs about 40 more per paper, and the targets below show exactly where they come from.</p></section>
    <section class="section"><h2>Where your marks will come from</h2>
      <p class="muted">These are targets, not the whole paper. Notice you're not trying to get full marks anywhere. You're taking the first, easier parts of every question.</p>
      <div class="grid-2">${tgt("maths-1", "Maths Paper 1")}${tgt("maths-2", "Maths Paper 2")}${tgt("phys-1", "Physics Paper 1")}${tgt("phys-2", "Chemistry Paper 2")}</div></section>
    <section class="section"><h2>In the exam room</h2><ol class="steps">
      <li><span><b>Read the whole paper first (10 minutes).</b> Put a star next to every question you know how to start.</span></li>
      <li><span><b>Do your starred questions first.</b> You may answer in any order. Number every answer exactly as in the paper, and start each main question on a new page.</span></li>
      <li><span><b>Budget 1,2 minutes per mark</b> (180 minutes ÷ 150 marks). A 6-mark question gets about 7 minutes. Stuck longer than that? Leave space, move on, come back.</span></li>
      <li><span><b>Never leave a blank.</b> Write the formula and substitute what you know. The formula and the substitution each earn a mark, even if the final answer is wrong.</span></li>
      <li><span><b>Use consistent accuracy (CA).</b> If you got 2.1 wrong but use your answer correctly in 2.2, you still get the 2.2 marks. So always carry on.</span></li>
      <li><span><b>Physical Sciences calculations:</b> formula ✓ → substitution ✓ → answer with unit ✓ (and a direction for vectors like velocity, force and momentum).</span></li>
      <li><span><b>Definitions:</b> write them word for word. Paraphrasing loses marks.</span></li>
      <li><span><b>Multiple choice:</b> never leave one blank. Cross out the options you know are wrong, then choose.</span></li>
      <li><span><b>Last 15 minutes:</b> check that the calculator was in DEG mode, that answers have units, and that every question has at least something written.</span></li>
    </ol></section>
    <section class="section"><h2>Your calculator</h2><div class="calc">
      <p>Use an approved, non-programmable scientific calculator, such as the Casio fx-82ZA PLUS or fx-991ZA PLUS. Use the same one every day from now so the buttons are automatic.</p>
      <p><b>Degrees mode:</b> SHIFT → MODE (SETUP) → Deg. A small “D” shows at the top of the screen. Check it before every paper.</p>
      <p><b>Statistics:</b> learn the STAT steps in <a href="#t.m-stats">Statistics</a>. It's the easiest 14+ marks on Maths Paper 2.</p>
      <p><b>Checking roots:</b> the fx-991ZA PLUS can solve quadratics (EQN mode). Use it to check, but always show the formula working: an answer with no working can get 0.</p></div></section>
    <section class="section"><h2>The day before and the day of</h2><div class="grid-2">
      <div class="card stack"><h3>The night before</h3><ul class="small"><li>Light review only: flashcards and the formula sheet</li><li>Pack your bag (list on the right)</li><li>No new topics after supper</li><li>Sleep at least 8 hours. Tired brains lose marks on easy questions</li></ul></div>
      <div class="card stack"><h3>In your bag</h3><ul class="small"><li>ID document and exam admission letter</li><li>At least two black or blue pens, a pencil, an eraser, a ruler</li><li>Calculator (check the battery or solar panel)</li><li>Compass and protractor for Maths Paper 2</li><li>Water and a watch. Phones are not allowed in the exam room</li><li>Arrive at least 30 minutes early</li></ul></div></div>
      <section class="callout"><b>If you panic in the exam</b><p class="small">Put your pen down. Breathe in for 4 seconds, hold for 4, breathe out for 4. Do it three times. Then find the easiest question you can see and write the first line. Marks come one line at a time.</p></section></section>
    <section class="section"><h2>Free official help</h2><div class="stack">${RESOURCES.map((r) => `<div><a class="ext" href="${esc(r.url)}" target="_blank" rel="noopener">${esc(r.label)}</a><p class="small muted">${esc(r.note)}</p></div>`).join("")}</div></section>`;
};

/* ───────────────────────── Focus timer ───────────────────────── */
function focusRemaining() {
  const f = L.focus;
  if (!f) return null;
  return f.running ? f.endsAt - Date.now() : f.remaining;
}
VIEWS.focus = () => {
  const f = L.focus;
  const len = L.focusLen === 50 ? 50 : 25;
  const subj = f ? f.subj : L.focusSubj;
  const phase = f ? f.phase : "focus";
  const total = f ? f.total : len * 60000;
  const rem = f ? focusRemaining() : total;
  const circ = 2 * Math.PI * 88;
  const off = circ * (1 - Math.max(0, rem) / total);
  const mins = S.minutes[todayYmd()] || {};
  let week = 0;
  for (let k = 0; k < 7; k++) {
    const m = S.minutes[addDays(todayYmd(), -k)] || {};
    week += (m.maths || 0) + (m.phys || 0);
  }
  const subjBtn = (v, label) => `<button data-act="focus-subj" data-v="${v}" aria-pressed="${subj === v}" ${f ? "disabled" : ""}>${label}</button>`;
  const lenBtn = (v, label) => `<button data-act="focus-len" data-v="${v}" aria-pressed="${len === v}" ${f ? "disabled" : ""}>${label}</button>`;
  return `<header class="stack"><h1>Focus timer</h1><p class="lead">Work for a fixed time with your phone face down, then take a real break. The minutes count towards your daily total.</p></header>
    <section class="card stack-lg" style="justify-items:center">
      <div class="row" style="justify-content:center"><div class="seg" role="group" aria-label="Subject">${subjBtn("maths", "Maths")}${subjBtn("phys", "Physical Sciences")}</div>
      <div class="seg" role="group" aria-label="Length">${lenBtn(25, "25 + 5 min")}${lenBtn(50, "50 + 10 min")}</div></div>
      <div class="ring-wrap ${subj === "phys" ? "phys" : ""} ${phase === "break" ? "brk" : ""}">
        <svg viewBox="0 0 200 200" aria-hidden="true"><circle class="ring-track" cx="100" cy="100" r="88"/><circle class="ring-fill" cx="100" cy="100" r="88" transform="rotate(-90 100 100)" stroke-dasharray="${circ.toFixed(1)}" stroke-dashoffset="${off.toFixed(1)}" data-ring="${circ.toFixed(1)}" data-total="${total}"/></svg>
        <div class="clock" data-clock="focus" role="timer" aria-live="off">${clockText(rem)}</div>
      </div>
      <p class="muted">${phase === "break" ? "Break. Stand up, drink water, look out of a window." : f ? `Focusing on ${subj === "maths" ? "Maths" : "Physical Sciences"}` : "Ready when you are"}</p>
      <div class="row" style="justify-content:center">${
        !f
          ? `<button class="btn" data-act="focus-start">Start focus</button>`
          : `${f.running ? `<button class="btn" data-act="focus-pause">Pause</button>` : `<button class="btn" data-act="focus-resume">Resume</button>`}<button class="btn ghost" data-act="focus-stop">${phase === "break" ? "Skip break" : "Stop"}</button>`
      }</div>
    </section>
    <section class="grid-2"><div class="card stack"><h2>Today</h2><p class="num">${hm(mins.maths || 0)} Maths · ${hm(mins.phys || 0)} Physical Sciences</p></div>
    <div class="card stack"><h2>Last 7 days</h2><p class="num">${hm(week)} of focused study</p></div></section>
    <p class="small muted">A full focus block is logged when it finishes. A chime plays at the end (turn your volume up).</p>`;
};
function chime() {
  try {
    const Ctx = window.AudioContext || window.webkitAudioContext;
    const ctx = chime.ctx || (chime.ctx = new Ctx());
    [660, 880, 990].forEach((f, i) => {
      const o = ctx.createOscillator();
      const g = ctx.createGain();
      o.frequency.value = f;
      o.type = "sine";
      g.gain.setValueAtTime(0.0001, ctx.currentTime + i * 0.22);
      g.gain.exponentialRampToValueAtTime(0.25, ctx.currentTime + i * 0.22 + 0.02);
      g.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + i * 0.22 + 0.6);
      o.connect(g).connect(ctx.destination);
      o.start(ctx.currentTime + i * 0.22);
      o.stop(ctx.currentTime + i * 0.22 + 0.65);
    });
  } catch {
    /* sound is optional */
  }
}
function focusFinishPhase() {
  const f = L.focus;
  if (!f) return;
  if (f.phase === "focus") {
    const d = todayYmd();
    const m = S.minutes[d] || (S.minutes[d] = {});
    m[f.subj] = (m[f.subj] || 0) + f.len;
    commit();
    const brk = f.len === 50 ? 10 : 5;
    L.focus = { subj: f.subj, len: f.len, phase: "break", total: brk * 60000, endsAt: Date.now() + brk * 60000, running: true };
    toast(`Nice. ${f.len} minutes of ${f.subj === "maths" ? "Maths" : "Physical Sciences"} logged. Take a ${brk}-minute break.`);
  } else {
    L.focus = null;
    toast("Break's over. Start the next focus block when you're ready.");
  }
  saveLocal();
  chime();
  if (parseHash().name === "focus") rerender();
}

/* ───────────────────────── Exam attempt overlay ───────────────────────── */
const EXAM_MS = 3 * 3600 * 1000;
function examElapsed() {
  const e = L.exam;
  if (!e) return 0;
  return (e.pausedAt || Date.now()) - e.startedAt - (e.pausedMs || 0);
}
function openExam() {
  const e = L.exam;
  if (!e) return;
  const [sess, subj, p] = e.key.split(".");
  const rem = EXAM_MS - examElapsed();
  document.getElementById("overlay-root").innerHTML = `<div class="overlay" role="dialog" aria-modal="true" aria-labelledby="exam-h">
    <div class="sheet"><div class="stack"><span class="eyebrow">Timed attempt · 3 hours</span><h2 id="exam-h">${paperName(subj, +p)} · ${esc(SESS[sess] ? SESS[sess].label : sess)}</h2></div>
      <div class="clock" data-clock="exam" role="timer">${clockText(rem)}</div>
      <p class="small muted" style="text-align:center">Time left. About 1,2 minutes per mark. Phone in another room.</p>
      <div class="paper-links" style="justify-content:center">${paperButtons(sess, subj, +p, false)}</div>
      <div class="row" style="justify-content:center">${e.pausedAt ? `<button class="btn" data-act="exam-resume">Resume</button>` : `<button class="btn ghost" data-act="exam-pause">Pause</button>`}
        <button class="btn" data-act="exam-finish">I'm done: mark it</button><button class="btn quiet" data-act="exam-hide">Hide timer</button></div>
      <button class="btn quiet sm" data-act="exam-cancel" style="justify-self:center">${L.confirmCancel ? "Tap again to cancel the attempt" : "Cancel attempt"}</button></div></div>`;
}
function closeOverlay() {
  document.getElementById("overlay-root").innerHTML = "";
}

/* ───────────────────────── Settings & More ───────────────────────── */
VIEWS.settings = () => {
  const pd = (k) => `<label class="lbl">${paperName(k.split(".")[0], +k.split(".")[1])}<input class="input" type="date" id="pd-${k.replace(".", "-")}" data-pd="${k}" value="${esc(S.paperDates[k] || "")}"></label>`;
  return `<header class="stack"><h1>Settings</h1><p class="lead">No account, no login. Everything is saved automatically.</p><p class="small muted" data-sync>${syncLabel()}</p></header>
  <form class="card stack-lg" data-form="settings">
    <label class="lbl">Your first name (optional, for the greeting)<input class="input" type="text" id="set-name" maxlength="40" value="${esc(S.name)}" autocomplete="given-name"></label>
    <label class="lbl">Date of your FIRST exam (the plan's Day 25 is the day before)<input class="input" type="date" id="set-exam" value="${S.examDate}" required></label>
    <div class="stack"><p class="small" style="font-weight:600">Your Maths and Physical Sciences paper dates (optional, from your timetable)</p>
      <div class="grid-2">${pd("maths.1")}${pd("maths.2")}${pd("phys.1")}${pd("phys.2")}</div></div>
    <div><button class="btn" type="submit">Save settings</button></div>
  </form>
  <section class="card stack"><h2>Back up your progress</h2>
    <p class="small muted">Copy this code and keep it somewhere safe (send it to yourself on WhatsApp or email). To move your progress to another phone or computer, paste it below there and press Restore.</p>
    <div class="row"><button class="btn ghost sm" data-act="backup-copy">Copy backup code</button></div>
    <label class="lbl" for="restore-box">Paste a backup code to restore</label><textarea class="input" id="restore-box" placeholder="Paste your backup code here"></textarea>
    <div class="row"><button class="btn ghost sm" data-act="restore">Restore</button></div></section>
  <section class="card stack"><h2>Start over</h2><p class="small muted">Clears every tick, score and flashcard. This can't be undone.</p>
    <div class="row"><button class="btn ${L.confirmReset ? "danger" : "ghost"} sm" data-act="reset">${L.confirmReset ? "Tap again to erase everything" : "Reset all progress"}</button></div></section>
  <p class="small muted">Matric Rewrite HQ is a free study tool. It isn't made by the Department of Basic Education; past papers and memos link to the DBE's official site, and videos are by their YouTube creators.</p>`;
};
VIEWS.more = () =>
  `<header class="stack"><h1>More</h1></header><div class="quick" style="grid-template-columns:repeat(2,minmax(0,1fr))">
  ${[["cards", "Drill", "Definitions & must-knows"], ["sheets", "Formula sheets", "What the exam gives you"], ["strategy", "Exam game plan", "How you'll pass"], ["focus", "Focus timer", "25 on, 5 off"], ["settings", "Settings", "Dates, backup, reset"]]
    .map(([k, b, s]) => `<a class="qlink" href="#${k}">${icon(k)}<b>${b}</b><span>${s}</span></a>`)
    .join("")}</div>`;

/* ───────────────────────── ticking clocks ───────────────────────── */
function tick() {
  const f = L.focus;
  if (f && f.running && f.endsAt - Date.now() <= 0) focusFinishPhase();
  const fr = focusRemaining();
  $$('[data-clock="focus"]').forEach((el) => (el.textContent = clockText(fr === null ? (L.focusLen === 50 ? 50 : 25) * 60000 : fr)));
  $$("[data-ring]").forEach((c) => {
    const circ = Number(c.dataset.ring);
    const total = Number(c.dataset.total);
    const r = fr === null ? total : fr;
    c.setAttribute("stroke-dashoffset", (circ * (1 - Math.max(0, r) / total)).toFixed(1));
  });
  const e = L.exam;
  const examRem = e ? EXAM_MS - examElapsed() : 0;
  $$('[data-clock="exam"]').forEach((el) => (el.textContent = clockText(examRem)));
  if (e && examRem <= 0 && !e.done) {
    e.done = true;
    saveLocal();
    chime();
    toast("Time's up. Pens down, then mark it with the memo.", 8000);
  }
  let chip = "";
  if (e) chip = `<button class="timer-chip exam" data-act="exam-show" aria-label="Exam timer">${clockText(examRem)} left</button>`;
  else if (f) chip = `<a class="timer-chip" href="#focus" aria-label="Focus timer">${f.phase === "break" ? "Break " : ""}${clockText(fr)}</a>`;
  ["top-chip", "rail-chip"].forEach((id) => {
    const el = document.getElementById(id);
    if (el && el.innerHTML !== chip) el.innerHTML = chip;
  });
}

/* ───────────────────────── celebrations ───────────────────────── */
function celebrate(n) {
  const reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (!reduce) {
    const el = document.createElement("div");
    el.className = "falling";
    el.style.left = 20 + Math.random() * 60 + "vw";
    el.innerHTML = `<svg width="44" height="44" viewBox="0 0 44 44" aria-hidden="true">${blossom(22, 22, 18, "").replace(/class="petal"/g, 'fill="var(--jac)"').replace('class="eye"', 'fill="var(--card)"')}</svg>`;
    document.body.appendChild(el);
    setTimeout(() => el.remove(), 3400);
  }
  toast(`Day ${n} done. They say if a jacaranda flower falls on you, you'll pass. You're not leaving it to luck.`, 6500);
}

/* ───────────────────────── events ───────────────────────── */
const ACT = {
  "open-day": (el) => go("day." + el.dataset.day),
  task: (el) => {
    const id = el.dataset.id;
    const n = +el.dataset.day;
    const before = dayProgress(n);
    if (el.checked) S.tasks[id] = Date.now();
    else delete S.tasks[id];
    commit();
    const afterP = dayProgress(n);
    rerender();
    if (afterP.done === afterP.total && before.done < before.total) celebrate(n);
  },
  "exam-ok": () => {
    S.examConfirmed = true;
    commit();
    rerender();
  },
  ltab: (el) => {
    L.learnTab = el.dataset.v;
    saveLocal();
    rerender();
  },
  "ltab-go": (el) => {
    L.learnTab = el.dataset.v;
    saveLocal();
  },
  status: (el) => {
    S.topics[el.dataset.id] = el.dataset.v;
    commit();
    rerender();
  },
  video: (el) => {
    S.videos[el.dataset.vid] = 1;
    commit();
    el.classList.add("seen");
  },
  reveal: (el) => {
    const a = document.getElementById(el.dataset.target);
    if (a) a.hidden = false;
    el.remove();
  },
  pq: (el) => {
    const k = el.dataset.k;
    S.practice[k] = S.practice[k] === el.dataset.v ? undefined : el.dataset.v;
    if (!S.practice[k]) delete S.practice[k];
    commit();
    rerender();
  },
  pf: (el) => {
    L[el.dataset.k] = el.dataset.v;
    saveLocal();
    rerender();
  },
  "log-open": (el) => {
    L.logOpen = L.logOpen === el.dataset.key ? null : el.dataset.key;
    saveLocal();
    rerender();
    const inp = document.getElementById("score-" + el.dataset.key.replace(/\./g, "-"));
    if (inp) inp.focus();
  },
  "log-close": () => {
    L.logOpen = null;
    saveLocal();
    rerender();
  },
  "del-attempt": (el) => {
    const id = +el.dataset.id;
    if (L.confirmDel === id) {
      S.attempts = S.attempts.filter((a) => a.id !== id);
      L.confirmDel = null;
      commit();
    } else {
      L.confirmDel = id;
      setTimeout(() => {
        if (L.confirmDel === id) {
          L.confirmDel = null;
          rerender();
        }
      }, 4000);
    }
    rerender();
  },
  "exam-start": (el) => {
    if (L.exam && L.exam.key !== el.dataset.key) {
      toast("Another timed attempt is still running. Finish or cancel it first.");
      openExam();
      return;
    }
    if (!L.exam) L.exam = { key: el.dataset.key, startedAt: Date.now(), pausedAt: null, pausedMs: 0 };
    saveLocal();
    openExam();
    tick();
  },
  "exam-show": () => openExam(),
  "exam-hide": () => closeOverlay(),
  "exam-pause": () => {
    L.exam.pausedAt = Date.now();
    saveLocal();
    openExam();
  },
  "exam-resume": () => {
    L.exam.pausedMs += Date.now() - L.exam.pausedAt;
    L.exam.pausedAt = null;
    saveLocal();
    openExam();
  },
  "exam-finish": () => {
    const key = L.exam.key;
    L.exam = null;
    L.logOpen = key;
    L.confirmCancel = false;
    saveLocal();
    closeOverlay();
    go("pp." + key);
    toast("Now mark it with the memo, strictly, then save your score here.");
  },
  "exam-cancel": () => {
    if (L.confirmCancel) {
      L.exam = null;
      L.confirmCancel = false;
      saveLocal();
      closeOverlay();
      tick();
    } else {
      L.confirmCancel = true;
      openExam();
      setTimeout(() => {
        if (L.confirmCancel) {
          L.confirmCancel = false;
          if (L.exam && document.querySelector(".overlay")) openExam();
        }
      }, 4000);
    }
  },
  flip: () => {
    if (!CS) return;
    CS.flipped = !CS.flipped;
    rerender();
  },
  card: (el) => {
    if (!CS || !CS.flipped) return;
    const i = CS.order[CS.pos];
    const b = S.cards[CS.id] || (S.cards[CS.id] = {});
    if (el.dataset.v === "got") {
      b[i] = Math.min(3, (b[i] || 0) + 1);
      CS.got++;
    } else {
      b[i] = 1;
      CS.again++;
    }
    commit();
    CS.pos++;
    CS.flipped = false;
    rerender();
  },
  "deck-again": () => {
    if (CS) startDeck(CS.id);
    rerender();
  },
  sheet: (el) => {
    L.sheet = el.dataset.v;
    saveLocal();
    go("sheets." + el.dataset.v);
  },
  "focus-subj": (el) => {
    L.focusSubj = el.dataset.v;
    saveLocal();
    rerender();
  },
  "focus-len": (el) => {
    L.focusLen = +el.dataset.v;
    saveLocal();
    rerender();
  },
  "focus-start": () => {
    const len = L.focusLen === 50 ? 50 : 25;
    L.focus = { subj: L.focusSubj, len, phase: "focus", total: len * 60000, endsAt: Date.now() + len * 60000, running: true };
    saveLocal();
    chime.ctx || (() => {
      try {
        const Ctx = window.AudioContext || window.webkitAudioContext;
        chime.ctx = new Ctx();
      } catch {
        /* no audio */
      }
    })();
    rerender();
  },
  "focus-quick": () => {
    ACT["focus-start"]();
    go("focus");
  },
  "focus-pause": () => {
    L.focus.remaining = L.focus.endsAt - Date.now();
    L.focus.running = false;
    saveLocal();
    rerender();
  },
  "focus-resume": () => {
    L.focus.endsAt = Date.now() + L.focus.remaining;
    L.focus.running = true;
    saveLocal();
    rerender();
  },
  "focus-stop": () => {
    L.focus = null;
    saveLocal();
    rerender();
  },
  "backup-copy": () => {
    const code = btoa(unescape(encodeURIComponent(JSON.stringify(S))));
    const done = () => toast("Backup code copied. Paste it somewhere safe.");
    const fallback = () => {
      const box = document.getElementById("restore-box");
      box.value = code;
      box.focus();
      box.select();
      toast("Couldn't copy automatically. The code is selected in the box: copy it from there.");
    };
    try {
      navigator.clipboard.writeText(code).then(done, fallback);
    } catch {
      fallback();
    }
  },
  restore: () => {
    const raw = (document.getElementById("restore-box").value || "").trim();
    if (!raw) return toast("Paste a backup code into the box first.");
    try {
      const obj = JSON.parse(decodeURIComponent(escape(atob(raw))));
      if (!obj || typeof obj !== "object" || !("tasks" in obj)) throw new Error("bad");
      S = normalize(obj);
      commit();
      toast("Progress restored.");
      go("today");
    } catch {
      toast("That code didn't work. Copy the whole code, with nothing extra, and try again.");
    }
  },
  reset: () => {
    if (!L.confirmReset) {
      L.confirmReset = true;
      rerender();
      setTimeout(() => {
        if (L.confirmReset) {
          L.confirmReset = false;
          if (parseHash().name === "settings") rerender();
        }
      }, 5000);
      return;
    }
    L.confirmReset = false;
    S = freshState();
    commit();
    toast("All progress cleared. Fresh start.");
    go("today");
  },
};

document.addEventListener("click", (e) => {
  const el = e.target.closest("[data-act]");
  if (!el || el.tagName === "INPUT") return;
  const fn = ACT[el.dataset.act];
  if (!fn) return;
  if (el.tagName === "BUTTON" || el.getAttribute("role")) e.preventDefault();
  if (el.dataset.act === "video" || el.dataset.act === "ltab-go") {
    fn(el);
    return; // let the link open
  }
  fn(el);
});
document.addEventListener("change", (e) => {
  const el = e.target;
  if (el.matches && el.matches('input[data-act="task"]')) ACT.task(el);
});
document.addEventListener("keydown", (e) => {
  const el = e.target;
  if ((e.key === "Enter" || e.key === " ") && el.getAttribute && el.getAttribute("role") && el.dataset.act) {
    e.preventDefault();
    ACT[el.dataset.act] && ACT[el.dataset.act](el);
    return;
  }
  if (parseHash().name === "deck" && CS && !/INPUT|TEXTAREA|SELECT/.test(el.tagName)) {
    if (e.key === " " && el.id !== "flashcard") {
      e.preventDefault();
      ACT.flip();
    } else if (CS.flipped && e.key === "1") ACT.card({ dataset: { v: "again" } });
    else if (CS.flipped && e.key === "2") ACT.card({ dataset: { v: "got" } });
  }
  if (e.key === "Escape" && document.querySelector(".overlay")) closeOverlay();
});
document.addEventListener("submit", (e) => {
  const form = e.target;
  const kind = form.dataset.form;
  if (!kind) return;
  e.preventDefault();
  if (kind === "exam-date") {
    const v = $("#first-exam").value;
    if (!isYmd(v)) return toast("Choose a date first.");
    S.examDate = v;
    S.examConfirmed = true;
    commit();
    toast(`Saved. Day 25 is now ${fmtDate(addDays(v, -1), { weekday: "long", day: "numeric", month: "long" })}.`);
    rerender();
  } else if (kind === "log") {
    const key = form.dataset.key;
    const id = key.replace(/\./g, "-");
    const score = Number($("#score-" + id).value);
    const date = $("#date-" + id).value;
    if (!Number.isInteger(score) || score < 0 || score > 150) return toast("Enter a whole-number mark between 0 and 150.");
    S.attempts.push({ id: Date.now(), key, score, total: 150, date: isYmd(date) ? date : todayYmd() });
    L.logOpen = null;
    saveLocal();
    commit();
    const p = pct(score);
    toast(p >= 40 ? `${p}%. That's above your 40% target. Keep this up.` : p >= 30 ? `${p}%. That's a pass. Now push for 40%: redo the questions you lost marks on.` : `${p}%. Every paper you mark shows you exactly which marks to go after next. Redo the questions you lost marks on in two days.`, 7000);
    rerender();
  } else if (kind === "settings") {
    const exam = $("#set-exam").value;
    if (!isYmd(exam)) return toast("Choose the date of your first exam.");
    S.name = $("#set-name").value.trim().slice(0, 40);
    S.examDate = exam;
    S.examConfirmed = true;
    $$("[data-pd]").forEach((inp) => (S.paperDates[inp.dataset.pd] = isYmd(inp.value) ? inp.value : ""));
    commit();
    toast("Settings saved.");
    rerender();
  }
});
window.addEventListener("hashchange", () => render());

/* ───────────────────────── boot ───────────────────────── */
function start() {
  shell();
  render();
  if (L.exam && !L.exam.done && EXAM_MS - examElapsed() > 0) {
    /* the chip in the header lets the learner reopen a running attempt */
  }
  setInterval(tick, 1000);
  Sync.init();
}
start();

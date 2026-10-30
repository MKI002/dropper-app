/* Dropper web UI.
   Views are pure functions from state to HTML; a small DOM morpher patches the page in place so
   animations, focus and scroll survive the live updates. All text goes through I18N.t(). */
(function () {
  "use strict";

  const { t, th, esc } = I18N;
  const $ = (sel, root) => (root || document).querySelector(sel);

  // ================================================================ icons (Lucide, ISC license)
  const ICONS = {
    dashboard: '<rect width="7" height="9" x="3" y="3" rx="1"/><rect width="7" height="5" x="14" y="3" rx="1"/><rect width="7" height="9" x="14" y="12" rx="1"/><rect width="7" height="5" x="3" y="16" rx="1"/>',
    gift: '<rect x="3" y="8" width="18" height="4" rx="1"/><path d="M12 8v13"/><path d="M19 12v7a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2v-7"/><path d="M7.5 8a2.5 2.5 0 0 1 0-5A4.8 8 0 0 1 12 8a4.8 8 0 0 1 4.5-5 2.5 2.5 0 0 1 0 5"/>',
    flag: '<path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z"/><line x1="4" x2="4" y1="22" y2="15"/>',
    tv: '<rect width="20" height="15" x="2" y="7" rx="2" ry="2"/><polyline points="17 2 12 7 7 2"/>',
    chart: '<path d="M3 3v18h18"/><path d="M18 17V9"/><path d="M13 17V5"/><path d="M8 17v-3"/>',
    sliders: '<line x1="21" x2="14" y1="4" y2="4"/><line x1="10" x2="3" y1="4" y2="4"/><line x1="21" x2="12" y1="12" y2="12"/><line x1="8" x2="3" y1="12" y2="12"/><line x1="21" x2="16" y1="20" y2="20"/><line x1="12" x2="3" y1="20" y2="20"/><line x1="14" x2="14" y1="2" y2="6"/><line x1="8" x2="8" y1="10" y2="14"/><line x1="16" x2="16" y1="18" y2="22"/>',
    terminal: '<polyline points="4 17 10 11 4 5"/><line x1="12" x2="20" y1="19" y2="19"/>',
    refresh: '<path d="M21 12a9 9 0 1 1-9-9c2.52 0 4.93 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/>',
    pause: '<rect x="6" y="4" width="4" height="16" rx="1"/><rect x="14" y="4" width="4" height="16" rx="1"/>',
    play: '<polygon points="6 3 20 12 6 21 6 3"/>',
    globe: '<circle cx="12" cy="12" r="10"/><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"/><path d="M2 12h20"/>',
    external: '<path d="M15 3h6v6"/><path d="M10 14 21 3"/><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>',
    check: '<path d="M20 6 9 17l-5-5"/>',
    x: '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
    plus: '<path d="M5 12h14"/><path d="M12 5v14"/>',
    alert: '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
    info: '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>',
    clock: '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
    eye: '<path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/>',
    eyeoff: '<path d="M9.88 9.88a3 3 0 1 0 4.24 4.24"/><path d="M10.73 5.08A10.43 10.43 0 0 1 12 5c7 0 10 7 10 7a13.16 13.16 0 0 1-1.67 2.68"/><path d="M6.61 6.61A13.526 13.526 0 0 0 2 12s3 7 10 7a9.74 9.74 0 0 0 5.39-1.61"/><line x1="2" x2="22" y1="2" y2="22"/>',
    users: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
    link: '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>',
    star: '<polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>',
    ban: '<circle cx="12" cy="12" r="10"/><path d="m4.9 4.9 14.2 14.2"/>',
    search: '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
    chevron: '<path d="m6 9 6 6 6-6"/>',
    chevright: '<path d="m9 18 6-6-6-6"/>',
    up: '<path d="m18 15-6-6-6 6"/>',
    down: '<path d="m6 9 6 6 6-6"/>',
    sparkles: '<path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z"/><path d="M5 3v4"/><path d="M19 17v4"/><path d="M3 5h4"/><path d="M17 19h4"/>',
    zap: '<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>',
    logout: '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" x2="9" y1="12" y2="12"/>',
    copy: '<rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>',
    gamepad: '<line x1="6" x2="10" y1="11" y2="11"/><line x1="8" x2="8" y1="9" y2="13"/><line x1="15" x2="15.01" y1="12" y2="12"/><line x1="18" x2="18.01" y1="10" y2="10"/><path d="M17.32 5H6.68a4 4 0 0 0-3.978 3.59c-.006.052-.01.101-.017.152C2.604 9.416 2 14.456 2 16a3 3 0 0 0 3 3c1 0 1.5-.5 2-1l1.414-1.414A2 2 0 0 1 9.828 16h4.344a2 2 0 0 1 1.414.586L17 18c.5.5 1 1 2 1a3 3 0 0 0 3-3c0-1.545-.604-6.584-.685-7.258-.007-.05-.011-.1-.017-.151A4 4 0 0 0 17.32 5z"/>',
    award: '<circle cx="12" cy="8" r="6"/><path d="M15.477 12.89 17 22l-5-3-5 3 1.523-9.11"/>',
    smile: '<circle cx="12" cy="12" r="10"/><path d="M8 14s1.5 2 4 2 4-2 4-2"/><line x1="9" x2="9.01" y1="9" y2="9"/><line x1="15" x2="15.01" y1="9" y2="9"/>',
    box: '<path d="m7.5 4.27 9 5.15"/><path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"/><path d="m3.3 7 8.7 5 8.7-5"/><path d="M12 22V12"/>',
    lock: '<rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
    hourglass: '<path d="M5 22h14"/><path d="M5 2h14"/><path d="M17 22v-4.172a2 2 0 0 0-.586-1.414L12 12l-4.414 4.414A2 2 0 0 0 7 17.828V22"/><path d="M7 2v4.172a2 2 0 0 0 .586 1.414L12 12l4.414-4.414A2 2 0 0 0 17 6.172V2"/>',
    calendar: '<rect width="18" height="18" x="3" y="4" rx="2" ry="2"/><line x1="16" x2="16" y1="2" y2="6"/><line x1="8" x2="8" y1="2" y2="6"/><line x1="3" x2="21" y1="10" y2="10"/>',
    coins: '<circle cx="8" cy="8" r="6"/><path d="M18.09 10.37A6 6 0 1 1 10.34 18"/><path d="M7 6h1v4"/><path d="m16.71 13.88.7.71-2.82 2.82"/>',
    radio: '<path d="M4.9 19.1C1 15.2 1 8.8 4.9 4.9"/><path d="M7.8 16.2c-2.3-2.3-2.3-6.1 0-8.5"/><circle cx="12" cy="12" r="2"/><path d="M16.2 7.8c2.3 2.3 2.3 6.1 0 8.5"/><path d="M19.1 4.9C23 8.8 23 15.1 19.1 19"/>',
    history: '<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M12 7v5l4 2"/>',
    user: '<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
    bell: '<path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/>',
    shield: '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/>',
    more: '<circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/><circle cx="5" cy="12" r="1"/>',
    droplet: '<path d="M12 22a7 7 0 0 0 7-7c0-2-1-3.9-3-5.5s-3.5-4-4-6.5c-.5 2.5-2 4.9-4 6.5C6 11.1 5 13 5 15a7 7 0 0 0 7 7z"/>',
    pausecircle: '<circle cx="12" cy="12" r="10"/><line x1="10" x2="10" y1="15" y2="9"/><line x1="14" x2="14" y1="15" y2="9"/>',
    trophy: '<path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6"/><path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18"/><path d="M4 22h16"/><path d="M10 14.66V17c0 .55-.47.98-.97 1.21C7.85 18.75 7 20.24 7 22"/><path d="M14 14.66V17c0 .55.47.98.97 1.21C16.15 18.75 17 20.24 17 22"/><path d="M18 2H6v7a6 6 0 0 0 12 0V2Z"/>',
    send: '<path d="m22 2-7 20-4-9-9-4Z"/><path d="M22 2 11 13"/>',
  };
  const icon = (name, cls) => `<svg class="i${cls ? " " + cls : ""}" viewBox="0 0 24 24" aria-hidden="true">${ICONS[name] || ""}</svg>`;

  // a cloud with three drops falling from it, for the "nothing to do" state
  const CLOUD = `<svg class="idle-art" viewBox="0 0 72 72" aria-hidden="true">
    <path class="cloud" d="M49 45.6H28.6a16.8 16.8 0 1 1 16.1-21.6h4.3a10.8 10.8 0 1 1 0 21.6Z"/>
    <line class="drip" x1="27" y1="52" x2="27" y2="57"/><line class="drip" x1="37" y1="52" x2="37" y2="57"/><line class="drip" x1="47" y1="52" x2="47" y2="57"/>
  </svg>`;

  // ================================================================ helpers
  const clone = (v) => JSON.parse(JSON.stringify(v));
  const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
  const lower = (s) => String(s || "").toLocaleLowerCase();
  // game names compare like on the server (models.norm_game): case, accents and punctuation do not count
  const gkey = (s) => {
    const text = String(s || "").normalize("NFKD").replace(/\p{M}/gu, "").toLowerCase().replace(/ß/g, "ss");
    return text.replace(/[^\p{L}\p{N}]+/gu, "") || text.trim();
  };
  const attr = (v) => esc(v);
  const uniq = (arr) => [...new Set(arr)];
  const byName = (a, b) => String(a).localeCompare(String(b), I18N.intl);
  const now = () => Date.now();
  const pad = (n) => String(n).padStart(2, "0");
  const isoDay = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  const noon = (day) => day + "T12:00:00";

  function boxArt(url, w, h) {
    if (!url) return "";
    if (url.includes("{width}")) return url.replace("{width}", w).replace("{height}", h);
    if (!url.includes("jtvnw.net/ttv-boxart/")) return url; // catalog images come in one size
    return /-\d+x\d+\.\w+$/.test(url) ? url.replace(/-\d+x\d+(\.\w+)$/, `-${w}x${h}$1`) : url.replace(/(\.\w+)$/, `-${w}x${h}$1`);
  }
  function thumb(login, w, h) {
    if (window.DropperDemo) return window.DropperDemo.thumb(login, w, h); // the demo site draws its own streams
    const bucket = Math.floor(now() / 300000);
    return `https://static-cdn.jtvnw.net/previews-ttv/live_user_${encodeURIComponent(lower(login))}-${w}x${h}.jpg?t=${bucket}`;
  }
  const rewardImage = (d) => (d && d.benefits && d.benefits[0] && d.benefits[0].image) || "";
  const imgTag = (src, cls, alt) => src ? `<img class="${cls || ""}" src="${attr(src)}" alt="${attr(alt || "")}" loading="lazy" decoding="async" onerror="this.style.visibility='hidden'">` : `<span class="${cls || ""}"></span>`;

  const STATUS = {
    claimed: { tone: "green", icon: "check" },
    ready: { tone: "accent", icon: "gift" },
    failed: { tone: "red", icon: "alert" },
    progress: { tone: "blue", icon: "radio" },
    pending: { tone: "gray", icon: "clock" },
    locked: { tone: "orange", icon: "lock" },
    upcoming: { tone: "teal", icon: "calendar" },
    expired: { tone: "gray", icon: "hourglass" },
    missed: { tone: "gray", icon: "x" },
    other: { tone: "gray", icon: "info" },
  };
  const DROP_GROUPS = {
    all: () => true,
    ready: (d) => d.status === "ready",
    failed: (d) => d.status === "failed",
    active: (d) => d.status === "progress" || d.status === "pending",
    claimed: (d) => d.status === "claimed",
    locked: (d) => d.status === "locked",
    upcoming: (d) => d.status === "upcoming",
    ended: (d) => ["expired", "missed", "other"].includes(d.status),
  };
  const GROUP_TONE = { ready: "accent", failed: "red", active: "blue", claimed: "green", locked: "orange", upcoming: "teal", ended: "gray" };
  const DROP_ORDER = ["ready", "failed", "progress", "pending", "locked", "upcoming", "claimed", "missed", "expired", "other"];
  const TYPE_ICON = { DIRECT_ENTITLEMENT: "box", BADGE: "award", EMOTE: "smile", UNKNOWN: "gift" };
  const toneVar = (tone) => (tone === "accent" ? "var(--accent-text)" : `var(--${tone})`);

  // ================================================================ api
  async function api(path, opts) {
    const res = await fetch(path, Object.assign({ headers: { "Content-Type": "application/json" } }, opts || {}));
    if (!res.ok) {
      let detail = res.statusText;
      try {
        const body = await res.json();
        if (typeof body.detail === "string") detail = body.detail;
        else if (Array.isArray(body.detail)) detail = body.detail.map((d) => `${(d.loc || []).slice(-1)[0] || ""}: ${d.msg}`).join("; ");
        else detail = JSON.stringify(body.detail);
      } catch (e) { /* not json */ }
      const err = new Error(detail || String(res.status));
      err.status = res.status;
      throw err;
    }
    return res.json();
  }
  const post = (path, body) => api(path, { method: "POST", body: JSON.stringify(body || {}) });
  const put = (path, body) => api(path, { method: "PUT", body: JSON.stringify(body || {}) });

  // ================================================================ store
  const S = {
    view: "overview",
    state: null,
    offline: false,
    campaigns: null,
    channels: null,
    drops: null,
    stats: null,
    week: null,
    settings: null,
    logs: [],
    logAfter: 0,
    draft: null,
    gqlText: null,
    menu: null,
    sheet: false,
    palette: null,
    modal: null,
    hover: null,
    seenClaims: null,
    wasLogin: false,
    notifyBusy: false,
    tagInput: {},
    games: {}, // gkey -> Twitch lookup: { status: "found" | "missing" | "unavailable", game }
    gameSearch: null, // { q, results, lookup } for the text in the priority list's game field
    ui: {
      drops: { filter: "all", q: "", game: "" },
      campaigns: { filter: "all", q: "", game: "", types: [], linked: false, open: [] },
      channels: { q: "", game: "", live: true, mine: false, manual: "" },
      stats: { days: 30 },
      log: { level: "all", q: "", follow: true },
      historyAll: false,
    },
  };

  // ================================================================ DOM morphing
  function sameKind(a, b) {
    if (a.nodeType !== b.nodeType) return false;
    if (a.nodeType !== 1) return true;
    return a.tagName === b.tagName && !a.hasAttribute("data-key");
  }
  function syncAttrs(cur, next) {
    for (const { name } of Array.from(cur.attributes)) {
      if (!next.hasAttribute(name)) cur.removeAttribute(name);
    }
    for (const { name, value } of Array.from(next.attributes)) {
      if (cur.getAttribute(name) === value) continue;
      if (name === "class" && cur.classList.contains("is-new")) cur.setAttribute("class", value + " is-new");
      else cur.setAttribute(name, value);
    }
  }
  function patch(cur, next) {
    if (cur.nodeType !== 1) {
      if (cur.nodeValue !== next.nodeValue) cur.nodeValue = next.nodeValue;
      return;
    }
    syncAttrs(cur, next);
    if (cur.hasAttribute("data-count") || cur.hasAttribute("data-keep")) return;
    const tag = cur.tagName;
    if (tag === "INPUT") {
      if (cur.type === "checkbox" || cur.type === "radio") cur.checked = next.hasAttribute("checked");
      else if (document.activeElement !== cur) {
        const v = next.getAttribute("value") || "";
        if (cur.value !== v) cur.value = v;
      }
      return;
    }
    if (tag === "TEXTAREA") {
      if (document.activeElement !== cur && cur.value !== next.textContent) cur.value = next.textContent;
      return;
    }
    morphChildren(cur, next);
    if (tag === "SELECT" && document.activeElement !== cur) {
      const sel = next.querySelector("option[selected]");
      cur.value = sel ? sel.value : (cur.options[0] && cur.options[0].value) || "";
    }
  }
  function morphChildren(parent, src) {
    const keyed = new Map();
    for (const c of Array.from(parent.children)) {
      const k = c.getAttribute("data-key");
      if (k !== null) keyed.set(k, c);
    }
    let ref = parent.firstChild;
    for (const nk of Array.from(src.childNodes)) {
      const key = nk.nodeType === 1 ? nk.getAttribute("data-key") : null;
      let cur = null;
      if (key !== null) {
        cur = keyed.get(key) || null;
        if (cur) keyed.delete(key);
      } else if (ref && sameKind(ref, nk)) {
        cur = ref;
      }
      if (cur) {
        if (cur === ref) ref = ref.nextSibling;
        else parent.insertBefore(cur, ref);
        patch(cur, nk);
      } else {
        if (key !== null && S.rendered) nk.classList.add("is-new");
        parent.insertBefore(nk, ref);
      }
    }
    while (ref) {
      const next = ref.nextSibling;
      parent.removeChild(ref);
      ref = next;
    }
  }
  function morph(el, html) {
    const tpl = document.createElement("template");
    tpl.innerHTML = html;
    morphChildren(el, tpl.content);
  }
  document.addEventListener("animationend", (e) => {
    if (e.target.classList && e.target.classList.contains("is-new")) e.target.classList.remove("is-new");
  });

  // ================================================================ render loop
  let queued = false;
  function render() {
    if (queued) return;
    queued = true;
    requestAnimationFrame(() => {
      queued = false;
      renderNow(false);
    });
  }
  function renderNow(fresh) {
    renderChrome();
    const viewEl = $("#view");
    const html = (VIEWS[S.view] || vOverview)();
    if (fresh) viewEl.innerHTML = html;
    else morph(viewEl, html);
    renderLogin();
    renderOverlays();
    afterRender();
    S.rendered = true;
  }

  const FORMATS = {
    int: (v) => I18N.num(Math.round(v)),
    pct: (v) => I18N.pct(v),
    hours: (v) => I18N.hours(v),
    compact: (v) => I18N.compact(Math.round(v)),
  };
  function afterRender() {
    document.querySelectorAll("[data-count]").forEach((el) => {
      const to = Number(el.dataset.count);
      const fmtName = el.dataset.fmt || "int";
      if (el._val !== to || el._fmt !== fmtName || el._lang !== I18N.lang) {
        el._fmt = fmtName;
        el._lang = I18N.lang;
        FX.countTo(el, to, FORMATS[fmtName] || FORMATS.int);
      }
    });
    if (S.view === "log" && S.ui.log.follow) {
      const body = $("#log-body");
      if (body) body.scrollTop = body.scrollHeight;
    }
  }

  // ================================================================ chrome
  const NAV = [
    { id: "overview", icon: "dashboard" },
    { id: "drops", icon: "gift" },
    { id: "campaigns", icon: "flag" },
    { id: "channels", icon: "tv" },
    { id: "stats", icon: "chart" },
    { id: "settings", icon: "sliders" },
    { id: "log", icon: "terminal" },
  ];
  const MOBILE_NAV = ["overview", "drops", "campaigns", "channels"];

  function navBadge(id) {
    const c = S.state && S.state.counts;
    if (!c) return "";
    if (id === "drops") {
      if (c.claim_failed) return `<b class="count bad">${I18N.num(c.claim_failed)}</b>`;
      if (c.claim_ready) return `<b class="count accent">${I18N.num(c.claim_ready)}</b>`;
    }
    if (id === "channels" && c.channels_live) return `<b class="count">${I18N.num(c.channels_live)}</b>`;
    return "";
  }

  function stateKey() {
    if (S.offline) return "offline";
    return (S.state && S.state.state) || "starting";
  }

  function renderChrome() {
    const nav = $("#nav");
    nav.style.setProperty("--i", Math.max(0, NAV.findIndex((n) => n.id === S.view)));
    morph(nav, `<span class="nav-indicator" aria-hidden="true"></span>` + NAV.map((n) => {
      const badge = navBadge(n.id);
      return `<a href="#${n.id}" data-key="${n.id}" ${S.view === n.id ? 'aria-current="page"' : ""} ${badge.includes("bad") ? "data-badge" : ""} title="${attr(t("nav." + n.id))}">${icon(n.icon)}<span>${esc(t("nav." + n.id))}</span>${badge}</a>`;
    }).join(""));

    const tabbar = $("#tabbar");
    const inMore = !MOBILE_NAV.includes(S.view);
    tabbar.style.setProperty("--i", inMore ? MOBILE_NAV.length : MOBILE_NAV.indexOf(S.view));
    morph(tabbar, MOBILE_NAV.map((id) => {
      const n = NAV.find((x) => x.id === id);
      const bad = navBadge(id).includes("bad");
      return `<a href="#${id}" data-key="${id}" ${S.view === id ? 'aria-current="page"' : ""} ${bad ? "data-badge" : ""}>${icon(n.icon)}<span>${esc(t("nav." + id))}</span></a>`;
    }).join("") + `<button data-key="more" data-action="sheet" ${inMore ? 'aria-current="page"' : ""}>${icon("more")}<span>${esc(t("nav.more"))}</span></button>`);

    const titleEl = $("#page-title");
    if (titleEl._view !== S.view || titleEl._lang !== I18N.lang) {
      const title = t("nav." + S.view);
      titleEl.innerHTML = `<h1>${esc(title)}</h1><p>${esc(t(`page.${S.view}.sub`))}</p>`;
      $("#mobile-title").innerHTML = `<h1>${esc(title)}</h1>`;
      titleEl._view = S.view;
      titleEl._lang = I18N.lang;
      document.title = `${title} · Dropper`;
    }

    const st = S.state;
    const key = stateKey();
    const paused = st && st.paused;
    const refreshing = key === "refreshing" || key === "starting";
    const pauseLabel = attr(t(paused ? "action.resume" : "action.pause"));
    morph($("#top-actions"), `
      <button class="state-pill desk-only st-${key}" data-action="go" data-arg="overview" title="${attr(activityText())}"><span class="dot"></span><span>${esc(t("state." + key))}</span></button>
      <button class="icon-btn desk-only ${refreshing ? "spin" : ""}" data-action="refresh" title="${attr(t("action.refresh"))}" aria-label="${attr(t("action.refresh"))}">${icon("refresh")}</button>
      <button class="icon-btn ${paused ? "on" : ""}" data-action="pause" title="${pauseLabel}" aria-label="${pauseLabel}">${icon(paused ? "play" : "pause")}</button>
      ${langButton("top")}`);

    const user = st && st.user;
    morph($("#account"), user
      ? `<span class="avatar">${esc((user.login || "?").slice(0, 1))}</span><div class="grow"><b class="ellipsis">${esc(user.login)}</b><span class="ellipsis">${esc(t("account.connected"))} · v${esc(st.version || "")}</span></div>`
      : `<span class="avatar">${icon("user")}</span><div class="grow"><b class="ellipsis">${esc(t("account.none"))}</b><span>v${esc((st && st.version) || "")}</span></div>`);

    morph($("#banners"), banners());
    I18N.apply($(".sidebar"));
  }

  function langButton(where) {
    const open = S.menu === "lang-" + where;
    const items = I18N.LANGS.map((l) => `<button role="menuitemradio" aria-checked="${l.code === I18N.lang}" data-action="lang" data-arg="${l.code}">${l.code === I18N.lang ? icon("check", "chk") : '<i class="chk"></i>'}<span>${esc(l.name)}</span><span class="code">${l.code.toUpperCase()}</span></button>`).join("");
    return `<div class="menu-wrap" data-key="lang-${where}"><button class="lang-btn" data-action="menu" data-arg="lang-${where}" aria-haspopup="menu" aria-expanded="${open}" title="${attr(t("action.language"))}">${icon("globe")}<span>${I18N.lang.toUpperCase()}</span></button>${open ? `<div class="menu" role="menu">${items}</div>` : ""}</div>`;
  }

  function activityText() {
    const a = S.state && S.state.activity;
    if (!a || !a.code) return "";
    return t("activity." + a.code, a.params || {});
  }

  function bannerHtml(key, tone, iconName, title, text, action) {
    return `<div class="banner ${tone}" data-key="${key}"><span class="bicon">${icon(iconName)}</span><div class="grow">${title ? `<b>${esc(title)}</b>` : ""}${text ? `<p>${esc(text)}</p>` : ""}</div>${action || ""}</div>`;
  }

  function banners() {
    const st = S.state;
    if (S.offline) return bannerHtml("offline", "", "alert", t("banner.offline.title"), t("banner.offline.text"));
    if (!st || st.state === "login") return "";
    const c = st.counts || {};
    const out = [];
    if (c.claim_failed && S.view !== "drops") {
      out.push(bannerHtml("failed", "", "alert", t("banner.failed.title", { n: c.claim_failed }), t("banner.failed.text"),
        `<a class="btn sm danger" href="#drops/failed">${esc(t("banner.failed.action"))}</a>`));
    }
    if (!st.auto_claim && c.claim_ready && S.view !== "drops") {
      out.push(bannerHtml("ready", "accent", "gift", t("banner.ready.title", { n: c.claim_ready }), t("banner.ready.text"),
        `<a class="btn sm primary" href="#drops/ready">${esc(t("banner.ready.action"))}</a>`));
    }
    if (st.error) out.push(bannerHtml("error", "orange", "info", t("banner.error.title"), st.error));
    return out.join("");
  }

  // ================================================================ views
  const VIEWS = {
    overview: vOverview,
    drops: vDrops,
    campaigns: vCampaigns,
    channels: vChannels,
    stats: vStats,
    settings: vSettings,
    log: vLog,
  };

  function skeleton(kind) {
    if (kind === "grid") {
      return `<div class="drops-grid">${Array.from({ length: 6 }, () => `<div class="card dcard"><div class="row" style="gap:12px"><div class="sk" style="width:56px;height:56px;border-radius:12px"></div><div class="grow"><div class="sk" style="height:14px;width:70%"></div><div class="sk" style="height:10px;width:45%;margin-top:8px"></div></div></div><div class="sk" style="height:4px"></div></div>`).join("")}</div>`;
    }
    return `<div class="grid cols-12"><div class="card span-8"><div class="sk" style="min-height:260px"></div></div><div class="card span-4"><div class="sk" style="width:168px;height:168px;border-radius:50%;margin:30px auto"></div></div></div>`;
  }

  function empty(iconName, text) {
    return `<div class="empty">${icon(iconName)}<div>${esc(text)}</div></div>`;
  }

  const cardHead = (title, link) => `<div class="card-head"><h3>${esc(title)}</h3>${link ? `<a class="link" href="${link.href}">${esc(link.label)}</a>` : ""}</div>`;

  function kpi(o) {
    const tag = o.href ? "a" : "div";
    const fmt = o.fmt || "int";
    const value = Number(o.value) || 0;
    return `<${tag} class="card kpi" style="--tone:${toneVar(o.tone)}" ${o.href ? `href="${o.href}"` : ""}>
      <div class="kpi-head">${icon(o.icon)}<span>${esc(o.label)}</span>${o.href ? icon("chevright", "chev") : ""}</div>
      <div class="kpi-value"><span data-count="${value}" data-fmt="${fmt}">${FORMATS[fmt](value)}</span>${o.unit ? `<small>${esc(o.unit)}</small>` : ""}</div>
      <div class="kpi-sub">${esc(o.sub)}</div>
      ${o.chart || ""}
    </${tag}>`;
  }

  function miniBars(values) {
    if (!values || values.length < 2) return "";
    const max = Math.max(1, ...values);
    return `<div class="mini-bars" aria-hidden="true">${values.map((v, i) => `<i class="${i === values.length - 1 ? "cur" : ""}" style="--h:${Math.max(4, Math.round((v / max) * 34))}px;--k:${i}"></i>`).join("")}</div>`;
  }

  function segments(drops) {
    if (!drops.length) return "";
    return `<div class="segments">${drops.map((x) => `<i class="${x.is_claimed ? "done" : ""}"><b style="--p:${(x.progress || 0) * 100}%"></b></i>`).join("")}</div>`;
  }

  /** iOS style segmented control; items: {action, arg, label, on, set} */
  function segmented(items, label) {
    const i = Math.max(0, items.findIndex((x) => x.on));
    return `<div class="seg" role="group" ${label ? `aria-label="${attr(label)}"` : ""} style="--n:${items.length};--i:${i}">${items.map((x) => `<button type="button" data-action="${x.action}" data-arg="${attr(x.arg)}" ${x.set ? `data-set="${x.set}"` : ""} aria-pressed="${!!x.on}">${esc(x.label)}</button>`).join("")}</div>`;
  }

  const gameSelect = (model, games, value) => `<select class="select" data-model="${model}" aria-label="${attr(t("filter.game"))}"><option value="">${esc(t("filter.allgames"))}</option>${games.map((g) => `<option value="${attr(g)}" ${g === value ? "selected" : ""}>${esc(g)}</option>`).join("")}</select>`;
  const searchBox = (model, value, placeholder, iconName) => `<label class="search">${icon(iconName || "search")}<input class="input" type="search" data-model="${model}" value="${attr(value)}" placeholder="${attr(placeholder)}"></label>`;
  const inlineSwitch = (model, on, label) => `<label class="inline-switch"><span class="switch"><input type="checkbox" data-model="${model}" ${on ? "checked" : ""}><span></span></span>${esc(label)}</label>`;

  // ---------------------------------------------------------------- overview
  function vOverview() {
    const st = S.state;
    if (!st) return skeleton();
    const w = st.watching;
    const camps = S.campaigns || [];
    const target = st.campaign ? camps.find((c) => c.id === st.campaign.id) : null;

    const week = S.week;
    const c = st.counts || {};
    const failed = c.claim_failed || 0;
    const timeline = week ? week.timeline : [];
    const kpis = [
      kpi({ tone: "blue", icon: "clock", label: t("kpi.today"), value: week ? week.totals.minutes_today : 0, fmt: "hours", unit: t("unit.hours_short"),
        sub: t("kpi.today.sub", { time: I18N.dur(st.session ? st.session.minutes : 0) }), chart: miniBars(timeline.map((d) => d.minutes)) }),
      kpi({ tone: "green", icon: "trophy", label: t("kpi.claimed"), value: week ? week.totals.claims : 0,
        sub: t("kpi.claimed.sub", { n: I18N.num(week ? week.totals.claims_today : 0) }), chart: miniBars(timeline.map((d) => d.claims)) }),
      failed
        ? kpi({ tone: "red", icon: "alert", label: t("kpi.failed"), value: failed, sub: t("kpi.failed.sub"), href: "#drops/failed" })
        : kpi({ tone: "accent", icon: "gift", label: t("kpi.ready"), value: c.claim_ready || 0, sub: t(st.auto_claim ? "kpi.ready.auto" : "kpi.ready.manual"), href: "#drops/ready" }),
      kpi({ tone: "teal", icon: "radio", label: t("kpi.live"), value: c.channels_live || 0, href: "#channels",
        sub: t("kpi.live.sub", { wanted: I18N.num(c.wanted || 0), active: I18N.num(c.active || 0) }) }),
    ].join("");

    const queue = camps.filter((x) => x.wanted).sort((a, b) => (a.queue_position || 0) - (b.queue_position || 0)).slice(0, 6);
    const queueHtml = queue.length
      ? `<div class="list queue">${queue.map((q) => `
          <div class="item" data-key="${attr(q.id)}">
            <span class="pos ${q.mining ? "on" : ""}">${q.queue_position}</span>
            ${imgTag(boxArt(q.game.box_art, 72, 96), "art", q.game.name)}
            <div class="item-main">
              <b class="ellipsis">${esc(q.game.name)}</b>
              <span class="ellipsis">${esc(q.name)}</span>
              <div class="bar"><i style="--p:${q.total ? (q.claimed / q.total) * 100 : 0}%"></i></div>
            </div>
            <div class="item-side">
              <b class="num">${q.claimed}/${q.total}</b>
              <span>${esc(q.live_channels ? t("count.live", { n: q.live_channels }) : t("queue.nolive"))}</span>
              <span>${esc(t("time.ends", { time: I18N.rel(q.ends_at) }))}</span>
            </div>
          </div>`).join("")}</div>`
      : empty("flag", t("queue.empty"));

    const claimed = S.drops ? S.drops.drops.filter((d) => d.status === "claimed" && d.claimed_at).sort((a, b) => String(b.claimed_at).localeCompare(String(a.claimed_at))).slice(0, 8) : [];
    const claimsHtml = claimed.length
      ? `<div class="claims">${claimed.map((d) => `
          <a class="claim" href="#drops/claimed" data-key="${attr(d.id)}" title="${attr(d.rewards + " · " + d.game.name)}">
            <span class="claim-img">${imgTag(rewardImage(d), "", d.rewards)}</span>
            <span class="claim-name">${esc(d.rewards)}</span>
            <time>${esc(I18N.rel(d.claimed_at))}</time>
          </a>`).join("")}</div>`
      : empty("gift", t("claims.empty"));

    return `
      <div class="grid cols-12">
        <section class="card now span-8">${w ? nowWatching(st, w) : idle(st)}</section>
        <section class="card drop-card span-4">${dropCard(st, target)}</section>
      </div>
      <div class="grid kpis">${kpis}</div>
      <div class="grid cols-12">
        <section class="card span-7">${cardHead(t("queue.title"), { href: "#campaigns", label: t("queue.all") })}${queueHtml}</section>
        <section class="card span-5">${cardHead(t("claims.title"), { href: "#drops", label: t("claims.all") })}${claimsHtml}</section>
      </div>`;
  }

  function nowWatching(st, w) {
    return `<div class="now-grid">
      <a class="now-media" href="${attr(w.url)}" target="_blank" rel="noopener">
        <img src="${attr(thumb(w.login, 640, 360))}" alt="" onerror="this.style.visibility='hidden'">
        <span class="live-badge">${esc(t("live"))}</span>
        <span class="viewers">${icon("users")}<span data-count="${w.viewers || 0}" data-fmt="int">${I18N.num(w.viewers || 0)}</span></span>
      </a>
      <div class="now-body">
        <div class="caption"><span class="pulse-dot"></span><span>${esc(t("hero.watching"))}</span>${st.manual ? `<span class="tag orange">${esc(t("hero.manual"))}</span>` : ""}</div>
        <h2><a href="${attr(w.url)}" target="_blank" rel="noopener">${esc(w.name)}</a></h2>
        <div class="now-game">${esc(w.game || "–")}</div>
        ${w.title ? `<div class="now-title">${esc(w.title)}</div>` : ""}
        <div class="row wrap">
          <a class="btn sm" href="${attr(w.url)}" target="_blank" rel="noopener">${icon("external")}${esc(t("action.open_twitch"))}</a>
          ${st.manual ? `<button class="btn sm primary" data-action="auto">${icon("zap")}${esc(t("action.auto"))}</button>` : `<a class="btn sm plain" href="#channels">${esc(t("hero.switch"))}</a>`}
        </div>
      </div>
      ${whyBox(st.selection)}
    </div>`;
  }

  function whyBox(sel) {
    if (!sel) return "";
    const lines = [];
    if (sel.rule === "manual") {
      lines.push(th("why.rule.manual"));
    } else {
      lines.push(th("why.queue", { campaign: sel.campaign, game: sel.game, position: sel.position, queue: sel.queue }));
      if (sel.position > 1) lines.push(th("why.earlier"));
      lines.push(th("why.candidates", { n: sel.candidates }));
      lines.push(th("why.rule." + sel.rule));
    }
    return `<div class="why"><h4>${esc(t("why.title"))}</h4><p>${lines.join(" ")}</p></div>`;
  }

  function idle(st) {
    const code = (st.activity && st.activity.code) || "starting";
    let title, text, actions = "";
    if (st.paused) {
      title = t("idle.paused.title");
      text = t("idle.paused.text");
      actions = `<button class="btn primary" data-action="pause">${icon("play")}${esc(t("action.resume"))}</button>`;
    } else if (code === "no_campaigns") {
      title = t("idle.no_campaigns.title");
      text = t(S.settings && S.settings.games_priority.length ? "idle.no_campaigns.watching" : "idle.no_campaigns.text");
      actions = `<a class="btn primary" href="#campaigns">${esc(t("nav.campaigns"))}</a><a class="btn" href="#settings">${esc(t("nav.settings"))}</a>`;
    } else if (code === "no_channels") {
      title = t("idle.no_channels.title");
      text = t("idle.no_channels.text", { time: st.next_refresh ? I18N.rel(st.next_refresh) : "…" });
      actions = `<button class="btn primary" data-action="refresh">${icon("refresh")}${esc(t("action.refresh"))}</button>`;
    } else {
      title = t("idle.working.title");
      text = activityText();
    }
    return `<div class="idle">
      ${st.paused ? icon("pausecircle", "idle-icon") : CLOUD}
      <h2>${esc(title)}</h2>
      <p>${esc(text)}</p>
      ${actions ? `<div class="row wrap center">${actions}</div>` : ""}
    </div>`;
  }

  function dropCard(st, target) {
    const d = st.drop;
    if (!d) return cardHead(t("drop.title")) + empty("hourglass", t("drop.none"));
    const p = d.progress || 0;
    const C = 2 * Math.PI * 54;
    const camp = st.campaign;
    const remaining = Math.max(0, d.required_minutes - d.current_minutes);
    const status = d.status === "ready" || d.status === "failed"
      ? `<span class="tone-${STATUS[d.status].tone}">${esc(t("status." + d.status))}</span>`
      : `<span>${esc(t("drop.eta", { time: I18N.dur(remaining) }))}</span>`;
    return `
      ${cardHead(t("drop.title"))}
      <div class="ring ${p >= 1 ? "full" : ""}">
        <svg viewBox="0 0 120 120" aria-hidden="true"><circle class="track" cx="60" cy="60" r="54"/><circle class="arc" cx="60" cy="60" r="54" stroke-dasharray="${C.toFixed(2)}" stroke-dashoffset="${(C * (1 - p)).toFixed(2)}"/></svg>
        <div class="ring-img">${imgTag(rewardImage(d), "", d.rewards)}</div>
      </div>
      <div class="drop-pct" data-count="${p}" data-fmt="pct">${I18N.pct(p)}</div>
      <h4>${esc(d.rewards)}</h4>
      <div class="drop-meta"><span class="num">${esc(t("drop.minutes", { cur: I18N.num(d.current_minutes), req: I18N.num(d.required_minutes) }))}</span><span>·</span>${status}</div>
      ${segments(target ? target.drops : [])}
      ${camp ? `<div class="drop-camp ellipsis">${esc(camp.name)} · ${esc(t("drop.of", { claimed: camp.claimed, total: camp.total }))}</div>` : ""}`;
  }

  // ---------------------------------------------------------------- drops
  function vDrops() {
    const D = S.drops;
    if (!D) return skeleton("grid");
    const ui = S.ui.drops;
    const all = D.drops;
    const counts = {};
    for (const g in DROP_GROUPS) counts[g] = all.filter(DROP_GROUPS[g]).length;
    const games = uniq(all.map((d) => d.game.name)).sort(byName);
    const q = lower(ui.q);
    const list = all.filter(DROP_GROUPS[ui.filter] || DROP_GROUPS.all)
      .filter((d) => !ui.game || d.game.name === ui.game)
      .filter((d) => !q || lower(`${d.rewards} ${d.name} ${d.game.name} ${d.campaign.name}`).includes(q))
      .sort((a, b) => (b.mining - a.mining)
        || (DROP_ORDER.indexOf(a.status) - DROP_ORDER.indexOf(b.status))
        || (a.status === "claimed" ? String(b.claimed_at || "").localeCompare(String(a.claimed_at || "")) : 0)
        || (b.progress - a.progress)
        || String(a.campaign.ends_at).localeCompare(String(b.campaign.ends_at)));

    const chips = Object.keys(DROP_GROUPS).map((g) => `
      <button class="chip" data-key="${g}" data-action="dropFilter" data-arg="${g}" aria-pressed="${ui.filter === g}">
        ${g === "all" ? "" : `<span class="cdot tone-${GROUP_TONE[g]}"></span>`}<span>${esc(t("dropgroup." + g))}</span><span class="n">${I18N.num(counts[g])}</span>
      </button>`).join("");

    const grid = list.length
      ? `<div class="drops-grid">${list.map((d) => dropTile(d, D.auto_claim)).join("")}</div>`
      : `<div class="card">${empty("gift", all.length ? t("drops.nomatch") : t("drops.empty"))}</div>`;

    const claims = D.claims || [];
    const shown = S.ui.historyAll ? claims : claims.slice(0, 12);
    const history = claims.length
      ? `<div class="list history">${shown.map((c) => `
          <div class="item" data-key="h${c.id}">
            <span class="hicon ${c.success ? "" : "bad"}">${icon(c.success ? "check" : "x")}</span>
            <div class="item-main"><b class="ellipsis">${esc(c.rewards || c.drop_name)}</b><span class="ellipsis">${esc(c.game)} · ${esc(t("method." + c.method))}${c.success ? "" : ` · ${esc(c.detail || "")}`}</span></div>
            <span class="item-num" title="${attr(I18N.date(c.ts))}">${esc(I18N.rel(c.ts))}</span>
          </div>`).join("")}</div>
          ${claims.length > 12 ? `<button class="more-btn ${S.ui.historyAll ? "open" : ""}" data-action="historyAll">${esc(t(S.ui.historyAll ? "action.show_less" : "action.show_all"))} ${icon("chevron")}</button>` : ""}`
      : empty("history", t("history.empty"));

    const rewards = D.rewards || [];
    const collection = rewards.length
      ? `<div class="collection">${rewards.map((r) => `
          <div class="reward-card" data-key="r${attr(r.id)}" title="${attr(r.name)}">
            <div class="reward-img">${imgTag(r.image, "", r.name)}${r.count > 1 ? `<span class="cnt">×${I18N.num(r.count)}</span>` : ""}${r.link_url && !r.connected ? `<a class="lk" href="${attr(r.link_url)}" target="_blank" rel="noopener" title="${attr(t("collection.unlinked"))}">${icon("link")}</a>` : ""}</div>
            <b>${esc(r.name)}</b>
            <span>${esc(r.game)}</span>
            ${r.last_awarded_at ? `<span class="date">${esc(I18N.date(r.last_awarded_at, "short"))}</span>` : ""}
          </div>`).join("")}</div>`
      : empty("trophy", t("collection.empty"));

    return `
      <div class="chips scroll">${chips}</div>
      <div class="toolbar">
        ${searchBox("drops.q", ui.q, t("drops.search"))}
        ${gameSelect("drops.game", games, ui.game)}
        <span class="note ${D.auto_claim ? "on" : ""}" title="${attr(t("drops.auto.hint"))}"><span class="ndot"></span>${esc(t(D.auto_claim ? "drops.auto.on" : "drops.auto.off"))}</span>
      </div>
      ${grid}
      <div class="grid cols-12">
        <section class="span-6">
          <div class="section-head"><h3>${esc(t("history.title"))}</h3><span>${esc(t("history.sub"))}</span></div>
          <div class="card list-card">${history}</div>
        </section>
        <section class="span-6">
          <div class="section-head"><h3>${esc(t("collection.title"))}</h3><span>${esc(t("collection.sub", { n: rewards.length }))}</span></div>
          <div class="card">${collection}</div>
        </section>
      </div>`;
  }

  function dropTile(d, autoClaim) {
    const meta = STATUS[d.status] || STATUS.other;
    const p = d.progress || 0;
    let when = "";
    switch (d.status) {
      case "claimed": when = d.claimed_at ? t("time.claimed", { time: I18N.rel(d.claimed_at) }) : ""; break;
      case "ready": when = t(autoClaim ? "drops.ready.auto" : "drops.ready.manual"); break;
      case "failed": when = d.claim_retry_at ? t("drops.retry", { time: I18N.rel(d.claim_retry_at) }) : ""; break;
      case "progress": case "pending": when = t("time.ends", { time: I18N.rel(d.ends_at) }); break;
      case "locked": when = t("drops.locked"); break;
      case "upcoming": when = t("time.starts", { time: I18N.rel(String(d.starts_at) > String(d.campaign.starts_at) ? d.starts_at : d.campaign.starts_at) }); break;
      case "expired": when = t("time.ended", { time: I18N.rel(d.ends_at) }); break;
      case "missed": when = t("drops.missed"); break;
      default: when = t("drops.other");
    }
    const canClaim = d.status === "ready" || d.status === "failed";
    const actions = [];
    if (d.mining) actions.push(`<span class="live-label"><span class="pulse-dot"></span>${esc(t("drops.watching"))}</span>`);
    if ((d.needs_link || (!d.campaign.link_known && d.campaign.link_url)) && d.status !== "claimed") actions.push(`<a class="btn sm" href="${attr(d.campaign.link_url)}" target="_blank" rel="noopener">${icon("link")}${esc(t("action.link_account"))}</a>`);
    if (canClaim) actions.push(`<button class="btn sm ${d.status === "ready" ? "primary" : ""}" data-action="claim" data-arg="${attr(d.id)}">${esc(t(d.status === "ready" ? "action.claim" : "action.retry_claim"))}</button>`);
    const err = d.status === "failed" ? `
      <div class="errbox">
        <div class="row between"><b>${esc(t("drops.failed.title"))}</b><span class="tries">${esc(t("drops.failed.tries", { n: d.claim_attempts }))}</span></div>
        <p>${esc(t(d.needs_link ? "drops.failed.link" : "drops.failed.retry"))}</p>
        <code>${esc(d.claim_error)}</code>
      </div>` : "";
    return `
      <article class="card dcard s-${d.status}" data-key="${attr(d.id)}">
        <div class="dcard-head">
          <div class="reward-img">${imgTag(rewardImage(d), "", d.rewards)}</div>
          <div class="dcard-title"><b>${esc(d.rewards)}</b><span class="ellipsis">${esc(d.game.name)} · ${esc(d.campaign.name)}</span></div>
        </div>
        ${d.required_minutes > 0 ? `<div class="prog">
          <div class="bar ${d.status === "claimed" ? "green" : d.status === "failed" ? "red" : ""}"><i style="--p:${p * 100}%"></i></div>
          <div class="prog-text"><span>${esc(t("drop.minutes", { cur: I18N.num(d.current_minutes), req: I18N.num(d.required_minutes) }))}</span><span>${I18N.pct(p)}</span></div>
        </div>` : ""}
        ${err}
        <div class="dcard-foot">
          <span class="status tone-${meta.tone}">${icon(meta.icon)}${esc(t("status." + d.status))}</span>
          <span class="when grow ellipsis">${esc(when)}</span>
        </div>
        ${actions.length ? `<div class="row wrap">${actions.join("")}</div>` : ""}
      </article>`;
  }

  // ---------------------------------------------------------------- campaigns
  function vCampaigns() {
    const list0 = S.campaigns;
    if (!list0) return skeleton("grid");
    const ui = S.ui.campaigns;
    const st = S.settings || {};
    const excludedGames = new Set((st.games_exclude || []).map(gkey));
    const prio = (st.games_priority || []).map(gkey);
    const disabled = new Set(st.campaigns_exclude || []);
    const games = uniq(list0.map((c) => c.game.name)).sort(byName);
    const q = lower(ui.q);
    const filters = {
      all: () => true,
      queue: (c) => c.wanted,
      active: (c) => c.status === "active",
      upcoming: (c) => c.status === "upcoming",
      skipped: (c) => !c.wanted && c.status === "active" && !c.finished,
      finished: (c) => c.finished,
    };
    const counts = {};
    for (const f in filters) counts[f] = list0.filter(filters[f]).length;
    const list = list0.filter(filters[ui.filter] || filters.all)
      .filter((c) => !ui.game || c.game.name === ui.game)
      .filter((c) => !ui.linked || c.linked)
      .filter((c) => !ui.types.length || ui.types.some((ty) => c.reward_types.includes(ty)))
      .filter((c) => !q || lower(`${c.name} ${c.game.name} ${c.drops.map((d) => d.rewards).join(" ")}`).includes(q));

    const chips = Object.keys(filters).map((f) => `<button class="chip" data-key="${f}" data-action="campFilter" data-arg="${f}" aria-pressed="${ui.filter === f}"><span>${esc(t("campfilter." + f))}</span><span class="n">${I18N.num(counts[f])}</span></button>`).join("");
    const types = ["DIRECT_ENTITLEMENT", "BADGE", "EMOTE"].map((ty) => {
      const on = ui.types.includes(ty);
      return `<button class="chip" data-key="${ty}" data-action="campType" data-arg="${ty}" aria-pressed="${on}">${icon(on ? "check" : TYPE_ICON[ty])}<span>${esc(t("type." + ty))}</span></button>`;
    }).join("");

    const cards = list.length ? `<div class="camp-grid">${list.map((c) => campaignCard(c, { excludedGames, prio, disabled })).join("")}</div>`
      : `<div class="card">${empty("flag", list0.length ? t("campaigns.nomatch") : t("campaigns.empty"))}</div>`;
    // games on the priority list that have no campaign yet: Dropper keeps watching them
    const waiting = (st.games_priority || []).filter((g) => !list0.some((c) => gkey(c.game.name) === gkey(g) && c.status !== "expired"));
    if (waiting.length) lookupGames(waiting);
    const watching = waiting.length ? `<div class="waitlist" data-key="watching">
        <span class="watching-label">${icon("eye")}${esc(t("campaigns.watching"))}</span>
        ${waiting.map((g) => `<span class="wchip" data-key="${attr(g)}">${gameArt(g)}<span class="ellipsis">${esc(g)}</span></span>`).join("")}
        <a class="watching-edit" href="#settings">${esc(t("campaigns.watching.edit"))}${icon("chevright")}</a>
      </div>` : "";
    const source = S.state && S.state.campaign_source;
    const note = source === "catalog" || source === "inventory"
      ? bannerHtml("src-" + source, source === "catalog" ? "accent" : "orange", "info", "", t("campaigns.source." + source))
      : "";

    return `
      ${note}
      <div class="chips scroll">${chips}</div>
      <div class="toolbar">
        ${searchBox("campaigns.q", ui.q, t("campaigns.search"))}
        ${gameSelect("campaigns.game", games, ui.game)}
        <div class="chips">${types}</div>
        ${inlineSwitch("campaigns.linked", ui.linked, t("campaigns.linkedonly"))}
      </div>
      ${watching}
      ${cards}`;
  }

  function campaignCard(c, ctx) {
    const game = gkey(c.game.name);
    const isPrio = ctx.prio.includes(game);
    const isExcluded = ctx.excludedGames.has(game);
    const enabled = !ctx.disabled.has(c.id);
    const tags = [];
    if (c.mining) tags.push(`<span class="tag green"><span class="pulse-dot"></span><span>${esc(t("camp.mining"))}</span></span>`);
    else if (c.wanted) tags.push(`<span class="tag accent">${esc(t("camp.queue", { n: c.queue_position }))}</span>`);
    if (c.status === "upcoming") tags.push(`<span class="tag teal">${icon("calendar")}<span>${esc(t("camp.upcoming"))}</span></span>`);
    if (c.finished && c.claimed >= c.total) tags.push(`<span class="tag green">${icon("check")}<span>${esc(t("camp.finished"))}</span></span>`);
    if (isPrio) tags.push(`<span class="tag yellow">${icon("star")}<span>${esc(t("camp.prio"))}</span></span>`);
    c.reward_types.forEach((ty) => tags.push(`<span class="tag">${icon(TYPE_ICON[ty] || "gift")}<span>${esc(t("type." + ty))}</span></span>`));
    const open = S.ui.campaigns.open.includes(c.id);
    const drops = c.drops.slice().sort((a, b) => a.required_minutes - b.required_minutes);
    const shown = open ? drops : drops.slice(0, 3);
    const when = c.status === "upcoming" ? t("time.starts", { time: I18N.rel(c.starts_at) }) : c.status === "expired" ? t("time.ended", { time: I18N.rel(c.ends_at) }) : t("time.ends", { time: I18N.rel(c.ends_at) });
    const link = !c.link_url ? ""
      : !c.link_known ? `<a class="tone-orange" href="${attr(c.link_url)}" target="_blank" rel="noopener">${icon("link")}${esc(t("camp.link_unknown"))}</a>`
      : c.linked ? `<span class="tone-green">${icon("link")}${esc(t("camp.linked"))}</span>`
      : `<a href="${attr(c.link_url)}" target="_blank" rel="noopener">${icon("link")}${esc(t("camp.unlinked"))}</a>`;
    const dim = !c.wanted && !c.mining && c.status !== "upcoming";
    return `
      <article class="card camp ${c.mining ? "mining" : ""} ${dim ? "dim" : ""}" data-key="${attr(c.id)}">
        <div class="camp-head">
          ${imgTag(boxArt(c.game.box_art, 108, 144) || c.image, "art", c.game.name)}
          <div class="camp-ttl">
            <span class="game ellipsis">${esc(c.game.name)}</span>
            <h4>${esc(c.name)}</h4>
            ${tags.length ? `<div class="tags">${tags.join("")}</div>` : ""}
          </div>
          <label class="switch" title="${attr(t("camp.toggle"))}"><input type="checkbox" data-action="toggleCampaign" data-arg="${attr(c.id)}" ${enabled ? "checked" : ""} aria-label="${attr(t("camp.toggle"))}"><span></span></label>
        </div>
        ${segments(drops)}
        <div class="meta">
          ${c.total ? `<span>${icon("gift")}${esc(t("camp.drops", { claimed: c.claimed, total: c.total }))}</span>` : ""}
          <span>${icon("clock")}${esc(when)}</span>
          ${c.remaining_minutes ? `<span>${icon("hourglass")}${esc(t("camp.left", { time: I18N.dur(c.remaining_minutes) }))}</span>` : ""}
          <span>${icon("radio")}${esc(t("count.live", { n: c.live_channels }))}</span>
          ${c.acl_channels ? `<span>${icon("users")}${esc(t("camp.acl", { n: c.acl_channels }))}</span>` : ""}
          ${link}
        </div>
        <div class="camp-drops">
          ${drops.length ? "" : `<div class="hint">${esc(t("camp.nodetails"))}</div>`}
          ${shown.map((d) => {
            const meta = STATUS[d.status] || STATUS.other;
            const canClaim = d.status === "ready" || d.status === "failed";
            const label = d.status === "progress" || d.status === "pending" ? t("drop.minutes", { cur: I18N.num(d.current_minutes), req: I18N.num(d.required_minutes) }) : t("status." + d.status);
            return `<div class="cdrop" data-key="${attr(d.id)}">
              <span class="cdrop-img">${imgTag(rewardImage(d), "", d.rewards)}</span>
              <div class="cdrop-main"><span class="ellipsis">${esc(d.rewards)}</span><div class="bar ${d.is_claimed ? "green" : ""}"><i style="--p:${(d.progress || 0) * 100}%"></i></div></div>
              ${canClaim ? `<button class="btn sm ${d.status === "ready" ? "primary" : "danger"}" data-action="claim" data-arg="${attr(d.id)}" title="${attr(d.claim_error || "")}">${esc(t(d.status === "ready" ? "action.claim" : "action.retry_claim"))}</button>`
                : `<span class="st tone-${meta.tone}">${icon(meta.icon)}${esc(label)}</span>`}
            </div>`;
          }).join("")}
          ${drops.length > 3 ? `<button class="more-btn ${open ? "open" : ""}" data-action="campOpen" data-arg="${attr(c.id)}">${esc(t(open ? "action.show_less" : "camp.more", { n: drops.length - 3 }))} ${icon("chevron")}</button>` : ""}
        </div>
        <div class="camp-foot">
          ${c.skip_reason && !c.wanted ? `<span class="skip">${icon("pausecircle")}${esc(t("skip." + c.skip_reason))}</span>` : '<span class="grow"></span>'}
          <div class="acts">
            <button class="btn sm ${isPrio ? "on" : ""}" data-action="prioritize" data-arg="${attr(c.game.name)}" title="${attr(t(isPrio ? "action.unprioritize" : "action.prioritize"))}">${icon("star")}${esc(t(isPrio ? "camp.prio" : "action.prioritize"))}</button>
            <button class="icon-btn sm ${isExcluded ? "off" : ""}" data-action="exclude" data-arg="${attr(c.game.name)}" title="${attr(t(isExcluded ? "action.include" : "action.exclude"))}" aria-label="${attr(t(isExcluded ? "action.include" : "action.exclude"))}">${icon(isExcluded ? "eye" : "eyeoff")}</button>
          </div>
        </div>
      </article>`;
  }

  // ---------------------------------------------------------------- channels
  function vChannels() {
    const all = S.channels;
    if (!all) return skeleton("grid");
    const ui = S.ui.channels;
    const q = lower(ui.q);
    const games = uniq(all.map((c) => c.game).filter(Boolean)).sort(byName);
    const list = all.filter((c) => (!ui.live || c.online))
      .filter((c) => !ui.mine || c.campaigns.some((k) => k.wanted))
      .filter((c) => !ui.game || c.game === ui.game)
      .filter((c) => !q || lower(`${c.name} ${c.login} ${c.game || ""} ${c.title || ""}`).includes(q));

    const live = (c, w, h) => c.online ? imgTag(thumb(c.login, w, h), "", c.name) + `<span class="live-badge">${esc(t("live"))}</span>` : "";
    const rows = list.map((c) => `<tr class="${c.watching ? "watching" : ""} ${c.online ? "" : "offline"}" data-key="${attr(c.id)}">
        <td><div class="ch-cell">
          <div class="ch-thumb">${live(c, 224, 126)}</div>
          <div class="ch-name"><a href="${attr(c.url)}" target="_blank" rel="noopener">${esc(c.name)}</a><small>${esc(c.title || "")}</small>${channelFlags(c)}</div>
        </div></td>
        <td class="muted">${esc(c.game || "–")}</td>
        <td class="num">${c.online ? I18N.compact(c.viewers) : "–"}</td>
        <td>${channelCampaigns(c)}</td>
        <td><span class="tag">${esc(t("source." + c.source))}</span></td>
        <td>${channelActions(c)}</td>
      </tr>`).join("");

    const cards = list.map((c) => `
      <div class="card ch-card" data-key="${attr(c.id)}">
        <div class="ch-thumb">${live(c, 440, 248)}</div>
        <div class="row between"><div class="ch-name"><a href="${attr(c.url)}" target="_blank" rel="noopener">${esc(c.name)}</a><small>${esc(c.game || "")} · ${esc(c.online ? t("count.viewers", { n: c.viewers }) : t("offline"))}</small></div>${channelActions(c)}</div>
        ${channelFlags(c)}
        ${channelCampaigns(c)}
      </div>`).join("");

    const table = list.length ? `
      <div class="card ch-table-wrap">
        <table class="ch-table">
          <thead><tr><th>${esc(t("channels.col.channel"))}</th><th>${esc(t("channels.col.game"))}</th><th>${esc(t("channels.col.viewers"))}</th><th>${esc(t("channels.col.campaigns"))}</th><th>${esc(t("channels.col.source"))}</th><th></th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
      <div class="ch-cards">${cards}</div>` : `<div class="card">${empty("tv", all.length ? t("channels.nomatch") : t("channels.empty"))}</div>`;

    return `
      <div class="toolbar">
        ${searchBox("channels.q", ui.q, t("channels.search"))}
        ${gameSelect("channels.game", games, ui.game)}
        ${inlineSwitch("channels.live", ui.live, t("channels.liveonly"))}
        ${inlineSwitch("channels.mine", ui.mine, t("channels.mineonly"))}
      </div>
      <form class="toolbar" data-action="manualWatch">
        <label class="search">${icon("tv")}<input class="input" data-model="channels.manual" value="${attr(ui.manual)}" placeholder="${attr(t("channels.manual"))}" autocomplete="off"></label>
        <button class="btn" type="submit">${icon("play")}${esc(t("action.watch"))}</button>
        <span class="hint">${esc(t("channels.manual.hint"))}</span>
      </form>
      ${table}`;
  }

  function channelFlags(c) {
    const f = [];
    if (c.watching) f.push(`<span class="tag green">${icon("radio")}<span>${esc(t("channels.watching"))}</span></span>`);
    if (c.preferred) f.push(`<span class="tag yellow">${icon("star")}<span>${esc(t("channels.preferred"))}</span></span>`);
    if (c.blacklisted) f.push(`<span class="tag red">${icon("ban")}<span>${esc(t("channels.blocked"))}</span></span>`);
    return f.length ? `<div class="row wrap">${f.join("")}</div>` : "";
  }

  function channelCampaigns(c) {
    if (!c.campaigns.length) {
      return c.drops_enabled ? `<span class="tag" title="${attr(t("channels.dropson.hint"))}">${icon("gift")}<span>${esc(t("channels.dropson"))}</span></span>` : `<span class="hint">${esc(t("channels.nodrops"))}</span>`;
    }
    const tags = c.campaigns.map((k) => k.wanted
      ? `<span class="tag accent" title="${attr(k.game)}">${icon("check")}<span>${esc(k.name || t("channels.unknown"))}</span></span>`
      : `<span class="tag" title="${attr(t("skip." + k.reason))}"><span>${esc(k.name || t("channels.unknown"))}</span></span>`).join("");
    const reasons = uniq(c.campaigns.filter((k) => !k.wanted).map((k) => t("skip." + k.reason)));
    return `<div class="ch-camps">${tags}${reasons.length ? `<span class="reason">${esc(t("channels.skipped"))}: ${esc(reasons.join(" · "))}</span>` : ""}</div>`;
  }

  function channelActions(c) {
    const prefer = attr(t(c.preferred ? "action.unprefer" : "action.prefer"));
    const block = attr(t(c.blacklisted ? "action.unblock" : "action.block"));
    return `<div class="ch-actions">
      ${c.online && !c.watching ? `<button class="btn sm" data-action="watch" data-arg="${attr(c.login)}">${esc(t("action.watch"))}</button>` : ""}
      <button class="icon-btn sm star ${c.preferred ? "on" : ""}" data-action="prefer" data-arg="${attr(c.login)}" title="${prefer}" aria-label="${prefer}">${icon("star")}</button>
      <button class="icon-btn sm ${c.blacklisted ? "off" : ""}" data-action="block" data-arg="${attr(c.login)}" title="${block}" aria-label="${block}">${icon("ban")}</button>
    </div>`;
  }

  // ---------------------------------------------------------------- stats
  /** Days for short ranges, weeks for a quarter, months for a year. */
  function bucketize(timeline, days) {
    const mode = days <= 31 ? "day" : days <= 120 ? "week" : "month";
    const out = [];
    for (const d of timeline) {
      let key = d.day;
      if (mode === "week") {
        const date = new Date(noon(d.day));
        date.setDate(date.getDate() - ((date.getDay() + 6) % 7));
        key = isoDay(date);
      } else if (mode === "month") {
        key = d.day.slice(0, 7) + "-01";
      }
      let b = out[out.length - 1];
      if (!b || b.key !== key) out.push(b = { key, minutes: 0, claims: 0 });
      b.minutes += d.minutes;
      b.claims += d.claims;
    }
    for (const b of out) {
      const at = noon(b.key);
      if (mode === "day") {
        b.label = I18N.date(at, days <= 7 ? "weekday" : "short");
        b.title = I18N.date(at, "day");
      } else if (mode === "week") {
        b.label = I18N.date(at, "short");
        b.title = t("stats.week", { date: I18N.date(at, "short") });
      } else {
        b.label = I18N.date(at, "month");
        b.title = I18N.date(at, "monthyear");
      }
    }
    return { mode, buckets: out };
  }

  function niceStep(x) {
    if (!(x > 0)) return 1;
    const p = Math.pow(10, Math.floor(Math.log10(x)));
    const f = x / p;
    return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10) * p;
  }

  function chart(buckets) {
    const n = buckets.length;
    const maxH = Math.max(0, ...buckets.map((b) => b.minutes / 60));
    const step = Math.max(0.5, niceStep(maxH / 4));
    const top = Math.max(step, Math.ceil(maxH / step - 1e-9) * step);
    const lines = [];
    for (let v = 0; v <= top + 1e-9; v += step) lines.push(v);
    const y = (v) => (v / top) * 100;
    const every = Math.max(1, Math.ceil(n / 8));
    const hover = S.hover !== null && S.hover < n ? S.hover : null;
    let tip = "";
    if (hover !== null) {
      const b = buckets[hover];
      const x = ((hover + 0.5) / n) * 100;
      tip = `<div class="chart-tip ${x < 15 ? "l" : x > 85 ? "r" : ""}" style="--x:${x}%;--h:${y(b.minutes / 60)}%"><b>${esc(b.title)}</b>${esc(I18N.hours(b.minutes))} ${esc(t("unit.hours_short"))} · ${esc(t("count.drops", { n: b.claims }))}</div>`;
    }
    return `<div class="chart ${hover !== null ? "hovering" : ""}" data-chart>
      <div class="chart-y" aria-hidden="true">${lines.map((v) => `<span style="--y:${y(v)}%">${esc(I18N.num(v, 1))}</span>`).join("")}</div>
      <div class="chart-plot">
        ${lines.map((v) => `<i class="gl" style="--y:${y(v)}%"></i>`).join("")}
        <div class="chart-bars">${buckets.map((b, i) => `<div class="col ${i === hover ? "hl" : ""}" data-hover="${i}" style="--h:${y(b.minutes / 60)}%;--k:${i}" title="${attr(b.title)}"><i class="b"></i>${b.claims ? '<i class="dot"></i>' : ""}</div>`).join("")}</div>
        ${tip}
      </div>
      <div class="chart-x" aria-hidden="true">${buckets.map((b, i) => `<span>${i % every === 0 ? esc(b.label) : ""}</span>`).join("")}</div>
    </div>`;
  }

  function vStats() {
    const s = S.stats;
    const days = S.ui.stats.days;
    const seg = segmented([7, 30, 90, 365].map((d) => ({ action: "statsDays", arg: d, label: t("stats.days", { n: d }), on: days === d })));
    if (!s) return `<div class="toolbar">${seg}</div>${skeleton()}`;
    const tot = s.totals;
    const rangeMinutes = s.timeline.reduce((a, d) => a + d.minutes, 0);
    const rangeClaims = s.timeline.reduce((a, d) => a + d.claims, 0);
    const kpis = [
      kpi({ tone: "blue", icon: "clock", label: t("stats.watch"), value: tot.minutes, fmt: "hours", unit: t("unit.hours_short"),
        sub: t("stats.inrange", { value: I18N.hours(rangeMinutes) + " " + t("unit.hours_short") }) }),
      kpi({ tone: "green", icon: "trophy", label: t("stats.claimed"), value: tot.claims, sub: t("stats.inrange", { value: I18N.num(rangeClaims) }) }),
      kpi({ tone: tot.failed_claims ? "red" : "gray", icon: "alert", label: t("stats.failed"), value: tot.failed_claims, sub: t("stats.failed.sub") }),
      kpi({ tone: "yellow", icon: "coins", label: t("stats.points"), value: tot.points, fmt: "compact", sub: t("stats.points.sub") }),
    ].join("");

    const { mode, buckets } = bucketize(s.timeline, days);
    const title = t(mode === "week" ? "stats.chart.week" : mode === "month" ? "stats.chart.month" : "stats.chart");

    const boxArts = {};
    (S.campaigns || []).forEach((c) => { boxArts[c.game.name] = c.game.box_art; });
    const maxGame = Math.max(1, ...s.per_game.map((g) => g.minutes));
    const games = s.per_game.length ? `<div class="list stat-list">${s.per_game.slice(0, 10).map((g) => `
      <div class="item" data-key="g${attr(g.game)}">
        ${imgTag(boxArt(boxArts[g.game], 72, 96), "art", g.game)}
        <div class="item-main">
          <div class="row between"><b class="ellipsis">${esc(g.game)}</b><span class="item-num">${esc(I18N.hours(g.minutes))} ${esc(t("unit.hours_short"))} · ${esc(t("count.drops", { n: g.claims }))}</span></div>
          <div class="bar"><i style="--p:${(g.minutes / maxGame) * 100}%"></i></div>
        </div>
      </div>`).join("")}</div>` : empty("gamepad", t("stats.empty"));
    const maxCh = Math.max(1, ...s.per_channel.map((c) => c.minutes));
    const chans = s.per_channel.length ? `<div class="list stat-list plain">${s.per_channel.slice(0, 10).map((c) => `
      <div class="item" data-key="c${attr(c.channel + c.game)}">
        <div class="item-main">
          <div class="row between"><a class="ellipsis" href="https://www.twitch.tv/${attr(c.channel)}" target="_blank" rel="noopener"><b>${esc(c.channel)}</b></a><span class="item-num ellipsis">${esc(c.game)} · ${esc(I18N.hours(c.minutes))} ${esc(t("unit.hours_short"))}</span></div>
          <div class="bar"><i style="--p:${(c.minutes / maxCh) * 100}%"></i></div>
        </div>
      </div>`).join("")}</div>` : empty("tv", t("stats.empty"));

    return `
      <div class="toolbar">${seg}</div>
      <div class="grid kpis">${kpis}</div>
      <section class="card">
        <div class="card-head"><h3>${esc(title)}</h3><span class="legend"><span><i class="lg-bar"></i>${esc(t("stats.legend.hours"))}</span><span><i class="lg-dot"></i>${esc(t("stats.legend.drops"))}</span></span></div>
        ${chart(buckets)}
      </section>
      <div class="grid cols-12">
        <section class="card span-6">${cardHead(t("stats.games"))}${games}</section>
        <section class="card span-6">${cardHead(t("stats.channels"))}${chans}</section>
      </div>`;
  }

  // ---------------------------------------------------------------- settings
  const GAME_SUGGEST = () => uniq((S.campaigns || []).map((c) => c.game.name)).sort(byName);
  const CHANNEL_SUGGEST = () => uniq((S.channels || []).map((c) => c.login)).sort(byName);
  const LANG_SUGGEST = () => ["en", "de", "es", "fr", "it", "pt", "pl", "tr", "ru", "ja", "ko", "zh", "nl", "sv", "uk", "cs"];
  const NOTIFY = ["claimed", "failed", "campaign_done", "watched", "new_campaign", "login"];
  const DISCORD_HOSTS = ["discord.com", "discordapp.com", "ptb.discord.com", "canary.discord.com"];
  function isDiscordUrl(url) {
    url = String(url || "").trim();
    try {
      const u = new URL(url.includes("://") ? url : "https://" + url);
      return DISCORD_HOSTS.includes(u.hostname) && u.pathname.startsWith("/api/webhooks/");
    } catch (e) { return false; }
  }
  // Discord refuses these sender names; the server would fall back to Dropper
  const badSenderName = (name) => /discord|clyde/i.test(name || "") || ["everyone", "here"].includes(lower(String(name || "").trim()));

  function senderCells(d) {
    const name = d.webhook_username || "";
    const bad = badSenderName(name);
    const pic = d.webhook_avatar || "";
    const shown = /^(data:image\/|https?:\/\/)/.test(pic) ? pic : "static/img/avatar.png";
    return `<label class="cell stack" data-key="i-webhook_username"><b>${esc(t("set.notify.name"))}</b>
        <input class="input" data-bind="webhook_username" value="${attr(name)}" placeholder="Dropper" maxlength="80" autocomplete="off" spellcheck="false">
        <small class="${bad ? "bad" : ""}">${esc(t(bad ? "set.notify.name.bad" : "set.notify.name.hint"))}</small></label>
      <div class="cell pic-cell" data-key="avatar">
        <img class="avatar pic" src="${attr(shown)}" alt="">
        <span class="cell-text"><b>${esc(t("set.notify.avatar"))}</b><small>${esc(t("set.notify.avatar.hint"))}</small>
          <span class="pic-actions">
            <label class="btn sm">${esc(t("set.notify.avatar.pick"))}<input type="file" accept="image/png,image/jpeg,image/gif,image/webp" data-avatar-file hidden></label>
            ${pic ? `<button type="button" class="btn sm" data-action="avatarReset">${esc(t("set.notify.avatar.reset"))}</button>` : ""}
          </span></span>
      </div>`;
  }

  // a picked image becomes a 256x256 square, the middle part like Discord crops it, small enough for the settings
  async function pickAvatar(file) {
    if (!file) return;
    try {
      const src = URL.createObjectURL(file);
      const img = await new Promise((ok, bad) => { const i = new Image(); i.onload = () => ok(i); i.onerror = bad; i.src = src; });
      URL.revokeObjectURL(src);
      const side = Math.min(img.naturalWidth, img.naturalHeight);
      if (!side) throw new Error("empty image");
      const draw = (fill) => {
        const canvas = document.createElement("canvas");
        canvas.width = canvas.height = 256;
        const ctx = canvas.getContext("2d");
        if (fill) { ctx.fillStyle = fill; ctx.fillRect(0, 0, 256, 256); }
        ctx.imageSmoothingQuality = "high";
        ctx.drawImage(img, (img.naturalWidth - side) / 2, (img.naturalHeight - side) / 2, side, side, 0, 0, 256, 256);
        return canvas;
      };
      let data = draw().toDataURL("image/png");
      if (data.length > 300000) data = draw("#000").toDataURL("image/jpeg", 0.9);  // a photo: no transparency to keep
      S.draft.webhook_avatar = data;
    } catch (e) {
      toast({ kind: "bad", title: t("set.notify.avatar.bad") });
    }
    render();
  }

  function vSettings() {
    if (!S.draft) return skeleton();
    const d = S.draft;
    const user = (S.state || {}).user;
    const hasUrl = !!String(d.webhook_url || "").trim();
    const modes = ["ending_soonest", "low_availability", "priority_only"];

    const account = user
      ? `<div class="cell"><span class="avatar">${esc(user.login.slice(0, 1))}</span><span class="cell-text"><b>${esc(user.login)}</b><small>${esc(t("set.account.connected"))}</small></span><button type="button" class="btn sm danger" data-action="logout">${esc(t("action.logout"))}</button></div>`
      : `<div class="cell"><span class="avatar">${icon("user")}</span><span class="cell-text"><b>${esc(t("account.none"))}</b><small>${esc(t("set.account.none"))}</small></span></div>`;

    const left = [
      group(t("set.account"), account, t("set.account.hint")),
      group(t("set.farm"), `
        <div class="cell stack" data-key="game_mode"><b>${esc(t("set.game_mode"))}</b>${segmented(["all", "whitelist"].map((m) => ({ action: "setValue", set: "game_mode", arg: m, label: t("set.game_mode." + m), on: d.game_mode === m })), t("set.game_mode"))}</div>
        ${d.game_mode === "whitelist" ? tagField("games_whitelist", t("set.whitelist"), t("set.whitelist.hint"), GAME_SUGGEST) : ""}
        ${tagField("games_exclude", t("set.exclude"), t("set.exclude.hint"), GAME_SUGGEST)}
        ${toggleCell("mine_badges_emotes", d.mine_badges_emotes, t("set.badges"), t("set.badges.hint"))}
        ${toggleCell("require_linked_account", d.require_linked_account, t("set.linked"), t("set.linked.hint"))}`),
      group(t("set.priority"), `<div class="cell stack" data-key="prio">${prioList(d.games_priority)}${gameAdder()}</div>`, t("set.priority.hint")),
      group(t("set.mode"), modes.map((m) => choiceCell("priority_mode", m, d.priority_mode === m, t("set.mode." + m), t("set.mode." + m + ".hint"))).join("")),
      group(t("set.channels"), `
        ${tagField("channels_preferred", t("set.preferred"), t("set.preferred.hint"), CHANNEL_SUGGEST)}
        ${tagField("channels_blacklist", t("set.blacklist"), t("set.blacklist.hint"), CHANNEL_SUGGEST)}
        ${tagField("stream_languages", t("set.languages"), t("set.languages.hint"), LANG_SUGGEST)}
        ${rangeCell("channels_per_game", d.channels_per_game, 1, 100, t("set.per_game"), t("set.per_game.hint"), "")}
        ${toggleCell("verify_channel_drops", d.verify_channel_drops, t("set.verify"), t("set.verify.hint"))}`),
    ];

    const right = [
      group(t("set.claiming"), `
        ${toggleCell("auto_claim", d.auto_claim, t("set.auto_claim"), t("set.auto_claim.hint"))}
        ${toggleCell("claim_channel_points", d.claim_channel_points, t("set.points"), t("set.points.hint"))}
        ${rangeCell("claim_sweep_interval_minutes", d.claim_sweep_interval_minutes, 1, 60, t("set.sweep"), t("set.sweep.hint"), "min")}`),
      group(t("set.notify"), `
        ${inputCell("webhook_url", t("set.webhook"), t("set.webhook.hint"), "https://discord.com/api/webhooks/…", 'inputmode="url"')}
        ${isDiscordUrl(d.webhook_url) ? senderCells(d) : ""}
        ${NOTIFY.map((k) => toggleCell("notify_" + k, d["notify_" + k], t("set.notify." + k), t("set.notify." + k + ".hint"), !hasUrl)).join("")}
        <button type="button" class="cell action" data-key="notify-test" data-action="notifyTest" ${S.notifyBusy ? "disabled" : ""}>${icon(S.notifyBusy ? "refresh" : "send", S.notifyBusy ? "spinning" : "")}<span>${esc(t("set.notify.test"))}</span></button>`,
        hasUrl ? "" : t("set.notify.nourl")),
      group(t("set.schedule"), rangeCell("refresh_interval_minutes", d.refresh_interval_minutes, 5, 240, t("set.refresh"), t("set.refresh.hint"), "min")),
      group(t("set.display"), `<div class="cell"><span class="cell-text"><b>${esc(t("set.language"))}</b></span><select class="select" data-action="langSelect" aria-label="${attr(t("set.language"))}">${I18N.LANGS.map((l) => `<option value="${l.code}" ${l.code === I18N.lang ? "selected" : ""}>${esc(l.name)}</option>`).join("")}</select></div>`),
      group(t("set.advanced"), `
        ${inputCell("campaign_catalog_url", t("set.catalog"), t("set.catalog.hint"), "https://…")}
        ${inputCell("proxy", t("set.proxy"), t("set.proxy.hint"), "http://user:pass@host:port")}
        <label class="cell stack" data-key="gql"><b>${esc(t("set.gql"))}</b><textarea class="input" data-bind-json="gql_hash_overrides" rows="4" spellcheck="false" placeholder='{"Inventory": "…sha256…"}'>${esc(S.gqlText ?? "")}</textarea><small>${esc(t("set.gql.hint"))}</small></label>`),
    ];

    return `
      <div class="settings">
        <div class="settings-col">${left.join("")}</div>
        <div class="settings-col">${right.join("")}</div>
      </div>
      <div class="savebar ${settingsDirty() ? "show" : ""}" role="region" aria-label="${attr(t("set.unsaved"))}">
        <span class="savebar-text"><span class="dot"></span>${esc(t("set.unsaved"))}</span>
        <button type="button" class="btn sm" data-action="discard">${esc(t("action.discard"))}</button>
        <button type="button" class="btn sm primary" data-action="save">${esc(t("action.save"))}</button>
      </div>`;
  }

  function group(title, body, foot) {
    return `<section class="group-wrap"><h3 class="group-title">${esc(title)}</h3><div class="group">${body}</div>${foot ? `<p class="group-foot">${esc(foot)}</p>` : ""}</section>`;
  }
  function toggleCell(key, on, label, hint, dim) {
    return `<label class="cell ${dim ? "dim" : ""}" data-key="c-${key}">
      <span class="cell-text"><b>${esc(label)}</b>${hint ? `<small>${esc(hint)}</small>` : ""}</span>
      <span class="switch"><input type="checkbox" data-bind="${key}" ${on ? "checked" : ""}><span></span></span>
    </label>`;
  }
  function choiceCell(key, value, on, label, hint) {
    return `<button type="button" class="cell choice" data-key="ch-${key}-${value}" data-action="setValue" data-set="${key}" data-arg="${value}" aria-pressed="${on}">
      <span class="cell-text"><b>${esc(label)}</b>${hint ? `<small>${esc(hint)}</small>` : ""}</span>${icon("check", "chk")}
    </button>`;
  }
  function inputCell(key, label, hint, placeholder, extra) {
    return `<label class="cell stack" data-key="i-${key}"><b>${esc(label)}</b>
      <input class="input" data-bind="${key}" value="${attr(S.draft[key] || "")}" placeholder="${attr(placeholder)}" autocomplete="off" spellcheck="false" ${extra || ""}>
      ${hint ? `<small>${esc(hint)}</small>` : ""}</label>`;
  }
  function rangeCell(key, value, min, max, label, hint, unitName) {
    const p = ((value - min) / (max - min)) * 100;
    const out = unitName === "min" ? I18N.dur(value) : I18N.num(value);
    return `<div class="cell stack" data-key="r-${key}">
      <div class="cell-row"><b>${esc(label)}</b><output>${esc(out)}</output></div>
      <input class="range" type="range" min="${min}" max="${max}" step="1" value="${value}" data-bind="${key}" data-num style="--p:${p}%" aria-label="${attr(label)}">
      ${hint ? `<small>${esc(hint)}</small>` : ""}
    </div>`;
  }
  function tagField(key, label, hint, suggest) {
    const items = S.draft[key] || [];
    return `<div class="cell stack" data-key="tf-${key}"><b>${esc(label)}</b>
      <div class="taginput" data-tags="${key}">
        ${items.map((v) => `<span class="tchip" data-key="${attr(v)}">${esc(v)}<button type="button" data-action="tagRemove" data-key2="${key}" data-arg="${attr(v)}" aria-label="${attr(t("action.remove"))}">${icon("x")}</button></span>`).join("")}
        <input data-tag-input="${key}" placeholder="${attr(t("set.tag.add"))}" autocomplete="off" value="${attr(S.tagInput[key] || "")}" aria-label="${attr(label)}">
        ${suggestBox(key, suggest)}
      </div>
      ${hint ? `<small>${esc(hint)}</small>` : ""}</div>`;
  }
  function tagAdder(key, suggest, placeholder) {
    return `<div class="taginput" data-tags="${key}" data-key="ta-${key}">
      <input data-tag-input="${key}" placeholder="${attr(placeholder)}" autocomplete="off" value="${attr(S.tagInput[key] || "")}" aria-label="${attr(placeholder)}">
      ${suggestBox(key, suggest)}
    </div>`;
  }
  function suggestBox(key, suggest) {
    const text = lower(S.tagInput[key] || "");
    if (S.tagFocus !== key) return "";
    const have = new Set((S.draft[key] || []).map(lower));
    const options = suggest().filter((s) => !have.has(lower(s)) && (!text || lower(s).includes(text))).slice(0, 8);
    if (!options.length) return "";
    return `<div class="suggest">${options.map((o) => `<button type="button" data-action="tagAdd" data-key2="${key}" data-arg="${attr(o)}">${esc(o)}</button>`).join("")}</div>`;
  }
  function prioList(items) {
    if (!items.length) return `<small>${esc(t("set.priority.empty"))}</small>`;
    lookupGames(items);
    return `<div class="prio-list">${items.map((g, i) => {
      const state = watchState(g);
      return `
      <div class="prio-item" data-key="${attr(g)}"><span class="ord">${i + 1}</span>${gameArt(g)}
        <span class="prio-text"><b class="ellipsis">${esc(g)}</b><small class="wstate" style="--tone:${toneVar(state.tone)}"><i></i><span class="ellipsis">${esc(state.text)}</span></small></span>
        <button type="button" class="icon-btn xs" data-action="prioMove" data-arg="${i}" data-dir="-1" ${i === 0 ? "disabled" : ""} aria-label="${attr(t("action.up"))}">${icon("up")}</button>
        <button type="button" class="icon-btn xs" data-action="prioMove" data-arg="${i}" data-dir="1" ${i === items.length - 1 ? "disabled" : ""} aria-label="${attr(t("action.down"))}">${icon("down")}</button>
        <button type="button" class="icon-btn xs" data-action="tagRemove" data-key2="games_priority" data-arg="${attr(g)}" aria-label="${attr(t("action.remove"))}">${icon("x")}</button>
      </div>`;
    }).join("")}</div>`;
  }

  // ---------------------------------------------------------------- games on the priority list
  /** Box art for a game name: from its campaigns, else from the Twitch lookup. */
  function gameBoxArt(name) {
    const k = gkey(name);
    const c = (S.campaigns || []).find((x) => gkey(x.game.name) === k && x.game.box_art);
    if (c) return c.game.box_art;
    const info = S.games[k];
    return (info && info.game && info.game.box_art) || "";
  }
  // the first letter shows through until the box art has loaded, or when there is none
  const gameArt = (name, art) => `<span class="gart" data-l="${attr(Array.from(String(name).trim())[0] || "?")}">${imgTag(boxArt(art === undefined ? gameBoxArt(name) : art, 52, 70), "", "")}</span>`;

  /** What a game on the priority list is up to: farmed, queued, skipped, coming, or waiting for a campaign. */
  function watchState(name) {
    const k = gkey(name);
    const camps = (S.campaigns || []).filter((c) => gkey(c.game.name) === k && c.status !== "expired");
    if (camps.some((c) => c.mining)) return { tone: "green", text: t("camp.mining") };
    const queued = camps.filter((c) => c.queue_position).sort((a, b) => a.queue_position - b.queue_position)[0];
    if (queued) return { tone: "accent", text: t("camp.queue", { n: queued.queue_position }) };
    const active = camps.find((c) => c.status === "active");
    if (active) {
      const reason = active.skip_reason || "not_wanted";
      return { tone: ["not_linked", "unavailable", "badges_off"].includes(reason) ? "orange" : "gray", text: t("skip." + reason) };
    }
    const next = camps.filter((c) => c.status === "upcoming").sort((a, b) => String(a.starts_at).localeCompare(String(b.starts_at)))[0];
    if (next) return { tone: "teal", text: t("set.watch.starts", { date: I18N.date(next.starts_at, "day") }) };
    const info = S.games[k];
    if (info && info.status === "missing") return { tone: "red", text: t("game.missing") };
    return { tone: "gray", text: t("set.watch.none") };
  }

  /** Asks the server once about names without a campaign: spelling check and box art. */
  const lookingUp = new Set();
  function lookupGames(names) {
    const have = new Set((S.campaigns || []).map((c) => gkey(c.game.name)));
    const todo = uniq(names).filter((n) => !have.has(gkey(n)) && !S.games[gkey(n)] && !lookingUp.has(gkey(n)));
    if (!S.campaigns || !todo.length) return;
    todo.forEach((n) => lookingUp.add(gkey(n)));
    post("/api/games/lookup", { names: todo }).then((r) => {
      r.games.forEach((g) => { S.games[gkey(g.query)] = g; if (g.game) S.games[gkey(g.game.name)] = g; });
      render();
    }).catch(() => { /* shown without box art; tried again after a reload */ }).finally(() => todo.forEach((n) => lookingUp.delete(gkey(n))));
  }

  /** Searches known games and Twitch for the text in the game field, a moment after typing stops. */
  let searchTimer = null;
  function searchGames(text) {
    clearTimeout(searchTimer);
    const q = text.trim();
    if (!q) { S.gameSearch = null; return; }
    searchTimer = setTimeout(async () => {
      try {
        const r = await api(`/api/games/search?q=${encodeURIComponent(q)}`);
        if (r.lookup) {
          S.games[gkey(r.lookup.query)] = r.lookup;
          if (r.lookup.game) S.games[gkey(r.lookup.game.name)] = r.lookup;
        }
        if ((S.tagInput.games_priority || "").trim() === q) { S.gameSearch = { q, results: r.results, lookup: r.lookup }; render(); }
      } catch (e) { /* the typed name can still be added */ }
    }, 280);
  }

  /** The best game for the typed text: Twitch's spelling when the lookup found it, else what was typed. */
  function pickGame(text) {
    const q = String(text || "").trim();
    const info = S.games[gkey(q)];
    if (info && info.game && gkey(info.game.name) === gkey(q)) return info.game.name;
    const camp = (S.campaigns || []).find((c) => gkey(c.game.name) === gkey(q));
    return camp ? camp.game.name : q;
  }

  function gameAdder() {
    const key = "games_priority";
    return `<div class="taginput game-add" data-tags="${key}" data-key="ta-${key}">
      ${icon("search", "lead")}
      <input data-tag-input="${key}" placeholder="${attr(t("set.priority.add"))}" autocomplete="off" spellcheck="false" value="${attr(S.tagInput[key] || "")}" aria-label="${attr(t("set.priority.add"))}">
      ${gameSuggest()}
    </div>`;
  }

  function gameSuggest() {
    const key = "games_priority";
    if (S.tagFocus !== key) return "";
    const text = String(S.tagInput[key] || "").trim();
    const q = gkey(text);
    const have = new Set((S.draft[key] || []).map(gkey));
    const camps = S.campaigns || [];
    const state = (name) => {
      const k = gkey(name);
      const mine = camps.filter((c) => gkey(c.game.name) === k);
      return mine.some((c) => c.status === "active") ? "active" : mine.some((c) => c.status === "upcoming") ? "upcoming" : null;
    };
    const search = S.gameSearch && S.gameSearch.q === text ? S.gameSearch : null;
    let items = uniq(camps.map((c) => c.game.name)).filter((n) => !q || gkey(n).includes(q))
      .map((n) => ({ name: n, box_art: gameBoxArt(n), campaign: state(n) }));
    if (search) items = search.results.concat(items);
    const lookup = search ? search.lookup : S.games[q];
    if (lookup && lookup.game) items.unshift(lookup.game);
    const seen = new Set();
    items = items.filter((g) => {
      const k = gkey(g.name);
      if (seen.has(k) || have.has(k)) return false;
      seen.add(k);
      return true;
    }).slice(0, 8);

    const rows = items.map((g) => {
      const note = g.campaign ? t("game.campaign." + g.campaign) : lookup && lookup.game && gkey(lookup.game.name) === gkey(g.name) ? t("game.twitch") : "";
      return `<button type="button" class="sg" data-action="tagAdd" data-key2="${key}" data-arg="${attr(g.name)}">${gameArt(g.name, g.box_art || gameBoxArt(g.name))}
        <span class="sg-text"><b class="ellipsis">${esc(g.name)}</b>${note ? `<small>${esc(note)}</small>` : ""}</span></button>`;
    });
    if (text && !seen.has(q) && !have.has(q)) {
      // still typing or a typo: say it neutrally here, the list row warns once the game is added
      const note = !search ? t("game.searching") : lookup && lookup.status === "missing" ? t("game.nomatch") : "";
      rows.push(`<button type="button" class="sg add" data-action="tagAdd" data-key2="${key}" data-arg="${attr(text)}"><span class="gart plus">${icon("plus")}</span>
        <span class="sg-text"><b class="ellipsis">${esc(t("game.add", { name: text }))}</b>${note ? `<small>${esc(note)}</small>` : ""}</span></button>`);
    }
    return rows.length ? `<div class="suggest games">${rows.join("")}</div>` : "";
  }
  function settingsDirty() {
    if (!S.draft || !S.settings) return false;
    if (S.gqlText !== null && S.gqlText !== gqlTextOf(S.settings)) return true;
    const a = Object.assign({}, S.draft, { gql_hash_overrides: null });
    const b = Object.assign({}, S.settings, { gql_hash_overrides: null });
    return !same(a, b);
  }
  const gqlTextOf = (s) => (s && s.gql_hash_overrides && Object.keys(s.gql_hash_overrides).length ? JSON.stringify(s.gql_hash_overrides, null, 2) : "");

  // ---------------------------------------------------------------- log
  function vLog() {
    const ui = S.ui.log;
    const q = lower(ui.q);
    const levels = { all: () => true, info: (l) => l.level === "INFO", warning: (l) => l.level === "WARNING", error: (l) => l.level === "ERROR" || l.level === "CRITICAL" };
    const lines = S.logs.filter(levels[ui.level] || levels.all).filter((l) => !q || lower(l.msg).includes(q));
    return `
      <div class="toolbar">
        ${segmented(Object.keys(levels).map((lv) => ({ action: "logLevel", arg: lv, label: t("log.level." + lv), on: ui.level === lv })))}
        ${searchBox("log.q", ui.q, t("log.search"))}
        ${inlineSwitch("log.follow", ui.follow, t("log.follow"))}
        <button class="btn sm" data-action="copyLog">${icon("copy")}${esc(t("action.copy"))}</button>
      </div>
      <section class="card log">
        <div class="log-head">${esc(t("log.lines", { n: lines.length }))}</div>
        <div class="log-body" id="log-body">
          ${lines.length ? lines.map((l) => `<div class="lline lv-${esc(l.level)}" data-key="l${l.id}"><time>${esc(I18N.date(l.ts, "time"))}</time><span class="lv">${esc(l.level)}</span><span class="msg">${esc(l.msg)}</span></div>`).join("") : empty("terminal", t("log.empty"))}
        </div>
      </section>`;
  }

  // ================================================================ login overlay
  function renderLogin() {
    const root = $("#login-root");
    const st = S.state;
    const needs = st && (st.state === "login" || st.login_prompt);
    if (!needs) {
      if (S.wasLogin && root.firstElementChild) {
        const el = root.firstElementChild;
        if (!el.classList.contains("leaving")) {
          el.classList.add("leaving");
          setTimeout(() => { root.innerHTML = ""; }, 360);
          if (st && st.user) toast({ kind: "party", title: t("login.done", { user: st.user.login }), text: t("login.done.text"), icon: "sparkles" });
        }
      }
      S.wasLogin = false;
      return;
    }
    S.wasLogin = true;
    const lp = st.login_prompt;
    const code = lp ? String(lp.code) : "";
    const chars = code ? code.split("") : Array.from({ length: 8 }, () => "");
    const half = Math.ceil(chars.length / 2);
    // two halves that wrap as a whole, never one stray letter on its own line
    const groups = chars.length > 6 ? [chars.slice(0, half), chars.slice(half)] : [chars];
    const tiles = groups.map((g, gi) => `<div class="grp">${g.map((ch, j) => `<span style="--d:${gi * half + j}">${esc(ch)}</span>`).join("")}</div>`).join("");
    const total = 1800;
    const left = lp ? lp.expires_in : 0;
    const R = 6, C = 2 * Math.PI * R;
    const meta = st.error && !lp
      ? `<div class="errbox"><b>${esc(t("login.error"))}</b><code>${esc(st.error)}</code><div class="row"><button class="btn sm" data-action="refresh">${icon("refresh")}${esc(t("action.retry"))}</button></div></div>`
      : lp ? `<span class="waiting"><span class="dots"><i></i><i></i><i></i></span>${esc(t("login.waiting"))}</span>
          <span class="row"><svg class="mini-ring" viewBox="0 0 16 16" aria-hidden="true"><circle class="t" cx="8" cy="8" r="${R}"/><circle class="b" cx="8" cy="8" r="${R}" stroke-dasharray="${C.toFixed(2)}" stroke-dashoffset="${(C * (1 - Math.min(1, left / total))).toFixed(2)}"/></svg>${esc(t("login.expires", { time: I18N.dur(Math.ceil(left / 60)) }))}</span>`
      : `<span class="waiting"><span class="dots"><i></i><i></i><i></i></span>${esc(t("login.requesting"))}</span>`;
    morph(root, `
      <div class="login" role="dialog" aria-modal="true" aria-labelledby="login-title">
        <div class="login-top">${langButton("login")}</div>
        <div class="login-card">
          <svg class="login-logo" aria-hidden="true"><use href="#logo"/></svg>
          <h2 id="login-title">${esc(t("login.title"))}</h2>
          <p class="lead">${esc(t("login.text"))}</p>
          <div class="group login-steps">
            <div class="cell stack">
              <div class="step-head"><span class="n">1</span><b>${esc(t("login.step1"))}</b></div>
              <a class="btn primary lg" href="${attr((lp && lp.url) || "https://www.twitch.tv/activate")}" target="_blank" rel="noopener">twitch.tv/activate ${icon("external")}</a>
            </div>
            <div class="cell stack">
              <div class="step-head"><span class="n">2</span><b>${esc(t("login.step2"))}</b></div>
              <div class="code ${code ? "" : "skeleton"}" data-key="code-${attr(code)}">${tiles}</div>
              ${code ? `<button class="btn sm" data-action="copyCode" data-arg="${attr(code)}">${icon("copy")}${esc(t("action.copy"))}</button>` : ""}
            </div>
          </div>
          <div class="login-meta">${meta}</div>
          <div class="login-note">${icon("shield")}<span>${esc(t("login.note"))}</span></div>
        </div>
      </div>`);
  }

  // ================================================================ overlays: alert, palette, sheet
  function renderOverlays() {
    const root = $("#overlay-root");
    let html = "";
    if (S.modal) {
      const m = S.modal;
      html += `<div class="modal-bg" data-key="modal" data-action="modalClose"><div class="alert" role="alertdialog" aria-modal="true" data-stop>
        <div class="alert-body"><h3>${esc(m.title)}</h3><p>${esc(m.text)}</p></div>
        <div class="alert-actions"><button data-action="modalClose">${esc(t("action.cancel"))}</button><button class="${m.danger ? "danger" : "strong"}" data-action="modalOk">${esc(m.ok)}</button></div>
      </div></div>`;
    }
    if (S.palette) {
      const items = paletteItems();
      const idx = Math.min(S.palette.idx, Math.max(0, items.length - 1));
      html += `<div class="modal-bg palette-bg" data-key="palette" data-action="paletteClose"><div class="palette" data-stop>
        <div class="pinput">${icon("search")}<input id="palette-input" data-palette value="${attr(S.palette.q)}" placeholder="${attr(t("palette.placeholder"))}" autocomplete="off"><kbd>Esc</kbd></div>
        <div class="plist">${items.length ? items.map((it, i) => `<button class="pitem ${i === idx ? "hl" : ""}" data-key="p${i}-${attr(it.id)}" data-action="paletteRun" data-arg="${i}">${icon(it.icon)}<span>${esc(it.label)}</span>${it.hint ? `<small>${esc(it.hint)}</small>` : ""}</button>`).join("") : `<div class="empty">${esc(t("palette.empty"))}</div>`}</div>
      </div></div>`;
    }
    if (S.sheet) {
      html += `<div class="modal-bg sheet-bg" data-key="sheetbg" data-action="sheetClose"></div>
        <div class="sheet" data-key="sheet"><div class="group">${NAV.filter((n) => !MOBILE_NAV.includes(n.id)).map((n) => `<a href="#${n.id}" ${S.view === n.id ? 'aria-current="page"' : ""}>${icon(n.icon)}${esc(t("nav." + n.id))}</a>`).join("")}
        <button data-action="palette">${icon("search")}${esc(t("palette.hint"))}</button></div></div>`;
    }
    morph(root, html);
  }

  function paletteItems() {
    const st = S.state || {};
    const items = [
      ...NAV.map((n) => ({ id: "go-" + n.id, icon: n.icon, label: t("palette.go", { page: t("nav." + n.id) }), run: () => go(n.id) })),
      { id: "refresh", icon: "refresh", label: t("action.refresh"), run: () => ACT.refresh() },
      { id: "pause", icon: st.paused ? "play" : "pause", label: t(st.paused ? "action.resume" : "action.pause"), run: () => ACT.pause() },
      { id: "failed", icon: "alert", label: t("palette.failed"), run: () => go("drops", "failed") },
      ...(st.watching ? [{ id: "open", icon: "external", label: t("palette.open", { channel: st.watching.name }), run: () => window.open(st.watching.url, "_blank", "noopener") }] : []),
      ...I18N.LANGS.map((l) => ({ id: "lang-" + l.code, icon: "globe", label: `${t("action.language")}: ${l.name}`, hint: l.code === I18N.lang ? "✓" : l.code.toUpperCase(), run: () => changeLang(l.code) })),
    ];
    const q = lower(S.palette.q).trim();
    if (!q) return items;
    return items.filter((it) => lower(it.label).includes(q) || lower(it.id).includes(q));
  }

  // ================================================================ toasts
  function toast(opts) {
    const box = $("#toasts");
    const el = document.createElement("div");
    el.className = `toast ${opts.kind || ""}`;
    const ic = opts.image ? `<img src="${attr(opts.image)}" alt="">` : icon(opts.icon || (opts.kind === "bad" ? "alert" : opts.kind === "good" ? "check" : "info"));
    // a few sparks fly off the icon when something worth celebrating happened
    const burst = opts.kind === "party" && !FX.reduced() ? `<span class="burst">${Array.from({ length: 8 }, (_, i) => `<i style="--a:${i * 45 + 22}deg"></i>`).join("")}</span>` : "";
    el.innerHTML = `<span class="ticon">${ic}${burst}</span><div class="grow"><b>${esc(opts.title)}</b>${opts.text ? `<p>${esc(opts.text)}</p>` : ""}</div>`;
    const close = () => { el.classList.add("out"); setTimeout(() => el.remove(), 260); };
    el.addEventListener("click", close);
    box.appendChild(el);
    while (box.children.length > 4) box.firstElementChild.remove();
    setTimeout(close, opts.ttl || 4500);
  }
  const fail = (e) => toast({ kind: "bad", title: t("toast.error"), text: e && e.message ? e.message : String(e) });

  // ================================================================ actions
  function go(view, arg) {
    location.hash = arg ? `${view}/${arg}` : view;
  }

  function toggleIn(list, value, same = lower) {
    const l = same(value);
    const i = list.findIndex((v) => same(v) === l);
    if (i >= 0) list.splice(i, 1);
    else list.push(value);
    return list;
  }

  /** Takes new settings from the server; unsaved edits in the settings draft survive. */
  function setSettings(next) {
    const old = S.settings;
    S.settings = next;
    if (!S.draft || !old) { S.draft = clone(next); S.gqlText = gqlTextOf(next); return; }
    for (const k in next) if (same(S.draft[k], old[k])) S.draft[k] = clone(next[k]);
    if (S.gqlText === null || S.gqlText === gqlTextOf(old)) S.gqlText = gqlTextOf(next);
  }

  async function saveSettings(patchData, message) {
    try {
      setSettings(await put("/api/settings", patchData));
      raw.settings = null;
      if (message) toast({ kind: "good", title: message });
      force("campaigns", "channels", "drops", "state");
    } catch (e) { fail(e); }
    render();
  }

  async function changeLang(code) {
    S.menu = null;
    await I18N.setLang(code);
    if (S.settings && S.settings.ui_language !== code) {
      try { setSettings(await put("/api/settings", { ui_language: code })); } catch (e) { /* keep the local choice */ }
    }
    renderNow(false);
    toast({ kind: "good", icon: "globe", title: t("toast.language") });
  }

  const ACT = {
    go: (arg) => go(arg),
    async refresh() {
      try { await post("/api/refresh"); toast({ title: t("toast.refresh"), icon: "refresh" }); force("state"); } catch (e) { fail(e); }
    },
    async pause() {
      try {
        const r = await post("/api/pause");
        toast({ title: t(r.paused ? "toast.paused" : "toast.resumed"), icon: r.paused ? "pause" : "play" });
        force("state");
      } catch (e) { fail(e); }
    },
    menu(arg) { S.menu = S.menu === arg ? null : arg; render(); },
    lang(arg) { changeLang(arg); },
    sheet() { S.sheet = !S.sheet; render(); },
    sheetClose() { S.sheet = false; render(); },
    async auto() {
      try { await post("/api/switch", { login: null }); force("state"); } catch (e) { fail(e); }
    },
    async watch(login) {
      try { await post("/api/switch", { login }); toast({ kind: "good", icon: "play", title: t("toast.watching", { channel: login }) }); force("state", "channels"); } catch (e) { fail(e); }
    },
    prefer(login) { if (S.settings) saveSettings({ channels_preferred: toggleIn([...S.settings.channels_preferred], login) }); },
    block(login) { if (S.settings) saveSettings({ channels_blacklist: toggleIn([...S.settings.channels_blacklist], login) }); },
    prioritize(game) {
      if (!S.settings) return;
      // a newly prioritized game goes to the top: that is what someone clicking it on a card wants farmed next
      const list = [...S.settings.games_priority];
      const i = list.findIndex((v) => gkey(v) === gkey(game));
      if (i >= 0) list.splice(i, 1);
      else list.unshift(game);
      saveSettings({ games_priority: list }, t("toast.priority"));
    },
    exclude(game) { if (S.settings) saveSettings({ games_exclude: toggleIn([...S.settings.games_exclude], game, gkey) }, t("toast.exclude")); },
    async claim(id, el) {
      if (el) el.disabled = true;
      S.quietUntil = now() + 8000; // the state poll should not celebrate this claim a second time
      try {
        const r = await post(`/api/claim/${encodeURIComponent(id)}`);
        if (r.ok) {
          const d = S.drops && S.drops.drops.find((x) => x.id === id);
          celebrate(d);
        } else {
          toast({ kind: "bad", title: t("toast.claim_failed"), text: t("toast.claim_failed.text") });
        }
        force("drops", "campaigns", "state");
      } catch (e) { fail(e); }
      if (el) el.disabled = false;
    },
    async toggleCampaign(id) {
      try {
        const r = await post(`/api/campaigns/${encodeURIComponent(id)}/toggle`);
        toast({ title: t(r.excluded ? "toast.camp_off" : "toast.camp_on"), icon: "flag" });
        setSettings(await api("/api/settings"));
        force("campaigns", "state");
      } catch (e) { fail(e); }
    },
    dropFilter(arg) { S.ui.drops.filter = arg; history.replaceState(null, "", arg === "all" ? "#drops" : `#drops/${arg}`); render(); },
    campFilter(arg) { S.ui.campaigns.filter = arg; render(); },
    campType(arg) { toggleIn(S.ui.campaigns.types, arg); render(); },
    campOpen(arg) { toggleIn(S.ui.campaigns.open, arg); render(); },
    historyAll() { S.ui.historyAll = !S.ui.historyAll; render(); },
    statsDays(arg) { S.ui.stats.days = Number(arg); S.stats = null; S.hover = null; force("stats"); render(); },
    logLevel(arg) { S.ui.log.level = arg; render(); },
    async copyLog() {
      const text = S.logs.map((l) => `${l.ts} ${l.level} ${l.msg}`).join("\n");
      try { await navigator.clipboard.writeText(text); toast({ kind: "good", title: t("action.copied") }); } catch (e) { fail(e); }
    },
    async copyCode(code) {
      try { await navigator.clipboard.writeText(code); toast({ kind: "good", title: t("action.copied"), icon: "copy" }); } catch (e) { fail(e); }
    },
    setValue(arg, el) { S.draft[el.dataset.set] = arg; render(); },
    tagRemove(arg, el) {
      const key = el.dataset.key2;
      S.draft[key] = (S.draft[key] || []).filter((v) => v !== arg);
      render();
    },
    tagAdd(arg, el) { addTag(el.dataset.key2, arg); },
    prioMove(arg, el) {
      const i = Number(arg), dir = Number(el.dataset.dir);
      const list = S.draft.games_priority;
      const j = i + dir;
      if (j < 0 || j >= list.length) return;
      const game = list[i];
      FX.flip(".prio-item", () => {
        [list[i], list[j]] = [list[j], list[i]];
        renderNow(false);
      });
      // moving the row takes the focus with it out of the document; give it back for keyboard users
      const row = Array.from(document.querySelectorAll(".prio-item")).find((r) => r.dataset.key === game);
      const again = row && row.querySelector(`[data-dir="${dir}"]:not([disabled])`);
      if (again) again.focus();
    },
    discard() { S.draft = clone(S.settings); S.gqlText = gqlTextOf(S.settings); render(); },
    async save() {
      if (isDiscordUrl(S.draft.webhook_url) && badSenderName(S.draft.webhook_username)) {
        toast({ kind: "bad", icon: "bell", title: t("set.notify.name.bad") });
        return;
      }
      // only what was edited here, so a pause or campaign toggle from elsewhere is never undone
      const data = {};
      for (const k in S.draft) {
        if (k !== "gql_hash_overrides" && !same(S.draft[k], S.settings[k])) data[k] = S.draft[k];
      }
      if (S.gqlText !== null && S.gqlText !== gqlTextOf(S.settings)) {
        try { data.gql_hash_overrides = S.gqlText.trim() ? JSON.parse(S.gqlText) : {}; }
        catch (e) { toast({ kind: "bad", title: t("toast.gql_invalid") }); return; }
      }
      try {
        S.settings = await put("/api/settings", data);
        S.draft = clone(S.settings);
        S.gqlText = gqlTextOf(S.settings);
        toast({ kind: "good", title: t("toast.saved"), text: t("toast.saved.text") });
        force("campaigns", "channels", "drops", "state");
      } catch (e) { fail(e); }
      render();
    },
    async notifyTest() {
      // URL, name and picture from the form, so they can be tried before saving
      const url = String((S.draft && S.draft.webhook_url) || "").trim();
      if (!url) { toast({ kind: "bad", icon: "bell", title: t("set.notify.nourl") }); return; }
      S.notifyBusy = true;
      render();
      try {
        const r = await post("/api/notify/test", { url, username: S.draft.webhook_username || "", avatar: S.draft.webhook_avatar || "" });
        if (r.ok) toast({ kind: "good", icon: "send", title: t("toast.notify_test"), text: t("toast.notify_test.text") });
        else toast({ kind: "bad", title: t("toast.notify_test_failed"), text: r.detail });
      } catch (e) { fail(e); }
      S.notifyBusy = false;
      render();
    },
    avatarReset() { S.draft.webhook_avatar = ""; render(); },
    logout() {
      S.modal = { title: t("modal.logout.title"), text: t("modal.logout.text"), ok: t("action.logout"), danger: true,
        run: async () => { try { await post("/api/logout"); force("state"); } catch (e) { fail(e); } } };
      render();
    },
    modalClose() { S.modal = null; render(); },
    async modalOk() { const m = S.modal; S.modal = null; render(); if (m && m.run) await m.run(); },
    palette() { S.sheet = false; S.palette = S.palette ? null : { q: "", idx: 0 }; render(); setTimeout(() => { const i = $("#palette-input"); if (i) i.focus(); }, 30); },
    paletteClose() { S.palette = null; render(); },
    paletteRun(arg) { const items = paletteItems(); const it = items[Number(arg)]; S.palette = null; render(); if (it) it.run(); },
  };

  const GAME_LISTS = ["games_priority", "games_whitelist", "games_exclude"];
  function addTag(key, value) {
    value = String(value || "").trim().replace(/^@/, "");
    if (!value) return;
    const same = GAME_LISTS.includes(key) ? gkey : lower;
    const list = S.draft[key] || (S.draft[key] = []);
    if (!list.some((v) => same(v) === same(value))) list.push(value);
    S.tagInput[key] = "";
    if (key === "games_priority") { clearTimeout(searchTimer); S.gameSearch = null; }
    // the morph leaves a focused field alone, so after Enter the typed text is cleared here
    const field = document.querySelector(`[data-tag-input="${key}"]`);
    if (field) field.value = "";
    render();
    setTimeout(() => { const inp = document.querySelector(`[data-tag-input="${key}"]`); if (inp) inp.focus(); }, 0);
  }

  function celebrate(d) {
    toast({ kind: "party", title: t("toast.claimed"), text: d ? `${d.rewards} · ${d.game.name}` : "", image: d ? rewardImage(d) : "", icon: "gift", ttl: 6000 });
  }

  // ================================================================ events
  document.addEventListener("click", (e) => {
    const target = e.target instanceof Element ? e.target : null;
    if (!target) return;
    if (S.menu && !target.closest(".menu-wrap")) { S.menu = null; render(); }
    const el = target.closest("[data-action]");
    if (!el) return;
    if (el.matches("input, select, form")) return;
    if (el.classList.contains("modal-bg") && target.closest("[data-stop]")) return;
    const fn = ACT[el.dataset.action];
    if (!fn) return;
    e.preventDefault();
    fn(el.dataset.arg, el, e);
  });

  document.addEventListener("submit", (e) => {
    const form = e.target;
    if (form.dataset.action === "manualWatch") {
      e.preventDefault();
      const login = S.ui.channels.manual.trim();
      if (login) { ACT.watch(login); S.ui.channels.manual = ""; render(); }
    }
  });

  function setModel(path, value) {
    const [group, key] = path.split(".");
    S.ui[group][key] = value;
  }

  document.addEventListener("input", (e) => {
    const el = e.target;
    if (el.dataset.model && el.type !== "checkbox") { setModel(el.dataset.model, el.value); render(); return; }
    if (el.dataset.bind && el.type !== "checkbox") {
      S.draft[el.dataset.bind] = el.hasAttribute("data-num") ? Number(el.value) : el.value;
      render();
      return;
    }
    if (el.dataset.bindJson) { S.gqlText = el.value; render(); return; }
    if (el.dataset.tagInput) {
      const key = el.dataset.tagInput;
      // a game name can hold a comma ("Warhammer 40,000"), so the game field adds one game at a time
      const split = key === "games_priority" ? /\n/ : /[,\n]/;
      if (split.test(el.value)) { el.value.split(split).forEach((v) => v.trim() && addTag(key, key === "games_priority" ? pickGame(v) : v)); el.value = ""; S.tagInput[key] = ""; return; }
      S.tagInput[key] = el.value;
      if (key === "games_priority") searchGames(el.value);
      render();
      return;
    }
    if (el.dataset.palette !== undefined) { S.palette.q = el.value; S.palette.idx = 0; render(); }
  });

  document.addEventListener("change", (e) => {
    const el = e.target;
    if (el.dataset.model && el.type === "checkbox") { setModel(el.dataset.model, el.checked); render(); return; }
    if (el.dataset.model && el.tagName === "SELECT") { setModel(el.dataset.model, el.value); render(); return; }
    if (el.dataset.bind && el.type === "checkbox") { S.draft[el.dataset.bind] = el.checked; render(); return; }
    if (el.dataset.action === "toggleCampaign") { ACT.toggleCampaign(el.dataset.arg); return; }
    if (el.dataset.action === "langSelect") { changeLang(el.value); return; }
    if (el.dataset.avatarFile !== undefined) { pickAvatar(el.files && el.files[0]); el.value = ""; }
  });

  document.addEventListener("focusin", (e) => {
    const key = e.target.dataset && e.target.dataset.tagInput;
    if (key && S.tagFocus !== key) { S.tagFocus = key; render(); }
  });
  document.addEventListener("focusout", (e) => {
    const key = e.target.dataset && e.target.dataset.tagInput;
    if (!key) return;
    setTimeout(() => {
      if (document.activeElement && document.activeElement.closest && document.activeElement.closest(`[data-tags="${key}"]`)) return;
      if (S.tagFocus === key) { S.tagFocus = null; render(); }
    }, 150);
  });

  document.addEventListener("keydown", (e) => {
    const el = e.target;
    if ((e.ctrlKey || e.metaKey) && lower(e.key) === "k") { e.preventDefault(); ACT.palette(); return; }
    if ((e.ctrlKey || e.metaKey) && lower(e.key) === "s" && S.view === "settings") { e.preventDefault(); if (settingsDirty()) ACT.save(); return; }
    if (e.key === "Escape") {
      if (S.palette) { S.palette = null; render(); return; }
      if (S.modal) { S.modal = null; render(); return; }
      if (S.menu || S.sheet) { S.menu = null; S.sheet = false; render(); return; }
    }
    if (S.palette && el.dataset && el.dataset.palette !== undefined) {
      const n = paletteItems().length;
      if (e.key === "ArrowDown") { e.preventDefault(); S.palette.idx = (S.palette.idx + 1) % Math.max(1, n); render(); }
      if (e.key === "ArrowUp") { e.preventDefault(); S.palette.idx = (S.palette.idx - 1 + n) % Math.max(1, n); render(); }
      if (e.key === "Enter") { e.preventDefault(); ACT.paletteRun(S.palette.idx); }
      return;
    }
    if (el.dataset && el.dataset.tagInput) {
      const key = el.dataset.tagInput;
      const games = key === "games_priority";
      if (e.key === "Enter") { e.preventDefault(); addTag(key, games ? pickGame(el.value) : el.value); return; }
      // the priority list has rows, not chips: backspace in its empty search field removes nothing
      if (e.key === "Backspace" && !games && !el.value && S.draft[key] && S.draft[key].length) { S.draft[key].pop(); render(); }
      return;
    }
    const typing = el.matches && el.matches("input, textarea, select, [contenteditable]");
    if (!typing && !e.ctrlKey && !e.metaKey && !e.altKey && /^[1-7]$/.test(e.key)) {
      go(NAV[Number(e.key) - 1].id);
    }
  });

  // chart bars: hover with a mouse, tap on a phone
  function chartPointer(e) {
    const target = e.target instanceof Element ? e.target : null;
    const hit = target && target.closest("[data-hover]");
    const v = hit ? Number(hit.dataset.hover) : null;
    if (v !== S.hover && (hit || !target || !target.closest("[data-chart]"))) {
      S.hover = v;
      if (S.view === "stats") render();
    }
  }
  document.addEventListener("pointermove", chartPointer, { passive: true });
  document.addEventListener("pointerdown", chartPointer, { passive: true });

  const topbar = $("#topbar");
  window.addEventListener("scroll", () => topbar.classList.toggle("scrolled", window.scrollY > 8), { passive: true });

  // ================================================================ routing
  function readHash() {
    const [view, arg] = location.hash.replace(/^#/, "").split("/");
    return { view: VIEWS[view] ? view : "overview", arg };
  }
  function onRoute() {
    const { view, arg } = readHash();
    if (view === "drops") S.ui.drops.filter = DROP_GROUPS[arg] ? arg : "all";
    const changed = view !== S.view || !S.rendered;
    S.view = view;
    S.sheet = false;
    S.menu = null;
    if (view === "settings" && S.settings && (!S.draft || !settingsDirty())) {
      S.draft = clone(S.settings);
      S.gqlText = gqlTextOf(S.settings);
    }
    try { localStorage.setItem("pr.view", view); } catch (e) { /* ignore */ }
    if (changed) {
      renderNow(true);
      window.scrollTo({ top: 0, behavior: "instant" in window ? "instant" : "auto" });
    } else {
      render();
    }
    tick();
  }
  window.addEventListener("hashchange", onRoute);

  // ================================================================ data
  const RES = {
    state: { url: () => "/api/state", every: 2500 },
    campaigns: { url: () => "/api/campaigns", every: 15000 },
    drops: { url: () => "/api/drops", every: 8000 },
    channels: { url: () => "/api/channels", every: 15000 },
    week: { url: () => "/api/stats?days=7", every: 60000 },
    stats: { url: () => `/api/stats?days=${S.ui.stats.days}`, every: 60000 },
    settings: { url: () => "/api/settings", every: 30000 },
    logs: { url: () => `/api/logs?after=${S.logAfter}`, every: 2000 },
  };
  const NEEDS = {
    overview: ["state", "campaigns", "drops", "week", "settings"],
    drops: ["state", "drops", "settings"],
    campaigns: ["state", "campaigns", "settings"],
    channels: ["state", "channels", "settings"],
    stats: ["state", "stats", "campaigns", "settings"],
    settings: ["state", "settings", "campaigns", "channels"],
    log: ["state", "logs", "settings"],
  };
  const last = {}, inflight = {};
  const raw = {};

  function force(...names) {
    names.forEach((n) => { last[n] = 0; });
    tick();
  }

  async function fetchRes(name) {
    inflight[name] = true;
    try {
      const data = await api(RES[name].url());
      last[name] = now();
      if (S.offline) { S.offline = false; render(); }
      if (name === "logs") {
        if (data.length) {
          S.logs = S.logs.concat(data).slice(-1000);
          S.logAfter = data[data.length - 1].id;
          render();
        }
        return;
      }
      const text = JSON.stringify(data);
      if (raw[name] === text) return;
      raw[name] = text;
      apply(name, data);
      render();
    } catch (e) {
      last[name] = now();
      if (name === "state" && (!e.status || e.status >= 500)) { S.offline = true; render(); }
    } finally {
      inflight[name] = false;
    }
  }

  function apply(name, data) {
    if (name === "state") {
      const claims = data.session ? data.session.claims : 0;
      if (S.seenClaims !== null && claims > S.seenClaims && now() > (S.quietUntil || 0)) {
        api("/api/drops").then((d) => {
          S.drops = d;
          raw.drops = JSON.stringify(d);
          const latest = d.drops.filter((x) => x.status === "claimed" && x.claimed_at).sort((a, b) => String(b.claimed_at).localeCompare(String(a.claimed_at)))[0];
          celebrate(latest);
          render();
        }).catch(() => celebrate(null));
      }
      S.seenClaims = claims;
      S.state = data;
      return;
    }
    if (name === "settings") {
      const first = !S.settings;
      setSettings(data);
      if (first && data.ui_language && data.ui_language !== I18N.lang) {
        I18N.setLang(data.ui_language).then(() => renderNow(false));
      }
      return;
    }
    S[name] = data;
  }

  function tick() {
    const needs = document.hidden ? ["state"] : NEEDS[S.view] || NEEDS.overview;
    const t0 = now();
    for (const name of needs) {
      const every = document.hidden ? 15000 : RES[name].every;
      if (!inflight[name] && t0 - (last[name] || 0) >= every) fetchRes(name);
    }
  }

  // ================================================================ boot
  async function boot() {
    let lang = "en";
    try { lang = localStorage.getItem("pr.lang") || "en"; } catch (e) { /* ignore */ }
    try { await I18N.setLang(lang); } catch (e) { console.error(e); }
    if (!location.hash) {
      let v = "overview";
      try { v = localStorage.getItem("pr.view") || "overview"; } catch (e) { /* ignore */ }
      history.replaceState(null, "", "#" + (VIEWS[v] ? v : "overview"));
    }
    onRoute();
    setInterval(tick, 500);
    setInterval(() => { if (S.view === "overview" || S.view === "drops") render(); }, 30000);
  }
  boot();
})();

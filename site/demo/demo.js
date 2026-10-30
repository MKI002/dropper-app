/* Dropper live demo.
   Loaded before the real web UI on the GitHub Pages site. It answers the UI's /api/* requests from an
   in-browser simulation, so the unchanged app runs without a server. Every game, channel and stream here
   is made up, and drawn as animated SVG. Watch time runs fast: one watched minute every MINUTE_MS. */
(function () {
  "use strict";

  const MINUTE_MS = 1500;
  const HOUR = 3600e3, DAY = 24 * HOUR;
  const START = Date.now();
  const iso = (ms) => new Date(ms).toISOString();
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));

  // seeded random, so the history looks the same on every visit
  let seed = 20261030;
  const rnd = () => ((seed = (seed * 1664525 + 1013904223) >>> 0) / 4294967296);
  const pick = (arr) => arr[Math.floor(Math.random() * arr.length)];
  const norm = (s) => String(s || "").normalize("NFKD").replace(/\p{M}/gu, "").toLowerCase().replace(/[^\p{L}\p{N}]+/gu, "");

  const blobUrl = (svg) => URL.createObjectURL(new Blob([svg], { type: "image/svg+xml" }));
  const xml = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  // ================================================================ games (all fictional)
  const GAMES = [
    { id: "9101", name: "Starfall Tactics", scene: "space", c: ["#0b1026", "#1d2a5c", "#7aa2ff", "#ffd36e"] },
    { id: "9102", name: "Neon Drift", scene: "road", c: ["#140a24", "#3a1460", "#ff4fd8", "#3ef2ff"] },
    { id: "9103", name: "Hollow Keep", scene: "land", c: ["#0e0d12", "#2a2433", "#8a7cff", "#ffb347"], night: true },
    { id: "9104", name: "Tidebreaker", scene: "sea", c: ["#062033", "#0c4a6e", "#38bdf8", "#f8fafc"] },
    { id: "9105", name: "Ironvale Online", scene: "land", c: ["#13261a", "#2f5d3a", "#9be39f", "#f2c14e"] },
    { id: "9106", name: "Pixel Harvest", scene: "land", c: ["#2a1a0e", "#7a4b1f", "#ffcf5c", "#ff7a59"], farm: true },
  ];
  // extra names the priority list search knows; none of them has a campaign right now
  const MORE_GAMES = [
    { id: "9107", name: "Moonlit Orchard", scene: "land", c: ["#101626", "#26385e", "#c3d0ff", "#ffe08a"], night: true },
    { id: "9108", name: "Glacier Run", scene: "road", c: ["#0a1a24", "#14506b", "#a5f3fc", "#ffffff"] },
    { id: "9109", name: "Copper Skies", scene: "space", c: ["#1f0f08", "#5b2a12", "#ffa36c", "#ffe2b8"] },
    { id: "9110", name: "Bramble & Bolt", scene: "land", c: ["#1b1410", "#4a3524", "#d9a066", "#9be39f"] },
  ];
  const ALL_GAMES = GAMES.concat(MORE_GAMES);
  const gameByName = (name) => ALL_GAMES.find((g) => norm(g.name) === norm(name));

  function boxArtSvg(g) {
    const [bg, mid, acc, hi] = g.c;
    const emblem = {
      space: `<circle cx="142" cy="150" r="62" fill="${acc}"/><ellipse cx="142" cy="150" rx="110" ry="22" fill="none" stroke="${hi}" stroke-width="7" transform="rotate(-18 142 150)"/>`,
      road: `<path d="M40 250 L142 80 L244 250Z" fill="${mid}"/><path d="M142 92 L142 250" stroke="${hi}" stroke-width="7" stroke-dasharray="18 14"/><circle cx="142" cy="88" r="16" fill="${acc}"/>`,
      sea: `<path d="M20 190 q30 -24 60 0 t60 0 t60 0 t60 0 t60 0 V260 H20Z" fill="${acc}"/><path d="M100 170 L142 70 L184 170Z" fill="${hi}"/><path d="M90 170 h104 l-14 22 h-76Z" fill="${mid}"/>`,
      land: `<path d="M0 250 L90 110 L150 190 L205 120 L285 250Z" fill="${acc}"/><path d="M90 110 L112 144 L68 144Z" fill="${hi}"/><circle cx="215" cy="70" r="24" fill="${hi}"/>`,
    }[g.scene];
    const words = g.name.split(" ");
    const lines = words.length > 1 ? [words.slice(0, Math.ceil(words.length / 2)).join(" "), words.slice(Math.ceil(words.length / 2)).join(" ")] : [g.name];
    const text = lines.map((l, i) => `<text x="22" y="${308 + i * 34}" font-family="-apple-system,Segoe UI,Roboto,sans-serif" font-size="30" font-weight="800" fill="#fff">${xml(l)}</text>`).join("");
    return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 285 380"><rect width="285" height="380" fill="${bg}"/><rect y="250" width="285" height="130" fill="${mid}"/>${emblem}${text}</svg>`;
  }
  ALL_GAMES.forEach((g) => { g.slug = norm(g.name); g.box_art = blobUrl(boxArtSvg(g)); });
  const gameDict = (g) => ({ id: g.id, name: g.name, slug: g.slug, box_art: g.box_art });

  function rewardSvg(g, type, n) {
    const [, mid, acc, hi] = g.c;
    const shape = {
      BADGE: `<path d="M48 14 L76 26 V50 C76 66 63 76 48 82 C33 76 20 66 20 50 V26Z" fill="${acc}"/><text x="48" y="58" text-anchor="middle" font-family="sans-serif" font-size="26" font-weight="800" fill="${mid}">${n}</text>`,
      EMOTE: `<circle cx="48" cy="48" r="32" fill="${hi}"/><circle cx="37" cy="42" r="5" fill="${mid}"/><circle cx="59" cy="42" r="5" fill="${mid}"/><path d="M34 56 q14 14 28 0" stroke="${mid}" stroke-width="5" fill="none" stroke-linecap="round"/>`,
      DIRECT_ENTITLEMENT: `<path d="M48 14 L80 30 V66 L48 82 L16 66 V30Z" fill="${acc}"/><path d="M16 30 L48 46 L80 30 M48 46 V82" stroke="${mid}" stroke-width="4" fill="none"/><circle cx="48" cy="30" r="6" fill="${hi}"/>`,
    }[type];
    return blobUrl(`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 96 96"><rect width="96" height="96" rx="18" fill="${mid}"/>${shape}</svg>`);
  }

  // ================================================================ fake live streams
  // One animated 16:9 scene per channel: a scrolling world for the game, a HUD and a facecam.
  const streamCache = {};
  function streamSvg(ch) {
    const g = gameByName(ch.game) || GAMES[0];
    const [bg, mid, acc, hi] = g.c;
    const sky = g.night ? bg : mid;
    const hue = (ch.login.length * 47) % 360;
    const dur = 6 + (ch.login.length % 5);
    let world = "";
    if (g.scene === "space") {
      let stars = "";
      for (let i = 0; i < 46; i++) stars += `<circle cx="${(i * 97) % 640}" cy="${(i * 53) % 300}" r="${i % 3 ? 1.2 : 2}" fill="#fff" opacity="${0.4 + (i % 5) / 10}"/>`;
      world = `<rect width="640" height="360" fill="${bg}"/>
        <g class="scroll">${stars}<g transform="translate(640 0)">${stars}</g></g>
        <circle cx="500" cy="90" r="46" fill="${acc}"/><ellipse cx="500" cy="90" rx="78" ry="14" fill="none" stroke="${hi}" stroke-width="4" transform="rotate(-15 500 90)"/>
        <g class="bob"><path d="M150 180 l60 -18 l-14 18 l14 18Z" fill="${hi}"/><path d="M150 180 l-26 -8 v16Z" fill="${acc}" class="flame"/></g>
        <g class="shots"><rect x="230" y="178" width="22" height="4" rx="2" fill="${acc}"/><rect x="300" y="178" width="22" height="4" rx="2" fill="${acc}"/></g>
        <g class="drift"><path d="M560 230 l-30 10 l30 10 l-8 -10Z" fill="#ff6b6b"/></g>`;
    } else if (g.scene === "road") {
      let lines = "";
      for (let i = 0; i < 8; i++) lines += `<rect x="${i * 160}" y="292" width="80" height="6" fill="${hi}"/>`;
      let city = "";
      for (let i = 0; i < 16; i++) { const h = 50 + ((i * 37) % 90); city += `<rect x="${i * 80}" y="${230 - h}" width="64" height="${h}" fill="${mid}"/><rect x="${i * 80 + 12}" y="${240 - h}" width="8" height="8" fill="${acc}" opacity=".7"/>`; }
      world = `<rect width="640" height="360" fill="${bg}"/>
        <g class="scroll slow">${city}</g>
        <rect y="230" width="640" height="130" fill="#0d0d12"/>
        <g class="scroll fast">${lines}</g>
        <rect y="230" width="640" height="3" fill="${acc}"/>
        <g class="bob"><rect x="190" y="262" width="110" height="30" rx="10" fill="${acc}"/><path d="M215 262 l14 -18 h46 l14 18Z" fill="${hi}" opacity=".85"/><circle cx="215" cy="294" r="11" fill="#111"/><circle cx="278" cy="294" r="11" fill="#111"/></g>
        <g class="drift"><rect x="470" y="300" width="80" height="24" rx="8" fill="${hi}"/></g>`;
    } else if (g.scene === "sea") {
      const wave = (y, c, cls) => `<g class="${cls}"><path d="M0 ${y} q40 -16 80 0 t80 0 t80 0 t80 0 t80 0 t80 0 t80 0 t80 0 t80 0 t80 0 t80 0 t80 0 t80 0 t80 0 t80 0 t80 0 V360 H0Z" fill="${c}"/></g>`;
      world = `<rect width="640" height="360" fill="${mid}"/><circle cx="520" cy="80" r="34" fill="${hi}" opacity=".9"/>
        ${wave(240, acc, "scroll slow")}
        <g class="rock"><path d="M260 236 L320 120 L380 236Z" fill="${hi}"/><path d="M246 236 h148 l-20 30 h-108Z" fill="${bg}"/><rect x="318" y="110" width="4" height="126" fill="${bg}"/></g>
        ${wave(270, bg, "scroll")}`;
    } else {
      let trees = "";
      for (let i = 0; i < 12; i++) trees += g.farm
        ? `<rect x="${i * 110 + 20}" y="244" width="70" height="12" rx="6" fill="${acc}"/><circle cx="${i * 110 + 40}" cy="240" r="7" fill="${hi}"/>`
        : `<path d="M${i * 110 + 40} 250 l22 -54 l22 54Z" fill="${g.night ? mid : acc}"/>`;
      let hills = "";
      for (let i = 0; i < 4; i++) hills += `<path d="M${i * 320} 230 q80 -90 160 -20 t160 10 V260 H${i * 320}Z" fill="${g.night ? "#1a1724" : mid}"/>`;
      world = `<rect width="640" height="360" fill="${sky}"/>
        ${g.night ? `<circle cx="520" cy="70" r="28" fill="${hi}" opacity=".85"/>` : `<circle cx="520" cy="70" r="30" fill="${hi}"/>`}
        <g class="scroll slow">${hills}</g>
        <rect y="252" width="640" height="108" fill="${g.night ? bg : g.farm ? "#5a3716" : "#1d3a24"}"/>
        <g class="scroll">${trees}</g>
        <g class="bob"><rect x="200" y="214" width="26" height="38" rx="8" fill="${acc}"/><circle cx="213" cy="204" r="12" fill="${hi}"/><rect x="226" y="222" width="30" height="5" rx="2" fill="${hi}" class="swing"/></g>
        ${g.night ? `<g class="flicker"><rect x="420" y="200" width="6" height="52" fill="#5a4a3a"/><circle cx="423" cy="196" r="9" fill="${hi}"/></g>` : ""}`;
    }
    return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 360" >
      <style>
        .scroll{animation:scroll ${dur}s linear infinite}.scroll.slow{animation-duration:${dur * 3}s}.scroll.fast{animation-duration:${dur / 4}s}
        @keyframes scroll{to{transform:translateX(-640px)}}
        .bob{animation:bob 1.6s ease-in-out infinite}@keyframes bob{50%{transform:translateY(-7px)}}
        .drift{animation:drift ${dur / 1.5}s linear infinite}@keyframes drift{from{transform:translateX(160px)}to{transform:translateX(-640px)}}
        .shots{animation:shots .7s linear infinite}@keyframes shots{from{transform:translateX(0);opacity:1}to{transform:translateX(320px);opacity:0}}
        .flame{animation:flick .25s steps(2) infinite}.flicker{animation:flick 1.1s steps(3) infinite}@keyframes flick{50%{opacity:.55}}
        .rock{animation:rock 3.2s ease-in-out infinite;transform-origin:320px 240px}@keyframes rock{25%{transform:rotate(-3deg)}75%{transform:rotate(3deg)}}
        .swing{animation:swing .9s ease-in-out infinite;transform-origin:226px 224px}@keyframes swing{50%{transform:rotate(-35deg)}}
        .cam{animation:talk 2.4s ease-in-out infinite;transform-origin:574px 318px}@keyframes talk{30%{transform:rotate(-4deg)}60%{transform:rotate(3deg)}}
        .blink{animation:blink 3.8s infinite}@keyframes blink{0%,94%,100%{transform:scaleY(1)}97%{transform:scaleY(.1)}}
        .hp{animation:hp 7s ease-in-out infinite}@keyframes hp{50%{width:70px}}
      </style>
      ${world}
      <g transform="translate(253 0)"><rect y="16" width="134" height="12" rx="6" fill="#000" opacity=".45"/><rect class="hp" x="2" y="18" width="110" height="8" rx="4" fill="#30d158"/>
        <rect x="19" y="34" width="96" height="8" rx="4" fill="#000" opacity=".45"/><rect x="21" y="36" width="60" height="4" rx="2" fill="${acc}"/></g>
      <g><rect x="560" y="16" width="64" height="64" rx="10" fill="#000" opacity=".4"/><circle cx="592" cy="48" r="4" fill="${acc}"/><circle cx="604" cy="36" r="2" fill="#fff" opacity=".7"/><circle cx="578" cy="60" r="2" fill="#ff453a"/></g>
      <g><rect x="512" y="268" width="116" height="80" rx="10" fill="hsl(${hue} 30% 22%)"/>
        <g class="cam"><rect x="548" y="318" width="52" height="34" rx="16" fill="hsl(${hue} 55% 55%)"/><circle cx="574" cy="304" r="20" fill="hsl(${(hue + 30) % 360} 35% 72%)"/>
          <g class="blink" style="transform-origin:574px 302px"><circle cx="567" cy="302" r="2.6" fill="#1c1c1e"/><circle cx="581" cy="302" r="2.6" fill="#1c1c1e"/></g>
          <path d="M556 290 q18 -18 36 0" fill="hsl(${hue} 40% 30%)"/></g></g>
    </svg>`;
  }

  // ================================================================ campaigns and drops
  const LINK = "https://www.twitch.tv/drops/inventory";
  let dropSeq = 0;
  function makeCampaign(id, gameName, name, startH, endH, linked, drops) {
    const g = gameByName(gameName);
    const camp = { id, name, game: g, starts_at: START + startH * HOUR, ends_at: START + endH * HOUR, linked, link_url: linked ? "" : LINK, image: g.box_art, drops: [] };
    drops.forEach(([minutes, reward, type, current, claimed, extra]) => {
      dropSeq++;
      camp.drops.push(Object.assign({
        id: `${id}-d${dropSeq}`, name: reward, minutes, current: current || 0, claimed: !!claimed,
        benefit: { id: `b${dropSeq}`, name: reward, type, image: rewardSvg(g, type, dropSeq % 9 + 1) },
        claim_error: "", claim_attempts: 0, pre: null,
      }, extra || {}));
    });
    return camp;
  }
  const CAMPAIGNS = [
    makeCampaign("c-comets", "Starfall Tactics", "Season of Comets", -72, 30, true, [
      [30, "Comet Trail Emblem", "DIRECT_ENTITLEMENT", 30, true],
      [60, "Nebula Hull Skin", "DIRECT_ENTITLEMENT", 41],
      [120, "Captain's Badge", "BADGE"],
      [240, "Starfall Mothership", "DIRECT_ENTITLEMENT"],
    ]),
    makeCampaign("c-fair", "Pixel Harvest", "Autumn Fair", -30, 70, true, [
      [15, "Happy Turnip", "EMOTE", 15, true],
      [45, "Golden Pumpkin Badge", "BADGE"],
    ]),
    makeCampaign("c-midnight", "Neon Drift", "Midnight Run", -48, 52, true, [
      [45, "Chrome Rims", "DIRECT_ENTITLEMENT"],
      [90, "Afterglow Paint", "DIRECT_ENTITLEMENT"],
      [180, "Night Racer Badge", "BADGE"],
    ]),
    makeCampaign("c-founders", "Ironvale Online", "Founders Week", -100, 120, true, [
      [30, "Founder's Cloak", "DIRECT_ENTITLEMENT", 30, true],
      [60, "Iron Sigil", "DIRECT_ENTITLEMENT", 60, true],
      [120, "Wyvern Mount", "DIRECT_ENTITLEMENT"],
      [240, "Ironvale Banner", "DIRECT_ENTITLEMENT"],
    ]),
    makeCampaign("c-harbor", "Tidebreaker", "Harbor Festival", -20, 140, false, [
      [60, "Lighthouse Sail", "DIRECT_ENTITLEMENT", 60, false, { claim_error: "The game account is not linked", claim_attempts: 3 }],
      [120, "Kraken Figurehead", "DIRECT_ENTITLEMENT"],
    ]),
    makeCampaign("c-lanterns", "Hollow Keep", "Lanterns of the Deep", 40, 220, true, [
      [60, "Ember Lantern", "DIRECT_ENTITLEMENT"],
      [120, "Keeper's Badge", "BADGE"],
    ]),
    makeCampaign("c-launch", "Starfall Tactics", "Launch Celebration", -400, -180, true, [
      [30, "Pioneer Decal", "DIRECT_ENTITLEMENT", 30, true],
      [60, "First Flight Emote", "EMOTE", 60, true],
    ]),
  ];
  // the badge of "Season of Comets" needs the hull skin first
  CAMPAIGNS[0].drops[2].pre = CAMPAIGNS[0].drops[1].id;
  const campaignById = (id) => CAMPAIGNS.find((c) => c.id === id);
  const allDrops = () => CAMPAIGNS.flatMap((c) => c.drops.map((d) => [c, d]));

  const now = () => Date.now();
  const cActive = (c) => c.starts_at <= now() && now() < c.ends_at;
  const cUpcoming = (c) => now() < c.starts_at;
  const preMet = (c, d) => !d.pre || c.drops.find((x) => x.id === d.pre).claimed;
  const complete = (d) => d.minutes > 0 && d.current >= d.minutes;
  const claimable = (c, d) => complete(d) && !d.claimed && preMet(c, d) && now() < c.ends_at + DAY;
  const canEarn = (c, d) => cActive(c) && !d.claimed && d.minutes > 0 && d.current < d.minutes && preMet(c, d);
  const isBadge = (d) => d.benefit.type === "BADGE" || d.benefit.type === "EMOTE";
  const needsLink = (c, d) => !c.linked && !!c.link_url && !isBadge(d);
  function dropStatus(c, d) {
    if (d.claimed) return "claimed";
    if (complete(d)) {
      if (now() >= c.ends_at + DAY) return "missed";
      if (!preMet(c, d)) return "locked";
      return d.claim_error ? "failed" : "ready";
    }
    if (now() >= c.ends_at) return "expired";
    if (now() < c.starts_at) return "upcoming";
    if (!preMet(c, d)) return "locked";
    return d.current > 0 ? "progress" : "pending";
  }
  function dropDict(c, d) {
    return {
      id: d.id, name: d.name, status: dropStatus(c, d), claim_error: d.claim_error, claim_attempts: d.claim_attempts,
      claim_retry_at: d.claim_error ? iso(now() + 20 * 60e3) : null, needs_link: needsLink(c, d), rewards: d.benefit.name,
      benefits: [Object.assign({}, d.benefit)], starts_at: iso(c.starts_at), ends_at: iso(c.ends_at),
      required_minutes: d.minutes, current_minutes: d.current, progress: d.minutes ? Math.round((d.current / d.minutes) * 1e4) / 1e4 : 0,
      is_claimed: d.claimed, claimable: claimable(c, d), can_earn: canEarn(c, d),
    };
  }
  const finished = (c) => c.drops.length > 0 && c.drops.every((d) => d.claimed || d.minutes <= 0);
  function remaining(c) {
    // like Drop.total_remaining_minutes: a drop's own minutes plus the ones of the drop it waits for
    const left = (d) => Math.max(d.minutes - d.current, 0);
    return Math.max(0, ...c.drops.filter((d) => !d.claimed).map((d) => left(d) + (d.pre ? left(c.drops.find((x) => x.id === d.pre)) : 0)));
  }
  function campaignDict(c) {
    return {
      id: c.id, name: c.name, game: gameDict(c.game), status: cActive(c) ? "active" : cUpcoming(c) ? "upcoming" : "expired",
      starts_at: iso(c.starts_at), ends_at: iso(c.ends_at), linked: c.linked, link_known: true, link_url: c.link_url, image: c.image,
      acl_channels: 0, reward_types: [...new Set(c.drops.map((d) => d.benefit.type))].sort(), finished: finished(c),
      claimed: c.drops.filter((d) => d.claimed).length, total: c.drops.length, remaining_minutes: remaining(c),
      drops: c.drops.slice().sort((a, b) => a.minutes - b.minutes).map((d) => dropDict(c, d)),
    };
  }

  // ================================================================ settings
  const SETTINGS_KEY = "pr.demo.settings";
  const DEFAULTS = {
    game_mode: "all", games_whitelist: [], games_exclude: [], games_priority: ["Starfall Tactics", "Moonlit Orchard"],
    campaigns_exclude: [], priority_mode: "ending_soonest", mine_badges_emotes: true, require_linked_account: true,
    channels_preferred: [], channels_blacklist: [], stream_languages: [], channels_per_game: 25, verify_channel_drops: true,
    auto_claim: true, claim_channel_points: true, refresh_interval_minutes: 30, claim_sweep_interval_minutes: 5, paused: false,
    webhook_url: "", notify_claimed: true, notify_failed: true, notify_campaign_done: true, notify_watched: true,
    notify_new_campaign: false, notify_login: true, webhook_username: "", webhook_avatar: "", ui_language: "en",
    campaign_catalog_url: "https://ttvdrops.lovinator.space/api/v1/twitch/campaigns/", proxy: "", gql_hash_overrides: {},
  };
  let settings = Object.assign({}, DEFAULTS);
  try {
    const saved = JSON.parse(localStorage.getItem(SETTINGS_KEY) || "null");
    if (saved) settings = Object.assign(settings, saved);
    else settings.ui_language = localStorage.getItem("pr.lang") || "en";
  } catch (e) { /* private window */ }
  const saveSettings = () => { try { localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings)); } catch (e) { /* ignore */ } };

  function skipReason(c) {
    const game = norm(c.game.name);
    if (settings.campaigns_exclude.includes(c.id)) return "disabled";
    if (settings.games_exclude.some((g) => norm(g) === game)) return "game_excluded";
    if (settings.game_mode === "whitelist" && !settings.games_whitelist.some((g) => norm(g) === game)) return "not_whitelisted";
    if (settings.priority_mode === "priority_only" && !settings.games_priority.some((g) => norm(g) === game)) return "not_prioritized";
    if (!settings.mine_badges_emotes && c.drops.every(isBadge)) return "badges_off";
    if (settings.require_linked_account && !c.linked && c.link_url && !c.drops.every(isBadge)) return "not_linked";
    if (cUpcoming(c)) return "upcoming";
    if (!cActive(c)) return "expired";
    if (finished(c)) return "finished";
    if (!c.drops.some((d) => canEarn(c, d))) return "unavailable";
    return null;
  }
  function wanted() {
    const prio = settings.games_priority.map(norm);
    const rank = (c) => { const i = prio.indexOf(norm(c.game.name)); return i < 0 ? prio.length : i; };
    const avail = (c) => (c.ends_at - now()) / 60e3 / Math.max(remaining(c), 1);
    return CAMPAIGNS.filter((c) => skipReason(c) === null)
      .sort((a, b) => settings.priority_mode === "low_availability" ? avail(a) - avail(b) : a.ends_at - b.ends_at)
      .sort((a, b) => rank(a) - rank(b));
  }

  // ================================================================ channels (all fictional)
  const CHANNELS = [
    ["astra_vance", "AstraVance", "Starfall Tactics", 8420, "Comet season grind! Hull skin today, chill vibes", ["c-comets"], "directory"],
    ["kometkid", "KometKid", "Starfall Tactics", 2310, "ranked climb + drops on | !commands", ["c-comets"], "directory"],
    ["orbital_otto", "OrbitalOtto", "Starfall Tactics", 640, "first time playing the new map", ["c-comets"], "directory"],
    ["driftqueen", "DriftQueen", "Neon Drift", 12880, "No brakes Thursday. Midnight Run drops are live", ["c-midnight"], "directory"],
    ["turbo_tam", "turbo_tam", "Neon Drift", 1730, "time trials, then viewer races", ["c-midnight"], "directory"],
    ["nightshift_nico", "NightshiftNico", "Neon Drift", 420, "lofi drifting till sunrise", [], "directory"],
    ["lanternlight", "Lanternlight", "Hollow Keep", 3050, "deep floors only, no saves", [], "directory"],
    ["mossandmortar", "MossAndMortar", "Hollow Keep", 980, "speedrun practice, any%", [], "directory"],
    ["captain_brine", "CaptainBrine", "Tidebreaker", 5590, "Harbor Festival! fishing for the kraken", ["c-harbor"], "directory"],
    ["seaglass_sam", "SeaglassSam", "Tidebreaker", 760, "cozy sailing, drops enabled", ["c-harbor"], "directory"],
    ["ironvale_irene", "IronvaleIrene", "Ironvale Online", 9940, "Founders Week raid night, wyvern hunting", ["c-founders"], "acl"],
    ["pikeandpint", "PikeAndPint", "Ironvale Online", 2120, "crafting stream + founders drops", ["c-founders"], "directory"],
    ["runeforged", "Runeforged", "Ironvale Online", 1340, "PvP tournament practice", ["c-founders"], "directory"],
    ["harvestmoonhq", "HarvestMoonHQ", "Pixel Harvest", 4410, "Autumn Fair day 3, pumpkin contest", ["c-fair"], "directory"],
    ["turnip_tycoon", "TurnipTycoon", "Pixel Harvest", 1260, "building the biggest farm in the valley", ["c-fair"], "directory"],
  ].map(([login, name, game, viewers, title, campaigns, source], i) => ({
    id: String(70100 + i), login, name, game, viewers, title, campaign_ids: campaigns, source, online: true, offlineUntil: 0,
  }));
  const OFFLINE = [["quiet_quill", "QuietQuill", "Moonlit Orchard"], ["pebble_pilot", "PebblePilot", "Glacier Run"]];
  OFFLINE.forEach(([login, name, game], i) => CHANNELS.push({
    id: String(70200 + i), login, name, game, viewers: 0, title: "", campaign_ids: [], source: "preferred", online: false, offlineUntil: Infinity,
  }));
  const channelBy = (login) => CHANNELS.find((c) => c.login === login);

  // ================================================================ miner state
  const M = {
    loggedIn: true, loginAt: 0, watching: null, manual: null, campaign: null, selection: null, previous: null,
    sessionMinutes: 0, sessionClaims: 0, lastRefresh: START - 4 * 60e3, error: "", tickN: 0,
  };

  // log lines like the real miner writes them
  const LOGS = [];
  let logId = 0;
  function log(msg, level, at) { LOGS.push({ id: ++logId, ts: iso(at || now()), level: level || "INFO", msg }); if (LOGS.length > 500) LOGS.shift(); }
  [
    [-300, "Dropper 2.5.0 starting (data in /data)"],
    [-298, "Logged in as demo_viewer"],
    [-296, "PubSub connected (4 topics)"],
    [-290, "7 campaigns loaded (6 active, 4 wanted, list from twitch)"],
    [-282, "17 channels found, 15 live with drops"],
    [-280, "Switching to AstraVance (Starfall Tactics, 8,392 viewers)"],
    [-250, "Channel points bonus claimed"],
    [-240, "Drop claimed: Comet Trail Emblem (Starfall Tactics, 1/4)"],
    [-120, "Claim for Lighthouse Sail failed: The game account is not linked, next try in 20 min", "WARNING"],
    [-60, "Channel points bonus claimed"],
  ].forEach(([s, msg, level]) => log(msg, level, now() + s * 1000));

  // claim history and statistics
  const CLAIMS = [];
  let claimId = 0;
  function addClaim(c, d, method, success, detail, at) {
    CLAIMS.unshift({
      id: ++claimId, ts: iso(at || now()), drop_id: d.id, drop_name: d.name, rewards: d.benefit.name, campaign_id: c.id,
      campaign_name: c.name, game: c.game.name, method, success: success ? 1 : 0, detail: detail || "",
    });
  }
  const REWARDS = [];
  function addReward(c, d, at) {
    REWARDS.unshift({ id: d.benefit.id, name: d.benefit.name, image: d.benefit.image, game: c.game.name, last_awarded_at: iso(at || now()), count: 1, link_url: c.link_url, connected: c.linked });
  }
  // older rewards from campaigns that are gone, then the claimed drops of current ones
  const PAST = [["Ironvale Online", "Winter Wolf Pelt", "DIRECT_ENTITLEMENT"], ["Neon Drift", "Holo Plates", "DIRECT_ENTITLEMENT"], ["Pixel Harvest", "Seed Bag Emote", "EMOTE"],
    ["Tidebreaker", "Anchor Badge", "BADGE"], ["Hollow Keep", "Cracked Lantern", "DIRECT_ENTITLEMENT"], ["Starfall Tactics", "Beta Tester Badge", "BADGE"],
    ["Neon Drift", "Tire Smoke: Violet", "DIRECT_ENTITLEMENT"], ["Ironvale Online", "Old Guard Helm", "DIRECT_ENTITLEMENT"]];
  PAST.forEach(([gname, name, type], i) => {
    const g = gameByName(gname);
    const at = now() - (40 - i * 4) * DAY - rnd() * DAY;
    const fake = { id: `old-${i}`, name, benefit: { id: `ob${i}`, name, type, image: rewardSvg(g, type, i + 1) } };
    const camp = { id: `old-c${i}`, name: `${gname} Event`, game: g, link_url: "", linked: true };
    addClaim(camp, fake, i % 3 ? "pubsub" : "progress", true, "", at);
    addReward(camp, fake, at);
  });
  allDrops().filter(([, d]) => d.claimed).sort((a, b) => a[0].starts_at - b[0].starts_at).forEach(([c, d], i) => {
    const at = Math.min(now() - (12 - i) * 3 * HOUR, c.ends_at - HOUR);
    addClaim(c, d, ["pubsub", "progress", "sweep"][i % 3], true, "", at);
    addReward(c, d, at);
  });
  { const [c, d] = allDrops().find(([, x]) => x.claim_error); addClaim(c, d, "progress", false, d.claim_error, now() - 2 * 60e3); }

  // watch history: a year of days, mostly long, with quiet stretches
  const TIMELINE = {};
  const WATCH = {}; // game -> channel -> minutes, for the per-game and per-channel tables
  const dayKey = (ms) => { const d = new Date(ms); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`; };
  function addWatch(game, channel, minutes, at) {
    const key = dayKey(at || now());
    const t = TIMELINE[key] || (TIMELINE[key] = { minutes: 0, claims: 0 });
    t.minutes = Math.min(1440, t.minutes + minutes);
    WATCH[game] = WATCH[game] || {};
    WATCH[game][channel] = (WATCH[game][channel] || 0) + minutes;
  }
  for (let i = 364; i >= 1; i--) {
    const at = now() - i * DAY;
    const quiet = (i > 200 && i < 215) || (i > 90 && i < 96) || rnd() < 0.06;
    if (quiet) continue;
    const total = Math.round(420 + rnd() * 980);
    const g = GAMES[Math.floor(rnd() * GAMES.length)];
    const chans = CHANNELS.filter((c) => c.game === g.name);
    const ch = chans[Math.floor(rnd() * chans.length)] || CHANNELS[0];
    addWatch(g.name, ch.name, total, at);
    TIMELINE[dayKey(at)].claims = rnd() < 0.3 ? 1 + Math.floor(rnd() * 2) : 0;
  }
  addWatch("Starfall Tactics", "AstraVance", 5 * 60, now());
  CLAIMS.filter((c) => c.success).forEach((c) => { const t = TIMELINE[c.ts.slice(0, 10)]; if (t) t.claims = Math.max(t.claims, 1); });
  let POINTS = 184250;

  function summary(days) {
    days = clamp(days | 0 || 30, 1, 365);
    const timeline = [];
    for (let i = days - 1; i >= 0; i--) {
      const key = dayKey(now() - i * DAY);
      const t = TIMELINE[key] || { minutes: 0, claims: 0 };
      timeline.push({ day: key, minutes: t.minutes, claims: t.claims });
    }
    const today = TIMELINE[dayKey(now())] || { minutes: 0, claims: 0 };
    const allMinutes = Object.values(TIMELINE).reduce((s, t) => s + t.minutes, 0);
    const okClaims = CLAIMS.filter((c) => c.success);
    const historic = Object.values(TIMELINE).reduce((s, t) => s + t.claims, 0);
    const perGame = Object.entries(WATCH).map(([game, chans]) => ({
      game, minutes: Object.values(chans).reduce((s, m) => s + m, 0),
      claims: okClaims.filter((c) => c.game === game).length + Math.round(historic / GAMES.length),
    })).sort((a, b) => b.minutes - a.minutes);
    const perChannel = Object.entries(WATCH).flatMap(([game, chans]) => Object.entries(chans).map(([channel, minutes]) => ({ channel, game, minutes })))
      .sort((a, b) => b.minutes - a.minutes).slice(0, 25);
    return {
      totals: {
        minutes: allMinutes, claims: historic + okClaims.length, failed_claims: CLAIMS.length - okClaims.length, points: POINTS,
        minutes_today: today.minutes, claims_today: okClaims.filter((c) => c.ts.slice(0, 10) === dayKey(now())).length,
      },
      timeline, per_game: perGame, per_channel: perChannel, recent_claims: CLAIMS.slice(0, 100),
    };
  }

  // ================================================================ the miner loop
  function serves(ch, c) {
    return ch.online && ch.game === c.game.name && ch.campaign_ids.includes(c.id) && !settings.channels_blacklist.includes(ch.login);
  }
  function select() {
    const prev = M.watching;
    if (!M.loggedIn) { M.watching = null; M.campaign = null; M.selection = null; return; }
    const list = wanted();
    let camp = null, chan = null, cands = [];
    if (M.manual) {
      chan = channelBy(M.manual);
      if (!chan || !chan.online) { log(`Manually picked channel ${chan ? chan.name : M.manual} is offline, back to automatic`); M.manual = null; chan = null; }
      else camp = list.find((c) => serves(chan, c)) || null;
    }
    if (!chan) {
      for (const c of list) {
        cands = CHANNELS.filter((ch) => serves(ch, c));
        if (!cands.length) continue;
        camp = c;
        const stay = prev && cands.find((ch) => ch.id === prev.id);
        chan = stay || cands.slice().sort((a, b) =>
          (settings.channels_preferred.includes(a.login) ? 0 : 1) - (settings.channels_preferred.includes(b.login) ? 0 : 1) ||
          (a.source === "acl" ? 0 : 1) - (b.source === "acl" ? 0 : 1) || b.viewers - a.viewers)[0];
        break;
      }
    }
    M.campaign = camp;
    if (camp && chan && !M.manual) {
      const rule = cands.length <= 1 ? "single" : prev && prev.id === chan.id ? "stay" : settings.channels_preferred.includes(chan.login) ? "preferred" : chan.source === "acl" ? "acl" : "viewers";
      M.selection = { campaign_id: camp.id, campaign: camp.name, game: camp.game.name, position: list.indexOf(camp) + 1, queue: list.length, candidates: cands.length, rule };
    } else M.selection = M.manual && chan ? { rule: "manual" } : null;
    if (chan && (!prev || prev.id !== chan.id)) log(`Switching to ${chan.name} (${chan.game}, ${chan.viewers.toLocaleString("en-US")} viewers)`);
    if (!chan && prev) log(list.length ? "No live channel with matching drops" : "No wanted campaign is active");
    M.watching = chan;
  }
  function currentDrop() {
    const c = M.campaign;
    if (!c) return null;
    const earnable = c.drops.filter((d) => canEarn(c, d)).sort((a, b) => (a.minutes - a.current) - (b.minutes - b.current));
    return earnable[0] || null;
  }
  function claim(c, d, method) {
    d.claimed = true; d.current = d.minutes; d.claim_error = ""; d.claim_attempts = 0;
    M.sessionClaims++;
    addClaim(c, d, method, true);
    addReward(c, d);
    const t = TIMELINE[dayKey(now())]; if (t) t.claims++;
    log(`Drop claimed: ${d.benefit.name} (${c.game.name}, ${c.drops.filter((x) => x.claimed).length}/${c.drops.length})`);
  }
  function renewIfDone() {
    // keep the demo going forever: when nothing is left to farm, campaigns start over
    if (wanted().length) return;
    CAMPAIGNS.filter((c) => cActive(c) && c.linked).forEach((c) => {
      c.drops.forEach((d) => { d.claimed = false; d.current = 0; });
      c.ends_at = now() + (40 + rnd() * 80) * HOUR;
    });
    log(`${CAMPAIGNS.length} campaigns loaded (${CAMPAIGNS.filter(cActive).length} active, ${wanted().length} wanted, list from twitch)`);
  }
  function tick() {
    M.tickN++;
    // viewers move a little, and now and then a stream ends or comes back
    CHANNELS.forEach((ch) => {
      if (ch.offlineUntil === Infinity) return;
      if (!ch.online && now() >= ch.offlineUntil) { ch.online = true; ch.viewers = 300 + Math.round(Math.random() * 3000); }
      if (ch.online) ch.viewers = Math.max(40, Math.round(ch.viewers * (0.985 + Math.random() * 0.03) + (Math.random() - 0.5) * 20));
    });
    if (M.tickN % 70 === 0 && M.watching && Math.random() < 0.6) {
      const ch = M.watching;
      ch.online = false; ch.offlineUntil = now() + 90e3;
      log(`${ch.name} went offline or switched games, looking for another channel`);
      select();
    }
    if (M.tickN % 40 === 0) { POINTS += 50; log("Channel points bonus claimed"); }
    if (!M.loggedIn) {
      if (now() - M.loginAt > 14000) { M.loggedIn = true; log("Logged in as demo_viewer"); select(); }
      return;
    }
    if (settings.paused) return;
    if (!M.watching || !M.watching.online) select();
    if (!M.watching) { renewIfDone(); return; }
    // finished drops are claimed right away, like PubSub would
    if (settings.auto_claim) {
      allDrops().forEach(([c, d]) => { if (claimable(c, d) && !d.claim_error) claim(c, d, "pubsub"); });
    }
    const d = currentDrop();
    const c = M.campaign;
    if (d) {
      d.current = Math.min(d.minutes, d.current + 1);
      M.sessionMinutes++;
      addWatch(c.game.name, M.watching.name, 1);
      if (complete(d) && !settings.auto_claim) log(`${d.benefit.name} is ready to claim (auto-claim is off)`);
    }
    if (!d || finished(c) || !c.drops.some((x) => canEarn(c, x))) {
      if (finished(c)) log(`Campaign complete: ${c.name} (${c.game.name})`);
      select();
      renewIfDone();
    }
  }
  select();
  setInterval(tick, MINUTE_MS);

  // ================================================================ API
  function state() {
    const c = M.campaign;
    const d = currentDrop() || (c && c.drops.find((x) => claimable(c, x)));
    const w = M.watching;
    const drops = allDrops();
    return {
      state: !M.loggedIn ? "login" : settings.paused ? "paused" : w ? "watching" : "idle",
      status: "", error: "",
      activity: !M.loggedIn ? { code: "login_required", params: {} } : settings.paused ? { code: "paused", params: {} }
        : w ? { code: "watching", params: { channel: w.name, game: w.game } } : { code: wanted().length ? "no_channels" : "no_campaigns", params: {} },
      user: M.loggedIn ? { login: "demo_viewer", id: "4242" } : null,
      login_prompt: M.loggedIn ? null : { code: "PRDEMO42", url: "https://www.twitch.tv/activate", expires_in: Math.max(0, 1800 - Math.round((now() - M.loginAt) / 1000)) },
      paused: settings.paused, pubsub: true,
      watching: w ? channelDict(w) : null,
      manual: M.manual,
      selection: M.selection,
      auto_claim: settings.auto_claim,
      campaign_source: "twitch",
      campaign: c ? { id: c.id, name: c.name, game: c.game.name, box_art: c.game.box_art, claimed: c.drops.filter((x) => x.claimed).length, total: c.drops.length, ends_at: iso(c.ends_at), remaining_minutes: remaining(c) } : null,
      drop: d ? dropDict(c, d) : null,
      last_refresh: iso(M.lastRefresh), next_refresh: iso(M.lastRefresh + settings.refresh_interval_minutes * 60e3), started_at: iso(START - 5 * 60e3),
      session: { minutes: M.sessionMinutes + 296, claims: M.sessionClaims },
      counts: {
        campaigns: CAMPAIGNS.length, active: CAMPAIGNS.filter(cActive).length, wanted: wanted().length,
        channels_live: CHANNELS.filter((x) => x.online).length,
        claimable: drops.filter(([cc, dd]) => claimable(cc, dd)).length,
        claim_ready: drops.filter(([cc, dd]) => dropStatus(cc, dd) === "ready").length,
        claim_failed: drops.filter(([cc, dd]) => dropStatus(cc, dd) === "failed").length,
      },
      version: "2.5.0",
    };
  }
  function channelDict(ch) {
    const g = gameByName(ch.game);
    return {
      id: ch.id, login: ch.login, name: ch.name, online: ch.online, game: ch.game, viewers: ch.online ? ch.viewers : 0, title: ch.title,
      drops_enabled: ch.campaign_ids.length > 0, campaign_ids: ch.campaign_ids.slice(), source: ch.source,
      url: `https://www.twitch.tv/${ch.login}`, box_art: g ? g.box_art : "",
    };
  }
  function channels() {
    const ids = wanted().map((c) => c.id);
    return CHANNELS.map((ch) => {
      const data = channelDict(ch);
      delete data.box_art;
      data.watching = !!M.watching && M.watching.id === ch.id;
      data.campaigns = ch.campaign_ids.map((id) => {
        const c = campaignById(id);
        const ok = ids.includes(id);
        return { id, name: c.name, game: c.game.name, wanted: ok, reason: ok ? "" : skipReason(c) || "not_wanted" };
      });
      data.blacklisted = settings.channels_blacklist.includes(ch.login);
      data.preferred = settings.channels_preferred.includes(ch.login);
      return data;
    }).sort((a, b) => (b.watching - a.watching) || (b.online - a.online) || (b.drops_enabled - a.drops_enabled) || (b.viewers - a.viewers));
  }
  function campaigns() {
    const ids = wanted().map((c) => c.id);
    return CAMPAIGNS.map((c) => Object.assign(campaignDict(c), {
      skip_reason: skipReason(c), wanted: ids.includes(c.id), queue_position: ids.includes(c.id) ? ids.indexOf(c.id) + 1 : null,
      mining: !!M.campaign && M.campaign.id === c.id,
      live_channels: CHANNELS.filter((ch) => ch.online && ch.campaign_ids.includes(c.id)).length,
    })).sort((a, b) => (b.mining - a.mining) || ((a.queue_position || 1e4) - (b.queue_position || 1e4)) || ((a.status !== "active") - (b.status !== "active")) || a.ends_at.localeCompare(b.ends_at));
  }
  function drops() {
    const ids = wanted().map((c) => c.id);
    const claimedAt = {};
    CLAIMS.slice().reverse().forEach((c) => { if (c.success) claimedAt[c.drop_id] = c.ts; });
    const cur = currentDrop();
    const list = allDrops().map(([c, d]) => Object.assign(dropDict(c, d), {
      claimed_at: claimedAt[d.id] || null, mining: !!cur && cur.id === d.id,
      campaign: { id: c.id, name: c.name, image: c.image, linked: c.linked, link_known: true, link_url: c.link_url, starts_at: iso(c.starts_at), ends_at: iso(c.ends_at), wanted: ids.includes(c.id) },
      game: { id: c.game.id, name: c.game.name, box_art: c.game.box_art },
    }));
    const counts = {};
    list.forEach((d) => { counts[d.status] = (counts[d.status] || 0) + 1; });
    return { drops: list, counts, rewards: REWARDS.slice(), claims: CLAIMS.slice(0, 200), auto_claim: settings.auto_claim };
  }
  function campaignState(name) {
    const key = norm(name);
    const cs = CAMPAIGNS.filter((c) => norm(c.game.name) === key);
    return cs.some(cActive) ? "active" : cs.some(cUpcoming) ? "upcoming" : null;
  }
  function checkGame(name) {
    const g = gameByName(name);
    return g ? { query: name, status: "found", game: { name: g.name, id: g.id, box_art: g.box_art, campaign: campaignState(g.name) } } : { query: name, status: "missing", game: null };
  }
  function gameSearch(q) {
    const key = norm(q);
    const results = ALL_GAMES.filter((g) => norm(g.name).includes(key))
      .map((g) => ({ name: g.name, id: g.id, box_art: g.box_art, campaign: campaignState(g.name) }))
      .sort((a, b) => (norm(b.name).startsWith(key) - norm(a.name).startsWith(key)) || ((a.campaign ? 0 : 1) - (b.campaign ? 0 : 1)) || a.name.localeCompare(b.name))
      .slice(0, 8);
    return { query: q, results, lookup: q.length >= 2 ? checkGame(q) : null };
  }

  const LIST_KEYS = ["games_whitelist", "games_exclude", "games_priority", "channels_preferred", "channels_blacklist", "stream_languages", "campaigns_exclude"];
  function updateSettings(data) {
    const next = Object.assign({}, settings);
    for (const [k, v] of Object.entries(data || {})) {
      if (!(k in DEFAULTS)) continue;
      if (LIST_KEYS.includes(k)) {
        const lower = k.startsWith("channels_");
        const seen = new Set();
        next[k] = (Array.isArray(v) ? v : []).map((s) => String(s).trim().replace(/^@/, "")).map((s) => lower ? s.toLowerCase() : s)
          .filter((s) => s && !seen.has(norm(s)) && seen.add(norm(s)));
      } else next[k] = v;
    }
    if (next.refresh_interval_minutes < 5) return [422, { detail: [{ loc: ["body", "refresh_interval_minutes"], msg: "Input should be greater than or equal to 5" }] }];
    settings = next;
    saveSettings();
    select();
    return [200, Object.assign({}, settings)];
  }

  function handle(method, path, query, body) {
    switch (`${method} ${path}`) {
      case "GET health": return [200, { ok: true, version: "2.5.0", state: state().state }];
      case "GET state": return [200, state()];
      case "GET campaigns": return [200, campaigns()];
      case "GET channels": return [200, channels()];
      case "GET drops": return [200, drops()];
      case "GET stats": return [200, summary(Number(query.get("days")) || 30)];
      case "GET logs": { const after = Number(query.get("after")) || 0; return [200, LOGS.filter((l) => l.id > after)]; }
      case "GET settings": return [200, Object.assign({}, settings)];
      case "PUT settings": return updateSettings(body);
      case "GET games/search": return [200, gameSearch(String(query.get("q") || "").trim().replace(/\s+/g, " ").slice(0, 100))];
      case "POST games/lookup": return [200, { games: (body.names || []).slice(0, 30).filter(Boolean).map((n) => checkGame(String(n))) }];
      case "POST refresh": M.lastRefresh = now(); log(`${CAMPAIGNS.length} campaigns loaded (${CAMPAIGNS.filter(cActive).length} active, ${wanted().length} wanted, list from twitch)`); select(); return [200, { ok: true }];
      case "POST switch": M.manual = body.login || null; select(); return [200, { ok: true, watching: M.watching ? channelDict(M.watching) : null }];
      case "POST pause": updateSettings({ paused: "paused" in body ? !!body.paused : !settings.paused }); select(); return [200, { paused: settings.paused }];
      case "POST logout": M.loggedIn = false; M.loginAt = now(); log("Logged out"); select(); return [200, { ok: true }];
      case "POST notify/test": return [200, { ok: false, detail: "This is the demo, so nothing was sent. In your own Dropper this sends a test message." }];
    }
    let m = path.match(/^claim\/(.+)$/);
    if (m && method === "POST") {
      const hit = allDrops().find(([, d]) => d.id === decodeURIComponent(m[1]));
      if (!hit) return [404, { detail: "drop not found" }];
      const [c, d] = hit;
      if (!claimable(c, d) && !d.claimed) return [409, { detail: "drop is not finished yet" }];
      if (needsLink(c, d) && !c.linked) {
        d.claim_attempts++;
        addClaim(c, d, "manual", false, d.claim_error);
        log(`Claim for ${d.benefit.name} failed: ${d.claim_error}, next try in 20 min`, "WARNING");
        return [200, { ok: false }];
      }
      if (!d.claimed) claim(c, d, "manual");
      return [200, { ok: true }];
    }
    m = path.match(/^campaigns\/(.+)\/toggle$/);
    if (m && method === "POST") {
      const id = decodeURIComponent(m[1]);
      const list = settings.campaigns_exclude.includes(id) ? settings.campaigns_exclude.filter((x) => x !== id) : settings.campaigns_exclude.concat(id);
      updateSettings({ campaigns_exclude: list });
      return [200, { ok: true, excluded: list.includes(id) }];
    }
    return [404, { detail: "Not Found" }];
  }

  const realFetch = window.fetch.bind(window);
  window.fetch = function (input, init) {
    const url = typeof input === "string" ? input : input.url;
    if (url.startsWith("/static/")) return realFetch(url.slice(1), init);
    const m = url.match(/^\/api\/([^?]*)(?:\?(.*))?$/);
    if (!m) return realFetch(input, init);
    const method = ((init && init.method) || "GET").toUpperCase();
    let body = {};
    try { body = init && init.body ? JSON.parse(init.body) : {}; } catch (e) { body = {}; }
    const [status, data] = handle(method, m[1], new URLSearchParams(m[2] || ""), body);
    // a little latency, like a server on the LAN
    return new Promise((resolve) => setTimeout(() => resolve(new Response(JSON.stringify(data), {
      status, headers: { "Content-Type": "application/json" },
    })), 40 + Math.random() * 80));
  };

  // ================================================================ stream player
  // Links to Twitch open a fake stream with a fake chat instead, since none of these channels exist.
  const CHAT_NAMES = ["pixelpanda", "moss_byte", "kettle_corn", "lumen_fox", "quietstorm", "byte_bard", "nova_noodle", "tinkerowl", "sundew", "glitchgarden", "orbit_ollie", "papercrane"];
  const CHAT_LINES = ["LETS GO", "that was clean", "gg", "how long until the next drop?", "first time here, love the vibe", "W stream", "no way",
    "hydrate check", "the music is so good today", "clip it!", "drops are working for me", "what's the build?", "LUL", "PogChamp moment",
    "chat is cozy today", "almost got the skin", "just claimed mine!", "that jump though", "lurking while I work", "o7"];
  let playerTimer = null;
  function openPlayer(login) {
    const ch = channelBy(login);
    if (!ch) return;
    closePlayer();
    const wrap = document.createElement("div");
    wrap.className = "demo-player-bg";
    wrap.innerHTML = `<div class="demo-player" role="dialog" aria-modal="true" aria-label="${xml(ch.name)}">
      <div class="demo-video"><img src="${thumbFor(ch)}" alt=""><span class="live-badge">Live</span></div>
      <aside class="demo-chat"><header><b>Stream chat</b><button class="demo-x" aria-label="Close">×</button></header><ol></ol>
        <footer>Fake chat for a fake stream. Nothing here is real.</footer></aside>
      <div class="demo-meta"><b>${xml(ch.name)}</b><span>${xml(ch.game)} · ${ch.viewers.toLocaleString()} viewers</span><p>${xml(ch.title)}</p></div>
    </div>`;
    document.body.appendChild(wrap);
    const ol = wrap.querySelector("ol");
    const say = () => {
      const li = document.createElement("li");
      const name = pick(CHAT_NAMES);
      li.innerHTML = `<b style="color:hsl(${(name.length * 53) % 360} 70% 68%)">${name}</b> ${xml(pick(CHAT_LINES))}`;
      ol.appendChild(li);
      while (ol.children.length > 60) ol.firstChild.remove();
      ol.scrollTop = ol.scrollHeight;
    };
    for (let i = 0; i < 8; i++) say();
    playerTimer = setInterval(say, 900);
    wrap.addEventListener("click", (e) => { if (e.target === wrap || e.target.closest(".demo-x")) closePlayer(); });
  }
  function closePlayer() {
    clearInterval(playerTimer);
    document.querySelectorAll(".demo-player-bg").forEach((el) => el.remove());
  }
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") closePlayer(); });
  document.addEventListener("click", (e) => {
    const a = e.target instanceof Element && e.target.closest('a[href^="https://www.twitch.tv/"]');
    if (!a) return;
    const login = a.getAttribute("href").slice("https://www.twitch.tv/".length).split(/[/?#]/)[0];
    if (channelBy(login)) { e.preventDefault(); e.stopPropagation(); openPlayer(login); }
  }, true);

  function thumbFor(ch) {
    return streamCache[ch.login] || (streamCache[ch.login] = blobUrl(streamSvg(ch)));
  }
  window.DropperDemo = {
    thumb(login) { const ch = channelBy(String(login).toLowerCase()); return ch ? thumbFor(ch) : ""; },
  };
})();

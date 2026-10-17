// Fingerprint frontend: plain JS, no build step. All external text is inserted with textContent.

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

const LEVELS = {
  light: "Name, phone and city. We search where your number and name show up, including people-finder sites.",
  standard: "Light, plus birth year, email and usernames: data breaches, accounts using your handle, and age matching.",
  deep: "Standard, plus other names, workplace, school and past cities: the sharpest match, with the fewest namesakes.",
};

const CATEGORIES = {
  contact: ["📞", "Contact", "var(--magenta)"],
  location: ["📍", "Location", "var(--orange)"],
  work: ["💼", "Work", "var(--blue)"],
  education: ["🎓", "Education", "var(--green)"],
  social: ["💬", "Social", "var(--purple)"],
  code: ["💻", "Code", "var(--lime)"],
  identity: ["🪪", "Mentions", "var(--blue)"],
  family: ["👪", "Family", "var(--magenta)"],
  breach: ["🔓", "Breaches", "var(--coral)"],
  broker: ["🕵️", "People-finders", "var(--orange)"],
  media: ["📷", "Photos", "var(--purple)"],
};
const RISK_RANK = { red: 0, amber: 1, green: 2 };
const SHORT = {
  phone: "Phone", email: "Email", address: "Address", dob: "Birth date", age: "Age", location: "Location",
  employer: "Work", education: "School", family: "Family", profile: "Profile", listing: "Listing",
  document: "Document", mention: "Mention", breach: "Breaches", username: "Account",
};
const REASON_TEXT = {
  phone: "your phone number", email: "your email", username: "your username", "full name": "your full name",
  "other name": "another name you gave", "name (split)": "your first and last name", "middle name": "your middle name",
  age: "an age that fits your birth year", city: "your city", state: "your state", "past city": "a past city",
  employer: "your workplace", school: "your school",
};
const STATUS_TEXT = { checking: "checking", ok: "done", blocked: "locked", failed: "couldn't check", skipped: "skipped" };
const STAGE_PROGRESS = { plan: 5, search: 10, fetch: 60, probe: 88, score: 96 };

const state = {
  name: "",
  level: null,
  scanId: null,
  report: null,
  filters: { risk: null, categories: new Set() },
  progress: { stage: "plan", byKind: {} },
  crumbs: 0,
  stream: null,
};

// ── navigation ────────────────────────────────────────────────────────────
function show(screen) {
  $$(".screen").forEach((s) => (s.hidden = s.dataset.screen !== screen));
  window.scrollTo({ top: 0, behavior: "instant" });
  const input = $(`[data-screen="${screen}"] input:not([type=checkbox])`);
  if (input && !input.value) input.focus();
}
$$("[data-go]").forEach((b) => b.addEventListener("click", () => show(b.dataset.go)));

// ── hello ─────────────────────────────────────────────────────────────────
$("#name-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const name = $("#full_name").value.trim().replace(/\s+/g, " ");
  const err = $("#name-error");
  if (name.split(" ").length < 2) {
    err.textContent = "Please enter your first and last name.";
    err.hidden = false;
    return;
  }
  err.hidden = true;
  state.name = name;
  $("#level-title").textContent = `How much do you want to share, ${name.split(" ")[0]}?`;
  show("level");
});

// ── level ─────────────────────────────────────────────────────────────────
$$(".tile[data-level]").forEach((tile) =>
  tile.addEventListener("click", () => {
    state.level = tile.dataset.level;
    $$(".tile[data-level]").forEach((t) => t.setAttribute("aria-checked", String(t === tile)));
    $("#level-help").textContent = LEVELS[state.level];
    $$("#details-form [data-levels]").forEach((el) => (el.hidden = !el.dataset.levels.split(" ").includes(state.level)));
    const form = $("#details-form");
    if (!form.elements.full_name.value) form.elements.full_name.value = state.name;
    updateMeter();
    setTimeout(() => show("details"), 180);
  })
);

// ── details: accuracy meter ───────────────────────────────────────────────
// Weights mirror backend/app/pipeline/match.py: unique identifiers and age matter most.
const METER = [
  ["birth_year", 18, "your birth year"], ["email", 16, "your email"], ["usernames", 10, "a username"],
  ["middle_name", 5, "your middle name"], ["employer", 5, "your workplace"], ["state", 3, "your state"],
  ["aliases", 4, "other names"], ["school", 3, "your school"], ["past_cities", 2, "a past city"],
];
function updateMeter() {
  const form = $("#details-form");
  const visible = (name) => !form.elements[name].closest("[data-levels]")?.hidden;
  let score = 34; // name + phone + city
  let tip = null;
  for (const [name, pts, label] of METER) {
    if (!visible(name)) continue;
    if (form.elements[name].value.trim()) score += pts;
    else tip ??= label;
  }
  const pct = Math.min(100, score);
  $("#meter-fill").style.width = `${pct}%`;
  $("#meter-label").textContent = pct >= 80 ? "Excellent" : pct >= 60 ? "Good" : pct >= 45 ? "Fair" : "Basic";
  $("#meter-tip").textContent = tip
    ? `Add ${tip} for a sharper match.`
    : state.level === "deep" ? "Great: that's everything we can use." : "Want it sharper? Go back and choose Deep.";
}
$("#details-form").addEventListener("input", updateMeter);

// ── details → start scan ──────────────────────────────────────────────────
const list = (v) => v.split(",").map((x) => x.trim()).filter(Boolean).slice(0, 3);

$("#details-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.target;
  const err = $("#details-error");
  err.hidden = true;
  const fail = (msg, el) => {
    err.textContent = msg;
    err.hidden = false;
    el?.focus();
  };
  const v = (name) => (form.elements[name].closest("[data-levels]")?.hidden ? "" : form.elements[name].value.trim());

  if (v("full_name").split(/\s+/).length < 2) return fail("Please enter your first and last name.", form.elements.full_name);
  if (v("phone").replace(/\D/g, "").length < 8) return fail("Please enter your phone number.", form.elements.phone);
  if (v("city").length < 2) return fail("Please enter the city you live in.", form.elements.city);
  if (!$("#consent").checked) return fail("Please confirm you're searching for yourself.", $("#consent"));

  const cc = form.elements.country.selectedOptions[0].dataset.cc;
  let phone = v("phone").replace(/\D/g, "");
  if (!v("phone").startsWith("+")) phone = cc + phone.replace(/^0+/, "");

  const fields = { full_name: v("full_name"), phone, city: v("city"), country: form.elements.country.value };
  if (v("birth_year")) fields.birth_year = Number(v("birth_year"));
  for (const k of ["email", "state", "middle_name", "employer", "school"]) if (v(k)) fields[k] = v(k);
  for (const k of ["usernames", "aliases", "past_cities"]) if (v(k)) fields[k] = list(v(k));

  const btn = $("#start-btn");
  btn.disabled = true;
  try {
    const res = await fetch("/api/scan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ level: state.level, fields, consent: true }),
    });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(readableError(body) || `Couldn't start the scan (${res.status}).`);
    state.scanId = body.scan_id;
    startStream();
  } catch (ex) {
    fail(ex.message);
  } finally {
    btn.disabled = false;
  }
});

function readableError(body) {
  if (typeof body.detail === "string") return body.detail;
  if (Array.isArray(body.detail) && body.detail.length) {
    const d = body.detail[0];
    const field = (d.loc || []).filter((x) => typeof x === "string" && !["body", "fields"].includes(x)).pop();
    return `${field ? field.replaceAll("_", " ") + ": " : ""}${(d.msg || "").replace(/^Value error, /, "")}`;
  }
  return "";
}

// ── scanning ──────────────────────────────────────────────────────────────
function startStream() {
  state.crumbs = 0;
  state.report = null;
  state.progress = { stage: "plan", byKind: {} };
  $("#crumb-count").textContent = "0";
  $("#source-list").replaceChildren();
  $("#stage-label").textContent = "Getting ready…";
  $("#scan-sub").textContent = "Smudge is sniffing around the web.";
  setProgress(2);
  show("scan");

  const es = new EventSource(`/api/scan/${state.scanId}/stream`);
  state.stream = es;
  es.onmessage = (msg) => handleEvent(JSON.parse(msg.data));
  es.onerror = () => {
    es.close();
    if (!state.report) pollReport(); // the stream can drop on flaky networks
  };
}

function handleEvent(ev) {
  switch (ev.type) {
    case "stage":
      state.progress.stage = ev.stage;
      $("#stage-label").textContent = ev.label + "…";
      setProgress(STAGE_PROGRESS[ev.stage] ?? 0);
      break;
    case "source":
      upsertSource($("#source-list"), ev);
      trackSource(ev);
      break;
    case "finding":
      state.crumbs += 1;
      $("#crumb-count").textContent = String(state.crumbs);
      break;
    case "done":
      state.stream?.close();
      setProgress(100);
      setTimeout(() => renderReport(ev.report), 450);
      break;
    case "error":
      state.stream?.close();
      $("#stage-label").textContent = "Oops, Smudge tripped over something.";
      $("#scan-sub").textContent = ev.message;
      break;
  }
}

function trackSource(ev) {
  const k = (state.progress.byKind[ev.kind] ||= { total: new Set(), done: new Set() });
  k.total.add(ev.name);
  if (ev.status !== "checking") k.done.add(ev.name);
  const frac = (kind) => {
    const x = state.progress.byKind[kind];
    return x ? x.done.size / Math.max(1, x.total.size) : 0;
  };
  if (state.progress.stage === "search") setProgress(10 + 50 * frac("search"));
  if (state.progress.stage === "fetch") setProgress(60 + 28 * frac("fetch"));
}

function setProgress(pct) {
  const p = Math.max(0, Math.min(100, Math.round(pct)));
  $("#scan-ring").style.setProperty("--p", p);
  $("#scan-pct").textContent = `${p}%`;
}

function upsertSource(listEl, ev) {
  const key = `${ev.kind}:${ev.name}`;
  let li = [...listEl.children].find((x) => x.dataset.key === key);
  if (!li) {
    li = document.createElement("li");
    li.dataset.key = key;
    li.innerHTML = '<span class="s-name"></span><span class="s-detail"></span><span class="status"></span>';
    listEl.prepend(li);
  }
  $(".s-name", li).textContent = `${kindIcon(ev.kind)} ${ev.name}`;
  $(".s-detail", li).textContent = ev.status === "checking" ? "" : ev.detail || "";
  const st = $(".status", li);
  st.className = `status st-${ev.status}`;
  st.textContent = STATUS_TEXT[ev.status] || ev.status;
}
const kindIcon = (k) => ({ search: "🔎", fetch: "📄", probe: "👤", breach: "🔓", agent: "🐟" })[k] || "•";

async function pollReport() {
  for (let i = 0; i < 90; i++) {
    await new Promise((r) => setTimeout(r, 2000));
    const res = await fetch(`/api/scan/${state.scanId}/report`).catch(() => null);
    if (!res || !res.ok) continue;
    const r = await res.json();
    if (r.status !== "running") return renderReport(r);
  }
}

// ── report: one card per source, confidence on the right ──────────────────
const effConf = (f) => (f.user_verdict === "me" ? 1 : f.user_verdict === "not_me" ? 0 : f.confidence);
const confWord = (c) => (c >= 0.75 ? "Very likely you" : c >= 0.5 ? "Likely you" : c >= 0.3 ? "Maybe you" : "Probably not you");
const confClass = (c) => (c >= 0.75 ? "cf-high" : c >= 0.5 ? "cf-mid" : c >= 0.3 ? "cf-low" : "cf-none");

function groupBySource(findings) {
  const map = new Map();
  for (const f of findings) {
    const key = f.category === "breach" ? `breach:${f.id}` : f.source_url;
    if (!map.has(key)) map.set(key, []);
    map.get(key).push(f);
  }
  return [...map.values()].map((items) => {
    items.sort((a, b) => RISK_RANK[a.risk] - RISK_RANK[b.risk]);
    const conf = Math.max(...items.map(effConf));
    const verdict = items.every((i) => i.user_verdict === "me") ? "me" : items.every((i) => i.user_verdict === "not_me") ? "not_me" : null;
    return { items, conf, verdict, risk: items[0].risk, lead: items[0] };
  }).sort((a, b) => (a.verdict === "not_me") - (b.verdict === "not_me") || RISK_RANK[a.risk] - RISK_RANK[b.risk] || b.conf - a.conf);
}

function renderReport(report) {
  state.report = report;
  $("#score").textContent = report.score;
  $("#score-label").textContent = `${report.score_label} exposure`;
  $("#summary").textContent = report.summary;
  for (const r of ["red", "amber", "green"]) $(`#c-${r}`).textContent = report.counts[r] ?? 0;
  $("#partial-note").hidden = !report.partial;

  const present = [...new Set(report.findings.map((f) => f.category))];
  const chips = $("#category-chips");
  chips.replaceChildren(
    ...present.map((cat) => {
      const [icon, label, color] = CATEGORIES[cat] || ["•", cat, "var(--ink-2)"];
      const b = document.createElement("button");
      b.className = "chip";
      b.style.background = color;
      b.dataset.cat = cat;
      b.textContent = `${icon} ${label} · ${report.findings.filter((f) => f.category === cat).length}`;
      b.addEventListener("click", () => {
        const set = state.filters.categories;
        set.has(cat) ? set.delete(cat) : set.add(cat);
        syncFilterButtons();
        renderSources();
      });
      return b;
    })
  );
  const srcList = $("#report-sources");
  srcList.replaceChildren();
  report.sources.forEach((s) => upsertSource(srcList, s));

  syncFilterButtons();
  renderSources();
  if ($('[data-screen="report"]').hidden) show("report");
}

function syncFilterButtons() {
  const { risk, categories } = state.filters;
  $$(".pill").forEach((x) => x.setAttribute("aria-pressed", String(x.dataset.risk === risk)));
  $$("#category-chips .chip").forEach((c) => c.setAttribute("aria-pressed", String(!categories.size || categories.has(c.dataset.cat))));
}

$$(".pill").forEach((p) =>
  p.addEventListener("click", () => {
    state.filters.risk = state.filters.risk === p.dataset.risk ? null : p.dataset.risk;
    syncFilterButtons();
    renderSources();
  })
);

function renderSources() {
  const listEl = $("#findings");
  const open = new Set($$(".finding-head[aria-expanded='true']", listEl).map((h) => h.closest(".finding").dataset.key));
  const { risk, categories } = state.filters;
  const groups = groupBySource(state.report.findings).filter(
    (g) => (!risk || g.items.some((i) => i.risk === risk)) && (!categories.size || g.items.some((i) => categories.has(i.category)))
  );
  if (!groups.length) {
    const li = document.createElement("li");
    li.className = "empty";
    li.textContent = state.report.findings.length ? "Nothing matches this filter." : "No public crumbs found. Nice and tidy!";
    listEl.replaceChildren(li);
    return;
  }
  listEl.replaceChildren(...groups.map((g) => sourceCard(g, open)));
}

function sourceCard(g, open) {
  const node = $("#source-tpl").content.firstElementChild.cloneNode(true);
  const lead = g.lead;
  const key = lead.category === "breach" ? lead.id : lead.source_url;
  node.dataset.key = key;
  node.classList.toggle("is-not-me", g.verdict === "not_me");

  const [icon] = CATEGORIES[lead.category] || ["•"];
  const iconEl = $(".cat-icon", node);
  iconEl.textContent = icon;
  iconEl.classList.add(`c-${lead.category}`);
  $(".finding-label", node).textContent = lead.category === "breach" || lead.type === "username" ? lead.label : lead.source_name;
  $(".finding-sub", node).textContent = lead.category === "breach" ? "" : lead.source_title || lead.label;

  // what this source exposes, one tag per item, coloured by risk
  $(".items", node).replaceChildren(
    ...g.items.slice(0, 6).map((i) => {
      const t = document.createElement("span");
      t.className = `item risk-${i.risk}`;
      t.textContent = ["profile", "listing", "mention", "document", "username"].includes(i.type)
        ? SHORT[i.type]
        : `${SHORT[i.type] || i.type}: ${i.value_masked}`;
      t.title = `${i.label} · ${{ red: "high", amber: "medium", green: "low" }[i.risk]} risk`;
      return t;
    }),
    ...(g.items.length > 6 ? [Object.assign(document.createElement("span"), { className: "item", textContent: `+${g.items.length - 6}` })] : [])
  );

  // confidence on the right
  const badge = $(".conf-badge", node);
  const pct = Math.round(g.conf * 100);
  badge.classList.add(g.verdict ? (g.verdict === "me" ? "cf-high" : "cf-none") : confClass(g.conf));
  $(".conf-pct", node).textContent = `${pct}%`;
  $(".conf-word", node).textContent = g.verdict === "me" ? "You confirmed" : g.verdict === "not_me" ? "Not you" : confWord(g.conf);
  badge.title = "How sure we are this source is about you";

  // why we think it's you
  const why = $(".why", node);
  const reasons = [...new Set(g.items.flatMap((i) => i.match_reasons))];
  const misses = [...new Set(g.items.flatMap((i) => i.mismatch_reasons || []))];
  const p = document.createElement("p");
  p.className = "why-line";
  p.textContent = reasons.length ? `Matched ${reasons.map((r) => REASON_TEXT[r] || r).join(", ")}.` : "Weak match.";
  why.append(p);
  if (misses.length) {
    const m = document.createElement("p");
    m.className = "why-miss";
    m.textContent = `But: ${misses.join(", ")}.`;
    why.append(m);
  }
  if (!reasons.some((r) => ["phone", "email", "username", "age"].includes(r)) && lead.category !== "breach") {
    const h = document.createElement("p");
    h.className = "hint";
    h.textContent = "Only your name and place matched, so this could be someone with the same name.";
    why.append(h);
  }

  const evs = [...new Set(g.items.map((i) => i.evidence).filter(Boolean))].slice(0, 3);
  $(".evidence-list", node).replaceChildren(
    ...evs.map((e) => Object.assign(document.createElement("li"), { className: "evidence", textContent: e }))
  );

  const a = $(".source", node);
  if (/^https?:\/\//i.test(lead.source_url)) {
    a.href = lead.source_url;
    a.textContent = `Open source: ${lead.source_name} ↗`;
  } else a.remove();

  if (lead.category === "breach") $(".verdict", node).remove();
  $$(".chip-btn", node).forEach((b) => {
    b.setAttribute("aria-pressed", String(g.verdict === b.dataset.verdict));
    b.addEventListener("click", () => sendVerdict(lead.id, b.dataset.verdict));
  });

  const fix = g.items.find((i) => i.risk === g.risk)?.removal || lead.removal;
  $(".fix-title", node).textContent = `How to fix: ${fix.title}`;
  $(".fix-steps", node).replaceChildren(...fix.steps.map((s) => Object.assign(document.createElement("li"), { textContent: s })));

  const head = $(".finding-head", node);
  const body = $(".finding-body", node);
  const toggle = (on) => {
    body.hidden = !on;
    head.setAttribute("aria-expanded", String(on));
  };
  head.addEventListener("click", () => toggle(body.hidden));
  if (open.has(key)) toggle(true);
  return node;
}

async function sendVerdict(findingId, verdict) {
  const res = await fetch(`/api/scan/${state.scanId}/verdict`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ finding_id: findingId, verdict }),
  });
  if (res.ok) renderReport(await res.json());
}

// ── actions ───────────────────────────────────────────────────────────────
$("#again-btn").addEventListener("click", () => {
  state.report = null;
  show("level");
});
$("#delete-btn").addEventListener("click", async () => {
  if (state.scanId) await fetch(`/api/scan/${state.scanId}`, { method: "DELETE" }).catch(() => {});
  state.scanId = null;
  state.report = null;
  state.filters = { risk: null, categories: new Set() };
  $("#details-form").reset();
  $("#full_name").value = "";
  show("splash");
});

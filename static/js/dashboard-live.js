/* লাইভ KOT বোর্ড: WebSocket + রিংটোন (Web Audio) + রোলভিত্তিক বাটন */
(function () {
  const { h, bn } = OM;
  const role = document.body.dataset.role;
  const ALLOW = { // accounts/permissions.py-র STATUS_ROLES-এর প্রতিচ্ছবি (সার্ভার আবার যাচাই করে)
    accepted: ["owner", "manager", "cashier", "waiter"], rejected: ["owner", "manager", "cashier", "waiter", "kitchen"],
    preparing: ["owner", "manager", "kitchen"], ready: ["owner", "manager", "kitchen"], served: ["owner", "manager", "waiter", "cashier"],
  };
  const COLS = [
    { key: "new", title: "নতুন", st: ["pending"], c: "var(--st-new)" },
    { key: "cook", title: "রান্না", st: ["accepted", "preparing"], c: "var(--st-cook)" },
    { key: "ready", title: "রেডি", st: ["ready"], c: "var(--st-ready)" },
    { key: "served", title: "পরিবেশিত", st: ["served"], c: "var(--st-served)" },
  ];
  const NEXT = {
    pending: ["accepted", "গ্রহণ করুন"], accepted: ["preparing", "রান্না শুরু"], preparing: ["ready", "রেডি"], ready: ["served", "পরিবেশিত"],
  };
  const board = document.getElementById("board"), tabs = document.getElementById("tabs"), svc = document.getElementById("svc");
  const cards = new Map(), orders = new Map(), bodies = {}, counts = {}, tabBtns = {};
  let activeTab = "new";

  COLS.forEach((c) => {
    const n = h("span.n", "০"), b = h("div.col-b");
    bodies[c.key] = b; counts[c.key] = n;
    board.append(h("section.col", { id: "col-" + c.key, style: `--c:${c.c}`, "aria-label": c.title }, h("header.col-h", h("h2", c.title), n), b));
    const cb = h("b", "০");
    tabBtns[c.key] = cb;
    tabs.append(h("button", { type: "button", "aria-pressed": c.key === activeTab, onclick: () => setTab(c.key), dataset: { k: c.key } }, c.title, cb));
  });
  function setTab(k) {
    activeTab = k;
    tabs.querySelectorAll("button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.k === k)));
    board.querySelectorAll(".col").forEach((c) => c.classList.toggle("show", c.id === "col-" + k));
  }
  setTab(activeTab);

  /* ---------- রিংটোন ---------- */
  let audio = null, soundOn = false;
  const soundBtn = document.getElementById("soundBtn");
  function chime() {
    if (!audio || !soundOn) return;
    const t = audio.currentTime;
    [[880, 0], [1318.5, .16], [1760, .32]].forEach(([f, d]) => {
      const o = audio.createOscillator(), g = audio.createGain();
      o.type = "sine"; o.frequency.value = f;
      g.gain.setValueAtTime(0, t + d); g.gain.linearRampToValueAtTime(.28, t + d + .02); g.gain.exponentialRampToValueAtTime(.001, t + d + .5);
      o.connect(g).connect(audio.destination); o.start(t + d); o.stop(t + d + .55);
    });
  }
  function paintSound() {
    soundBtn.classList.toggle("attn", !soundOn);
    OM.clear(soundBtn).append(OM.icon(soundOn ? "volume-2" : "volume-x"), h("span", soundOn ? "সাউন্ড চালু" : "সাউন্ড চালু করুন"));
    OM.refreshIcons();
  }
  function enableSound() {
    try { audio = audio || new (window.AudioContext || window.webkitAudioContext)(); audio.resume(); } catch (e) { OM.toast("এই ব্রাউজারে সাউন্ড চলবে না।", "bad"); return; }
    soundOn = true; try { localStorage.setItem("om:sound", "1"); } catch (e) {}
    paintSound(); chime();
  }
  soundBtn.addEventListener("click", () => {
    if (!soundOn) return enableSound();
    soundOn = false; try { localStorage.setItem("om:sound", "0"); } catch (e) {} paintSound();
  });
  paintSound();
  // আগে চালু রাখা থাকলে প্রথম ক্লিক/কী-তেই সাউন্ড সচল (ব্রাউজার অটোপ্লে নিষেধ করে)
  try {
    if (localStorage.getItem("om:sound") === "1") {
      const arm = () => { if (!soundOn) enableSound(); removeEventListener("pointerdown", arm); removeEventListener("keydown", arm); };
      addEventListener("pointerdown", arm); addEventListener("keydown", arm);
    }
  } catch (e) {}
  setInterval(() => { if ([...orders.values()].some((o) => o.status === "pending")) chime(); }, 10000);

  /* ---------- কার্ড ---------- */
  const mins = (o) => Math.max(0, Math.floor((Date.now() - new Date(o.created_at)) / 60000));
  function timeEl(o) {
    const m = mins(o);
    const cls = o.status === "served" ? "" : m >= 10 ? ".w2" : m >= 5 ? ".w1" : "";
    return h("span.tk-time" + cls, { dataset: { t: o.created_at } }, bn(m) + " মি");
  }
  async function act(o, to, btn) {
    let reason = "";
    if (to === "rejected") {
      reason = await OM.prompt("অর্ডার বাতিল করুন", "কারণ (কাস্টমারকে দেখানো হবে)", { ok: "বাতিল করুন", value: "আইটেম শেষ" });
      if (reason === null) return;
    }
    btn.disabled = true;
    try { upsert(await OM.api(`/api/d/orders/${o.id}/status/`, { method: "POST", json: { status: to, reason } }), false); }
    catch (e) { OM.fail(e); btn.disabled = false; }
  }
  function card(o, fresh) {
    const next = NEXT[o.status];
    const acts = h("div.tk-act");
    if (next && ALLOW[next[0]].includes(role)) { const b = h("button.go", { type: "button" }, next[1]); b.onclick = () => act(o, next[0], b); acts.append(b); }
    if (["pending", "accepted", "preparing"].includes(o.status) && ALLOW.rejected.includes(role)) {
      const b = h("button.no", { type: "button" }, "বাতিল"); b.onclick = () => act(o, "rejected", b); acts.append(b);
    }
    return h("article.tk" + (fresh ? ".fresh" : ".nofx"), { "data-s": o.status, "data-id": o.id },
      h("div.tk-h",
        h("div.tk-table", h("small", "টেবিল"), bn(o.table)),
        h("div.tk-meta", h("b", o.customer_name), h("span", "#" + bn(o.id) + (role === "kitchen" ? "" : " · " + bn(o.customer_phone)))),
        timeEl(o)),
      h("ul.tk-items", o.items.map((i) => h("li", h("span.q", bn(i.quantity) + "×"), h("div", i.name, i.note ? h("span.nt", "নোট: " + i.note) : null)))),
      o.note ? h("div.tk-note", o.note) : null,
      acts.children.length ? acts : null);
  }
  function colFor(status) { return COLS.find((c) => c.st.includes(status)); }
  function empty() {
    COLS.forEach((c) => {
      const b = bodies[c.key], n = [...b.children].filter((x) => x.classList.contains("tk")).length;
      const ph = b.querySelector(".col-empty");
      if (!n && !ph) b.append(h("div.col-empty", "এখানে কোনো অর্ডার নেই"));
      if (n && ph) ph.remove();
      counts[c.key].textContent = tabBtns[c.key].textContent = bn(n);
    });
  }
  function upsert(o, fresh) {
    orders.set(o.id, o);
    const old = cards.get(o.id);
    const col = colFor(o.status);
    if (!col) { if (old) { old.remove(); cards.delete(o.id); orders.delete(o.id); } return empty(); } // বাতিল/পরিশোধিত
    const el = card(o, fresh && !old);
    if (old) old.replaceWith(el);
    cards.set(o.id, el);
    const dest = bodies[col.key];
    if (el.parentElement !== dest) dest.append(el);
    if (!old) { const ph = dest.querySelector(".col-empty"); if (ph) ph.remove(); }
    else if (old.parentElement !== dest) old.remove();
    // পুরনো অর্ডার ওপরে
    [...dest.querySelectorAll(".tk")].sort((a, b) => orders.get(+a.dataset.id).created_at.localeCompare(orders.get(+b.dataset.id).created_at)).forEach((x) => dest.append(x));
    empty();
    if (fresh) setTimeout(() => el.classList.remove("fresh"), 3000);
  }

  /* ---------- সার্ভিস রিকোয়েস্ট ---------- */
  const reqs = new Map();
  function drawSvc() {
    if (!svc) return;
    OM.clear(svc);
    if (!reqs.size) { svc.append(h("span.svc-empty", "টেবিলের কোনো ডাক নেই")); return; }
    reqs.forEach((r) => {
      const b = h("button", { type: "button" }, "সম্পন্ন");
      b.onclick = async () => { try { await OM.api(`/api/d/service-requests/${r.id}/resolve/`, { method: "POST" }); reqs.delete(r.id); drawSvc(); } catch (e) { OM.fail(e); } };
      svc.append(h("div.svc-item" + (r.kind === "bill" ? ".bill" : ""), OM.icon(r.kind === "bill" ? "receipt" : "bell-ring"),
        h("span", `টেবিল ${bn(r.table)} · ${r.kind === "bill" ? "বিল চাইছে" : "ওয়েটার ডাকছে"}`), b));
    });
    OM.refreshIcons();
  }

  /* ---------- লোড ও লাইভ ---------- */
  async function loadAll(announce) {
    try {
      const list = await OM.api("/api/d/orders/");
      const fresh = announce === true ? list.filter((o) => !orders.has(o.id) && o.status === "pending") : [];
      const keep = new Set(list.map((o) => o.id));
      [...cards.keys()].forEach((id) => { if (!keep.has(id)) { cards.get(id).remove(); cards.delete(id); orders.delete(id); } });
      list.forEach((o) => upsert(o, false));
      if (fresh.length) { chime(); setTab("new"); }
      empty();
      if (svc) { const rs = await OM.api("/api/d/service-requests/"); reqs.clear(); rs.forEach((r) => reqs.set(r.id, r)); drawSvc(); }
    } catch (e) { OM.fail(e); empty(); }
  }
  const conn = document.getElementById("conn");
  let pollTimer = null, lastV = null, busy = false;
  async function pulse() {
    if (busy || document.hidden && lastV !== null && Math.random() < 0.5) return;
    busy = true;
    try {
      const { v } = await OM.api("/api/d/pulse/");
      if (v !== lastV) { const first = lastV === null; lastV = v; if (!first) await loadAll(true); }
    } catch (e) {} finally { busy = false; }
  }
  OM.socket("/ws/dashboard/", {
    onstate: (on, denied) => {
      conn.classList.toggle("on", on);
      conn.lastChild.textContent = on ? "লাইভ সংযুক্ত" : "প্রতি ২ সেকেন্ডে আপডেট হচ্ছে";
      clearInterval(pollTimer);
      if (!on) pollTimer = setInterval(pulse, 2000);
    },
    onopen: () => loadAll(),
    onmsg: (m) => {
      if (m.type === "order.new") { upsert(m.order, true); chime(); setTab("new"); }
      else if (m.type === "order.update") upsert(m.order, false);
      else if (m.type === "service.new") { reqs.set(m.request.id, m.request); drawSvc(); chime(); }
    },
  });
  setInterval(() => document.querySelectorAll(".tk-time[data-t]").forEach((el) => {
    const o = [...orders.values()].find((x) => x.created_at === el.dataset.t); if (!o) return;
    const m = mins(o); el.textContent = bn(m) + " মি";
    el.className = "tk-time" + (o.status !== "served" ? (m >= 10 ? " w2" : m >= 5 ? " w1" : "") : "");
  }), 20000);
  empty(); loadAll();
})();

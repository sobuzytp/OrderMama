/* কমন হেল্পার: fetch + CSRF, DOM বিল্ডার, টোস্ট, মডাল, ফরম্যাট। ইউজার-ডেটা সবসময় textContent দিয়ে বসে। */
(function () {
  const BN = "০১২৩৪৫৬৭৮৯";
  const OM = (window.OM = {});

  OM.bn = (v) => String(v).replace(/\d/g, (d) => BN[d]);
  OM.money = (v) => {
    const n = Number(v) || 0;
    const s = Number.isInteger(n) ? n.toLocaleString("en-US") : n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    return "৳" + OM.bn(s);
  };
  OM.date = (iso) => {
    if (!iso) return "—";
    return OM.bn(new Date(iso).toLocaleDateString("bn-BD", { day: "numeric", month: "short", year: "numeric" }));
  };
  OM.dateTime = (iso) => OM.bn(new Date(iso).toLocaleString("bn-BD", { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" }));

  OM.cookie = (name) => {
    const m = document.cookie.match(new RegExp("(?:^|; )" + name + "=([^;]*)"));
    return m ? decodeURIComponent(m[1]) : "";
  };

  /** h("div.cls#id", {attr}, child...) — নিরাপদ DOM বিল্ডার */
  OM.h = function (tag, attrs, ...kids) {
    const m = tag.match(/^([a-z0-9]+)((?:[.#][\w-]+)*)$/i);
    const el = document.createElement(m ? m[1] : tag);
    if (m && m[2]) {
      m[2].replace(/([.#])([\w-]+)/g, (_, t, n) => (t === "." ? el.classList.add(n) : (el.id = n)));
    }
    if (attrs && typeof attrs === "object" && !(attrs instanceof Node) && !Array.isArray(attrs)) {
      for (const [k, v] of Object.entries(attrs)) {
        if (v === false || v == null) continue;
        if (k.startsWith("on") && typeof v === "function") el.addEventListener(k.slice(2), v);
        else if (k === "text") el.textContent = v;
        else if (k === "dataset") Object.assign(el.dataset, v);
        else if (k in el && k !== "list" && k !== "form" && typeof v !== "object" && !k.includes("-")) el[k] = v;
        else el.setAttribute(k, v === true ? "" : v);
      }
    } else if (attrs != null) kids.unshift(attrs);
    OM.append(el, kids);
    return el;
  };
  OM.append = (el, kids) => {
    for (const k of kids.flat(Infinity)) {
      if (k == null || k === false) continue;
      el.append(k instanceof Node ? k : document.createTextNode(String(k)));
    }
    return el;
  };
  OM.clear = (el) => { while (el.firstChild) el.removeChild(el.firstChild); return el; };
  OM.icon = (name, cls) => {
    const i = document.createElement("i");
    i.setAttribute("data-lucide", name);
    i.className = "i" + (cls ? " " + cls : "");
    return i;
  };
  OM.refreshIcons = () => { if (window.lucide) window.lucide.createIcons({ attrs: { class: "i" } }); };

  /* ---------- API ---------- */
  OM.api = async function (url, opts = {}) {
    const o = { method: "GET", headers: {}, credentials: "same-origin", ...opts };
    o.headers = { Accept: "application/json", ...(opts.headers || {}) };
    if (o.method !== "GET") o.headers["X-CSRFToken"] = OM.cookie("csrftoken");
    if (o.json !== undefined) {
      o.body = JSON.stringify(o.json);
      o.headers["Content-Type"] = "application/json";
    }
    let res;
    try {
      res = await fetch(url, o);
    } catch (e) {
      const err = new Error("ইন্টারনেট সংযোগ নেই বা সার্ভারে পৌঁছানো যাচ্ছে না।");
      err.status = 0;
      throw err;
    }
    let data = null;
    if (res.status !== 204) {
      const ct = res.headers.get("content-type") || "";
      data = ct.includes("json") ? await res.json().catch(() => null) : null;
    }
    if (!res.ok) {
      const err = new Error(OM.errMsg(data, res.status));
      err.status = res.status;
      err.data = data;
      throw err;
    }
    return data;
  };
  OM.errMsg = (data, status) => {
    if (status === 401 || (status === 403 && data && /credentials|authentication/i.test(data.detail || ""))) return "সেশন শেষ। আবার লগইন করুন।";
    if (data && typeof data === "object") {
      if (data.detail) return String(data.detail);
      const parts = [];
      for (const [k, v] of Object.entries(data)) parts.push((Array.isArray(v) ? v : [v]).join(" "));
      if (parts.length) return parts.join(" ");
    }
    if (status === 429) return "অনেক বেশি অনুরোধ। একটু পরে চেষ্টা করুন।";
    if (status >= 500) return "সার্ভারে সমস্যা হয়েছে। একটু পরে আবার চেষ্টা করুন।";
    return "কাজটি করা যায়নি।";
  };
  /** ফিল্ড-ভিত্তিক এরর (DRF 400) বের করে */
  OM.fieldErrors = (err) => (err && err.data && typeof err.data === "object" ? err.data : {});

  /* ---------- টোস্ট ---------- */
  OM.toast = (msg, kind) => {
    let box = document.getElementById("toasts");
    if (!box) {
      box = OM.h("div#toasts.toasts", { "aria-live": "polite", role: "status" });
      document.body.append(box);
    }
    const t = OM.h("div.toast" + (kind ? "." + kind : ""), msg);
    box.append(t);
    setTimeout(() => t.remove(), kind === "bad" ? 6500 : 3500);
  };
  OM.fail = (e) => {
    OM.toast(e.message || "কাজটি করা যায়নি।", "bad");
    if (e.status === 402) setTimeout(() => (location.href = "/merchant/billing/"), 1800);
  };

  /* ---------- মডাল (native dialog) ---------- */
  OM.modal = function (title, body, actions) {
    const dlg = OM.h("dialog.modal", { "aria-labelledby": "md-title" });
    const inner = OM.h("div.modal-in", OM.h("h2#md-title", title), body);
    if (actions) inner.append(OM.h("div.modal-actions", actions));
    dlg.append(inner);
    dlg.addEventListener("close", () => dlg.remove());
    document.body.append(dlg);
    dlg.showModal();
    return dlg;
  };
  OM.confirm = (msg, { ok = "নিশ্চিত করুন", danger = false, title = "আপনি কি নিশ্চিত?" } = {}) =>
    new Promise((resolve) => {
      let done = false;
      const fin = (v) => { if (!done) { done = true; resolve(v); } };
      const dlg = OM.modal(title, OM.h("p", msg), [
        OM.h("button.btn", { type: "button", onclick: () => dlg.close() }, "বাতিল"),
        OM.h("button.btn" + (danger ? ".danger" : ".primary"), { type: "button", onclick: () => { fin(true); dlg.close(); } }, ok),
      ]);
      dlg.addEventListener("close", () => fin(false));
    });
  OM.prompt = (title, label, { type = "text", ok = "সংরক্ষণ", value = "" } = {}) =>
    new Promise((resolve) => {
      let done = false;
      const inp = OM.h("input.inp", { type, value, id: "pr-in", autocomplete: "off" });
      const form = OM.h("form", { onsubmit: (e) => { e.preventDefault(); done = true; resolve(inp.value); dlg.close(); } },
        OM.h("div.field", OM.h("label", { for: "pr-in" }, label), inp),
        OM.h("div.modal-actions",
          OM.h("button.btn", { type: "button", onclick: () => dlg.close() }, "বাতিল"),
          OM.h("button.btn.primary", { type: "submit" }, ok)));
      const dlg = OM.modal(title, form);
      dlg.addEventListener("close", () => { if (!done) resolve(null); });
      inp.focus();
    });

  /* ---------- অন্যান্য ---------- */
  OM.skeleton = (n = 3, h = 72) => {
    const w = OM.h("div", { style: "display:grid;gap:12px" });
    for (let i = 0; i < n; i++) w.append(OM.h("div.skel", { style: `min-height:${h}px` }));
    return w;
  };
  OM.empty = (icon, title, text, extra) =>
    OM.h("div.empty", OM.icon(icon), OM.h("b", title), text ? OM.h("p", text) : null, extra || null);
  OM.errorBox = (msg, retry) =>
    OM.h("div.empty", OM.icon("triangle-alert"), OM.h("b", "লোড করা যায়নি"), OM.h("p", msg),
      retry ? OM.h("button.btn", { onclick: retry }, "আবার চেষ্টা করুন") : null);
  OM.debounce = (fn, ms) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };

  /** রিকানেক্টিং WebSocket। onmsg(data), onstate(bool), onopen-এ কলার রি-ফেচ করবে। */
  OM.socket = function (path, { onmsg, onstate, onopen }) {
    let ws, tries = 0, closed = false, ping;
    const connect = () => {
      const proto = location.protocol === "https:" ? "wss" : "ws";
      ws = new WebSocket(`${proto}://${location.host}${path}`);
      ws.onopen = () => {
        tries = 0; onstate && onstate(true); onopen && onopen();
        ping = setInterval(() => { try { ws.send('{"type":"ping"}'); } catch (e) {} }, 25000);
      };
      ws.onmessage = (e) => { try { const d = JSON.parse(e.data); if (d.type !== "pong") onmsg(d); } catch (_) {} };
      ws.onclose = (e) => {
        clearInterval(ping); onstate && onstate(false);
        if (closed || e.code === 4403) { if (e.code === 4403) onstate && onstate(false, true); return; }
        setTimeout(connect, Math.min(15000, 800 * 2 ** tries++));
      };
    };
    connect();
    return { close() { closed = true; ws && ws.close(); } };
  };

  document.addEventListener("DOMContentLoaded", () => OM.refreshIcons());
})();

/* কাস্টমার পেজের কমন হেল্পার। ইউজার-ডেটা সবসময় textContent দিয়ে বসে (XSS-নিরাপদ)। */
(function () {
  const BN = "০১২৩৪৫৬৭৮৯";
  const OMC = (window.OMC = {});
  OMC.boot = JSON.parse(document.getElementById("boot").textContent);
  OMC.bn = (v) => String(v).replace(/\d/g, (d) => BN[d]);
  OMC.money = (v) => {
    const n = Number(v) || 0;
    const s = Number.isInteger(n) ? String(n) : n.toFixed(2);
    return "৳" + OMC.bn(s.replace(/\B(?=(\d{3})+(?!\d))/g, ","));
  };
  OMC.time = (iso) => OMC.bn(new Date(iso).toLocaleTimeString("bn-BD", { hour: "numeric", minute: "2-digit" }));

  /** h("div.cls#id", {attr}, ...children) */
  OMC.h = function (tag, attrs, ...kids) {
    const m = tag.match(/^([a-z0-9]+)((?:[.#][\w-]+)*)$/i);
    const el = document.createElement(m[1]);
    (m[2] || "").replace(/([.#])([\w-]+)/g, (_, t, n) => (t === "." ? el.classList.add(n) : (el.id = n)));
    if (attrs && typeof attrs === "object" && !(attrs instanceof Node) && !Array.isArray(attrs)) {
      for (const [k, v] of Object.entries(attrs)) {
        if (v === false || v == null) continue;
        if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
        else if (k === "style") el.setAttribute("style", v);
        else if (k === "value" || k === "checked" || k === "disabled") el[k] = v;
        else el.setAttribute(k, v === true ? "" : v);
      }
    } else if (attrs != null) kids.unshift(attrs);
    for (const k of kids.flat(Infinity)) {
      if (k == null || k === false) continue;
      el.append(k instanceof Node ? k : document.createTextNode(String(k)));
    }
    return el;
  };
  OMC.icon = (name) => { const i = document.createElement("i"); i.setAttribute("data-lucide", name); return i; };
  OMC.icons = () => { try { window.lucide && window.lucide.createIcons(); } catch (e) {} };
  OMC.clear = (el) => { while (el.firstChild) el.removeChild(el.firstChild); return el; };

  OMC.toast = (msg, bad) => {
    const box = document.getElementById("toasts");
    const t = OMC.h("div.toast" + (bad ? ".err" : ""), msg);
    box.append(t);
    setTimeout(() => { t.classList.add("out"); setTimeout(() => t.remove(), 260); }, bad ? 5200 : 3000);
  };

  OMC.store = {
    get(k, d) { try { const v = localStorage.getItem(k); return v == null ? d : JSON.parse(v); } catch (e) { return d; } },
    set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} },
  };

  /** টেবিল-সেশন টোকেনসহ fetch; ৪০১ হলে টোকেন নবায়ন করে একবার রিট্রাই */
  OMC.api = async function (url, { method = "GET", json, retry = true } = {}) {
    const headers = { Accept: "application/json" };
    if (OMC.boot.token) headers["X-Table-Session"] = OMC.boot.token;
    let body;
    if (json !== undefined) { body = JSON.stringify(json); headers["Content-Type"] = "application/json"; }
    let res;
    try { res = await fetch(url, { method, headers, body, credentials: "omit" }); }
    catch (e) { const er = new Error("ইন্টারনেট সংযোগ নেই। আবার চেষ্টা করুন।"); er.status = 0; throw er; }
    if (res.status === 401 && retry && OMC.boot.api.session) {
      const r2 = await fetch(OMC.boot.api.session, { method: "POST", headers: { Accept: "application/json" } });
      if (r2.ok) { OMC.boot.token = (await r2.json()).token; OMC.onToken && OMC.onToken(); return OMC.api(url, { method, json, retry: false }); }
    }
    const data = res.status === 204 ? null : await res.json().catch(() => null);
    if (!res.ok) {
      const er = new Error(OMC.errText(data, res.status));
      er.status = res.status; er.data = data;
      throw er;
    }
    return data;
  };
  OMC.errText = (d, status) => {
    if (status === 429) return "একটু পরে চেষ্টা করুন — অনেক বেশি অনুরোধ হয়ে গেছে।";
    if (status >= 500) return "সার্ভারে সমস্যা হয়েছে। একটু পরে আবার চেষ্টা করুন।";
    if (d && typeof d === "object") {
      if (d.detail) return String(d.detail);
      const parts = [];
      for (const v of Object.values(d)) parts.push(Array.isArray(v) ? v.map((x) => (typeof x === "object" ? Object.values(x).flat().join(" ") : x)).join(" ") : String(v));
      if (parts.length) return parts.join(" ");
    }
    return "কাজটি করা যায়নি।";
  };

  /* শিট (dialog) */
  OMC.openSheet = (dlg) => { if (!dlg.open) { dlg.showModal(); document.body.classList.add("lock"); } };
  document.querySelectorAll("dialog.sheet").forEach((d) => {
    d.addEventListener("close", () => document.body.classList.remove("lock"));
    d.addEventListener("click", (e) => { if (e.target === d) d.close(); });
    d.querySelectorAll("[data-close]").forEach((b) => b.addEventListener("click", () => d.close()));
  });
})();

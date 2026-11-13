/* মেনু, কার্ট শিট ও অর্ডার সাবমিট — পুরো কাস্টমার ফ্লো এখানে জোড়া লাগে। */
(function () {
  const { h, bn, money, boot } = OMC;
  const $ = (id) => document.getElementById(id);
  const hasTable = !!boot.table || !!boot.api.orders;
  const state = { cats: [], byId: new Map(), orderingOn: false, vat: 0, svc: 0, q: "", kind: "all", sheetOpen: false };
  const menuEl = $("menu"), chipsTrack = $("chipsTrack"), chipsNav = $("chips"), dock = $("dock");
  const cartSheet = $("cartSheet"), cartBody = $("cartBody"), cartFoot = $("cartFoot");
  let firstRender = true, observer;

  /* ---------- লোড ---------- */
  async function loadMenu(silent) {
    try {
      const d = await OMC.api(boot.api.menu);
      state.cats = d.categories;
      state.orderingOn = hasTable && d.ordering_enabled;
      OMC.orderingOn = state.orderingOn;
      state.vat = Number(d.vat_percent) || 0;
      state.svc = Number(d.service_charge_percent) || 0;
      state.byId = new Map(d.categories.flatMap((c) => c.items.map((i) => [i.id, i])));
      const gone = OMC.cart.prune(state.byId);
      if (gone.length) OMC.toast(`“${gone.join("”, “")}” এখন পাওয়া যাচ্ছে না, কার্ট থেকে সরানো হয়েছে।`, true);
      renderMenu(); renderDock(); OMC.orders && OMC.orders.rerender();
      if (hasTable && !state.orderingOn) showNotice("এই রেস্টুরেন্টে এখন অনলাইন অর্ডার চালু নেই। মেনু দেখে ওয়েটারকে অর্ডার জানান।");
      $("serviceRow") && ($("serviceRow").hidden = !state.orderingOn);
    } catch (e) {
      if (silent) return;
      menuEl.setAttribute("aria-busy", "false");
      OMC.clear(menuEl).append(h("div.empty-state", h("div.empty-art", OMC.icon("wifi-off")), h("h3", "মেনু লোড হয়নি"), h("p", e.message),
        h("button.btn.btn-primary", { type: "button", onclick: () => location.reload() }, "আবার চেষ্টা করুন")));
      OMC.icons();
    }
  }
  function showNotice(t) {
    const n = $("notice");
    OMC.clear(n).append(OMC.icon("info"), h("span", t));
    n.hidden = false; OMC.icons();
  }

  /* ---------- মেনু রেন্ডার ---------- */
  function visible(item) {
    if (state.kind === "veg" && !item.is_veg) return false;
    if (state.kind === "nonveg" && item.is_veg) return false;
    if (state.q && !(item.name + " " + item.description).toLowerCase().includes(state.q)) return false;
    return true;
  }
  function priceBlock(i) {
    const kids = [h("span", money(i.price))];
    if (i.discount_percent > 0) {
      kids.push(h("s.old", money(i.compare_at_price)), h("span.off-tag", bn(i.discount_percent) + "% ছাড়"));
    }
    return h("div.dish-price", kids);
  }
  function control(i) {
    if (!state.orderingOn) return null;
    if (i.is_stock_out) return h("span.out-tag", "স্টক নেই");
    const q = OMC.cart.qty(i.id);
    if (!q) return h("button.add-btn", { type: "button", "aria-label": i.name + " কার্টে যোগ করুন", onclick: () => OMC.cart.add(i) }, "যোগ করুন");
    return h("div.stepper", { role: "group", "aria-label": i.name + " পরিমাণ" },
      h("button", { type: "button", "aria-label": "কমান", onclick: () => OMC.cart.dec(i.id) }, "−"),
      h("output", { "aria-live": "polite" }, bn(q)),
      h("button", { type: "button", "aria-label": "বাড়ান", onclick: () => OMC.cart.add(i) }, "+"));
  }
  function dish(i, idx) {
    const media = h("div.dish-media",
      i.image ? h("img", { src: i.image, alt: "", loading: "lazy", width: 120, height: 120 }) : h("div.ph", i.name.slice(0, 1)),
      i.badge ? h("span.tag.tag-" + i.badge, i.badge === "popular" ? "জনপ্রিয়" : "নতুন") : null,
      h("div.shade"), h("div.dish-ctl", control(i)));
    return h("article.dish" + (i.is_stock_out ? ".is-out" : ""), { "data-id": i.id, style: `--i:${idx}` },
      h("div.dish-main",
        h("h3.dish-name", h("span.vmark." + (i.is_veg ? "veg" : "nonveg"), { title: i.is_veg ? "ভেজ" : "নন-ভেজ", role: "img", "aria-label": i.is_veg ? "ভেজ" : "নন-ভেজ" }), i.name),
        i.description ? h("p.dish-desc", i.description) : null, priceBlock(i)),
      media);
  }
  function renderMenu() {
    menuEl.setAttribute("aria-busy", "false");
    OMC.clear(menuEl); OMC.clear(chipsTrack);
    if (observer) observer.disconnect();
    let n = 0, any = false;
    const secs = [];
    state.cats.forEach((c) => {
      const items = c.items.filter(visible);
      if (!items.length) return;
      any = true;
      const sec = h("section.cat", { id: "cat-" + c.id, "data-cat": c.id }, h("h2", c.name), items.map((i) => dish(i, n++)));
      menuEl.append(sec); secs.push(sec);
      chipsTrack.append(h("button.chip", { type: "button", "data-cat": c.id, "aria-current": "false",
        onclick: () => sec.scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" }) }, c.name));
    });
    if (!any) {
      menuEl.append(h("div.empty-state", h("div.empty-art", OMC.icon("utensils-crossed")),
        h("h3", state.q || state.kind !== "all" ? "কিছু পাওয়া যায়নি" : "মেনু এখনো সাজানো হয়নি"),
        h("p", state.q || state.kind !== "all" ? "অন্য শব্দে খুঁজুন বা ফিল্টার বদলান।" : "রেস্টুরেন্ট শিগগিরই খাবার যোগ করবে।")));
    }
    if (firstRender) { menuEl.classList.add("enter"); setTimeout(() => menuEl.classList.remove("enter"), 1600); firstRender = false; }
    else menuEl.classList.remove("enter");
    observeCats(secs);
    OMC.icons();
  }
  function setCurrent(id) {
    chipsTrack.querySelectorAll(".chip").forEach((c) => {
      const on = c.dataset.cat === String(id);
      c.setAttribute("aria-current", on ? "true" : "false");
      if (on) { const r = c.getBoundingClientRect(), p = chipsTrack.getBoundingClientRect();
        if (r.left < p.left || r.right > p.right) chipsTrack.scrollTo({ left: c.offsetLeft - 24, behavior: "smooth" }); }
    });
  }
  function observeCats(secs) {
    if (!("IntersectionObserver" in window) || !secs.length) return;
    observer = new IntersectionObserver((es) => {
      es.forEach((e) => { if (e.isIntersecting) setCurrent(e.target.dataset.cat); });
    }, { rootMargin: "-110px 0px -65% 0px" });
    secs.forEach((s) => observer.observe(s));
    setCurrent(secs[0].dataset.cat);
  }
  /** শুধু একটি আইটেমের কন্ট্রোল হালনাগাদ (পুরো মেনু রি-রেন্ডার ছাড়া) */
  function refreshControls() {
    menuEl.querySelectorAll(".dish").forEach((el) => {
      const i = state.byId.get(Number(el.dataset.id));
      if (!i) return;
      const ctl = el.querySelector(".dish-ctl");
      const key = i.is_stock_out ? "o" : OMC.cart.qty(i.id);
      if (ctl.dataset.k === String(key)) return;
      const grew = ctl.dataset.k !== undefined && Number(key) > Number(ctl.dataset.k || 0);
      ctl.dataset.k = key;
      OMC.clear(ctl).append(control(i) || "");
      if (grew) { const b = ctl.firstElementChild; b && b.classList.add("bump"); }
    });
  }

  /* ---------- ফিল্টার ---------- */
  $("q").addEventListener("input", (e) => { state.q = e.target.value.trim().toLowerCase(); renderMenu(); });
  document.querySelectorAll(".seg button").forEach((b) => b.addEventListener("click", () => {
    state.kind = b.dataset.v;
    document.querySelectorAll(".seg button").forEach((x) => x.setAttribute("aria-checked", String(x === b)));
    renderMenu();
  }));
  addEventListener("scroll", () => chipsNav.classList.toggle("stuck", chipsNav.getBoundingClientRect().top <= 0), { passive: true });

  /* ---------- নিচের ডক ---------- */
  let lastCount = 0;
  function renderDock() {
    if (!state.orderingOn) { dock.hidden = true; return; }
    const count = OMC.cart.count(), has = OMC.orders.total() > 0;
    if (!count && !has) { dock.hidden = true; lastCount = 0; return; }
    const active = OMC.orders.active();
    OMC.clear(dock);
    if (has) {
      const b = h("button.ticket-btn" + (count ? "" : ".wide"), { type: "button", onclick: () => OMC.orders.open(), "aria-label": "আমার অর্ডার দেখুন" },
        OMC.icon("receipt-text"), count ? null : h("span", "আমার অর্ডার"), active ? h("span.badge", bn(active)) : null);
      dock.append(b);
    }
    if (count) {
      const bar = h("button.cart-bar" + (count !== lastCount ? ".bump" : ""), { type: "button", onclick: openCart, "aria-label": "কার্ট খুলুন" },
        h("span.sum", h("b", h("span.tick", { key: count }, bn(count)), "টি আইটেম · " + money(OMC.cart.subtotal())), h("small", "ভ্যাট/চার্জ আলাদা যোগ হবে")),
        h("span.go", "অর্ডার দিন", OMC.icon("arrow-right")));
      dock.append(bar);
    }
    lastCount = count;
    dock.hidden = false; OMC.icons();
  }

  /* ---------- কার্ট শিট ---------- */
  function totals() {
    const sub = OMC.cart.subtotal();
    const vat = Math.round(sub * state.vat) / 100, svc = Math.round(sub * state.svc) / 100;
    return { sub, vat, svc, total: sub + vat + svc };
  }
  function openCart() { renderCart(); OMC.openSheet(cartSheet); }
  function renderCart() {
    OMC.clear(cartBody); OMC.clear(cartFoot);
    const lines = OMC.cart.lines();
    if (!lines.length) {
      cartBody.append(h("div.cart-empty", h("div.empty-art", OMC.icon("shopping-basket")), h("h3", "কার্ট খালি"), h("p", "মেনু থেকে পছন্দের খাবার যোগ করুন।"),
        h("button.btn.btn-primary", { type: "button", onclick: () => cartSheet.close() }, "মেনুতে ফিরুন")));
      OMC.icons(); return;
    }
    lines.forEach((l) => {
      cartBody.append(h("div.line",
        h("div", h("div.line-name", l.name), h("div.line-price", money(l.price) + " × " + bn(l.qty) + " = " + money(l.price * l.qty))),
        h("div.stepper", h("button", { type: "button", "aria-label": "কমান", onclick: () => OMC.cart.dec(l.id) }, "−"), h("output", bn(l.qty)),
          h("button", { type: "button", "aria-label": "বাড়ান", onclick: () => OMC.cart.add(state.byId.get(l.id) || l) }, "+")),
        h("label.line-note", h("span.sr-only", l.name + " এর রান্নার নোট"),
          h("input", { type: "text", maxlength: 200, placeholder: "রান্নার নোট (যেমন: কম ঝাল, পেঁয়াজ ছাড়া)", value: l.note, oninput: (e) => OMC.cart.note(l.id, e.target.value) }))));
    });
    const t = totals();
    const saved = OMC.store.get("ordermama:customer", { name: "", phone: "" });
    const name = h("input", { type: "text", id: "cName", autocomplete: "name", maxlength: 80, placeholder: "আপনার নাম", value: saved.name, required: true });
    const phone = h("input", { type: "tel", id: "cPhone", autocomplete: "tel", inputmode: "numeric", maxlength: 14, placeholder: "01XXXXXXXXX", value: saved.phone, required: true });
    const nameErr = h("div.err", { id: "nameErr", role: "alert" }), phoneErr = h("div.err", { id: "phoneErr", role: "alert" });
    cartBody.append(h("div.cust", h("h3", "অর্ডারের তথ্য"),
      h("div.field", h("label", { for: "cName" }, "নাম"), name, nameErr),
      h("div.field", h("label", { for: "cPhone" }, "মোবাইল নম্বর"), phone, phoneErr, h("p.fine", "শুধু অর্ডারের জন্য — কোনো অ্যাকাউন্ট বা পাসওয়ার্ড লাগবে না।"))));
    const formErr = h("div.err.form-err", { role: "alert" });
    const submit = h("button.btn.btn-primary.btn-block", { type: "button" }, "অর্ডার পাঠান · " + money(t.total));
    cartFoot.append(
      h("div.totals", h("div", h("span", "সাবটোটাল"), h("span", money(t.sub))),
        state.vat ? h("div", h("span", "ভ্যাট (" + bn(state.vat) + "%)"), h("span", money(t.vat))) : null,
        state.svc ? h("div", h("span", "সার্ভিস চার্জ (" + bn(state.svc) + "%)"), h("span", money(t.svc))) : null,
        h("div.grand", h("span", "মোট"), h("span", money(t.total)))),
      formErr, submit);
    submit.addEventListener("click", async () => {
      nameErr.textContent = phoneErr.textContent = formErr.textContent = "";
      const n = name.value.trim(), p = phone.value.replace(/[\s-]/g, "");
      let bad = false;
      if (!n) { nameErr.textContent = "নাম লিখুন।"; bad = true; }
      if (!/^(?:\+?88)?01[3-9]\d{8}$/.test(p)) { phoneErr.textContent = "সঠিক মোবাইল নম্বর দিন (যেমন 01712345678)।"; bad = true; }
      if (bad) { (nameErr.textContent ? name : phone).focus(); return; }
      submit.setAttribute("aria-busy", "true");
      try {
        const o = await OMC.api(boot.api.orders, { method: "POST", json: {
          customer_name: n, customer_phone: p,
          items: OMC.cart.lines().map((l) => ({ id: l.id, qty: l.qty, note: l.note })),
        } });
        OMC.store.set("ordermama:customer", { name: n, phone: p });
        OMC.cart.clear(); cartSheet.close();
        OMC.orders.add(o);
        OMC.toast("অর্ডার পাঠানো হয়েছে! রান্নাঘর শিগগিরই দেখবে।");
        OMC.orders.open();
      } catch (e) {
        if (e.data && e.data.customer_phone) phoneErr.textContent = [].concat(e.data.customer_phone).join(" ");
        else if (e.data && e.data.customer_name) nameErr.textContent = [].concat(e.data.customer_name).join(" ");
        else formErr.textContent = e.message;
        if (e.status === 400) loadMenu(true); // স্টক-আউট হলে মেনু হালনাগাদ
      } finally { submit.removeAttribute("aria-busy"); }
    });
    OMC.icons();
  }

  /* ---------- ওয়েটার / বিল ---------- */
  async function service(btn, url, okMsg) {
    btn.setAttribute("aria-busy", "true");
    try { const d = await OMC.api(url, { method: "POST", json: {} }); OMC.toast(d.detail || okMsg); }
    catch (e) { OMC.toast(e.message, true); }
    finally { btn.removeAttribute("aria-busy"); }
  }
  $("callWaiter") && $("callWaiter").addEventListener("click", (e) => service(e.currentTarget, boot.api.waiter, "ওয়েটারকে জানানো হয়েছে।"));
  $("askBill") && $("askBill").addEventListener("click", (e) => service(e.currentTarget, boot.api.bill, "বিলের অনুরোধ পাঠানো হয়েছে।").then(() => OMC.orders.load()));

  /* ---------- জোড়া লাগানো ---------- */
  OMC.menuIndex = () => state.byId;
  OMC.canReorder = () => state.orderingOn;
  OMC.cart.onChange(() => { refreshControls(); renderDock(); if (cartSheet.open) renderCart(); });
  OMC.orders.onChange(renderDock);
  const debouncedMenu = (() => { let t; return () => { clearTimeout(t); t = setTimeout(() => loadMenu(true), 250); }; })();
  if (hasTable) {
    OMC.live({
      onstate: OMC.orders.setState,
      onopen: () => { OMC.orders.load(); loadMenu(true); },
      onmsg: (m) => { if (m.type === "order.update") OMC.orders.upsert(m.order); else if (m.type === "menu.change") debouncedMenu(); },
    });
    OMC.orders.load();
  }
  loadMenu();
})();

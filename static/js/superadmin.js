(function () {
  const { h, bn, money } = OM;
  const page = document.body.dataset.page;
  const $ = (id) => document.getElementById(id);
  const STATE = { active: ["ok", "সক্রিয়"], expiring: ["warn", "শিগগির শেষ"], grace: ["warn", "গ্রেস পিরিয়ড"], expired: ["bad", "মেয়াদ শেষ"], none: ["", "সাবস্ক্রিপশন নেই"] };

  /* ---------- ওভারভিউ ---------- */
  function drawIncome(list) {
    const box = $("income");
    if (!box) return;
    OM.clear(box);
    if (!list.length) { box.append(OM.empty("banknote", "এখনো আয়ের রেকর্ড নেই", "পেমেন্ট অনুমোদন হলে এখানে মাসিক আয় দেখা যাবে।")); OM.refreshIcons(); return; }
    const max = Math.max(1, ...list.map((m) => Number(m.total) || 0));
    list.forEach((m) => {
      const [y, mo] = m.label.split("-");
      const name = new Date(Number(y), Number(mo) - 1, 1).toLocaleDateString("bn-BD", { month: "long", year: "numeric" });
      box.append(h("div.row-b", h("span", name), h("div.bar", h("i", { style: `width:${((Number(m.total) || 0) / max) * 100}%` })),
        h("b.num", money(m.total), h("em.hint", { style: "display:block;font-weight:400" }, bn(m.count) + "টি পেমেন্ট"))));
    });
  }
  async function home() {
    try {
      const d = await OM.api("/api/sa/stats/");
      const ok = (v, t) => h("span" + (v ? "" : ".down"), h("i"), t + (v ? " সচল" : " সমস্যা"));
      OM.clear($("health")).append(ok(d.health.database, "ডেটাবেজ"), ok(d.health.realtime, "রিয়েল-টাইম"));
      const c = (l, v, s) => h("div.stat", h("span", l), h("b.num", v), h("em", s || ""));
      OM.clear($("stats")).append(c("মোট রেস্টুরেন্ট", bn(d.restaurants), bn(d.active) + "টি সক্রিয়"), c("অনুমোদনের অপেক্ষায়", bn(d.pending), d.pending ? "পর্যালোচনা দরকার" : "সব ঠিক আছে"),
        c("আয় (৩০ দিন)", money(d.revenue_30d), "মোট " + money(d.revenue_total)), c("স্থগিত", bn(d.blocked)));
      drawIncome(d.monthly_income || []);
      if (d.pending_payments > 0) $("payAlert").hidden = false, $("payAlertCount").textContent = bn(d.pending_payments);
      const fill = (id, list, f, empty) => { const ul = $(id); OM.clear(ul); if (!list.length) ul.append(h("li", h("span.hint", empty))); list.forEach((x) => ul.append(h("li", h("b", x.name), h("span.hint", f(x))))); };
      fill("expiring", d.expiring, (x) => (x.days_left <= 0 ? "আজই শেষ" : bn(x.days_left) + " দিন বাকি"), "কেউ নেই");
      fill("grace", d.grace, (x) => OM.date(x.end_date) + " এ শেষ হয়েছে", "কেউ নেই");
      fill("expired", d.expired, (x) => OM.date(x.end_date) + " এ শেষ হয়েছে", "কেউ নেই");
    } catch (e) { OM.clear($("stats")).append(OM.errorBox(e.message, home)); }
  }

  /* ---------- রেস্টুরেন্ট ---------- */
  let all = [], plans = [];
  const statusOf = (r) => (r.is_blocked ? "blocked" : !r.is_approved ? "pending" : r.state);
  async function approve(r) {
    const plan = h("select.inp", { id: "ap" }, plans.map((p) => h("option", { value: p.code, selected: p.code === (r.plan_code || "basic") }, `${p.name} (৳${p.price})`)));
    const days = h("input.inp", { id: "ad", type: "number", min: 1, max: 3650, value: (plans.find((p) => p.code === plan.value) || {}).duration_days || 30 });
    plan.onchange = () => { days.value = (plans.find((p) => p.code === plan.value) || {}).duration_days || 30; };
    const err = h("div.err-text", { role: "alert" });
    const dlg = OM.modal(r.is_approved ? `${r.name} — মেয়াদ বাড়ান` : `${r.name} — অনুমোদন`, h("div", h("p.hint", { style: "margin-bottom:12px" }, r.is_approved ? "দিনগুলো বর্তমান মেয়াদের শেষে যোগ হবে (শেষ হয়ে গেলে আজ থেকে)।" : "অনুমোদনের পর কাস্টমার মেনু সাথে সাথে চালু হবে।"),
      h("div.field", h("label", { for: "ap" }, "প্ল্যান"), plan), h("div.field", h("label", { for: "ad" }, "কত দিন"), days), err),
      [h("button.btn", { type: "button", onclick: () => dlg.close() }, "বাতিল"), h("button.btn.primary", { type: "button", id: "apok" }, r.is_approved ? "মেয়াদ বাড়ান" : "অনুমোদন দিন")]);
    dlg.querySelector("#apok").onclick = async () => {
      try { await OM.api(`/api/sa/restaurants/${r.id}/${r.is_approved ? "extend" : "approve"}/`, { method: "POST", json: { plan: plan.value, days: Number(days.value) } }); dlg.close(); OM.toast("সম্পন্ন", "ok"); loadR(); }
      catch (e) { err.textContent = e.message; }
    };
  }
  async function toggleBlock(r) {
    const to = !r.is_blocked;
    if (!await OM.confirm(to ? `“${r.name}” স্থগিত করলে কাস্টমার মেনু ও স্টাফ ড্যাশবোর্ড সাথে সাথে বন্ধ হবে।` : `“${r.name}” আবার চালু করবেন?`, { ok: to ? "স্থগিত করুন" : "চালু করুন", danger: to })) return;
    try { await OM.api(`/api/sa/restaurants/${r.id}/${to ? "block" : "unblock"}/`, { method: "POST", json: {} }); loadR(); } catch (e) { OM.fail(e); }
  }
  function drawR() {
    const q = $("q").value.trim().toLowerCase(), f = $("f").value, rows = $("rows");
    const list = all.filter((r) => (!q || (r.name + r.slug).toLowerCase().includes(q)) && (!f || statusOf(r) === f));
    OM.clear(rows);
    if (!list.length) rows.append(h("tr", h("td", { colspan: 6 }, OM.empty("store", "কিছু পাওয়া যায়নি", "ফিল্টার বা সার্চ বদলে দেখুন।"))));
    list.forEach((r) => {
      const s = statusOf(r);
      const badge = s === "blocked" ? ["bad", "স্থগিত"] : s === "pending" ? ["info", "অনুমোদনের অপেক্ষায়"] : STATE[r.state] || STATE.none;
      rows.append(h("tr", h("td", h("b", r.name), h("div.hint", "/" + r.slug)), h("td", r.owner || "—", h("div.hint", r.phone)), h("td", r.plan || "—"),
        h("td", r.end_date ? OM.date(r.end_date) : "—", r.days_left != null && r.state !== "expired" ? h("div.hint", bn(r.days_left) + " দিন বাকি") : null),
        h("td", h("span.badge" + (badge[0] ? "." + badge[0] : ""), badge[1])),
        h("td", { style: "text-align:right;white-space:nowrap" },
          h("button.btn.sm" + (r.is_approved ? "" : ".primary"), { type: "button", onclick: () => approve(r) }, r.is_approved ? "মেয়াদ/প্ল্যান" : "অনুমোদন"), " ",
          h("button.btn.sm" + (r.is_blocked ? "" : ".danger"), { type: "button", onclick: () => toggleBlock(r) }, r.is_blocked ? "চালু করুন" : "স্থগিত"))));
    });
  }
  async function loadR() {
    try { [all, plans] = await Promise.all([OM.api("/api/sa/restaurants/"), OM.api("/api/sa/plans/")]); drawR(); }
    catch (e) { OM.clear($("rows")).append(h("tr", h("td", { colspan: 6 }, OM.errorBox(e.message, loadR)))); }
  }

  /* ---------- প্ল্যান ---------- */
  async function loadP() {
    try {
      const list = await OM.api("/api/sa/plans/"), box = $("plans"); OM.clear(box);
      const field = (label, value, type, attrs = {}) => {
        const input = h("input.inp", { type, value, ...attrs });
        return { input, node: h("div.field", h("label", label), input) };
      };
      const add = h("button.btn.primary", { type: "button" }, "+ নতুন প্ল্যান");
      add.onclick = async () => {
        const code = field("প্ল্যান কোড (যেমন starter)", "", "text", { maxlength: 20, required: true });
        const name = field("প্ল্যানের নাম", "", "text", { maxlength: 60, required: true });
        const price = field("দাম (৳)", "0", "number", { min: 0, max: 99999999.99, step: "0.01" });
        const days = field("মেয়াদ (দিন)", "30", "number", { min: 1, max: 3650 });
        const err = h("div.err-text", { role: "alert" });
        const dlg = OM.modal("নতুন সাবস্ক্রিপশন প্ল্যান", h("div", code.node, name.node, h("div.grid2", price.node, days.node),
          h("p.hint", "নতুন প্ল্যানে ফিচারগুলো ডিফল্টভাবে বন্ধ থাকবে। তৈরি করার পর প্রয়োজনমতো চালু করুন।"), err),
          [h("button.btn", { type: "button", onclick: () => dlg.close() }, "বাতিল"),
           h("button.btn.primary", { type: "button", id: "new-plan-save" }, "তৈরি করুন")]);
        dlg.querySelector("#new-plan-save").onclick = async () => {
          try {
            await OM.api("/api/sa/plans/", { method: "POST", json: {
              code: code.input.value.trim().toLowerCase(), name: name.input.value.trim(),
              price: price.input.value, duration_days: Number(days.input.value),
              live_orders: false, qr_generator: false, branding: false, is_active: true
            }});
            dlg.close(); OM.toast("নতুন প্ল্যান তৈরি হয়েছে", "ok"); loadP();
          } catch (e) { err.textContent = e.message; }
        };
      };
      box.append(h("div.page-tools", add));
      list.forEach((p) => {
        const code = h("input.inp", { type: "text", maxlength: 20, value: p.code });
        const name = h("input.inp", { type: "text", maxlength: 60, value: p.name });
        const price = h("input.inp", { type: "number", min: 0, max: 99999999.99, step: "0.01", value: p.price });
        const days = h("input.inp", { type: "number", min: 1, max: 3650, value: p.duration_days });
        const flag = (k, l) => h("label.switch", h("input", { type: "checkbox", checked: p[k], dataset: { k } }), h("i"), l);
        const form = h("div", h("div.field", h("label", "প্ল্যানের নাম"), name),
          h("div.field", h("label", "প্ল্যান কোড"), code),
          h("div.grid2", h("div.field", h("label", "দাম (৳)"), price), h("div.field", h("label", "মেয়াদ (দিন)"), days)),
          h("div", { style: "display:grid;gap:10px;margin-bottom:14px" },
            flag("live_orders", "লাইভ অর্ডার ও KOT"), flag("qr_generator", "QR PDF জেনারেটর"),
            flag("branding", "ব্র্যান্ডিং"), flag("is_active", "বিক্রির জন্য চালু")));
        const save = h("button.btn.primary", { type: "button" }, "সংরক্ষণ");
        save.onclick = async () => {
          const body = { code: code.value.trim().toLowerCase(), name: name.value.trim(),
            price: price.value, duration_days: Number(days.value) };
          form.querySelectorAll("input[data-k]").forEach((c) => (body[c.dataset.k] = c.checked));
          try { await OM.api(`/api/sa/plans/${p.id}/`, { method: "PATCH", json: body }); OM.toast(`${name.value} সংরক্ষিত`, "ok"); loadP(); }
          catch (e) { OM.fail(e); }
        };
        const remove = h("button.btn.sm.danger", { type: "button" }, "মুছুন");
        remove.onclick = async () => {
          if (!await OM.confirm(`“${p.name}” প্ল্যানটি মুছবেন? সাবস্ক্রিপশন/পেমেন্ট যুক্ত থাকলে মুছতে দেবে না।`, { ok: "মুছুন", danger: true })) return;
          try { await OM.api(`/api/sa/plans/${p.id}/`, { method: "DELETE" }); OM.toast("প্ল্যান মুছে ফেলা হয়েছে", "ok"); loadP(); }
          catch (e) { OM.fail(e); }
        };
        box.append(h("article.plan", h("h3", p.name), h("span.hint", "প্ল্যান ID: " + p.id), form,
          h("div.page-tools", save, remove)));
      });
    } catch (e) { OM.clear($("plans")).append(OM.errorBox(e.message, loadP)); }
  }

  /* ---------- পেমেন্ট ---------- */
  async function reviewPayment(p, action) {
    if (action === "reject") {
      const reason = await OM.prompt("পেমেন্ট প্রত্যাখ্যান", "প্রত্যাখ্যানের কারণ লিখুন", { ok: "প্রত্যাখ্যান করুন" });
      if (reason === null) return;
      if (!reason.trim()) { OM.toast("কারণ লেখা বাধ্যতামূলক।", "bad"); return; }
      try { await OM.api(`/api/sa/payments/${p.id}/review/`, { method: "POST", json: { action, reason } }); OM.toast("পেমেন্ট প্রত্যাখ্যান করা হয়েছে", "ok"); loadPay(); }
      catch (e) { OM.fail(e); }
      return;
    }
    if (!await OM.confirm(`${p.restaurant} — ৳${p.amount} পেমেন্টটি যাচাই করে অনুমোদন করবেন? টাকা পাওয়া নিশ্চিত না হলে অনুমোদন দেবেন না।`, { ok: "অনুমোদন দিন" })) return;
    try { await OM.api(`/api/sa/payments/${p.id}/review/`, { method: "POST", json: { action } }); OM.toast("পেমেন্ট অনুমোদিত; সাবস্ক্রিপশন আপডেট হয়েছে", "ok"); loadPay(); }
    catch (e) { OM.fail(e); }
  }
  async function loadPay() {
    try {
      const list = await OM.api("/api/sa/payments/"), rows = $("rows"); OM.clear(rows);
      if (!list.length) rows.append(h("tr", h("td", { colspan: 9 }, OM.empty("banknote", "এখনো কোনো পেমেন্ট নেই"))));
      list.forEach((p) => {
        const labels = { pending: "অপেক্ষমাণ", submitted: "অনুমোদনের অপেক্ষায়", approved: "অনুমোদিত", rejected: "প্রত্যাখ্যাত", paid: "সফল", failed: "ব্যর্থ", cancelled: "বাতিল" };
        const badge = p.status === "paid" || p.status === "approved" ? ".ok" : p.status === "submitted" || p.status === "pending" ? ".warn" : ".bad";
        const actions = p.status === "submitted" && p.gateway === "manual"
          ? h("div", h("button.btn.sm.primary", { type: "button", onclick: () => reviewPayment(p, "approve") }, "অনুমোদন"),
              " ", h("button.btn.sm.danger", { type: "button", onclick: () => reviewPayment(p, "reject") }, "প্রত্যাখ্যান"))
          : "—";
        rows.append(h("tr",
          h("td", OM.date(p.created_at)),
          h("td", h("b", p.restaurant), p.sender_number ? h("div.hint", "Sender: " + p.sender_number) : null),
          h("td", p.plan),
          h("td.num", money(p.amount)),
          h("td", p.method || p.gateway),
          h("td", h("span.badge" + badge, labels[p.status] || p.status), p.rejection_reason ? h("div.hint", p.rejection_reason) : null),
          h("td.hint", p.trx_id || p.tran_id),
          h("td", actions)
        ));
      });
    } catch (e) { OM.clear($("rows")).append(h("tr", h("td", { colspan: 9 }, OM.errorBox(e.message, loadPay)))); }
  }

  if (page === "home") home();
  else if (page === "restaurants") { $("q").oninput = drawR; $("f").onchange = drawR; $("rows").append(h("tr", h("td", { colspan: 6 }, OM.skeleton(3)))); loadR(); }
  else if (page === "plans") loadP();
  else if (page === "payments") loadPay();
})();

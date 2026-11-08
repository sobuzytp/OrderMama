(function () {
  const { h, bn, money } = OM;
  const root = document.getElementById("bills"), conn = document.getElementById("conn"), receipt = document.getElementById("receipt");
  const can = ["owner", "manager"].includes(document.body.dataset.role);
  const LBL = { pending: "পেন্ডিং", accepted: "গৃহীত", preparing: "রান্না হচ্ছে", ready: "রেডি", served: "পরিবেশিত" };

  function printBill(b) {
    OM.clear(receipt).append(h("h2", document.querySelector(".rest-chip").firstChild.textContent.trim()), h("div.c", `টেবিল ${bn(b.table)} · ${OM.dateTime(new Date().toISOString())}`), h("hr"),
      b.orders.flatMap((o) => o.items.map((i) => h("div.l", h("span", `${i.name} × ${bn(i.quantity)}`), h("span", money(i.unit_price * i.quantity))))), h("hr"),
      h("div.l", h("span", "সাবটোটাল"), h("span", money(b.totals.subtotal))),
      Number(b.totals.vat) ? h("div.l", h("span", `ভ্যাট (${bn(b.vat_percent)}%)`), h("span", money(b.totals.vat))) : null,
      Number(b.totals.service_charge) ? h("div.l", h("span", `সার্ভিস চার্জ (${bn(b.service_charge_percent)}%)`), h("span", money(b.totals.service_charge))) : null,
      h("div.l.b", h("span", "মোট"), h("span", money(b.totals.total))), h("hr"), h("div.c", "ধন্যবাদ! আবার আসবেন।"));
    window.print();
  }
  async function pay(b, btn) {
    btn.disabled = true;
    try { await OM.api(`/api/d/bills/${b.id}/pay/`, { method: "POST", json: {} }); OM.toast(`টেবিল ${bn(b.table)} — পরিশোধ নেওয়া হয়েছে`, "ok"); load(); }
    catch (e) {
      btn.disabled = false;
      if (e.status === 409 && can && await OM.confirm("এখনো কিছু অর্ডার পরিবেশিত হয়নি। তবুও পরিশোধিত ধরবেন?", { ok: "হ্যাঁ, পরিশোধিত", danger: true })) {
        try { await OM.api(`/api/d/bills/${b.id}/pay/`, { method: "POST", json: { force: true } }); load(); } catch (e2) { OM.fail(e2); }
      } else OM.fail(e);
    }
  }
  function card(b) {
    const pb = h("button.btn.primary", { type: "button" }, OM.icon("banknote"), "পরিশোধ নেওয়া হয়েছে"); pb.onclick = () => pay(b, pb);
    const t = b.totals;
    return h("article.bill" + (b.status === "requested" ? ".req" : ""),
      h("div.bill-h", h("span.t", "টেবিল " + bn(b.table)), b.status === "requested" ? h("span.badge.warn", "বিল চাওয়া হয়েছে") : null, h("span.sp"), h("span.hint", OM.dateTime(b.opened_at))),
      h("div.bill-b", b.orders.map((o) => h("div.bill-o",
        h("div.who", h("span", `${o.customer_name} · #${bn(o.id)}`), h("span.badge" + (o.status === "served" ? ".ok" : ".info"), LBL[o.status] || o.status)),
        h("ul", o.items.map((i) => h("li", h("span", `${i.name} × ${bn(i.quantity)}`), h("span.num", money(i.unit_price * i.quantity)))))))),
      h("div.sum", h("div", h("span", "সাবটোটাল"), h("span.num", money(t.subtotal))),
        Number(t.vat) ? h("div", h("span", `ভ্যাট (${bn(b.vat_percent)}%)`), h("span.num", money(t.vat))) : null,
        Number(t.service_charge) ? h("div", h("span", `সার্ভিস চার্জ (${bn(b.service_charge_percent)}%)`), h("span.num", money(t.service_charge))) : null,
        h("div.tot", h("span", "মোট"), h("span.num", money(t.total)))),
      h("div.bill-f", h("button.btn", { type: "button", onclick: () => printBill(b) }, OM.icon("printer"), "রিসিট"), pb));
  }
  async function load() {
    try {
      const list = await OM.api("/api/d/bills/");
      list.sort((a, b) => (b.status === "requested") - (a.status === "requested"));
      OM.clear(root);
      if (!list.length) root.append(OM.empty("receipt", "কোনো খোলা বিল নেই", "টেবিল থেকে অর্ডার এলে এখানে বিল জমা হবে।"));
      list.forEach((b) => root.append(card(b)));
      OM.refreshIcons();
    } catch (e) { OM.clear(root).append(OM.errorBox(e.message, load)); }
  }
  root.append(OM.skeleton(3, 200));
  const reload = OM.debounce(load, 300);
  OM.socket("/ws/dashboard/", {
    onstate: (on) => { conn.classList.toggle("on", on); conn.lastChild.textContent = on ? "লাইভ" : "সংযোগ ছিন্ন"; },
    onopen: load, onmsg: (m) => { if (m.type !== "service.new" || m.request.kind === "bill") reload(); },
  });
  load();
})();

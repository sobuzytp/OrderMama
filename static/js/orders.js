/* অর্ডার ট্র্যাকার — কিচেন টিকেটের আদলে। WebSocket দিয়ে লাইভ; সংযোগ না থাকলে ১০s পোলিং। */
(function () {
  const { h, bn, money } = OMC;
  const STEPS = [["pending", "পেন্ডিং"], ["accepted", "গৃহীত"], ["preparing", "রান্না হচ্ছে"], ["ready", "রেডি"], ["served", "পরিবেশিত"]];
  const body = document.getElementById("trackBody");
  const liveState = document.getElementById("liveState");
  const liveText = document.getElementById("liveText");
  const sheet = document.getElementById("trackSheet");
  const subs = [];
  let orders = [], bill = null, connected = false, pollTimer = null;

  const stepIndex = (s) => (s === "paid" ? 4 : Math.max(0, STEPS.findIndex((x) => x[0] === s)));

  function ticket(o) {
    const rejected = o.status === "rejected";
    const idx = stepIndex(o.status);
    const t = h("div.ticket" + (rejected ? ".is-rejected" : ""), { "data-status": o.status, style: `--p:${idx / 4}` },
      h("div.ticket-top",
        h("div", h("span.t-no", "টিকেট #" + bn(o.id)), h("span.t-time", OMC.time(o.created_at) + " · " + o.table_name)),
        h("span.t-status", rejected ? "বাতিল" : o.status === "paid" ? "পরিশোধিত" : o.status_label)),
      h("div.ticket-rule"),
      h("ul.t-items", o.items.map((i) =>
        h("li", h("span.q", bn(i.quantity) + "×"), h("span.n", i.name), i.note ? h("em", "“" + i.note + "”") : null))),
      rejected
        ? h("div.reject-box", h("b", "অর্ডারটি নেওয়া যায়নি"), h("span", o.reject_reason || "রেস্টুরেন্ট অর্ডারটি গ্রহণ করতে পারেনি। ওয়েটারকে জানান।"))
        : h("ol.steps", STEPS.map((s, i) => h("li" + (i < idx ? ".done" : i === idx ? ".now" : ""),
            { "aria-current": i === idx ? "step" : false }, h("span.node"), h("span.lbl", s[1])))),
      h("div.t-foot", h("span", "অর্ডার মোট"), h("b", money(o.subtotal))));
    return h("div.ticket-wrap", { "data-id": o.id }, t);
  }

  function render() {
    OMC.clear(body);
    if (!orders.length) {
      body.append(h("div.cart-empty", h("div.empty-art", OMC.icon("receipt-text")), h("h3", "এখনো কোনো অর্ডার নেই"),
        h("p", "মেনু থেকে খাবার বেছে অর্ডার দিলে এখানে লাইভ অবস্থা দেখতে পাবেন।")));
      OMC.icons();
      return;
    }
    const wrap = h("div.tickets");
    [...orders].reverse().forEach((o) => wrap.append(ticket(o)));
    body.append(wrap);
    if (bill) {
      const asked = bill.status === "requested";
      body.append(h("div.bill-card",
        h("h3", "টেবিলের বিল", h("span.pill", asked ? "বিল চাওয়া হয়েছে" : "চলমান")),
        h("div.totals",
          h("div", h("span", "সাবটোটাল"), h("span", money(bill.subtotal))),
          Number(bill.vat) ? h("div", h("span", "ভ্যাট"), h("span", money(bill.vat))) : null,
          Number(bill.service_charge) ? h("div", h("span", "সার্ভিস চার্জ"), h("span", money(bill.service_charge))) : null,
          h("div.grand", h("span", "মোট"), h("span", money(bill.total)))),
        h("p.fine", "একই টেবিলের সবার অর্ডার এই এক বিলে যোগ হয়।")));
    }
    OMC.icons();
  }

  function setState(on) {
    connected = on;
    liveState.classList.toggle("on", on);
    liveState.classList.toggle("poll", !on);
    liveText.textContent = on ? "লাইভ সংযুক্ত" : "সংযোগ নেই — প্রতি ১০ সেকেন্ডে হালনাগাদ হচ্ছে";
    clearInterval(pollTimer);
    if (!on) pollTimer = setInterval(load, 10000);
  }

  async function load() {
    if (!OMC.boot.api.orders) return;
    try {
      const d = await OMC.api(OMC.boot.api.orders);
      orders = d.orders; bill = d.bill;
      render(); subs.forEach((f) => f());
    } catch (e) { /* পরের পোলে আবার চেষ্টা */ }
  }

  function upsert(o) {
    const i = orders.findIndex((x) => x.id === o.id);
    const prev = i >= 0 ? orders[i] : null;
    if (i >= 0) orders[i] = { ...prev, ...o }; else orders.push(o);
    if (prev && prev.status !== o.status) {
      if (o.status === "ready") OMC.toast("আপনার খাবার রেডি!");
      if (o.status === "rejected") OMC.toast("একটি অর্ডার বাতিল হয়েছে।", true);
    }
    render(); subs.forEach((f) => f());
    // বিলের মোট বদলাতে পারে
    load();
  }

  OMC.orders = {
    active: () => orders.filter((o) => ["pending", "accepted", "preparing", "ready"].includes(o.status)).length,
    total: () => orders.length,
    add: (o) => upsert(o),
    load, setState, upsert,
    open() { load(); OMC.openSheet(sheet); },
    onChange: (f) => subs.push(f),
  };
})();

(function () {
  const { h, bn } = OM;
  const root = document.getElementById("tables");
  async function load() {
    try {
      const list = await OM.api("/api/d/tables/");
      OM.clear(root);
      if (!list.length) root.append(OM.empty("layout-grid", "এখনো কোনো টেবিল নেই", "ওপরে টেবিল সংখ্যা লিখে “টেবিল তৈরি করুন” চাপুন।"));
      list.forEach((t) => {
        const copy = h("button.btn.sm", { type: "button", onclick: async () => { try { await navigator.clipboard.writeText(t.url); OM.toast("লিংক কপি হয়েছে", "ok"); } catch (e) { prompt("লিংক কপি করুন", t.url); } } }, OM.icon("link"), "লিংক");
        const sw = h("input", { type: "checkbox", checked: t.is_active, "aria-label": "টেবিল " + t.number + " চালু" });
        sw.onchange = async () => { try { await OM.api(`/api/d/tables/${t.id}/`, { method: "PATCH", json: { is_active: sw.checked } }); load(); } catch (e) { sw.checked = !sw.checked; OM.fail(e); } };
        const label = h("input.inp", { value: t.label, maxlength: 40, placeholder: "লেবেল (যেমন: ছাদ ৩)", "aria-label": "টেবিল " + t.number + " লেবেল" });
        label.onchange = async () => { try { await OM.api(`/api/d/tables/${t.id}/`, { method: "PATCH", json: { label: label.value.trim() } }); OM.toast("সংরক্ষিত", "ok"); } catch (e) { OM.fail(e); } };
        root.append(h("article.tcard" + (t.is_active ? "" : ".off"), h("div.no", bn(t.number)), label, h("div.url", t.url),
          h("div.row", window.CAN_QR ? h("a.btn.sm", { href: "/api/d/qr/?table=" + t.id, target: "_blank", rel: "noopener" }, OM.icon("qr-code"), "QR PDF") : null, copy),
          h("div.row", { style: "justify-content:space-between" }, h("label.switch", sw, h("i"), "চালু"),
            h("button.btn.sm.danger", { type: "button", onclick: async () => {
              if (!await OM.confirm(`টেবিল ${bn(t.number)} মুছবেন? অর্ডার-ইতিহাস থাকলে শুধু নিষ্ক্রিয় হবে।`, { ok: "মুছুন", danger: true })) return;
              try { await OM.api(`/api/d/tables/${t.id}/`, { method: "DELETE" }); load(); } catch (e) { OM.fail(e); } } }, OM.icon("trash-2")))));
      });
      OM.refreshIcons();
    } catch (e) { OM.clear(root).append(OM.errorBox(e.message, load)); }
  }
  document.getElementById("gen").onclick = async (ev) => {
    const n = parseInt(document.getElementById("count").value, 10);
    if (!(n >= 1 && n <= 200)) return OM.toast("১ থেকে ২০০ এর মধ্যে সংখ্যা দিন।", "bad");
    const btn = ev.currentTarget;
    btn.disabled = true;
    try { const r = await OM.api("/api/d/tables/generate/", { method: "POST", json: { count: n } }); OM.toast(r.created ? `${bn(r.created)}টি নতুন টেবিল তৈরি হয়েছে` : "এই সংখ্যার টেবিল আগেই আছে", "ok"); load(); }
    catch (e) { OM.fail(e); } finally { btn.disabled = false; }
  };
  root.append(OM.skeleton(4, 120)); load();

  /* ---------- টেবিল বোর্ড (খালি / রান্না / বিল বাকি) ---------- */
  const board = document.getElementById("board"), boardSum = document.getElementById("boardSum");
  const STATE = {
    free: ["খালি", "ok"], cooking: ["খাবার আসছে", "warn"], bill: ["বিল বাকি", "info"],
  };
  async function boardLoad() {
    try {
      const d = await OM.api("/api/d/table-board/");
      OM.clear(board);
      if (!d.tables.length) {
        board.append(OM.empty("layout-grid", "কোনো সক্রিয় টেবিল নেই", "উপরে টেবিল তৈরি করুন।"));
        boardSum.textContent = "";
        OM.refreshIcons();
        return;
      }
      d.tables.forEach((t) => {
        const [label, cls] = STATE[t.state];
        board.append(h("article.tb-tile.tb-" + t.state, { title: t.name },
          h("div.tb-no", bn(t.number)),
          h("span.badge." + cls, label),
          t.waiting ? h("span.tb-bell", OM.icon("bell-ring"), "ডাকছে") : null,
          t.state !== "free" ? h("div.tb-meta", bn(t.active) + " চলমান · " + bn(t.served) + " পরিবেশিত") : null,
          t.state !== "free" && Number(t.total) ? h("div.tb-total", OM.money(t.total)) : null));
      });
      boardSum.textContent = `খালি ${bn(d.summary.free)} · চলমান ${bn(d.summary.cooking)} · বিল বাকি ${bn(d.summary.bill)}` +
        (d.summary.waiting ? ` · ডাকছে ${bn(d.summary.waiting)}` : "");
      OM.refreshIcons();
    } catch (e) { OM.clear(board).append(OM.errorBox(e.message, boardLoad)); }
  }
  board.append(OM.skeleton(2, 90));
  boardLoad();
  OM.socket("/ws/dashboard/", {
    onopen: boardLoad,
    onmsg: (m) => { if (m.type === "order.new" || m.type === "order.update" || m.type === "service.new") OM.debounce(boardLoad, 400)(); },
  });
})();

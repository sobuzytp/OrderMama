(function () {
  const { h } = OM;
  const rows = document.getElementById("rows");
  const ROLES = [["manager", "ম্যানেজার"], ["cashier", "ক্যাশিয়ার"], ["kitchen", "কিচেন স্টাফ"], ["waiter", "ওয়েটার"]];
  const rl = (r) => (ROLES.find((x) => x[0] === r) || [0, r])[1];
  async function load() {
    try {
      const list = await OM.api("/api/d/staff/"); OM.clear(rows);
      if (!list.length) rows.append(h("tr", h("td", { colspan: 5 }, OM.empty("users", "এখনো কোনো স্টাফ নেই", "“নতুন স্টাফ” চেপে লগইন তৈরি করুন।"))));
      list.forEach((u) => {
        const sw = h("input", { type: "checkbox", checked: u.is_active, "aria-label": u.username + " সক্রিয়" });
        sw.onchange = async () => { try { await OM.api(`/api/d/staff/${u.id}/`, { method: "PATCH", json: { is_active: sw.checked } }); load(); } catch (e) { sw.checked = !sw.checked; OM.fail(e); } };
        rows.append(h("tr", h("td", h("b", u.username)), h("td", u.first_name || "—"), h("td", h("span.badge.info", rl(u.role))), h("td", h("label.switch", sw, h("i"), u.is_active ? "সক্রিয়" : "বন্ধ")),
          h("td", { style: "text-align:right;white-space:nowrap" },
            h("button.btn.sm", { type: "button", onclick: async () => { const p = await OM.prompt("নতুন পাসওয়ার্ড", `${u.username}-এর জন্য (কমপক্ষে ৮ অক্ষর)`, { type: "password", ok: "বদলান" }); if (!p) return;
              try { await OM.api(`/api/d/staff/${u.id}/`, { method: "PATCH", json: { password: p } }); OM.toast("পাসওয়ার্ড বদলেছে", "ok"); } catch (e) { OM.fail(e); } } }, OM.icon("key-round"), "পাসওয়ার্ড"), " ",
            h("button.btn.sm.danger", { type: "button", "aria-label": u.username + " মুছুন", onclick: async () => { if (!await OM.confirm(`${u.username}-এর অ্যাকাউন্ট মুছে যাবে।`, { ok: "মুছুন", danger: true })) return;
              try { await OM.api(`/api/d/staff/${u.id}/`, { method: "DELETE" }); load(); } catch (e) { OM.fail(e); } } }, OM.icon("trash-2")))));
      });
      OM.refreshIcons();
    } catch (e) { OM.clear(rows).append(h("tr", h("td", { colspan: 5 }, OM.errorBox(e.message, load)))); }
  }
  document.getElementById("add").onclick = () => {
    const f = (id, l, el) => h("div.field", h("label", { for: id }, l), el);
    const un = h("input.inp", { id: "su", autocomplete: "off", required: true, maxlength: 150 }), nm = h("input.inp", { id: "sn", maxlength: 150 });
    const pw = h("input.inp", { id: "sp", type: "password", autocomplete: "new-password", minlength: 8, required: true });
    const role = h("select.inp", { id: "sr" }, ROLES.map((r) => h("option", { value: r[0] }, r[1])));
    const err = h("div.err-text", { role: "alert" });
    const form = h("form", f("su", "ইউজারনেম", un), f("sn", "নাম", nm), f("sr", "রোল", role), f("sp", "পাসওয়ার্ড (কমপক্ষে ৮ অক্ষর)", pw), err);
    const dlg = OM.modal("নতুন স্টাফ", form, [h("button.btn", { type: "button", onclick: () => dlg.close() }, "বাতিল"), h("button.btn.primary", { type: "submit", id: "ssave" }, "তৈরি করুন")]);
    const save = async () => { err.textContent = "";
      try { await OM.api("/api/d/staff/", { method: "POST", json: { username: un.value.trim(), first_name: nm.value.trim(), role: role.value, password: pw.value } }); dlg.close(); OM.toast("স্টাফ তৈরি হয়েছে", "ok"); load(); }
      catch (e) { err.textContent = e.message; } };
    form.onsubmit = (e) => { e.preventDefault(); save(); };
    dlg.querySelector("#ssave").onclick = (e) => { e.preventDefault(); form.reportValidity() && save(); }; un.focus();
  };
  load();
})();

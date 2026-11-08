(function () {
  const { h, bn, money } = OM;
  const catsEl = document.getElementById("cats"), itemsEl = document.getElementById("items");
  let cats = [], items = [], sel = null, q = "";

  const load = async () => {
    try { [cats, items] = await Promise.all([OM.api("/api/d/categories/"), OM.api("/api/d/menu-items/")]); draw(); }
    catch (e) { OM.clear(itemsEl).append(OM.errorBox(e.message, load)); }
  };

  function drawCats() {
    OM.clear(catsEl);
    const all = h("li" + (sel === null ? ".on" : ""), h("button.name", { type: "button", onclick: () => { sel = null; draw(); } }, "সব খাবার ", h("span.hint", bn(items.length))));
    catsEl.append(all);
    cats.forEach((c, i) => catsEl.append(h("li" + (sel === c.id ? ".on" : "") + (c.is_active ? "" : ".off"),
      h("button.name", { type: "button", onclick: () => { sel = c.id; draw(); } }, c.name, " ", h("span.hint", bn(c.items_count))),
      h("div.ctl",
        h("button.btn.icon.sm", { type: "button", title: "ওপরে", "aria-label": c.name + " ওপরে সরান", disabled: i === 0, onclick: () => move(i, -1) }, OM.icon("chevron-up")),
        h("button.btn.icon.sm", { type: "button", title: "নিচে", "aria-label": c.name + " নিচে সরান", disabled: i === cats.length - 1, onclick: () => move(i, 1) }, OM.icon("chevron-down")),
        h("button.btn.icon.sm", { type: "button", title: "সম্পাদনা", "aria-label": c.name + " সম্পাদনা", onclick: () => catForm(c) }, OM.icon("pencil"))))));
    OM.refreshIcons();
  }
  async function move(i, d) {
    const a = cats[i], b = cats[i + d];
    const pa = a.position, pb = b.position === a.position ? a.position + d : b.position;
    try {
      await OM.api(`/api/d/categories/${a.id}/`, { method: "PATCH", json: { position: pb } });
      await OM.api(`/api/d/categories/${b.id}/`, { method: "PATCH", json: { position: pa } });
      load();
    } catch (e) { OM.fail(e); }
  }
  async function catForm(c) {
    const name = h("input.inp", { id: "cn", value: c ? c.name : "", maxlength: 80, required: true });
    const act = c ? h("label.switch", h("input", { type: "checkbox", id: "ca", checked: c.is_active }), h("i"), "কাস্টমারকে দেখান") : null;
    const err = h("div.err-text");
    const form = h("form", h("div.field", h("label", { for: "cn" }, "ক্যাটাগরির নাম"), name, err), act);
    const del = c ? h("button.btn.danger", { type: "button" }, "মুছুন") : null;
    const dlg = OM.modal(c ? "ক্যাটাগরি সম্পাদনা" : "নতুন ক্যাটাগরি", form, [del, h("button.btn", { type: "button", onclick: () => dlg.close() }, "বাতিল"), h("button.btn.primary", { type: "button", id: "catsave" }, "সংরক্ষণ")]);
    if (del) del.onclick = async () => {
      if (!await OM.confirm(`“${c.name}” ও এর সব খাবার মুছে যাবে।`, { ok: "মুছে ফেলুন", danger: true })) return;
      try { await OM.api(`/api/d/categories/${c.id}/`, { method: "DELETE" }); if (sel === c.id) sel = null; dlg.close(); load(); } catch (e) { OM.fail(e); }
    };
    const save = async () => {
      err.textContent = "";
      try {
        const body = { name: name.value.trim() }; if (c) body.is_active = form.querySelector("#ca").checked;
        await OM.api(c ? `/api/d/categories/${c.id}/` : "/api/d/categories/", { method: c ? "PATCH" : "POST", json: body });
        dlg.close(); OM.toast("সংরক্ষিত হয়েছে", "ok"); load();
      } catch (e) { err.textContent = e.message; }
    };
    dlg.querySelector("#catsave").onclick = save; form.onsubmit = (e) => { e.preventDefault(); save(); }; name.focus();
  }

  function drawItems() {
    OM.clear(itemsEl);
    const list = items.filter((i) => (sel === null || i.category === sel) && (!q || (i.name + i.description).toLowerCase().includes(q)));
    if (!cats.length) return itemsEl.append(OM.empty("folder-plus", "প্রথমে একটি ক্যাটাগরি বানান", "যেমন: বিরিয়ানি, ড্রিংকস।", h("button.btn.primary", { type: "button", onclick: () => catForm() }, "ক্যাটাগরি যোগ করুন")));
    if (!list.length) return itemsEl.append(OM.empty("utensils", "কোনো খাবার নেই", q ? "অন্য শব্দে খুঁজুন।" : "“নতুন খাবার” চেপে মেনু সাজান।"));
    list.forEach((i) => {
      const sw = h("input", { type: "checkbox", checked: !i.is_stock_out, "aria-label": i.name + " স্টকে আছে" });
      sw.onchange = async () => {
        try { Object.assign(i, await OM.api(`/api/d/menu-items/${i.id}/`, { method: "PATCH", json: { is_stock_out: !sw.checked } })); OM.toast(i.is_stock_out ? `“${i.name}” স্টক আউট` : `“${i.name}” আবার স্টকে`, "ok"); drawItems(); }
        catch (e) { sw.checked = !sw.checked; OM.fail(e); }
      };
      itemsEl.append(h("article.item" + (i.is_stock_out ? ".out" : ""),
        i.image_url ? h("img.ph", { src: i.image_url, alt: "", loading: "lazy" }) : h("div.ph", i.name.slice(0, 1)),
        h("div", h("h3", h("span.veg" + (i.is_veg ? "" : ".non"), { title: i.is_veg ? "ভেজ" : "নন-ভেজ" }), i.name),
          h("div.pr", money(i.price), i.compare_at_price ? h("s.hint", { style: "margin-left:8px;font-weight:400" }, money(i.compare_at_price)) : null),
          !i.is_active ? h("span.badge", "লুকানো") : null),
        h("div.ctl", h("label.switch", sw, h("i"), i.is_stock_out ? "স্টক নেই" : "স্টকে আছে"),
          h("span", h("button.btn.sm", { type: "button", onclick: () => itemForm(i) }, OM.icon("pencil"), "এডিট")))));
    });
    OM.refreshIcons();
  }
  function draw() { drawCats(); drawItems(); }

  function itemForm(it) {
    if (!cats.length) return catForm();
    const f = (id, label, el, hint) => h("div.field", h("label", { for: id }, label), el, hint ? h("small", hint) : null, h("div.err-text", { id: id + "-e" }));
    const name = h("input.inp", { id: "in", value: it ? it.name : "", maxlength: 120, required: true });
    const desc = h("input.inp", { id: "id", value: it ? it.description : "", maxlength: 300 });
    const cat = h("select.inp", { id: "ic" }, cats.map((c) => h("option", { value: c.id, selected: it ? c.id === it.category : c.id === (sel ?? cats[0].id) }, c.name)));
    const price = h("input.inp", { id: "ip", type: "number", min: 0, step: "0.01", value: it ? it.price : "", required: true });
    const cmp = h("input.inp", { id: "icp", type: "number", min: 0, step: "0.01", value: it && it.compare_at_price ? it.compare_at_price : "" });
    const veg = h("input", { type: "checkbox", checked: it ? it.is_veg : false });
    const act = h("input", { type: "checkbox", checked: it ? it.is_active : true });
    const file = h("input.inp", { id: "ii", type: "file", accept: "image/png,image/jpeg,image/webp" });
    const prev = h("img.preview-img", { alt: "", src: it && it.image_url ? it.image_url : "", hidden: !(it && it.image_url) });
    file.onchange = () => { const f0 = file.files[0]; if (f0) { prev.src = URL.createObjectURL(f0); prev.hidden = false; } };
    const rm = it && it.image_url ? h("input", { type: "checkbox" }) : null;
    const err = h("div.err-text", { role: "alert" });
    const form = h("form", { enctype: "multipart/form-data" }, f("in", "খাবারের নাম", name), f("id", "বিবরণ (ঐচ্ছিক)", desc),
      h("div.grid2", f("ic", "ক্যাটাগরি", cat), f("ip", "দাম (৳)", price)),
      f("icp", "ছাড়ের আগের দাম (ঐচ্ছিক)", cmp, "দামের চেয়ে বেশি হলে কাস্টমার “ছাড়” ব্যাজ দেখবে।"),
      h("div.field", h("label", { for: "ii" }, "ছবি"), prev, file, h("small", "JPG/PNG/WEBP — সার্ভার নিজে ছোট ও কম্প্রেস করে নেবে।"), rm ? h("label.switch", rm, h("i"), "বর্তমান ছবি সরান") : null),
      h("div.row", h("label.switch", veg, h("i"), "ভেজ"), h("label.switch", act, h("i"), "কাস্টমারকে দেখান")), err);
    const del = it ? h("button.btn.danger", { type: "button" }, "মুছুন") : null;
    const dlg = OM.modal(it ? "খাবার সম্পাদনা" : "নতুন খাবার", form, [del, h("button.btn", { type: "button", onclick: () => dlg.close() }, "বাতিল"), h("button.btn.primary", { type: "submit", id: "itemsave" }, "সংরক্ষণ")]);
    if (del) del.onclick = async () => {
      if (!await OM.confirm(`“${it.name}” মেনু থেকে মুছে যাবে।`, { ok: "মুছে ফেলুন", danger: true })) return;
      try { await OM.api(`/api/d/menu-items/${it.id}/`, { method: "DELETE" }); dlg.close(); load(); } catch (e) { OM.fail(e); }
    };
    const save = async () => {
      err.textContent = "";
      const fd = new FormData();
      fd.set("name", name.value.trim()); fd.set("description", desc.value.trim()); fd.set("category", cat.value); fd.set("price", price.value);
      fd.set("compare_at_price", cmp.value); fd.set("is_veg", veg.checked); fd.set("is_active", act.checked);
      if (file.files[0]) fd.set("image", file.files[0]);
      if (rm && rm.checked) fd.set("remove_image", "true");
      if (!cmp.value) fd.delete("compare_at_price");
      try {
        await OM.api(it ? `/api/d/menu-items/${it.id}/` : "/api/d/menu-items/", { method: it ? "PATCH" : "POST", body: fd });
        dlg.close(); OM.toast("সংরক্ষিত হয়েছে", "ok"); load();
      } catch (e) { err.textContent = e.message; }
    };
    form.onsubmit = (e) => { e.preventDefault(); save(); };
    dlg.querySelector("#itemsave").onclick = (e) => { e.preventDefault(); form.reportValidity() && save(); };
    name.focus();
  }

  document.getElementById("addCat").onclick = () => catForm();
  document.getElementById("addItem").onclick = () => itemForm();
  document.getElementById("search").oninput = (e) => { q = e.target.value.trim().toLowerCase(); drawItems(); };
  itemsEl.append(OM.skeleton(4, 110)); load();
})();

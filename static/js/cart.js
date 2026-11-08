/* কার্ট: localStorage-এ জমা (রিলোডে হারায় না)। দাম এখানে শুধু প্রদর্শনের জন্য — আসল দাম সার্ভার ঠিক করে। */
(function () {
  const KEY = `ordermama:${OMC.boot.slug}:cart`;
  let lines = OMC.store.get(KEY, []);
  if (!Array.isArray(lines)) lines = [];
  const subs = [];
  const save = () => { OMC.store.set(KEY, lines); subs.forEach((f) => f()); };
  const find = (id) => lines.find((l) => l.id === id);

  OMC.cart = {
    lines: () => lines,
    qty: (id) => (find(id) ? find(id).qty : 0),
    count: () => lines.reduce((a, l) => a + l.qty, 0),
    subtotal: () => lines.reduce((a, l) => a + l.qty * l.price, 0),
    add(item) {
      const l = find(item.id);
      if (l) l.qty = Math.min(50, l.qty + 1);
      else lines.push({ id: item.id, name: item.name, price: Number(item.price), qty: 1, note: "" });
      save();
    },
    dec(id) {
      const l = find(id);
      if (!l) return;
      l.qty -= 1;
      if (l.qty <= 0) lines = lines.filter((x) => x.id !== id);
      save();
    },
    note(id, text) { const l = find(id); if (l) { l.note = text.slice(0, 200); OMC.store.set(KEY, lines); } },
    remove(id) { lines = lines.filter((l) => l.id !== id); save(); },
    clear() { lines = []; save(); },
    /** মেনু বদলালে: আর নেই / স্টক-আউট আইটেম সরায়, নামের তালিকা ফেরত দেয় */
    prune(menuById) {
      const gone = lines.filter((l) => !menuById.has(l.id) || menuById.get(l.id).is_stock_out);
      if (gone.length) { lines = lines.filter((l) => !gone.includes(l)); save(); }
      // দাম বদলালে হালনাগাদ
      let changed = false;
      lines.forEach((l) => { const m = menuById.get(l.id); if (m && Number(m.price) !== l.price) { l.price = Number(m.price); l.name = m.name; changed = true; } });
      if (changed) save();
      return gone.map((l) => l.name);
    },
    onChange: (f) => subs.push(f),
  };
})();

/* Customer cart: quantities and per-item cooking notes. Prices are display-only;
   the server recalculates every total from the database. */
(() => {
  const cart = {}; // menu item id -> { id, name, price, qty, note }
  const lines = document.querySelector("#lines");
  const totalBox = document.querySelector("#total");
  const field = document.querySelector("#items");
  const form = document.querySelector("#order-form");

  function syncField() {
    field.value = JSON.stringify(
      Object.values(cart).map((x) => ({ id: x.id, qty: x.qty, note: x.note }))
    );
  }

  function draw() {
    lines.innerHTML = "";
    let sum = 0;
    Object.values(cart).forEach((item) => {
      sum += item.price * item.qty;

      const row = document.createElement("div");
      row.className = "cart-line";

      const title = document.createElement("div");
      title.className = "cart-title";
      title.textContent = `${item.name} — ৳${(item.price * item.qty).toFixed(2)}`;

      const controls = document.createElement("div");
      controls.className = "qty";
      const minus = document.createElement("button");
      minus.type = "button";
      minus.textContent = "−";
      minus.onclick = () => change(item.id, -1);
      const qty = document.createElement("span");
      qty.textContent = item.qty;
      const plus = document.createElement("button");
      plus.type = "button";
      plus.textContent = "+";
      plus.onclick = () => change(item.id, +1);
      controls.append(minus, qty, plus);

      const note = document.createElement("input");
      note.className = "cart-note";
      note.placeholder = "রান্নার নির্দেশ (যেমন: কম ঝাল)";
      note.maxLength = 250;
      note.value = item.note;
      note.oninput = () => { item.note = note.value; syncField(); };

      row.append(title, controls, note);
      lines.append(row);
    });
    totalBox.textContent = "৳" + sum.toFixed(2).replace(/\.00$/, "");
    syncField();
  }

  function change(id, delta) {
    const item = cart[id];
    if (!item) return;
    item.qty = Math.min(20, item.qty + delta);
    if (item.qty <= 0) delete cart[id];
    draw();
  }

  document.querySelectorAll(".add").forEach((button) => {
    button.addEventListener("click", () => {
      const id = button.dataset.id;
      cart[id] = cart[id] || { id: +id, name: button.dataset.name, price: +button.dataset.price, qty: 0, note: "" };
      change(id, +1);
    });
  });

  document.querySelector("#search").addEventListener("input", (event) => {
    const q = event.target.value.toLowerCase();
    document.querySelectorAll(".food").forEach((card) => {
      card.hidden = !card.innerText.toLowerCase().includes(q);
    });
  });

  form.addEventListener("submit", (event) => {
    if (!Object.keys(cart).length) {
      event.preventDefault();
      OM.toast("আগে কার্টে খাবার যোগ করুন");
    }
  });

  draw();
})();

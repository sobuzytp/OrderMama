/* Customer order tracking: refreshes the status automatically. */
(() => {
  const root = document.querySelector("#track");
  const label = document.querySelector("#status-label");
  const steps = document.querySelector("#steps");
  const rejected = document.querySelector("#rejected-note");
  const interval = Math.max(2000, +root.dataset.poll || 5000);

  function paint(step) {
    steps.querySelectorAll("li").forEach((li, index) => li.classList.toggle("done", index <= step));
  }

  async function refresh() {
    try {
      const response = await fetch(root.dataset.statusUrl, { headers: { "X-Requested-With": "fetch" } });
      if (!response.ok) throw new Error("bad response");
      const data = await response.json();
      label.textContent = data.label;
      paint(data.step);
      rejected.hidden = !data.rejected;
      if (data.status === "paid" || data.status === "rejected") return; // final state, stop polling
    } catch (error) { /* offline: try again next tick */ }
    setTimeout(refresh, interval);
  }

  paint(+steps.dataset.step || 0);
  setTimeout(refresh, interval);
})();

(function () {
  const { h, bn, money } = OM;
  const stats = document.getElementById("stats"), top = document.getElementById("top"), fb = document.getElementById("fallback"), canvas = document.getElementById("chart");
  let chart = null, period = "daily";
  const NAME = { daily: "গত ৩০ দিনের বিক্রি", weekly: "গত ১২ সপ্তাহের বিক্রি", monthly: "গত ১২ মাসের বিক্রি" };

  function card(label, value, sub) { return h("div.stat", h("span", label), h("b.num", value), h("em", sub || "")); }
  async function load() {
    document.getElementById("chartTitle").textContent = NAME[period];
    try {
      const [d, live] = await Promise.all([OM.api("/api/d/analytics/?period=" + period), OM.api("/api/d/orders/").catch(() => null)]);
      OM.clear(stats).append(
        card("আজকের বিক্রি", money(d.summary.today.total), bn(d.summary.today.orders) + "টি অর্ডার"),
        card("এই সপ্তাহ", money(d.summary.week.total), bn(d.summary.week.orders) + "টি অর্ডার"),
        card("এই মাস", money(d.summary.month.total), bn(d.summary.month.orders) + "টি অর্ডার"),
        live ? card("চলমান অর্ডার", bn(live.filter((o) => o.status !== "served").length), "এখন রান্নাঘরে/অপেক্ষায়") : null);
      drawChart(d.series);
      OM.clear(top);
      const max = Math.max(1, ...d.top_items.map((t) => t.qty));
      if (!d.top_items.length) top.append(OM.empty("chart-column", "এখনো বিক্রির তথ্য নেই", "অর্ডার পরিবেশিত হলে এখানে সেরা খাবারগুলো দেখা যাবে।"));
      d.top_items.forEach((t) => top.append(h("li", h("span", t.name), h("div.bar", h("i", { style: `width:${(t.qty / max) * 100}%` })), h("span.num", `${bn(t.qty)}টি · ${money(t.revenue)}`))));
    } catch (e) { OM.clear(stats).append(OM.errorBox(e.message, load)); }
  }
  function drawChart(series) {
    if (chart) { chart.destroy(); chart = null; }
    const empty = !series.length;
    canvas.parentElement.hidden = !window.Chart || empty; fb.hidden = !!window.Chart && !empty;
    if (empty) { OM.clear(fb).append(OM.empty("chart-line", "এই সময়ে কোনো বিক্রি নেই")); fb.hidden = false; return; }
    if (!window.Chart) { // CDN না পেলে সাধারণ বার
      const max = Math.max(1, ...series.map((s) => s.total));
      OM.clear(fb); series.forEach((s) => fb.append(h("div.row-b", h("span", s.label), h("div.bar", h("i", { style: `width:${(s.total / max) * 100}%` })), h("b.num", money(s.total)))));
      return;
    }
    const css = getComputedStyle(document.documentElement);
    chart = new Chart(canvas, { type: "bar", data: { labels: series.map((s) => s.label), datasets: [{ label: "বিক্রি (৳)", data: series.map((s) => s.total), backgroundColor: css.getPropertyValue("--accent").trim() || "#0B7A6B", borderRadius: 4 }] },
      options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => " " + money(c.parsed.y) } } },
        scales: { y: { beginAtZero: true, ticks: { callback: (v) => "৳" + v } }, x: { ticks: { maxRotation: 0, autoSkip: true } } } } });
  }
  document.querySelectorAll(".seg button").forEach((b) => b.addEventListener("click", () => {
    period = b.dataset.p; document.querySelectorAll(".seg button").forEach((x) => x.setAttribute("aria-pressed", String(x === b))); load();
  }));
  stats.append(OM.skeleton(1, 90));
  window.addEventListener("load", load);
})();

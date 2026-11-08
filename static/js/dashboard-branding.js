(function () {
  const $ = (id) => document.getElementById(id);
  const F = ["name", "primary_color", "secondary_color", "theme", "font_style", "welcome_message", "vat_percent", "service_charge_percent"];
  const pv = $("pv");
  let logoUrl = "", coverUrl = "";
  const HEX = /^#[0-9a-fA-F]{6}$/;

  function paint() {
    const p = $("primary_color").value, s = $("secondary_color").value, dark = $("theme").value === "dark";
    pv.style.setProperty("--primary", p); pv.style.setProperty("--bg", dark ? "#14181D" : s);
    pv.classList.toggle("dark", dark);
    pv.style.setProperty("--pvfont", $("font_style").value === "noto" ? '"Noto Sans Bengali",sans-serif' : '"Hind Siliguri",sans-serif');
    $("pvName").textContent = $("name").value || "রেস্টুরেন্টের নাম";
    $("pvWel").textContent = $("welcome_message").value;
    $("pvCover").style.backgroundImage = coverUrl ? `url("${coverUrl}")` : "none";
    const lg = $("pvLogo");
    lg.style.backgroundImage = logoUrl ? `url("${logoUrl}")` : "none";
    lg.textContent = logoUrl ? "" : ($("name").value || "অ").slice(0, 1);
    $("primary_hex").value = p; $("secondary_hex").value = s;
  }
  ["name", "welcome_message", "theme", "font_style", "primary_color", "secondary_color"].forEach((id) => $(id).addEventListener("input", paint));
  [["primary_hex", "primary_color"], ["secondary_hex", "secondary_color"]].forEach(([h, c]) => $(h).addEventListener("input", (e) => { if (HEX.test(e.target.value)) { $(c).value = e.target.value; paint(); } }));
  [["logo", (u) => (logoUrl = u)], ["cover_image", (u) => (coverUrl = u)]].forEach(([id, set]) => $(id).addEventListener("change", (e) => {
    const f = e.target.files[0]; if (f) { set(URL.createObjectURL(f)); paint(); }
  }));

  async function load() {
    try {
      const d = await OM.api("/api/d/branding/");
      F.forEach((k) => { $(k).value = d[k] ?? ""; });
      logoUrl = d.logo_url; coverUrl = d.cover_url; paint();
    } catch (e) { OM.fail(e); }
  }
  $("form").addEventListener("submit", async (ev) => {
    ev.preventDefault(); $("err").textContent = "";
    const fd = new FormData(); F.forEach((k) => fd.set(k, $(k).value));
    if ($("logo").files[0]) fd.set("logo", $("logo").files[0]);
    if ($("cover_image").files[0]) fd.set("cover_image", $("cover_image").files[0]);
    const btn = ev.submitter; btn && (btn.disabled = true);
    try { const d = await OM.api("/api/d/branding/", { method: "PATCH", body: fd }); logoUrl = d.logo_url; coverUrl = d.cover_url; paint(); OM.toast("ব্র্যান্ডিং সংরক্ষিত হয়েছে", "ok"); }
    catch (e) { $("err").textContent = e.message; OM.fail(e); }
    finally { btn && (btn.disabled = false); }
  });
  load();
})();

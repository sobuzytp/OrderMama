/* রেস্টুরেন্ট রেজিস্টার ফর্ম: /api/register/ এ পাঠায়, ফিল্ড-ভিত্তিক এরর দেখায়। */
(function () {
  const form = document.getElementById("regForm");
  const btn = document.getElementById("regBtn");
  const formErr = document.getElementById("formErr");
  const preview = document.getElementById("slugPreview");
  const slugEl = document.getElementById("slug");
  const nameEl = document.getElementById("restaurant_name");
  const origin = location.origin;

  const slugify = (s) => s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
  let slugTouched = false;
  function showPreview() {
    preview.textContent = slugEl.value ? origin + "/" + slugEl.value + "/" : "";
  }
  slugEl.addEventListener("input", () => { slugTouched = true; slugEl.value = slugEl.value.toLowerCase(); showPreview(); });
  nameEl.addEventListener("input", () => {
    if (!slugTouched) { slugEl.value = slugify(nameEl.value); showPreview(); }
  });

  function clearErrors() {
    form.querySelectorAll("[data-err]").forEach((p) => (p.textContent = ""));
    formErr.textContent = "";
  }
  function getCookie(n) {
    const m = document.cookie.match("(?:^|; )" + n + "=([^;]*)");
    return m ? decodeURIComponent(m[1]) : "";
  }

  form.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    clearErrors();
    const data = {};
    new FormData(form).forEach((v, k) => (data[k] = String(v).trim()));
    btn.disabled = true;
    const label = btn.textContent;
    btn.textContent = "পাঠানো হচ্ছে…";
    try {
      const res = await fetch("/api/register/", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": getCookie("csrftoken") },
        body: JSON.stringify(data),
      });
      let body = {};
      try { body = await res.json(); } catch (e) {}
      if (res.status === 201) {
        form.hidden = true;
        document.getElementById("doneUrl").textContent = origin + "/" + body.slug + "/";
        document.getElementById("regDone").hidden = false;
        return;
      }
      if (res.status === 429) { formErr.textContent = "অনেকবার চেষ্টা হয়েছে, কিছুক্ষণ পরে আবার চেষ্টা করুন।"; return; }
      let shown = false;
      for (const [k, v] of Object.entries(body)) {
        const p = form.querySelector('[data-err="' + k + '"]');
        const msg = Array.isArray(v) ? v.join(" ") : String(v);
        if (p) { p.textContent = msg; shown = true; }
      }
      if (!shown) formErr.textContent = "রেজিস্টার করা যায়নি। আবার চেষ্টা করুন।";
    } catch (e) {
      formErr.textContent = "নেটওয়ার্ক সমস্যা। ইন্টারনেট দেখে আবার চেষ্টা করুন।";
    } finally {
      btn.disabled = false;
      btn.textContent = label;
    }
  });
})();

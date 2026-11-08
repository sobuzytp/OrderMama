document.querySelectorAll(".pay").forEach((b) => b.addEventListener("click", async () => {
  b.disabled = true; document.getElementById("payErr").textContent = "";
  try {
    const res = await fetch("/payments/start/", { method: "POST", credentials: "same-origin", headers: { "X-CSRFToken": OM.cookie("csrftoken"), "Content-Type": "application/x-www-form-urlencoded", Accept: "application/json" }, body: "plan=" + encodeURIComponent(b.dataset.plan) });
    const d = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(d.detail || "পেমেন্ট শুরু করা যায়নি। একটু পরে আবার চেষ্টা করুন।");
    location.href = d.redirect;
  } catch (e) { document.getElementById("payErr").textContent = e.message; b.disabled = false; }
}));

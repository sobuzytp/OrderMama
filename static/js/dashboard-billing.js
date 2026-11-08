document.querySelectorAll(".pay").forEach((b) => b.addEventListener("click", async () => {
  b.disabled = true; document.getElementById("payErr").textContent = "";
  try {
    const body = new URLSearchParams({ plan: b.dataset.plan, gateway: b.dataset.gateway || "sslcommerz" });
    const res = await fetch("/payments/start/", { method: "POST", credentials: "same-origin", headers: { "X-CSRFToken": OM.cookie("csrftoken"), "Content-Type": "application/x-www-form-urlencoded", Accept: "application/json" }, body });
    const d = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(d.detail || "পেমেন্ট শুরু করা যায়নি। একটু পরে আবার চেষ্টা করুন।");
    if (d.redirect) location.href = d.redirect;
    else location.reload();
  } catch (e) { document.getElementById("payErr").textContent = e.message; b.disabled = false; }
}));

const manualBox = document.getElementById("manualPayment");
const manualForm = document.getElementById("manualPaymentForm");
document.querySelectorAll(".manual-pay").forEach((b) => b.addEventListener("click", () => {
  document.getElementById("manualPlan").value = b.dataset.plan;
  manualBox.hidden = false;
  manualBox.scrollIntoView({ behavior: "smooth", block: "start" });
}));
document.getElementById("manualClose")?.addEventListener("click", () => { manualBox.hidden = true; });
manualForm?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const submit = document.getElementById("manualSubmit"), error = document.getElementById("payErr");
  submit.disabled = true; error.textContent = "";
  try {
    const body = new URLSearchParams(new FormData(manualForm));
    body.set("gateway", "manual");
    const res = await fetch("/payments/start/", {
      method: "POST", credentials: "same-origin",
      headers: { "X-CSRFToken": OM.cookie("csrftoken"), "Content-Type": "application/x-www-form-urlencoded", Accept: "application/json" },
      body
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || "পেমেন্ট জমা দেওয়া যায়নি।");
    location.reload();
  } catch (e) { error.textContent = e.message; submit.disabled = false; }
});

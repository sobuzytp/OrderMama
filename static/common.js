/* Helpers shared by the customer and kitchen screens. */
window.OM = (() => {
  function csrfToken() {
    const input = document.querySelector("[name=csrfmiddlewaretoken]");
    if (input) return input.value;
    const match = document.cookie.match(/csrftoken=([^;]+)/);
    return match ? match[1] : "";
  }

  // POST helper that tells the server we want JSON instead of a redirect.
  function post(url, body) {
    return fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: { "X-CSRFToken": csrfToken(), "X-Requested-With": "fetch" },
      body: body || new FormData(),
    });
  }

  function toast(message) {
    const box = document.querySelector("#toast");
    if (!box) return;
    box.textContent = message;
    box.hidden = false;
    clearTimeout(box._timer);
    box._timer = setTimeout(() => { box.hidden = true; }, 3500);
  }

  // "Call waiter" / "Ask for bill" buttons.
  function bindServiceButtons() {
    document.querySelectorAll(".service-btn").forEach((button) => {
      button.addEventListener("click", async () => {
        button.disabled = true;
        try {
          const response = await post(button.dataset.url);
          toast(response.ok ? button.dataset.done : "কিছু সমস্যা হয়েছে, আবার চেষ্টা করুন");
        } catch (error) {
          toast("ইন্টারনেট সংযোগ পরীক্ষা করুন");
        }
        setTimeout(() => { button.disabled = false; }, 4000);
      });
    });
  }

  document.addEventListener("DOMContentLoaded", bindServiceButtons);
  return { csrfToken, post, toast };
})();

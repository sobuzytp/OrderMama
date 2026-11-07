/* Live kitchen screen.
   Tries a WebSocket first; polling always runs as well, because cPanel/Passenger
   cannot serve WebSockets. Whichever delivers first updates the board. */
(() => {
  const board = document.querySelector("#board");
  const stateBadge = document.querySelector("#live-state");
  const soundButton = document.querySelector("#sound-toggle");
  const pollMs = Math.max(2000, +board.dataset.poll || 5000);
  const baseTitle = document.title;

  let lastOrderId = null;           // baseline is set silently on the first poll
  let knownServices = null;
  let lastSignature = null;
  let soundOn = localStorage.getItem("om_sound") === "1";
  let audio = null;
  let wsOpen = false;
  let wsFailures = 0;

  /* ---------- sound ---------- */
  function beep(times = 3) {
    if (!soundOn || !audio) return;
    for (let i = 0; i < times; i++) {
      const osc = audio.createOscillator();
      const gain = audio.createGain();
      osc.frequency.value = 880;
      gain.gain.value = 0.25;
      osc.connect(gain);
      gain.connect(audio.destination);
      const start = audio.currentTime + i * 0.35;
      osc.start(start);
      osc.stop(start + 0.2);
    }
  }

  function paintSoundButton() {
    soundButton.textContent = soundOn ? "🔔 শব্দ চালু" : "🔕 শব্দ চালু করুন";
  }

  soundButton.addEventListener("click", () => {
    // Browsers only allow audio after a click, so the context is created here.
    audio = audio || new (window.AudioContext || window.webkitAudioContext)();
    audio.resume();
    soundOn = !soundOn;
    localStorage.setItem("om_sound", soundOn ? "1" : "0");
    paintSoundButton();
    if (soundOn) beep(1);
  });

  // If sound was enabled earlier, the first click anywhere re-activates audio.
  if (soundOn) {
    document.addEventListener("click", () => {
      audio = audio || new (window.AudioContext || window.webkitAudioContext)();
      audio.resume();
    }, { once: true });
  }
  paintSoundButton();

  /* ---------- refreshing the board ---------- */
  function setState(text, ok) {
    stateBadge.textContent = text;
    stateBadge.classList.toggle("badge-off", !ok);
  }

  async function refresh() {
    try {
      const response = await fetch(board.dataset.url, {
        credentials: "same-origin", headers: { "X-Requested-With": "fetch" },
      });
      if (response.status === 401) { setState("লগইন শেষ — আবার লগইন করুন", false); return; }
      if (!response.ok) throw new Error("bad response");
      const data = await response.json();

      const newOrder = lastOrderId !== null && data.latest_order_id > lastOrderId;
      const newService = knownServices !== null && data.service_ids.some((id) => !knownServices.has(id));
      if (newOrder || newService) beep();
      lastOrderId = data.latest_order_id;
      knownServices = new Set(data.service_ids);

      if (data.signature !== lastSignature) {
        board.innerHTML = data.html;
        lastSignature = data.signature;
      }
      document.title = (data.pending_count ? `(${data.pending_count}) ` : "") + baseTitle;
      setState(wsOpen ? "Live · WebSocket" : "Live · প্রতি " + pollMs / 1000 + " সেকেন্ডে", true);
    } catch (error) {
      setState("অফলাইন — আবার চেষ্টা চলছে", false);
    }
  }

  function pollLoop() {
    refresh().finally(() => setTimeout(pollLoop, wsOpen ? 30000 : pollMs));
  }

  /* ---------- optional WebSocket ---------- */
  function connectSocket() {
    if (wsFailures >= 2 || !("WebSocket" in window)) return;
    const scheme = location.protocol === "https:" ? "wss" : "ws";
    let socket;
    try {
      socket = new WebSocket(`${scheme}://${location.host}/ws/orders/${board.dataset.ws}/`);
    } catch (error) { wsFailures++; return; }
    socket.onopen = () => { wsOpen = true; wsFailures = 0; };
    socket.onmessage = () => refresh();
    socket.onclose = () => {
      wsOpen = false;
      wsFailures++;
      setTimeout(connectSocket, 30000);
    };
  }

  /* ---------- status buttons without a full page reload ---------- */
  board.addEventListener("submit", async (event) => {
    const form = event.target;
    event.preventDefault();
    const data = new FormData(form);
    if (event.submitter && event.submitter.name) data.set(event.submitter.name, event.submitter.value);
    try {
      await OM.post(form.action, data);
    } catch (error) { /* the next poll shows the real state */ }
    refresh();
  });

  connectSocket();
  pollLoop();
})();

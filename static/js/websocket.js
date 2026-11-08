/* লাইভ সংযোগ: রিকানেক্টসহ WebSocket; ব্যর্থ হলে ১০ সেকেন্ডের পোলিং ফলব্যাক। */
(function () {
  OMC.live = function ({ onmsg, onstate, onopen }) {
    if (!OMC.boot.token) return { close() {} };
    let ws, tries = 0, ping, closed = false;
    const connect = () => {
      const proto = location.protocol === "https:" ? "wss" : "ws";
      try { ws = new WebSocket(`${proto}://${location.host}/ws/c/?token=${encodeURIComponent(OMC.boot.token)}`); }
      catch (e) { onstate(false); return retry(); }
      ws.onopen = () => {
        tries = 0; onstate(true); onopen && onopen();
        ping = setInterval(() => { try { ws.send('{"type":"ping"}'); } catch (e) {} }, 30000);
      };
      ws.onmessage = (e) => { try { const d = JSON.parse(e.data); if (d.type !== "pong") onmsg(d); } catch (_) {} };
      ws.onclose = (e) => {
        clearInterval(ping); onstate(false);
        if (closed) return;
        if (e.code === 4403) { refreshToken().then(retry); return; }
        retry();
      };
    };
    const retry = () => setTimeout(connect, Math.min(15000, 800 * 2 ** tries++));
    const refreshToken = async () => {
      try {
        const r = await fetch(OMC.boot.api.session, { method: "POST" });
        if (r.ok) OMC.boot.token = (await r.json()).token;
      } catch (e) {}
    };
    connect();
    return { close() { closed = true; ws && ws.close(); } };
  };
})();

// VoiceBridge AI meeting UI: controls + WebSocket event stream.

const el = (id) => document.getElementById(id);
const statusEl = el("status");
const logEl = el("log");
const player = el("player");

let ws = null;

function setStatus(text, cls) {
  statusEl.textContent = text;
  statusEl.className = "status " + cls;
}

async function loadInfo() {
  const res = await fetch("/api/info");
  const info = await res.json();
  const langs = info.languages || {};
  const myLang = el("myLang");
  const otherLang = el("otherLang");
  for (const [id, name] of Object.entries(langs)) {
    myLang.add(new Option(name, id));
    otherLang.add(new Option(name, id));
  }
  const d = info.defaults || {};
  if (d.my_language) myLang.value = d.my_language;
  if (d.other_language) otherLang.value = d.other_language;
}

function connectWs() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  ws = new WebSocket(`${proto}://${location.host}/ws`);
  ws.onmessage = (ev) => handleEvent(JSON.parse(ev.data));
  ws.onclose = () => setTimeout(connectWs, 1500);
}

// Which participant panel a direction's *output* belongs to.
function targetPanel(speaker) {
  // Speaker "me" produces speech the "other" hears, shown on the other panel.
  return speaker === "me" ? "other" : "me";
}

function handleEvent(e) {
  switch (e.type) {
    case "status":
      if (e.note && e.note.toLowerCase().includes("stopped")) setStatus("idle", "idle");
      else setStatus("running", "running");
      break;
    case "transcript":
      el(`caption-${e.speaker}`).textContent = e.text;
      break;
    case "translation":
      addLog(e, "translation");
      break;
    case "speech_ready":
      playSpeech(e);
      break;
    case "error":
      addLog(e, "error");
      setStatus("error", "error");
      break;
  }
}

function addLog(e, cls) {
  const li = document.createElement("li");
  li.className = cls;
  if (cls === "error") {
    li.innerHTML = `<span class="dir">${e.direction}</span> ${e.note || "error"}`;
  } else {
    const lat = e.latency_ms ? `<span class="lat">${Math.round(e.latency_ms)} ms</span>` : "";
    li.innerHTML =
      `<span class="dir">${e.direction}</span>` +
      `<span class="src">${escapeHtml(e.text)}</span> &rarr; ` +
      `<span class="tgt">${escapeHtml(e.translated_text)}</span>${lat}`;
  }
  logEl.prepend(li);
}

function playSpeech(e) {
  const panel = targetPanel(e.speaker);
  el(`caption-${panel}`).textContent = e.translated_text;
  highlight(panel, true);

  const video = el(`video-${panel}`);
  if (e.is_synced && e.video_url) {
    // Lip-synced clip already contains the audio.
    video.src = e.video_url;
    video.classList.add("active");
    video.muted = false;
    video.onended = () => highlight(panel, false);
    video.play().catch(() => {});
  } else if (e.audio_url) {
    video.classList.remove("active");
    player.src = e.audio_url;
    player.onended = () => highlight(panel, false);
    player.play().catch(() => {});
  } else {
    highlight(panel, false);
  }
}

function highlight(panel, on) {
  el(`p-${panel}`).classList.toggle("speaking", on);
}

function escapeHtml(s) {
  return (s || "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

el("sourceKind").addEventListener("change", (ev) => {
  el("wavPath").classList.toggle("hidden", ev.target.value !== "wav");
});

el("startBtn").addEventListener("click", async () => {
  const body = {
    my_language: el("myLang").value,
    other_language: el("otherLang").value,
    source_kind: el("sourceKind").value,
    wav_path: el("wavPath").value || null,
    two_way: el("sourceKind").value === "microphone",
  };
  const res = await fetch("/api/start", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (res.ok) {
    setStatus("running", "running");
    el("startBtn").disabled = true;
    el("stopBtn").disabled = false;
  } else {
    const err = await res.json();
    setStatus(err.error || "error", "error");
  }
});

el("stopBtn").addEventListener("click", async () => {
  await fetch("/api/stop", { method: "POST" });
  setStatus("idle", "idle");
  el("startBtn").disabled = false;
  el("stopBtn").disabled = true;
});

loadInfo();
connectWs();

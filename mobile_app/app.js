const settingsForm = document.getElementById("settings-form");
const sessionInput = document.getElementById("session-id");
const stageSelect = document.getElementById("stage");
const deviceInput = document.getElementById("device-id");
const piUrlInput = document.getElementById("pi-url");
const startBtn = document.getElementById("start-scan");
const stopBtn = document.getElementById("stop-scan");
const manualBtn = document.getElementById("manual-add");
const manualDialog = document.getElementById("manual-dialog");
const manualForm = document.getElementById("manual-form");
const manualTokenInput = document.getElementById("manual-token");
const closeManualBtn = document.getElementById("close-manual");
const nfcStatus = document.getElementById("nfc-status");
const unsyncedBadge = document.getElementById("unsynced-count");
const unsyncedInline = document.getElementById("unsynced-count-inline");
const lastToken = document.getElementById("last-token");
const lastTime = document.getElementById("last-time");
const totalCount = document.getElementById("total-count");
const recentList = document.getElementById("recent-list");
const syncPiBtn = document.getElementById("sync-pi");
const exportJsonBtn = document.getElementById("export-json");
const exportCsvBtn = document.getElementById("export-csv");
const markSyncedBtn = document.getElementById("mark-synced");
const clearCacheBtn = document.getElementById("clear-cache");
const toast = document.getElementById("toast");
const nfcWarning = document.getElementById("nfc-warning");

const SETTINGS_KEY = "nfc-mobile-settings-v1";
const DEBOUNCE_MS = 1000;

let controller = null;
let reader = null;
let lastSeen = new Map();

class MobileStore {
  constructor() {
    this.dbPromise = this._open();
  }

  _open() {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open("flowstate", 1);

      request.onupgradeneeded = () => {
        const db = request.result;
        const store = db.createObjectStore("events", {
          keyPath: "id",
          autoIncrement: true,
        });
        store.createIndex("synced", "synced");
        store.createIndex("timestamp", "timestampMs");
      };

      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  }

  async addEvent(event) {
    const db = await this.dbPromise;
    return new Promise((resolve, reject) => {
      const tx = db.transaction("events", "readwrite");
      tx.objectStore("events").add(event);
      tx.oncomplete = () => resolve(true);
      tx.onerror = () => reject(tx.error);
    });
  }

  async getUnsyncedEvents() {
    const db = await this.dbPromise;
    return new Promise((resolve, reject) => {
      const tx = db.transaction("events", "readonly");
      const store = tx.objectStore("events");
      const index = store.index("synced");
      const request = index.getAll(IDBKeyRange.only(false));
      request.onsuccess = () => resolve(request.result || []);
      request.onerror = () => reject(request.error);
    });
  }

  async getAllEvents() {
    const db = await this.dbPromise;
    return new Promise((resolve, reject) => {
      const tx = db.transaction("events", "readonly");
      const store = tx.objectStore("events");
      const request = store.getAll();
      request.onsuccess = () => resolve(request.result || []);
      request.onerror = () => reject(request.error);
    });
  }

  async markAllSynced() {
    const db = await this.dbPromise;
    const unsynced = await this.getUnsyncedEvents();
    return new Promise((resolve, reject) => {
      const tx = db.transaction("events", "readwrite");
      const store = tx.objectStore("events");
      unsynced.forEach((evt) => {
        store.put({ ...evt, synced: true, syncedAtMs: Date.now() });
      });
      tx.oncomplete = () => resolve(unsynced.length);
      tx.onerror = () => reject(tx.error);
    });
  }

  async clearAll() {
    const db = await this.dbPromise;
    return new Promise((resolve, reject) => {
      const tx = db.transaction("events", "readwrite");
      tx.objectStore("events").clear();
      tx.oncomplete = () => resolve(true);
      tx.onerror = () => reject(tx.error);
    });
  }
}

const store = new MobileStore();

async function saveSettings() {
  const settings = {
    sessionId: sessionInput.value.trim(),
    stage: stageSelect.value,
    deviceId: deviceInput.value.trim(),
    piUrl: piUrlInput.value.trim().replace(/\/$/, ""),
  };
  localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
  showToast("Settings saved");

  // Reload stages from new Pi URL
  await loadStagesFromAPI();

  return settings;
}

async function loadStagesFromAPI() {
  // Try to load stages from Pi URL if configured
  const piUrl = piUrlInput.value?.trim();
  if (!piUrl) {
    console.log("No Pi URL configured, using default stages");
    return;
  }

  try {
    const configUrl = `${piUrl}/api/service-config`;
    const response = await fetch(configUrl);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);

    const config = await response.json();

    // Update page title with service name
    const serviceName = config.service_name || "NFC Tap Logger";
    document.querySelector("h1").textContent = `${serviceName} (Mobile)`;

    // Populate stage dropdown dynamically
    if (config.workflow_stages && config.workflow_stages.length > 0) {
      const currentValue = stageSelect.value; // Save current selection
      stageSelect.innerHTML = ""; // Clear existing options

      config.workflow_stages.forEach((stage) => {
        const option = document.createElement("option");
        option.value = stage.id;
        option.textContent = stage.label;
        stageSelect.appendChild(option);
      });

      // Restore previous selection if it still exists
      if (
        currentValue &&
        Array.from(stageSelect.options).some(
          (opt) => opt.value === currentValue,
        )
      ) {
        stageSelect.value = currentValue;
      }

      console.log(
        `Loaded ${config.workflow_stages.length} stages from ${serviceName}`,
      );
    }
  } catch (error) {
    console.warn("Could not load service config from API:", error);
    // Keep default stages if API fails
  }
}

function loadSettings() {
  const saved = localStorage.getItem(SETTINGS_KEY);
  if (!saved) return;

  try {
    const settings = JSON.parse(saved);
    if (settings.sessionId) sessionInput.value = settings.sessionId;
    if (settings.stage) stageSelect.value = settings.stage;
    if (settings.deviceId) deviceInput.value = settings.deviceId;
    if (settings.piUrl) piUrlInput.value = settings.piUrl;
  } catch (e) {
    console.warn("Could not parse saved settings", e);
  }
}

function showToast(message) {
  toast.textContent = message;
  toast.hidden = false;
  setTimeout(() => (toast.hidden = true), 1600);
}

function vibrate(pattern = [60]) {
  if (navigator.vibrate) {
    navigator.vibrate(pattern);
  }
}

function formatTime(ms) {
  const dt = new Date(ms);
  return dt.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

async function updateStats() {
  const events = await store.getAllEvents();
  const unsynced = events.filter((evt) => !evt.synced);
  const sorted = events.sort((a, b) => b.timestampMs - a.timestampMs);
  const latest = sorted[0];

  unsyncedBadge.textContent = `${unsynced.length} unsynced`;
  unsyncedInline.textContent = unsynced.length;
  totalCount.textContent = events.length;

  if (latest) {
    lastToken.textContent = latest.tokenId;
    lastTime.textContent = formatTime(latest.timestampMs);
  }

  recentList.innerHTML = sorted
    .slice(0, 10)
    .map(
      (evt) => `
      <div class="recent-item">
        <div>
          <div><strong>${evt.tokenId}</strong> · ${evt.stage}</div>
          <div class="muted">${evt.deviceId}</div>
        </div>
        <div class="muted">${formatTime(evt.timestampMs)}</div>
      </div>`,
    )
    .join("");
}

function deriveToken(event) {
  let token = null;
  const record = event.message?.records?.find((r) => r.recordType === "text");
  if (record) {
    try {
      const decoder = new TextDecoder(record.encoding || "utf-8");
      token = decoder.decode(record.data).trim();
    } catch (err) {
      console.warn("Failed to decode text record", err);
    }
  }
  if (!token && event.serialNumber) {
    token =
      event.serialNumber.replace(/[^A-Za-z0-9]/g, "").substring(0, 8) ||
      "UNKNOWN";
  }
  return token || "UNKNOWN";
}

async function handleTap(event, source = "nfc") {
  const settings = saveSettings();
  const tokenId = event.tokenId || deriveToken(event);
  const uid = event.uid || event.serialNumber || tokenId;
  const timestampMs = event.timestampMs || Date.now();

  const lastTimeSeen = lastSeen.get(uid) || 0;
  if (timestampMs - lastTimeSeen < DEBOUNCE_MS) {
    nfcStatus.textContent = "Ignored duplicate";
    return;
  }
  lastSeen.set(uid, timestampMs);

  const entry = {
    tokenId,
    uid,
    stage: settings.stage,
    sessionId: settings.sessionId,
    deviceId: settings.deviceId,
    timestampMs,
    synced: false,
    source,
  };

  await store.addEvent(entry);
  nfcStatus.textContent = `Logged ${tokenId}`;
  vibrate([50, 30, 50]);
  updateStats();
}

async function startScanning() {
  if (!("NDEFReader" in window)) {
    nfcWarning.hidden = false;
    showToast("Web NFC not supported");
    return;
  }

  try {
    controller = new AbortController();
    reader = new NDEFReader();
    await reader.scan({ signal: controller.signal });
    reader.onreading = (evt) => handleTap(evt, "nfc");
    reader.onreadingerror = () =>
      (nfcStatus.textContent = "Scan error, retrying...");
    startBtn.disabled = true;
    stopBtn.disabled = false;
    nfcStatus.textContent = "Scanning... tap a card";
    showToast("NFC scanning started");
  } catch (err) {
    nfcStatus.textContent = "Unable to start NFC";
    showToast(err.message || "NFC error");
  }
}

function stopScanning() {
  controller?.abort();
  startBtn.disabled = false;
  stopBtn.disabled = true;
  nfcStatus.textContent = "NFC idle";
}

async function downloadFile(filename, content, type = "text/plain") {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

async function syncToPi() {
  const settings = saveSettings();
  if (!settings.piUrl) {
    showToast("Please set Pi Station URL in settings");
    showSyncStatus(
      "error",
      "⚠ No Pi URL configured - set in settings to enable sync",
    );
    setTimeout(() => hideSyncStatus(), 3000);
    return;
  }

  const events = await store.getUnsyncedEvents();
  if (!events.length) {
    showToast("No unsynced events");
    showSyncStatus("success", "✓ All synced - no new events to send");
    setTimeout(() => hideSyncStatus(), 3000);
    return;
  }

  const payload = events.map((evt) => ({
    token_id: evt.tokenId,
    uid: evt.uid,
    stage: evt.stage,
    session_id: evt.sessionId,
    device_id: evt.deviceId,
    timestamp_ms: evt.timestampMs,
    source: evt.source || "mobile-web-nfc-v1",
  }));

  syncPiBtn.disabled = true;
  syncPiBtn.textContent = "Syncing...";
  showSyncStatus("syncing", `Syncing ${events.length} events to server...`);

  try {
    const response = await fetch(`${settings.piUrl}/api/ingest`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      throw new Error(`Server returned ${response.status}`);
    }

    const result = await response.json();
    if (result.status === "ok") {
      const count = await store.markAllSynced();
      updateStats();
      const timestamp = new Date().toLocaleTimeString();
      showToast(`Synced ${count} events!`);
      showSyncStatus(
        "success",
        `✓ Synced ${count} events to server at ${timestamp}`,
      );
      setTimeout(() => hideSyncStatus(), 5000);
    } else {
      throw new Error(result.error || "Unknown error");
    }
  } catch (err) {
    console.error("Sync failed", err);
    showToast(`Sync failed: ${err.message}`);
    showSyncStatus(
      "error",
      `⚠ Sync failed: ${err.message}. Taps saved locally.`,
    );
    setTimeout(() => hideSyncStatus(), 5000);
  } finally {
    syncPiBtn.disabled = false;
    syncPiBtn.textContent = "Sync to Pi Station";
  }
}

function showSyncStatus(type, message) {
  const statusEl = document.getElementById("sync-status-message");
  if (statusEl) {
    statusEl.className = `sync-message ${type}`;
    statusEl.textContent = message;
    statusEl.style.display = "flex";
  }
}

function hideSyncStatus() {
  const statusEl = document.getElementById("sync-status-message");
  if (statusEl) {
    statusEl.style.display = "none";
  }
}

async function exportJsonl() {
  const events = await store.getUnsyncedEvents();
  if (!events.length) {
    showToast("No unsynced events");
    return;
  }
  const lines = events.map((evt) =>
    JSON.stringify({
      token_id: evt.tokenId,
      uid: evt.uid,
      stage: evt.stage,
      session_id: evt.sessionId,
      device_id: evt.deviceId,
      timestamp_ms: evt.timestampMs,
      source: evt.source || "mobile-web-nfc-v1",
    }),
  );
  await downloadFile(
    `mobile-export-${Date.now()}.jsonl`,
    lines.join("\n"),
    "application/x-ndjson",
  );
  showToast("JSONL downloaded");
}

async function exportCsv() {
  const events = await store.getUnsyncedEvents();
  if (!events.length) {
    showToast("No unsynced events");
    return;
  }
  const header = "token_id,uid,stage,session_id,device_id,timestamp_ms";
  const rows = events.map((evt) =>
    [
      evt.tokenId,
      evt.uid,
      evt.stage,
      evt.sessionId,
      evt.deviceId,
      evt.timestampMs,
    ]
      .map((v) => `${v}`.replace(/"/g, '""'))
      .map((v) => (v.includes(",") ? `"${v}"` : v))
      .join(","),
  );
  await downloadFile(
    `mobile-export-${Date.now()}.csv`,
    [header, ...rows].join("\n"),
    "text/csv",
  );
  showToast("CSV downloaded");
}

function initServiceWorker() {
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker
      .register("service-worker.js")
      .catch((err) => console.warn("Service worker registration failed", err));
  }
}

settingsForm.addEventListener("submit", (e) => {
  e.preventDefault();
  saveSettings();
});

syncPiBtn.addEventListener("click", syncToPi);
startBtn.addEventListener("click", startScanning);
stopBtn.addEventListener("click", stopScanning);
manualBtn.addEventListener("click", () => {
  manualTokenInput.value = "";
  manualDialog.showModal();
});
closeManualBtn.addEventListener("click", () => manualDialog.close());
manualForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const token = manualTokenInput.value.trim();
  if (!token) return;
  await handleTap(
    {
      tokenId: token,
      serialNumber: `manual-${token}`,
      timestampMs: Date.now(),
    },
    "manual",
  );
  manualDialog.close();
});

exportJsonBtn.addEventListener("click", exportJsonl);
exportCsvBtn.addEventListener("click", exportCsv);
markSyncedBtn.addEventListener("click", async () => {
  const count = await store.markAllSynced();
  showToast(`Marked ${count} as synced`);
  updateStats();
});
clearCacheBtn.addEventListener("click", async () => {
  await store.clearAll();
  lastSeen = new Map();
  showToast("Cleared all stored events");
  updateStats();
});

window.addEventListener("DOMContentLoaded", async () => {
  loadSettings();
  await loadStagesFromAPI(); // Load stages from API after settings are loaded
  updateStats();
  initServiceWorker();
  if (!("NDEFReader" in window)) {
    nfcWarning.hidden = false;
  }
});

window.addEventListener("unload", () => {
  stopScanning();
});

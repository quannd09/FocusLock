// FocusLock Chrome/Edge/CocCoc Companion Extension - Background Worker
// Manifest V3 compliant with local persistence, multi-event interception, and automatic reconnect

let socket = null;
let isLocked = false;
let allowedUrls = [];
let reconnectTimer = null;

const WS_URL = "ws://127.0.0.1:8765";

// Load persisted lock state immediately on service worker boot
chrome.storage.local.get(["isLocked", "allowedUrls"], (res) => {
  if (res && res.isLocked) {
    isLocked = true;
    allowedUrls = res.allowedUrls || [];
    console.log("[FocusLock] Restored lock state from storage. Allowed count:", allowedUrls.length);
    updateBadge();
    enforceLockOnExistingTabs();
  }
});

function getBrowserName() {
  const ua = navigator.userAgent;
  if (ua.includes("Edg/")) return "Edge";
  if (ua.includes("CocCoc/")) return "Cốc Cốc";
  if (ua.includes("Brave/")) return "Brave";
  if (ua.includes("Chrome/")) return "Chrome";
  return "Browser";
}

function connectWebSocket() {
  if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) {
    return;
  }

  try {
    socket = new WebSocket(WS_URL);

    socket.onopen = () => {
      const browser = getBrowserName();
      console.log("[FocusLock Extension] Connected to Desktop App:", browser);
      sendToDesktop({ type: "HELLO", client: "browser_extension", browser: browser });
      updateBadge();
    };

    socket.onmessage = async (event) => {
      try {
        const data = JSON.parse(event.data);
        handleServerMessage(data);
      } catch (err) {
        console.error("[FocusLock Extension] Error parsing message:", err);
      }
    };

    socket.onclose = () => {
      console.log("[FocusLock Extension] Disconnected. Retrying in 2s...");
      scheduleReconnect();
      updateBadge();
    };

    socket.onerror = () => {
      socket.close();
    };
  } catch (e) {
    scheduleReconnect();
  }
}

function scheduleReconnect() {
  if (!reconnectTimer) {
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null;
      connectWebSocket();
    }, 2000);
  }
}

function sendToDesktop(msg) {
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify(msg));
  }
}

async function handleServerMessage(data) {
  switch (data.type) {
    case "PING":
      sendToDesktop({ type: "PONG" });
      break;

    case "GET_TABS": {
      const browser = getBrowserName();
      const tabs = await chrome.tabs.query({});
      const tabList = tabs.map(t => ({
        id: t.id,
        title: t.title || "Untitled",
        url: t.url || t.pendingUrl || "",
        favIconUrl: t.favIconUrl || "",
        browser: browser
      })).filter(t => t.url && !t.url.startsWith("chrome://") && !t.url.startsWith("edge://") && !t.url.startsWith("coccoc://") && !t.url.startsWith("about:"));
      sendToDesktop({ type: "TABS_LIST", tabs: tabList, browser: browser });
      break;
    }

    case "LOCK_START": {
      isLocked = true;
      allowedUrls = data.allowedUrls || [];
      console.log("[FocusLock Extension] Lockdown activated. Whitelist count:", allowedUrls.length);
      chrome.storage.local.set({ isLocked: true, allowedUrls: allowedUrls });
      await enforceLockOnExistingTabs();
      updateBadge();
      sendToDesktop({ type: "LOCK_ACK", status: "active" });
      break;
    }

    case "LOCK_STOP": {
      isLocked = false;
      allowedUrls = [];
      console.log("[FocusLock Extension] Lockdown ended.");
      chrome.storage.local.set({ isLocked: false, allowedUrls: [] });
      updateBadge();
      sendToDesktop({ type: "LOCK_STOP_ACK", status: "idle" });
      break;
    }
  }
}

function extractDomain(url) {
  if (!url) return "";
  try {
    const parsed = new URL(url.startsWith("http") ? url : "https://" + url);
    let host = (parsed.hostname || "").toLowerCase();
    if (host.startsWith("www.")) {
      host = host.slice(4);
    }
    return host;
  } catch {
    let clean = url.trim().toLowerCase();
    clean = clean.replace(/^(https?:\/\/)?(www\.)?/, "");
    return clean.split("/")[0].split("?")[0].split("#")[0];
  }
}

function isAllowed(url) {
  if (!url) return false;
  const lower = url.trim().toLowerCase();

  // Internal browser and extension schemes
  if (
    lower.startsWith("chrome-extension://") ||
    lower.startsWith("edge-extension://") ||
    lower.startsWith("devtools://") ||
    lower === "about:blank" ||
    lower === "about:newtab" ||
    lower === "chrome://newtab/" ||
    lower === "edge://newtab/" ||
    lower === "coccoc://newtab/" ||
    lower === "brave://newtab/" ||
    lower.startsWith("chrome://extensions") ||
    lower.startsWith("edge://extensions") ||
    lower.startsWith("coccoc://extensions")
  ) {
    return true;
  }

  // If locked with an empty whitelist, block all external URLs
  if (!allowedUrls || allowedUrls.length === 0) {
    return false;
  }

  const reqHost = extractDomain(lower);
  if (!reqHost) return false;

  for (const item of allowedUrls) {
    if (!item) continue;
    const allowedHost = extractDomain(item);
    if (!allowedHost) continue;

    // Direct domain match or allowed subdomain
    if (reqHost === allowedHost || reqHost.endsWith("." + allowedHost)) {
      return true;
    }
  }

  return false;
}

function getSafeFallbackUrl() {
  if (allowedUrls && allowedUrls.length > 0) {
    const first = allowedUrls[0].trim();
    if (first.startsWith("http")) return first;
    return `https://${first}`;
  }
  return "about:blank";
}

async function enforceLockOnExistingTabs() {
  if (!isLocked) return;
  const tabs = await chrome.tabs.query({});
  let keptAny = false;

  for (const tab of tabs) {
    const urlToCheck = tab.pendingUrl || tab.url;
    if (!urlToCheck) continue;
    if (isAllowed(urlToCheck)) {
      keptAny = true;
    } else {
      console.log("[FocusLock] Closing unauthorized tab:", urlToCheck);
      try {
        await chrome.tabs.remove(tab.id);
      } catch (_) {}
    }
  }

  // Prevent browser window from closing entirely if all tabs are removed
  if (!keptAny && tabs.length > 0) {
    chrome.tabs.create({ url: getSafeFallbackUrl() });
  }
}

// Intercept new tabs
chrome.tabs.onCreated.addListener((tab) => {
  if (!isLocked) return;
  const targetUrl = tab.pendingUrl || tab.url;
  if (targetUrl && !isAllowed(targetUrl)) {
    console.log("[FocusLock] Closing forbidden new tab:", targetUrl);
    chrome.tabs.remove(tab.id);
  }
});

// Intercept tab updates and navigations
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (!isLocked) return;
  const targetUrl = changeInfo.url || tab.pendingUrl || tab.url;
  if (targetUrl && !isAllowed(targetUrl)) {
    console.log("[FocusLock] Closing forbidden updated tab:", targetUrl);
    chrome.tabs.remove(tabId);
  }
});

// Intercept pre-navigation events via webNavigation before request loads
chrome.webNavigation?.onBeforeNavigate?.addListener(async (details) => {
  if (!isLocked) return;
  if (details.frameId === 0) {
    const url = details.url;
    if (url && !isAllowed(url)) {
      console.log("[FocusLock] WebNavigation blocked unauthorized URL:", url);
      try {
        await chrome.tabs.remove(details.tabId);
      } catch (_) {}
    }
  }
});

// Intercept committed navigations
chrome.webNavigation?.onCommitted?.addListener(async (details) => {
  if (!isLocked) return;
  if (details.frameId === 0) {
    const url = details.url;
    if (url && !isAllowed(url)) {
      console.log("[FocusLock] Closing committed unauthorized URL:", url);
      try {
        await chrome.tabs.remove(details.tabId);
      } catch (_) {}
    }
  }
});

// Intercept Single Page Application history transitions
chrome.webNavigation?.onHistoryStateUpdated?.addListener(async (details) => {
  if (!isLocked) return;
  if (details.frameId === 0) {
    const url = details.url;
    if (url && !isAllowed(url)) {
      console.log("[FocusLock] Closing unauthorized SPA transition:", url);
      try {
        await chrome.tabs.remove(details.tabId);
      } catch (_) {}
    }
  }
});

function updateBadge() {
  if (isLocked) {
    chrome.action.setBadgeText({ text: "LOCK" });
    chrome.action.setBadgeBackgroundColor({ color: "#EF4444" });
  } else if (socket && socket.readyState === WebSocket.OPEN) {
    chrome.action.setBadgeText({ text: "ON" });
    chrome.action.setBadgeBackgroundColor({ color: "#10B981" });
  } else {
    chrome.action.setBadgeText({ text: "OFF" });
    chrome.action.setBadgeBackgroundColor({ color: "#6B7280" });
  }
}

// Initial connection
connectWebSocket();

// Periodic alarm to keep service worker alive and re-enforce lock
chrome.alarms?.create("heartbeat", { periodInMinutes: 0.5 });
chrome.alarms?.onAlarm.addListener(() => {
  connectWebSocket();
  if (isLocked) {
    enforceLockOnExistingTabs();
  }
});

// FocusLock Chrome/Edge Companion Extension - Background Worker

let socket = null;
let isLocked = false;
let allowedUrls = [];
let reconnectTimer = null;

const WS_URL = "ws://127.0.0.1:8765";

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
      console.log(`[FocusLock Extension] Connected to Desktop App (${browser})`);
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

    socket.onerror = (err) => {
      console.warn("[FocusLock Extension] Socket error. Retrying...");
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
        url: t.url || "",
        favIconUrl: t.favIconUrl || "",
        browser: browser
      })).filter(t => t.url && !t.url.startsWith("chrome://") && !t.url.startsWith("edge://") && !t.url.startsWith("about:"));
      sendToDesktop({ type: "TABS_LIST", tabs: tabList, browser: browser });
      break;
    }

    case "LOCK_START": {
      isLocked = true;
      allowedUrls = data.allowedUrls || [];
      console.log("[FocusLock Extension] Lockdown activated. Whitelist:", allowedUrls);
      await enforceLockOnExistingTabs();
      updateBadge();
      sendToDesktop({ type: "LOCK_ACK", status: "active" });
      break;
    }

    case "LOCK_STOP": {
      isLocked = false;
      allowedUrls = [];
      console.log("[FocusLock Extension] Lockdown ended.");
      updateBadge();
      sendToDesktop({ type: "LOCK_STOP_ACK", status: "idle" });
      break;
    }
  }
}

function normalizeUrl(url) {
  if (!url) return "";
  try {
    const parsed = new URL(url);
    return parsed.hostname.toLowerCase();
  } catch {
    return url.toLowerCase();
  }
}

function isAllowed(url) {
  if (!url) return true;
  // Allow system/extension pages
  if (url.startsWith("chrome-extension://") || url.startsWith("edge-extension://")) {
    return true;
  }
  // If user allows everything (empty whitelist), let it pass
  if (!allowedUrls || allowedUrls.length === 0) {
    return false;
  }

  const host = normalizeUrl(url);
  const full = url.toLowerCase();

  for (const item of allowedUrls) {
    const cleanItem = item.trim().toLowerCase();
    if (!cleanItem) continue;

    // Direct string match
    if (full.includes(cleanItem)) return true;

    // Domain match
    const itemHost = normalizeUrl(cleanItem.startsWith("http") ? cleanItem : `https://${cleanItem}`);
    if (host === itemHost || host.endsWith("." + itemHost)) {
      return true;
    }
  }

  return false;
}

async function enforceLockOnExistingTabs() {
  if (!isLocked) return;
  const tabs = await chrome.tabs.query({});
  let keptAny = false;

  for (const tab of tabs) {
    if (!tab.url) continue;
    if (isAllowed(tab.url)) {
      keptAny = true;
    } else {
      console.log(`[FocusLock] Closing unauthorized tab: ${tab.url}`);
      try {
        await chrome.tabs.remove(tab.id);
      } catch (err) {
        // Tab may have already closed
      }
    }
  }

  // If all tabs were closed, create one safe page to prevent browser from quitting entirely
  if (!keptAny && tabs.length > 0) {
    // If there is an allowed URL, open the first allowed URL, otherwise a clean page
    const target = (allowedUrls.length > 0 && allowedUrls[0].startsWith("http")) 
      ? allowedUrls[0] 
      : (allowedUrls.length > 0 ? `https://${allowedUrls[0]}` : "about:blank");
    chrome.tabs.create({ url: target });
  }
}

// Intercept new tabs
chrome.tabs.onCreated.addListener((tab) => {
  if (!isLocked) return;
  if (tab.url && !isAllowed(tab.url)) {
    console.log(`[FocusLock] Immediately closing new tab with forbidden URL: ${tab.url}`);
    chrome.tabs.remove(tab.id);
  }
});

// Intercept tab updates / navigations
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (!isLocked) return;
  const urlToCheck = changeInfo.url || tab.url;
  if (urlToCheck) {
    // Ignore internal transitional states
    if (urlToCheck === "chrome://newtab/" || urlToCheck === "edge://newtab/" || urlToCheck === "about:blank") {
      return;
    }
    if (!isAllowed(urlToCheck)) {
      console.log(`[FocusLock] Closed tab navigating to forbidden URL: ${urlToCheck}`);
      chrome.tabs.remove(tabId);
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

// Keep service worker alive
chrome.alarms?.create("heartbeat", { periodInMinutes: 0.5 });
chrome.alarms?.onAlarm.addListener(() => {
  connectWebSocket();
});

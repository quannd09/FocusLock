document.addEventListener("DOMContentLoaded", () => {
  const connStatus = document.getElementById("connStatus");
  const lockStatus = document.getElementById("lockStatus");

  // Check connection by trying to fetch badge or query background state
  chrome.action.getBadgeText({}, (text) => {
    if (text === "LOCK") {
      connStatus.innerHTML = '<span class="status-indicator status-connected"></span>Đã kết nối';
      lockStatus.innerHTML = '<span class="status-indicator status-locked"></span>ĐANG KHOÁ';
      lockStatus.style.color = "#EF4444";
    } else if (text === "ON") {
      connStatus.innerHTML = '<span class="status-indicator status-connected"></span>Đã kết nối';
      lockStatus.innerHTML = '<span class="status-indicator status-connected"></span>Sẵn sàng';
      lockStatus.style.color = "#10B981";
    } else {
      connStatus.innerHTML = '<span class="status-indicator status-disconnected"></span>Chưa kết nối';
      lockStatus.innerHTML = 'Ngoại tuyến';
      lockStatus.style.color = "#9CA3AF";
    }
  });
});

# 🛡️ FocusLock

Ứng dụng hỗ trợ học tập và làm việc kỷ luật cao trên hệ điều hành Windows:
- **Khoá và đóng ngay lập tức** mọi ứng dụng ngoài danh sách cho phép.
- **Kiểm soát tab trình duyệt**: Đóng các tab ngoài danh sách và chặn mọi liên kết không được phép qua Extension cho Chrome, Edge, Cốc Cốc, Brave.
- **Màn hình khoá Overlay tràn viền**: Tự động che màn hình khi người dùng cố mở ứng dụng khác.
- **Chống tắt ứng dụng**: Vô hiệu hoá phím tắt thoát, tiến trình Watchdog chạy ngầm tự động phục hồi ứng dụng nếu bị đóng trong Task Manager.
- **Đồng hồ đếm ngược**: Widget mini ghim nổi trên màn hình và hiển thị trên màn hình khoá.
- **Quản lý Profile**: Hỗ trợ lưu và áp dụng nhanh các bộ cấu hình mẫu: Lập trình, Học tập, Pomodoro.
- **Dual-Theme Engine**: Hỗ trợ chuyển đổi giao diện Dark Slate và Warm Peach với độ tương phản cao.

---

## 🚀 Cách chạy ứng dụng

### Cách 1: Chạy trực tiếp bằng file BAT
Nhấp đúp chuột vào file:
```text
FocusLock\start.bat
```

### Cách 2: Chạy bằng dòng lệnh
```bash
git clone https://github.com/<your-username>/FocusLock.git
cd FocusLock
pip install -r requirements.txt
python app/main.py
```

---

## 🧩 Hướng dẫn cài đặt Extension trình duyệt

Tiện ích **FocusLock Companion** nằm trong thư mục `extension` của dự án. Hỗ trợ toàn bộ trình duyệt nhân Chromium gồm Google Chrome, Microsoft Edge, Cốc Cốc, Brave:

1. Mở trang quản lý tiện ích trên trình duyệt:
   - Google Chrome: `chrome://extensions`
   - Microsoft Edge: `edge://extensions`
   - Cốc Cốc: `coccoc://extensions`
2. Bật công tắc **Developer mode** trên thanh công cụ.
3. Bấm nút **Load unpacked**.
4. Chọn thư mục `extension` nằm trong thư mục dự án FocusLock bạn vừa tải về.
5. Biểu tượng **FocusLock Companion** sẽ xuất hiện trên thanh công cụ và tự động đồng bộ trạng thái kết nối với ứng dụng Desktop.

---

## 📋 Hướng dẫn sử dụng

1. **Chọn ứng dụng máy tính**:
   - Bấm `🔄 Quét ứng dụng` và tích chọn những ứng dụng cần dùng.
   - Bạn cũng có thể chọn trực tiếp bằng cách bấm `🎯 Chọn cửa sổ` hoặc chọn file `.exe`.

2. **Chọn Tab trình duyệt**:
   - Bấm `🔄 Quét tab` để danh sách tab đang mở hiển thị.
   - Tích chọn các tab được phép hoặc nhập thêm domain mong muốn.

3. **Cài đặt thời gian và Widget**:
   - Chọn thời gian tập trung bằng các nút chọn nhanh `15m`, `25m`, `45m`, `60m`, `90m` hoặc nhập số giờ/phút.
   - Bật hoặc tắt tuỳ chọn widget đếm ngược nổi trên màn hình.

4. **Bắt đầu tập trung**:
   - Bấm `⚡ Bắt đầu tập trung` và xác nhận để kích hoạt phiên tập trung.

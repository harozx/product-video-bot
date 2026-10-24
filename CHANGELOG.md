# Changelog

## [1.0.0] - 2026-10-25

Bản đầu tiên đưa lên git.

### Có sẵn
- Bot Telegram: nhận ảnh sản phẩm, tên, giá; Gemini viết caption
  TikTok/Facebook và hashtag.
- Dựng video 9:16: slideshow FFmpeg có nhạc nền, MoneyPrinterTurbo
  (AI review, stock video), Google Veo 3.1 (Lite, Pro).
- Upload Cloudflare R2, duyệt video, chọn nền tảng/tài khoản/giờ đăng.
- FastAPI cho video, tài khoản, lịch đăng, thống kê.
- Dọn file local và R2 theo lịch.

### Sửa khi chuẩn bị phát hành
- **Bảo mật:** khi chưa cấu hình `TELEGRAM_ADMIN_IDS`, bot trước đây cho mọi
  người dùng (có thể đốt credit Veo); giờ từ chối tất cả và ghi ID vào log.
- **Bảo mật:** API mặc định nghe `127.0.0.1` thay vì `0.0.0.0` vì không có
  xác thực; `DEBUG` mặc định tắt.
- Thêm error handler cho bot: lỗi mạng Telegram chỉ ghi 1 dòng cảnh báo thay
  vì stack trace, lỗi khác báo cho người dùng.
- Địa chỉ MoneyPrinterTurbo (`TURBO_BASE_URL`) và model Gemini
  (`GEMINI_MODEL`) cấu hình được qua `.env`.
- `requirements.txt` khớp với code: thêm `google-genai`, `httpx`; bỏ các
  thư viện không dùng (`google-generativeai`, `google-cloud-*`, `moviepy`,
  `numpy`, `playwright`, `cryptography`, `aiohttp`).
- Các script `test_*.py` gọi dịch vụ thật chuyển sang `scripts/check_*.py`;
  thêm test offline trong `tests/`.
- Bỏ tên bot viết cứng trong log khởi động.

### Chưa có
- Module tự đăng lên TikTok/Facebook (lịch chỉ được lưu).
- Dashboard web.

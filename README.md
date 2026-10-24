# Product Video Bot

Bot Telegram tạo **video bán hàng dọc 9:16** từ ảnh sản phẩm: gửi ảnh, tên
và giá cho bot → Gemini viết caption TikTok/Facebook và hashtag → bot dựng
video → duyệt ngay trong Telegram → lên lịch đăng cho từng tài khoản.

```text
Telegram (ảnh + tên + giá)
        │
        ▼
Gemini: caption TikTok, caption Facebook, hashtag
        │
        ▼
Chọn cách dựng video ──┬─ Slideshow FFmpeg + nhạc nền  (miễn phí)
                       ├─ MoneyPrinterTurbo: AI review / stock video  (miễn phí)
                       └─ Google Veo 3.1: Lite (~$0.30) / Pro (~$3)
        │
        ▼
Upload Cloudflare R2 → xem trước + duyệt trong Telegram
        │
        ▼
Chọn nền tảng, tài khoản, giờ đăng → lưu lịch vào SQLite
```

Cùng một tiến trình còn chạy **FastAPI** (API cho dashboard) và một
**scheduler** dọn file cũ mỗi ngày.

## Trạng thái

| Phần | Trạng thái |
|---|---|
| Nhận ảnh, tạo caption, dựng video, upload R2, duyệt | ✅ Chạy được |
| Lưu lịch đăng, quản lý tài khoản, thống kê | ✅ Chạy được |
| Dọn file local (7 ngày) và trên R2 (90 ngày) | ✅ Chạy được |
| **Tự động đăng lên TikTok/Facebook** | ❌ Chưa có: lịch được lưu với trạng thái `pending` nhưng chưa có module nào đăng |
| Dashboard web | ❌ Chưa có: mới có API |

## Lệnh bot

| Lệnh | Tác dụng |
|---|---|
| `/start` | Bắt đầu: gửi 1 ảnh (Veo) hoặc 3–10 ảnh (slideshow) |
| `/cancel` | Hủy thao tác đang làm |
| `/status` | Trạng thái hệ thống |
| `/stats` | Thống kê video, lượt đăng, chi phí |
| `/accounts` | Danh sách tài khoản đăng |
| `/add_account <platform> <tên> <username>` | Thêm tài khoản, ví dụ `/add_account tiktok MyShop @myshop` |
| `/schedule` | Lịch đăng sắp tới |
| `/cleanup` | Chạy dọn dẹp ngay |
| `/help` | Trợ giúp |

Chỉ các Telegram ID trong `TELEGRAM_ADMIN_IDS` dùng được bot. Nếu để trống,
bot từ chối mọi người và ghi ID của người nhắn vào log để bạn copy.

## Cấu trúc

```text
main.py            khởi động bot + FastAPI + scheduler
config.py          cấu hình, đọc từ .env
database.py        SQLite (aiosqlite): products, videos, accounts, schedule...
ai/                Gemini (caption, prompt) và Veo (tạo video)
bot/               hội thoại Telegram, lệnh, bàn phím inline
engine/            slideshow FFmpeg, client MoneyPrinterTurbo
server/            FastAPI: /api/videos, /api/accounts, /api/schedule, /api/stats
storage/           upload R2, dọn dẹp
scripts/           kiểm tra kết nối thật: check_db, check_gemini, check_r2
tests/             test offline (pytest)
music/             nhạc nền: chill/, energetic/, trending/ (không commit)
```

## Cài đặt

Yêu cầu: Python 3.11+, FFmpeg trong `PATH`.

```bash
pip install -r requirements.txt
copy .env.example .env
```

Điền vào `.env`:

1. `TELEGRAM_BOT_TOKEN` (tạo bot qua @BotFather) và `TELEGRAM_ADMIN_IDS`.
2. `GEMINI_API_KEY`. Muốn dùng Veo thì cần thêm `GOOGLE_CLOUD_PROJECT` và
   file service account ở `credentials/` (`GOOGLE_APPLICATION_CREDENTIALS`).
3. Thông tin Cloudflare R2 (`CF_*`).
4. Gói miễn phí AI Review / Stock Video cần
   [MoneyPrinterTurbo](https://github.com/harry0703/MoneyPrinterTurbo) chạy ở
   `TURBO_BASE_URL`.

Chép nhạc nền (mp3) vào `music/chill`, `music/energetic`, `music/trending`.

Kiểm tra kết nối:

```bash
python scripts/check_db.py
python scripts/check_gemini.py
python scripts/check_r2.py
```

## Chạy

```bash
python main.py
```

- Bot: nhắn `/start` cho bot trên Telegram.
- API: <http://127.0.0.1:8000/docs>

API **không có xác thực**, nên mặc định chỉ nghe ở `127.0.0.1`. Chỉ đổi
`API_HOST` khi đặt sau reverse proxy có đăng nhập.

## Kiểm thử

```bash
pip install pytest
python -m pytest tests
```

## Bảo mật

Không commit `.env`, `credentials/`, file `*.json` của Google, `data/`
(database, ảnh tạm, profile) và `music/`. Tất cả đã nằm trong `.gitignore`.

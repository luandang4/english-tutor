# Công nghệ & kiến trúc

## Stack

| Tầng | Lựa chọn |
|---|---|
| Backend | Python 3.12, FastAPI, Pydantic v2 |
| Cơ sở dữ liệu | SQLAlchemy 2.0 (async) + Alembic; SQLite (WAL) mặc định, Postgres qua `DATABASE_URL` |
| Ôn tập | FSRS (py-fsrs) |
| Frontend | React 19, TypeScript (strict), Vite, React Router, TanStack Query; CSS token tự viết (dark / light) |
| Âm thanh | Mic: AudioWorklet → PCM16 16 kHz; phát: WebAudio 24 kHz |
| Công cụ | uv, ruff, pytest (Gemini giả), oxlint, `tsc -b` |

## Nhà cung cấp AI

| Nhà cung cấp | Dùng cho |
|---|---|
| **Gemini** | mọi việc AI: hội thoại giọng nói (Gemini Live, giọng `Kore`), soạn bài học / bài tập / đề viết, chấm bài, tổng kết buổi hội thoại |
| **Azure Speech** | chỉ chấm phát âm |
| **Âm thanh miễn phí** | từ: gTTS → Kokoro; câu: Kokoro-82M chạy local. Cache ở `data/tts/` (production: S3) |

Gọi Gemini (trừ Live) đi qua `services/ai/client.py` (chuỗi model dự phòng, chỉnh trong `.env`); gọi Azure đi
qua `services/speech/azure.py`.

## Kiến trúc

```
Trình duyệt (React SPA)
 ├─ REST /api/*  ───────────────► routes ─► services ─► SQLAlchemy ─► SQLite / Postgres
 │                                            ├─► Gemini (soạn / chấm, JSON schema)
 │                                            ├─► gTTS / Kokoro
 │                                            └─► Azure (chấm phát âm)
 └─ WebSocket /ws/conversation ─► routes/live.py ─► Gemini Live (âm thanh hai chiều)
```

- `api/routes/` chỉ là lớp HTTP / WebSocket mỏng; nghiệp vụ ở `services/`.
- Soạn bài chạy nền: `POST` trả `status=generating`, UI poll tới `ready` / `failed`.
- Chấm bài ưu tiên quy tắc: trắc nghiệm và điền từ khớp chính xác chấm ngay, chỉ câu mở mới gửi Gemini. Đáp án
  ẩn khỏi API tới khi đã làm bài.
- Gia sư Emma: quy tắc theo trình độ CEFR ở `services/conversation/tutor.py`; thẻ trên màn hình (dịch, sửa lỗi,
  gợi ý) qua function call của Live; tổng kết cuối buổi và trí nhớ người học ở `recap.py` / `memory.py`.

## Tài khoản, quyền & gói

- Email + mật khẩu (Argon2id), cookie `et_session` HttpOnly; DB chỉ lưu SHA-256 của token.
- Mọi bảng học tập có `user_id`; dữ liệu của người khác trả 404.
- Tính năng tốn AI (`conversation`, `vocabulary`, `grammar`, `writing`, `pronunciation`) đi qua
  `services/access.py`: tài khoản hoạt động → tính năng đang bật → gói có tính năng → còn lượt ngày / tháng.
  Kiểm tra ở API, UI chỉ ẩn / khoá theo `me.features`.
- Gói (`plans`, `subscriptions`, `usage_grants`) do admin gán ở `/admin`. Gói hết hạn thì khoá AI, vẫn ôn tập và
  xem bài cũ được. Tài khoản đầu tiên là admin.

## Cấu trúc thư mục

```
backend/app/
  api/routes/      HTTP / WebSocket
  services/        nghiệp vụ (ai/, speech/, conversation/, ...)
  models/          bảng ORM
  schemas/         DTO (api.py), JSON schema cho Gemini (ai.py)
  core/, db/       cài đặt, kết nối DB
backend/alembic/   migration
backend/tests/     pytest
frontend/src/
  api/             client, kiểu, hook TanStack Query
  components/      layout, bộ UI dùng chung
  features/        từng trang (hội thoại, bài học, ôn tập, tập viết, viết luận, quản trị, ...)
  lib/             âm thanh, tuỳ chọn, định dạng
  styles/          CSS token
```

## Triển khai

AWS EC2 (`ap-southeast-2`, profile `new-frontiers`), tên miền https://english-tutor.us.ci. Caddy (HTTPS) →
uvicorn (systemd `english-tutor`), code ở `/opt/english-tutor`, SQLite ở `/opt/english-tutor/data`, cache âm
thanh trên S3. Script trong `deploy/`:

```sh
make provision                        # 1 lần: tạo tài nguyên AWS (chạy lại khi đổi IP SSH)
make bootstrap                        # 1 lần: cài server, .env, bản đầu tiên
git push origin main && make deploy   # mỗi lần release
deploy/set-env.sh KEY=value           # đổi cài đặt trên server + restart
deploy/create-user.sh EMAIL "Tên"     # thêm tài khoản từ dòng lệnh
```

Chưa có sao lưu tự động cho `app.db` trên server.

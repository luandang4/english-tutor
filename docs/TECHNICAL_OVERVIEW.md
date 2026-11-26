# English Tutor: tổng quan kỹ thuật

Tài liệu giới thiệu app cho team dev: dùng công nghệ gì, các phần chính được xử lý ra sao và vì sao làm như vậy.
Cách cài đặt và chạy xem ở [README.md](../README.md), danh sách stack và cấu trúc thư mục ở
[TECHSTACK.md](TECHSTACK.md).

## 1. App làm gì

Gia sư tiếng Anh AI cho người Việt, mỗi người học có tài khoản và tiến độ riêng:

- **Hội thoại giọng nói** với tutor "Emma": nói chuyện thời gian thực, có thẻ dịch, sửa lỗi, gợi ý trên màn
  hình, chấm phát âm từng lượt nói, tổng kết cuối buổi.
- **Từ vựng / ngữ pháp**: AI soạn bài theo chủ đề có sẵn hoặc chủ đề người học tự nhập, kèm bài tập.
- **Tập viết từ**: chép lại từ và nghĩa nhiều lần, chấm ngay trên trình duyệt.
- **Viết luận**: AI ra đề và chấm theo 4 tiêu chí, đánh dấu lỗi ngay trong bài.
- **Ôn tập**: thẻ từ theo thuật toán lặp lại ngắt quãng FSRS.
- **Quản trị**: duyệt tài khoản, gán gói, giới hạn lượt dùng AI.

## 2. Công nghệ

| Phần | Công nghệ |
|---|---|
| Backend | Python 3.12, FastAPI (async), Pydantic v2 |
| DB | SQLAlchemy 2.0 async + Alembic. SQLite chế độ WAL (chạy được Postgres qua `DATABASE_URL`) |
| Frontend | React 19, TypeScript strict, Vite, React Router (lazy route), TanStack Query |
| AI | Google Gemini (soạn bài, chấm bài, Gemini Live cho hội thoại giọng nói) |
| Giọng nói | Azure Speech, **chỉ** để chấm phát âm |
| Đọc từ / câu | gTTS, bản ghi Wiktionary, Kokoro-82M (model TTS mã nguồn mở chạy trên server, ONNX) |
| Ôn tập | py-fsrs |
| Công cụ | uv, ruff, pytest, oxlint, `tsc -b` |
| Hạ tầng | 1 máy AWS EC2, Caddy (HTTPS), systemd, S3 làm cache âm thanh |

CSS tự viết bằng design token, không dùng UI framework.

## 3. Kiến trúc

```
Trình duyệt (React SPA)
 ├─ REST /api/*  ─────────────► routes ─► services ─► SQLAlchemy ─► SQLite
 │                                          ├─► Gemini (JSON có schema)
 │                                          ├─► gTTS / Wiktionary / Kokoro ─► cache local hoặc S3
 │                                          └─► Azure (chấm phát âm)
 └─ WebSocket /ws/conversation ─► routes/live.py ─► Gemini Live (âm thanh hai chiều)
```

Một tiến trình FastAPI phục vụ cả API, WebSocket và file build của frontend. Không có queue hay cache server
riêng: với quy mô hiện tại, một tiến trình là đủ và dễ vận hành.

Nguyên tắc tổ chức code:

- `api/routes/` chỉ là lớp HTTP / WebSocket mỏng. Nghiệp vụ nằm ở `services/`, bảng ORM ở `models/`, DTO ở
  `schemas/api.py`, schema JSON cho Gemini ở `schemas/ai.py`.
- Mọi lời gọi Gemini (trừ Live) đi qua `services/ai/client.py`. Mọi lời gọi Azure đi qua
  `services/speech/azure.py`. Muốn đổi nhà cung cấp chỉ cần thay một chỗ.
- Mỗi bảng học tập có `user_id`. Route dùng `CurrentUser` + `get_owned()`, dữ liệu của người khác trả 404
  (không phải 403) để không lộ việc bản ghi có tồn tại.

## 4. Gọi AI: chỉ sinh dữ liệu, không sinh giao diện

### Structured output thay cho văn bản tự do

Mọi lời gọi Gemini (trừ Live) đều kèm một Pydantic model làm `response_schema`. Gemini buộc phải trả JSON đúng
schema, backend parse thẳng ra object. Không phải tách chuỗi hay regex trên câu trả lời của AI.

`client.py` có **chuỗi model dự phòng** (cấu hình trong `.env`): model đầu bị quá tải hoặc hết quota (429) thì
chuyển ngay sang model sau. Lỗi tạm thời (5xx, timeout, JSON sai schema) thì thử lại một lần. Hết chuỗi thì báo
lỗi tiếng Việt cho người dùng.

### Bài ngữ pháp dựng từ các "khối"

AI **không sinh HTML**. Mỗi mục của bài ngữ pháp là danh sách khối có kiểu cố định. Frontend có sẵn component
cho từng kiểu:

| Khối | Nội dung | Hiển thị |
|---|---|---|
| `forms` | Công thức của **một** thì / cấu trúc | Thẻ riêng: Khẳng định / Phủ định / Nghi vấn, mỗi dòng có ví dụ và nút nghe |
| `compare` | So sánh 2–3 điểm ngữ pháp | Các cột đặt cạnh nhau |
| `table` | Bảng tổng hợp, động từ bất quy tắc | Bảng |
| `word_list` | Dấu hiệu nhận biết, nhóm động từ | Các nhãn từ |
| `tip`, `text` | Ghi chú, giải thích ngắn | Khung ghi chú, đoạn văn |

Prompt quy định khi nào dùng khối nào, ví dụ "hai thì là hai khối `forms`, không trộn". Cùng một điểm ngữ
pháp phải dùng một tên duy nhất trong cả bài để frontend tô cùng một màu.

Lý do không cho AI sinh HTML:

- Ít token hơn.
- Bố cục giữa các bài luôn đồng nhất.
- Không phải lọc HTML (tránh XSS).
- Dark mode và giao diện điện thoại luôn đúng.

Cần kiểu hiển thị mới thì thêm một loại khối. Bài cũ (định dạng trước đó) được frontend chuyển sang khối khi
hiển thị, không cần migrate dữ liệu.

### Tác vụ chạy nền

Soạn bài và chấm bài viết mất 10–40 giây. `POST` lưu bản ghi với `status=generating`, trả về ngay, rồi chạy
task nền (`services/tasks.py`, asyncio trong cùng tiến trình). Frontend poll tới khi `ready` hoặc `failed`.
Khi cần mở rộng có thể thay bằng queue thật (arq, Celery) mà không phải đổi API.

## 5. Chấm bài: ưu tiên quy tắc, AI chỉ khi cần

- Trắc nghiệm và điền từ chấm bằng quy tắc trên server, không tốn lượt AI:
  - So khớp sau khi chuẩn hoá (bỏ hoa thường, dấu câu, khoảng trắng).
  - Từ dài sai đúng 1 chữ (khoảng cách Levenshtein ≤ 1) tính là "gần đúng".
- Chỉ câu trả lời mở (viết lại câu, tự đặt câu, bài luận) mới gửi Gemini chấm.
- **Đáp án không bao giờ gửi xuống trình duyệt trước khi làm bài.** Câu hỏi ôn tập chỉ mang id dạng
  `<kind>:<ref>`, server dựng lại đáp án từ id lúc chấm.
- "Kiểm tra lại" và phiên ôn tập dựng câu hỏi từ dữ liệu bài đã có, không gọi AI.

## 6. Ôn tập từ vựng (FSRS)

Mỗi từ là một thẻ FSRS. Quy tắc riêng (`services/srs.py`):

- Thẻ đến hạn:
  - Trả lời đúng → Good.
  - Đúng nhưng cần gợi ý hoặc sai 1 chữ → Hard.
  - Sai → Again.
- Thẻ **chưa** đến hạn: trả lời đúng không đổi lịch, vì nhớ khi vừa học chưa chứng minh được gì. Trả lời sai
  vẫn tính Again.
- Giới hạn số từ mới mỗi ngày; từ dư lùi sang ngày sau.

Bài ngữ pháp không có thẻ nên cả bài được kiểm tra lại theo lịch 1-3-7-14 ngày.

## 7. Hội thoại giọng nói

Đây là phần phức tạp nhất.

### Luồng âm thanh

```
Mic ─► AudioWorklet (PCM16, 16 kHz, mono) ─► WebSocket ─► backend ─► Gemini Live
Loa ◄─ WebAudio (PCM16, 24 kHz) ◄──────────── WebSocket ◄─ backend ◄─┘
```

- Trình duyệt thu âm bằng AudioWorklet, chuyển sang PCM16 rồi gửi dạng binary frame. Mic bật sẵn khử tiếng
  vọng và khử ồn, nên người học nói xen được khi Emma đang nói (barge-in).
- Backend làm cầu nối hai chiều giữa trình duyệt và Gemini Live. Nhờ vậy API key không bao giờ xuống client,
  và backend kiểm soát được quyền, thời lượng và nội dung lưu lại.
- Âm thanh hai chiều đi qua `AnalyserNode` để vẽ quả cầu "Emma" trên canvas phản ứng theo giọng nói.
- Thời gian im lặng để coi là hết lượt nói thay đổi theo trình độ: A1 chờ 2 giây, B2 trở lên 0,9 giây.

Giao thức WebSocket được mô tả ở đầu `api/routes/live.py`:

- Client gửi các message `start`, `text`, `action`, `stop` và âm thanh dạng binary.
- Server gửi `transcript`, `pronunciation`, các thẻ, `wrap_up`, `session_end` và âm thanh tutor.

### Thẻ trên màn hình qua function calling

Emma (model Live) được khai báo các tool `show_vietnamese`, `show_feedback`, `show_hint`. Khi model gọi tool,
backend kiểm tra và cắt ngắn tham số (`services/conversation/tools.py`), rồi đẩy xuống client thành thẻ dịch,
thẻ sửa lỗi hoặc thẻ gợi ý. Giọng nói và thẻ chạy song song: Emma vẫn nói tự nhiên, phần chữ cần nhìn thì hiện
trên màn hình.

Các nút trợ giúp nhanh (gợi ý, dịch, nói lại, nói chậm) không gửi câu tự do lên model. Mỗi nút map sang một chỉ
dẫn cố định (`actions.py`), vì vậy hành vi ổn định và người dùng không chèn prompt được. Nếu người học im lặng
quá lâu, frontend tự gửi `auto_hint`.

### Prompt cho tutor

`services/conversation/tutor.py` ghép system prompt từ các phần:

- Persona của Emma.
- Phong cách hội thoại: phản hồi → sửa ngắn → chia sẻ → hỏi tiếp, không hỏi dồn kiểu phỏng vấn.
- Quy tắc theo trình độ CEFR: độ dài câu, tốc độ, mức sửa lỗi.
- Kịch bản role-play.
- Trí nhớ của người học.

Khi người học bí, Emma đi theo từng nấc trợ giúp: trấn an → thu hẹp câu hỏi → đưa câu mẫu và khung câu → hai
câu trả lời mẫu. Emma luôn ở lại câu hỏi hiện tại, không nhảy sang câu khác.

### Chấm phát âm trong lúc nói

Model nghe được giọng nhưng không chấm phát âm đáng tin, vì nó chỉ thấy transcript. Vì vậy backend gom âm thanh
mic của từng lượt nói, cắt khoảng lặng rồi gửi Azure Pronunciation Assessment (chạy song song, không chặn hội
thoại). Kết quả được dùng hai cách:

- Gửi xuống client: điểm và các từ phát âm yếu.
- Gửi một ghi chú ngắn cho Emma, để Emma nhắc từ phát âm sai dựa trên dữ liệu thật thay vì đoán.

### Sau buổi nói

- **Recap**: một lời gọi Gemini thường trên transcript tạo tổng kết gồm lỗi, từ mới và mục tiêu. Tổng kết lưu
  vào session.
- **Trí nhớ**: các lỗi lặp lại, mục tiêu và từ đến hạn ôn được đưa vào prompt buổi sau. Chỉ lưu dữ liệu học
  tập, không lưu thông tin cá nhân. Người học xem và xoá được ở trang tài khoản.
- **Dịch theo yêu cầu**: bấm vào câu hoặc từ của Emma để dịch. Dùng Gemini thường, có cache trong bộ nhớ và
  giới hạn tần suất theo người dùng.

## 8. Âm thanh đọc từ và câu (miễn phí)

Không dùng TTS trả phí. Chuỗi nguồn trong `services/speech/tts.py`, nguồn nào chạy được trước thì dùng:

- **Từ / cụm ngắn**: gTTS (giọng Google Translate, đọc kiểu từ điển) → bản ghi người thật từ Wiktionary →
  Kokoro.
- **Câu**: Kokoro-82M chạy trên server (ngữ điệu câu tự nhiên) → gTTS.

Kokoro đọc từ đơn hay sai trọng âm (model học trên câu), nên với từ đơn mới ưu tiên gTTS. File âm thanh cache
theo hash nội dung, lưu ở `data/tts/` khi chạy local hoặc S3 trên production. Nếu đang phải dùng nguồn dự
phòng, server sẽ thử lại nguồn ưu tiên sau 10 phút.

## 9. Tài khoản, quyền và gói

- Đăng nhập bằng email và mật khẩu, mật khẩu băm Argon2id.
- Phiên đăng nhập lưu trong cookie `et_session` (HttpOnly, SameSite=Lax). DB chỉ lưu SHA-256 của token, nên lộ
  DB cũng không dùng lại được phiên.
- WebSocket kiểm tra header `Origin` để chặn cross-site WebSocket hijacking.
- Tính năng tốn AI (`conversation`, `vocabulary`, `grammar`, `writing`, `pronunciation`) đi qua
  `services/access.py`. Trình tự kiểm tra:
  1. Tài khoản đã được duyệt.
  2. Tính năng đang bật toàn hệ thống.
  3. Gói của người dùng có tính năng đó.
  4. Còn lượt theo ngày / tháng (tính theo giờ Việt Nam).
- Kiểm tra quyền luôn ở API. Frontend chỉ ẩn hoặc khoá UI theo `me.features`.
- Hội thoại giới hạn theo phút. Backend báo thời gian còn lại khi bắt đầu, nhắc Emma kết thúc khi còn 2 phút
  và tự đóng buổi khi hết giờ.

## 10. Frontend

- SPA với các route lazy load. TanStack Query quản lý dữ liệu từ server. Khi gặp 401, cache `me` được xoá để app
  chuyển về trang đăng nhập.
- Tuỳ chọn riêng của từng trình duyệt (giao diện sáng/tối, nguồn âm thanh, cài đặt tập viết) lưu ở
  `localStorage`. Dữ liệu học thật luôn lưu ở backend.
- **Theme**: token màu trong `styles/global.css`, đổi theo thuộc tính `data-theme` trên `<html>`. Một đoạn
  script nhỏ trong `index.html` áp theme trước khi trang hiện, nên không bị nháy màu.
- **Tập viết từ** chấm hoàn toàn trên trình duyệt:
  - So khớp chính xác.
  - Phân biệt sai dấu tiếng Việt với sai nghĩa.
  - Tô từng chữ thiếu hoặc thừa bằng thuật toán LCS.

  Không tốn lượt AI.

## 11. Kiểm thử và chất lượng

- Khoảng 130 test pytest, chạy với **Gemini giả** (`tests/fake_ai.py`), không tốn quota và chạy ổn định trên
  máy dev.
- `make smoke` chạy một buổi hội thoại thật với Gemini Live để kiểm tra đầu cuối (tốn quota, chạy tay).
- `make lint`: ruff check, ruff format check, oxlint. `make test` có thêm `tsc -b` (TypeScript strict).
- Thay đổi model DB luôn đi qua migration Alembic mới. Khi khởi động, app tự migrate.

## 12. Triển khai

Một máy EC2:

```
Internet ─► Caddy (HTTPS tự động) ─► uvicorn (systemd) ─► SQLite trên ổ đĩa
                                                       └─► S3 (cache âm thanh, xác thực bằng IAM role)
```

- `make deploy` chạy script trên server:
  1. `git reset` về `origin/main`.
  2. `uv sync`.
  3. Build frontend.
  4. Restart service (app tự chạy migration khi khởi động).
  5. Đợi health check.
- Biến môi trường và API key chỉ nằm trong `.env` trên server. S3 dùng IAM role của máy nên không cần key.
- Hạn chế hiện tại:
  - Chưa có sao lưu tự động cho SQLite.
  - Task nền và cache dịch nằm trong bộ nhớ tiến trình, nên chưa chạy được nhiều instance.

## 13. Các quyết định thiết kế chính

| Quyết định | Lý do |
|---|---|
| Azure chỉ chấm phát âm, còn lại dùng Gemini | Một nhà cung cấp chính, chi phí thấp. Azure là bên chấm phát âm trên âm thanh thật tốt nhất |
| Backend làm cầu nối cho Gemini Live | Giấu API key, kiểm soát quota, thời lượng và lưu transcript |
| Structured output và khối có kiểu | Ổn định, ít token, giao diện đồng nhất, không phải parse văn bản |
| Chấm bằng quy tắc trước | Nhanh, miễn phí, kết quả nhất quán |
| TTS miễn phí, có cache | Không phát sinh chi phí theo lượt nghe |
| SQLite và một tiến trình | Đủ cho quy mô hiện tại, vận hành đơn giản. Đã sẵn đường chuyển sang Postgres và queue |

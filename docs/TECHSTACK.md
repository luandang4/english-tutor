# Công nghệ & kiến trúc

## Quy tắc nhà cung cấp (đã chốt, không đổi nếu chưa bàn)

| Nhà cung cấp | Dùng cho | Không bao giờ dùng cho |
|---|---|---|
| **Azure Speech** | Chỉ chấm phát âm (Pronunciation Assessment: điểm âm vị / từ / độ trôi chảy / ngữ điệu) | soạn nội dung, chấm bài, hội thoại |
| **Google Gemini** | mọi thứ còn lại: hội thoại giọng nói trực tiếp, soạn bài học và bài tập (từ vựng, ngữ pháp, đề viết), chấm câu trả lời và bài luận | chấm phát âm, âm thanh từ vựng |
| **Âm thanh phát âm miễn phí** (không dùng AI trả phí) | từ đơn: giọng Google Dịch (gTTS), dự phòng bằng bản ghi người thật từ Wiktionary rồi tới Kokoro. Câu: Kokoro-82M, chạy local, không cần mạng | mọi việc khác |

Tính năng AI mới mặc định dùng Gemini. Mọi lời gọi Gemini (trừ Live) đi qua
`backend/app/services/ai/client.py` (chuỗi model dự phòng), mọi lời gọi Azure đi qua
`backend/app/services/speech/azure.py`. Đổi nhà cung cấp chỉ cần sửa 2 module này.

## Model Gemini (chỉnh trong `.env`)

| Việc | Chuỗi mặc định (thử lần lượt) | Lý do |
|---|---|---|
| Hội thoại trực tiếp | `gemini-3.8-live` | giọng nói ↔ giọng nói gốc, có transcript, nối lại phiên |
| Soạn bài học / đề viết | `gemini-3.5-flash` → `gemini-3.8-flash` → `gemini-3.5-flash-lite` | ~6 giây một bài, trả JSON có cấu trúc |
| Chấm câu trả lời ngắn | `gemini-3.5-flash-lite` → `gemini-3.5-flash` | ~1–2 giây một câu |
| Chấm bài luận | `gemini-3.5-flash` → `gemini-3.8-flash` | nhận xét theo tiêu chí, chất lượng tốt |

Khi nào chuyển model: lỗi 429 (hết quota) chuyển ngay sang model tiếp theo; lỗi 5xx, quá thời gian và JSON
sai được thử lại 1 lần rồi mới chuyển.

## Stack

| Tầng | Lựa chọn |
|---|---|
| Backend | Python 3.12, **FastAPI**, Pydantic v2, pydantic-settings |
| Cơ sở dữ liệu | **SQLAlchemy 2.0 (async)** + migration **Alembic**. Mặc định SQLite (WAL); Postgres qua `DATABASE_URL` |
| Lặp lại ngắt quãng | **FSRS** (`fsrs` / py-fsrs) |
| Âm thanh phát âm | `services/speech/tts.py`, chuỗi nguồn cấu hình bằng `TTS_WORD_SOURCES` / `TTS_SENTENCE_SOURCES`. Từ: **gTTS** ([pndurette/gTTS](https://github.com/pndurette/gTTS), giọng Google Dịch; endpoint không chính thức, miễn phí; đọc đều kiểu từ điển) → **bản ghi Wiktionary** (người tình nguyện thu, giấy phép CC; ngữ điệu không đều, ví dụ "season" lên giọng) → **Kokoro-82M** ([kokoro-onnx](https://github.com/thewh1teagle/kokoro-onnx), chạy CPU local; đọc từ đơn hay sai trọng âm nên chỉ là lựa chọn cuối cho từ). Câu: Kokoro → gTTS. Kết quả cache ở `data/tts/`, từ của bài từ vựng mới được tải trước ở nền. Trên Mac Intel, onnxruntime được ghim dưới 1.24 (bản cuối có wheel macOS x86_64). Nếu tất cả đều lỗi thì dùng giọng có sẵn của trình duyệt |
| Việc chạy nền | task asyncio trong cùng tiến trình (`services/tasks.py`). Việc bị ngắt do khởi động lại được đánh dấu failed khi app chạy lên |
| Frontend | **React 19 + TypeScript (strict) + Vite**, React Router (route lazy), TanStack Query |
| Giao diện | CSS token tự viết (màu chính tím pastel, nhấn hồng neon, xanh cyan cho người học), dark / light theo `prefers-color-scheme`. Component chỉ dùng token ngữ nghĩa (`--primary`, `--accent`, `--cool`, …) |
| Âm thanh | AudioWorklet → PCM16 16 kHz (mic); phát bằng WebAudio 24 kHz; quả cầu vẽ bằng canvas |
| Công cụ | uv, ruff, pytest (Gemini giả, không tốn quota), oxlint, `tsc -b` |

## Kiến trúc

```
Trình duyệt (React SPA)
 ├─ REST /api/*  ──────────────►  FastAPI routers ─► services ─► SQLAlchemy ─► SQLite/Postgres
 │                                     │
 │                                     ├─ services/ai/client.py ──► Gemini (soạn / chấm, JSON schema)
 │                                     ├─ services/speech/tts.py ─► Wiktionary / gTTS / Kokoro (có cache)
 │                                     └─ services/speech/azure.py ► Azure Pronunciation Assessment
 └─ WebSocket /ws/conversation ─► api/routes/live.py ───────────► Gemini Live (âm thanh hai chiều)
                                   (transcript lưu vào DB khi kết thúc)
```

- **Soạn bài / đề chạy bất đồng bộ**: `POST` trả về ngay với `status=generating`, việc chạy nền điền nội dung,
  UI poll tới khi `ready` hoặc `failed` (việc lỗi có thể chạy lại).
- **Chấm bài ưu tiên quy tắc**: trắc nghiệm và điền từ khớp chính xác được chấm ngay, không gọi AI. Chỉ câu
  mở và câu điền từ không khớp mới gửi Gemini.
- **Đáp án bị ẩn** khỏi API cho tới khi bài tập đã được làm.
- **Vòng bài tập**: `POST /api/lessons/{id}/exercises/regenerate` nhờ Gemini soạn bộ mới trên cùng từ vựng
  hoặc điểm ngữ pháp. Mọi câu hỏi cũ được gửi kèm để không lặp lại. Id là duy nhất theo vòng (`r2e1`…), điểm
  bài học là điểm của vòng hoàn thành gần nhất.
- **Điểm bài viết** được tính lại phía server bằng trung bình 4 tiêu chí. Lỗi sửa nào không tìm thấy vị trí
  trong bài của người học thì bị bỏ, nên phần tô màu luôn khớp.

## Chủ đề tự tạo

Trang từ vựng, ngữ pháp và viết có form "Chủ đề của bạn": tên chủ đề cùng mong muốn (tuỳ chọn).
`POST /api/lessons` / `POST /api/writing/tasks` nhận `topic_id` (chủ đề có sẵn) hoặc `custom: {title, request}`
(bài học cần thêm `skill`). Service tạo một dòng `Topic` riêng (`user_id` = chủ sở hữu, `focus` = mong muốn);
prompt chỉ dùng mong muốn để định hướng nội dung (cấu trúc, số lượng và trình độ giữ nguyên). Chủ đề tự tạo
không bao giờ hiện trong `/api/topics`, người khác không dùng được (404), và bị xoá cùng bài học / đề cuối
cùng dùng nó (`services/topics.py`).

## Gia sư hội thoại

- **Hành vi khoá theo trình độ** (`services/conversation/tutor.py`): một bộ quy tắc chung cộng một
  `LEVEL_POLICY` nhỏ cho mỗi bậc CEFR (cách nói tiếng Anh, được dùng bao nhiêu tiếng Việt, cách sửa lỗi, bật /
  tắt nâng cấp câu, độ dài câu trả lời). Trình độ chọn lúc bắt đầu cố định suốt buổi: người học nói tiếng Việt
  cũng không làm Emma dùng tiếng Việt nhiều hơn.
- **Sửa lỗi chặt** ở mọi trình độ, ưu tiên lỗi điển hình của người Việt; **nâng cấp câu** (câu đúng nhưng đơn
  giản) ở mọi trình độ, cao hơn người học một bậc (A1 câu đầy đủ → C1 sắc thái / thành ngữ), không bao giờ
  trong lượt có lỗi thật, với tần suất người học chọn (Ít / Vừa / Nhiều).
- **Thang trợ giúp** khi người học bí: thu hẹp câu hỏi → khung câu → 2 câu mẫu → hỏi lại.
- **Thẻ trên màn hình** qua function call của Live (`services/conversation/tools.py`): `show_vietnamese`
  (dịch nghĩa), `show_feedback` (sửa lỗi / "Nói hay hơn"), `show_hint` ("Gợi ý trả lời"; tiếng Việt chỉ ở
  A1–B1, server tự bỏ ở trình độ cao hơn). Thẻ được lưu trong transcript thành lượt riêng.
- **Nút trợ giúp nhanh** gửi `{"type": "action"}`; server ánh xạ các action trong danh sách cho phép sang chỉ
  dẫn cố định (`services/conversation/actions.py`), không bao giờ chuyển nguyên văn chữ từ client. Trình duyệt
  gửi `auto_hint` sau 6 giây im lặng kể từ câu hỏi của Emma. Còn 2 phút trước khi hết giờ, Emma được báo để
  chốt buổi.
- **Không cắt lời**: VAD của Gemini Live dùng độ nhạy kết thúc lời nói thấp và khoảng lặng theo trình độ trước
  khi kết thúc lượt người học (A1 2000 ms, A2 1600, B1 1200, B2/C1 900; `LIVE_END_OF_SPEECH_MS` ép một giá trị).
- **Chấm phát âm chỉ từ âm thanh thật** (`services/conversation/pronunciation.py`): server giữ âm thanh mic và
  transcript của từng lượt người học nói. Sau khi Emma trả lời lượt đó, đoạn âm thanh được cắt gọn và Azure chấm
  (văn bản tham chiếu = transcript; bỏ qua lượt lẫn tiếng Việt, lượt gõ chữ, lượt quá ngắn hoặc dài hơn 30 giây).
  Kết quả gửi tới UI (điểm + từ phát âm yếu kèm nút nghe, cũng lưu trong transcript) và tới model dưới dạng tin
  nhắn ngữ cảnh `[Pronunciation data]` (`turn_complete=False`, giữ lại khi Emma đang nói vì nội dung từ client
  sẽ ngắt câu trả lời của Live). Không có Azure thì prompt cấm Emma nhận xét phát âm. Tắt bằng
  `LIVE_PRONUNCIATION=false`.

## Cache âm thanh và tuỳ chọn

- Âm thanh từ / câu đã tạo được cache (tên = hash + nguồn + đuôi file) ở `data/tts/` khi chạy local, hoặc S3
  trên production (`TTS_STORAGE=s3`, `TTS_S3_BUCKET`, `TTS_S3_PREFIX`; `services/speech/audio_store.py`, dùng
  IAM role của EC2, không cần key). Một vòng lặp nền (mỗi giờ và lúc khởi động) xoá file cũ hơn
  `TTS_CACHE_MAX_DAYS` (30), rồi xoá file cũ nhất tới khi cache dưới `TTS_CACHE_MAX_MB` (1024); bucket S3 cũng
  có rule tự xoá sau 30 ngày. File bị xoá sẽ được tạo lại khi cần.
- Người học chọn nguồn âm thanh theo từng trình duyệt (trang bài học, ôn tập và tài khoản): Tự động, Google
  Dịch, người thật (Wiktionary), Kokoro. `GET /api/tts?source=...` đặt lựa chọn đó lên đầu và giữ chuỗi mặc
  định làm dự phòng.
- Hội thoại: bật "Đeo tai nghe" = mic vẫn mở khi Emma nói (ngắt lời được); tắt = client tạm dừng mic khi Emma
  nói.
- Gia sư luôn dùng giọng Gemini `Kore` (không có chọn giọng).
- Tổng kết cuối buổi (`services/conversation/recap.py`): `POST /api/conversations/{id}/recap` tạo một lần
  (số liệu từ transcript + một lời gọi Gemini thường: lỗi, từ mới, điểm mạnh, mục tiêu) và lưu vào
  `conversation_sessions.summary`. Không tính vào quota.
- Trí nhớ người học (`services/conversation/memory.py`, bảng `learner_memories`): lỗi hay lặp lại theo nhóm và
  các mục tiêu gần nhất, gộp từ mỗi bản tổng kết; cộng thêm các từ trong bộ ôn sắp đến hạn. Được đưa vào prompt
  của gia sư dưới dạng dữ liệu. Chỉ là dữ liệu học tập (không có thông tin cá nhân); người học xem / xoá ở trang
  tài khoản.
- "I don't understand" / "tôi không hiểu": Emma gọi function Live `show_vietnamese(english, vietnamese)`;
  server gửi `{"type": "translation"}` tới UI (bong bóng viền nét đứt, lưu trong transcript với role
  `translation`), rồi Emma nhắc lại bằng tiếng Anh đơn giản hơn. Chỉ là chữ trên màn hình nên áp dụng ở mọi
  trình độ.

## Quản trị, gói & giới hạn

Mọi thứ tốn quota AI là một **tính năng**: `conversation`, `vocabulary`, `grammar`, `writing` (Gemini) và
`pronunciation` (Azure). Người dùng có tính năng thông qua **gói** (bảng `plans`: các tính năng, giới hạn mỗi
tính năng `{daily, monthly}` với 0 = không giới hạn, số phút mỗi buổi hội thoại, thời hạn mặc định, nhãn giá /
chu kỳ thanh toán chỉ để hiển thị). Một dòng `subscriptions` gán người dùng vào gói (ngày bắt đầu, ngày hết hạn
hoặc không có, trạng thái `active` / `expired` / `cancelled`, ghi chú, `assigned_by`, `source` admin | payment);
lịch sử được giữ lại và mỗi người dùng có tối đa một dòng đang hiệu lực. `usage_grants` cộng thêm lượt cho một
người (trong tháng này hoặc một ngày). Các gói ban đầu (migration tạo sẵn): Dùng thử, Cơ bản, Nâng cao, Bạn bè.

`services/access.py` quyết định quyền; một tính năng dùng được khi:

1. tài khoản đang hoạt động (tài khoản bị khoá bị đăng xuất ở mọi nơi và không đăng nhập được),
2. tính năng đang bật toàn hệ thống (công tắc khẩn của admin; áp dụng cả cho admin),
3. admin: được phép, không giới hạn; người khác: có gói đang hiệu lực, chưa hết hạn và gói có tính năng đó
   (hạn được kiểm tra khi cần và dòng bị đánh dấu `expired`),
4. mức dùng hôm nay dưới giới hạn ngày của gói, và tháng dương lịch này dưới giới hạn tháng (cộng lượt tặng;
   hội thoại tính theo phút, còn lại tính theo số lần gọi AI; ranh giới ngày / tháng theo `TIMEZONE`).

Khi gói hết hạn, các tính năng AI bị khoá, nhưng vẫn ôn từ vựng và mở lại bài học / đề viết / hội thoại cũ của
mình được (`ensure_view`; `require_feature` coi GET / DELETE là quyền xem).

**Kiểm tra ở API, không phải ở UI.** Router phụ thuộc `require_feature(...)`; thao tác gọi AI còn chạy
`access.ensure_quota()` + `record_usage()` (bảng `usage_events`). WebSocket hội thoại kiểm tra tính năng và giới
hạn buổi ở min(số phút mỗi buổi của gói hoặc `MAX_LIVE_SESSION_MINUTES`, số phút còn lại hôm nay / tháng này);
chấm phát âm trong hội thoại kiểm tra tính năng phát âm và giới hạn của nó ở từng lượt. `/api/tts` cần tài khoản
đã được duyệt (gói đang hiệu lực hoặc đã hết hạn). Từ chối trả `403` (không có quyền / chờ duyệt / hết hạn / đang
tắt) hoặc `429` (hết giới hạn ngày hoặc tháng), kèm dòng `upgrade_contact` admin nhập. Frontend ẩn hoặc khoá
những gì `me.features` không có (`FeatureGate`, biểu tượng khoá trên thanh điều hướng), nhưng request tự tạo
vẫn nhận đúng 403 / 429.

- Cài đặt hệ thống nằm trong `app_settings` (key `system`): `features_enabled`, `registration_open`,
  `upgrade_contact`.
- Đăng ký trên web chỉ do công tắc của admin quyết định (`registration_open`). Tài khoản mới **chờ admin chọn
  gói**, trừ khi có gói được đánh dấu "mặc định cho tài khoản mới".
- Tài khoản đầu tiên được tạo thành admin; `deploy/create-user.sh EMAIL "Tên" [--admin] [--plan CODE]` thêm tài
  khoản từ dòng lệnh. Admin không tự khoá hay tự bỏ quyền admin của mình được (luôn còn ít nhất một admin).
- Trang quản trị `/admin`: các tab Người dùng (duyệt = chọn gói, hạn dùng, lượt tặng, khoá / admin, thanh mức
  dùng, bộ lọc), Gói (tạo / sửa / ngừng gói), Sử dụng (tổng tháng này so với mức miễn phí của Azure), Hệ thống.
- Người học xem gói và mức dùng ngày / tháng ở trang Tài khoản và trang chủ (`GET /api/auth/me/usage`); trang
  chủ nhắc trước 3 ngày khi gói sắp hết hạn.
- Mật khẩu: ít nhất 8 ký tự, có chữ và số (`core/security.py: password_problem`, cùng quy tắc hiện trực tiếp dưới
  ô mật khẩu).

## Tài khoản & tách dữ liệu

- Tài khoản bằng email và mật khẩu. Mật khẩu băm bằng **Argon2id** (`argon2-cffi`).
- Đăng nhập tạo một token ngẫu nhiên 256 bit trong **cookie HttpOnly, SameSite=Lax** (`et_session`). DB chỉ lưu
  SHA-256 của nó trong `auth_sessions`, nên lộ DB cũng không lộ phiên đang dùng. Phiên kéo dài `SESSION_DAYS`
  (30). Đăng xuất xoá phiên phía server, đổi mật khẩu đăng xuất mọi thiết bị khác.
- Mọi bảng học tập có `user_id`. Route dùng `CurrentUser` và `get_owned()`, trả **404** (không phải 403) với dữ
  liệu của người khác để không lộ gì. Bài nộp thuộc về đề viết, lần làm bài tập thuộc về bài học, lịch sử ôn
  thuộc về thẻ. Bộ từ ôn tập là duy nhất theo `(user_id, word_key)`.
- WebSocket hội thoại kiểm tra cùng cookie đó (cộng kiểm tra Origin) trước khi mở phiên Gemini Live.
- Endpoint công khai: `/api/health`, `/api/meta`, `/api/topics`, `/api/auth/*`. Mọi thứ còn lại, kể cả
  `/api/tts`, cần đăng nhập.
- Chống dò mật khẩu: tối đa 10 lần đăng nhập sai mỗi IP trong 15 phút (lưu trong bộ nhớ). Email không tồn tại
  mất thời gian xử lý bằng mật khẩu sai.
- **Chuyển dữ liệu cũ**: các dòng tạo trước khi có tài khoản có `user_id = NULL`, tài khoản đăng ký đầu tiên
  nhận hết.
- Cài đặt: `COOKIE_SECURE` (bật khi chạy sau HTTPS), `SESSION_DAYS`.

## Mô hình dữ liệu

`users` + `auth_sessions` · `topics` (chủ đề có sẵn với `user_id` NULL, cộng chủ đề tự tạo có `user_id`) ·
theo người dùng: `lessons` (+ `exercise_attempts`, `lesson_rechecks`) · `vocab_cards` (trạng thái FSRS) +
`review_logs` + `srs_settings` · `writing_tasks` (+ `writing_submissions`) · `conversation_sessions`
(transcript, tổng kết) + `learner_memories` · `pronunciation_attempts` · gói: `plans`, `subscriptions`,
`usage_grants`, `usage_events` · `app_settings`.

## Cấu trúc thư mục

```
backend/
  app/
    main.py              tạo app, lifespan (migration, seed, dọn việc dở), phục vụ SPA
    core/                cài đặt, hằng số (trình độ, kỹ năng, trạng thái), logging
    db/                  declarative base, kiểu datetime UTC, engine / session async
    models/              bảng ORM
    schemas/ai.py        JSON schema Gemini phải điền
    schemas/api.py       DTO request / response
    services/            nghiệp vụ (bài học, chấm bài, srs, viết, tiến độ, việc chạy nền)
      ai/                client Gemini + prompt
      speech/            chấm phát âm Azure + chuỗi âm thanh từ / câu
      conversation/      cấu hình Gemini Live (live.py), quy tắc gia sư theo CEFR (tutor.py),
                         chấm phát âm từng lượt (pronunciation.py), tổng kết, trí nhớ
    api/routes/          lớp HTTP / WebSocket mỏng
    seed/topics.py       chủ đề có sẵn (sửa để thêm)
  alembic/               migration
  tests/                 pytest (AI giả), fixture
  scripts/smoke_live.py  smoke test Gemini Live thật
frontend/
  src/
    api/                 client có kiểu, kiểu DTO, hook TanStack Query
    components/          khung layout, bộ UI, bài tập, phát âm
    features/            trang chủ, hội thoại, bài học (từ vựng + ngữ pháp), ôn tập từ vựng,
                         tập viết từ (drill; số lần viết lưu ở localStorage), viết luận, quản trị, tài khoản
    lib/                 âm thanh (phiên live, ghi âm, TTS), định dạng, tuỳ chọn
    orb/                 quả cầu canvas phản ứng theo âm thanh
    styles/global.css    design token + component
  public/pcm-worklet.js  AudioWorklet thu âm mic
docs/TECHSTACK.md
```

## Triển khai (AWS EC2)

Mọi bước đều có script trong `deploy/` (AWS profile `new-frontiers`, region `ap-southeast-2`, xem
`deploy/config.sh`).

| Tài nguyên | Giá trị |
| --- | --- |
| EC2 | `english-tutor`, t3.small, Ubuntu 24.04, 20 GB gp3 (mã hoá), 2 GB swap |
| Tên miền | https://english-tutor.us.ci (bản ghi A → Elastic IP của instance, tag `english-tutor`) |
| S3 | `english-tutor-tts-<account id>`, riêng tư (Block Public Access), `tts/` tự xoá sau 30 ngày |
| IAM | role / instance profile `english-tutor-ec2`: chỉ được truy cập bucket đó |
| Security group | `english-tutor-web`: mở 80/443, cổng 22 chỉ cho IP của các máy deploy |
| SSH key | `~/.ssh/english-tutor.pem` (không bao giờ commit; `ssh -i ~/.ssh/english-tutor.pem ubuntu@english-tutor.us.ci`) |

Trên server: Caddy (HTTPS bằng Let's Encrypt, security header, giới hạn body 1 MB, `deploy/Caddyfile`) → uvicorn
ở 127.0.0.1:8000 (systemd unit `english-tutor`, `deploy/english-tutor.service`). Code ở `/opt/english-tutor`
(git clone repo public), SQLite + model Kokoro ở `/opt/english-tutor/data`, `.env` (quyền 600) = `.env` local +
các giá trị riêng cho production.

```sh
make provision                    # 1 lần: tạo tài nguyên AWS (chạy lại để cho phép SSH từ IP mới)
make bootstrap                    # 1 lần: cài gói, .env, bản release đầu tiên
git push origin main && make deploy   # mỗi lần release: git reset về origin/main, uv sync, npm build, restart
deploy/set-env.sh COOKIE_SECURE=true          # đổi một cài đặt trên server + restart
deploy/create-user.sh you@example.com "Tên"   # thêm tài khoản khi đăng ký web đang đóng
deploy/enable-https.sh tutor.example.com      # sau khi DNS trỏ về Elastic IP
```

## Giữ repo public sạch

Repo GitHub là public nên không bao giờ được chứa: `.env` / API key, `*.pem` / SSH key, file SQLite, `data/`,
AWS account ID hoặc access key. `.gitignore` đã chặn các mục này; script deploy tra account ID lúc chạy
(`aws sts get-caller-identity`) và server lấy quyền AWS chỉ qua instance role.
Biết code cũng không vào được hệ thống: đăng ký đang đóng, đăng nhập bị giới hạn tần suất, mọi API route cần
cookie phiên, và SSH chỉ nhận key deploy từ các IP đã cho phép.

## Checklist production

- [x] systemd + Caddy, cache âm thanh trên S3, giới hạn SSH
- [x] HTTPS (`deploy/enable-https.sh english-tutor.us.ci`): `COOKIE_SECURE=true`, `ALLOWED_ORIGINS` = tên miền
- [x] `API_DOCS=false` (không có `/docs`, `/openapi.json`)
- [x] đăng ký bật / tắt trong `/admin`; tài khoản mới chờ duyệt; `deploy/create-user.sh` cũng thêm được tài khoản
- [ ] sao lưu `/opt/english-tutor/data/app.db` (SQLite nằm trên ổ của instance; chưa có)

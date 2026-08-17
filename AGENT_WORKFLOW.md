# AGENT_WORKFLOW.md
# ESP32 AUDIO SYSTEM — AGENT WORKFLOW, TASK & LOG RULES

## 1. Mục tiêu

File này quy định cách agent làm việc với project.

Không chứa kiến trúc chi tiết.

Kiến trúc và contract kỹ thuật nằm trong:

```text
PROJECT_RULES.md
```

---

# 2. Session Start Rule

Đầu mỗi session mới, trước khi sửa code:

1. Đọc `TASK.md`
2. Đọc các phần liên quan trong `PROJECT_RULES.md`
3. Đọc các entry gần nhất trong `LOG.md`
4. Kiểm tra Source Code liên quan
5. Kiểm tra Git status nếu project dùng Git
6. Xác định:
   - cái gì đã hoàn thành
   - cái gì đang làm dở
   - cái gì đang FAIL
   - dependency tiếp theo
7. Sau đó mới bắt đầu sửa code

Không cần đọc toàn bộ LOG.md nếu File đã dài.

Mặc định:

- đọc 5–10 entry gần nhất
- search entry cũ khi task hiện tại liên quan

---

# 3. Source of Truth khi bắt đầu session

Không được tin hoàn toàn LOG.md.

Source of Truth cuối cùng:

1. Source Code hiện tại
2. Config hiện tại
3. `PROJECT_RULES.md`
4. API / MQTT Contract hiện tại
5. Test hiện tại

Nếu LOG.md mâu thuẫn với Source Code:

- ưu tiên Source Code + Test thực tế
- ghi chú discrepancy vào LOG.md sau khi xác minh

---

# 4. TASK.md

`TASK.md` dùng cho task hiện tại.

`TASK.md` có thể update hoặc ghi đè.

Format đề xuất:

```md
# Current Task

## Goal

...

## Acceptance Criteria

- ...
- ...

## Status

TODO / IN PROGRESS / BLOCKED / DONE

## Current Issue

...

## Related Files

- ...

## Next Step

...
```

Ví dụ:

```md
# Current Task

## Goal

Hoàn thành HTTP Audio Streaming từ Backend tới ESP32.

## Acceptance Criteria

- ESP32 mở được Audio URL
- Không tải toàn bộ File vào RAM
- Đọc Audio theo chunk
- MP3 decode được
- I2S phát được Audio
- STOP hủy Stream ngay
- Không crash sau nhiều lần PLAY

## Status

IN PROGRESS

## Current Issue

Decoder bị buffer underrun sau khoảng 20 giây.

## Related Files

- esp32/audio_stream.cpp
- esp32/audio_player.cpp
- backend/app/routes/audio_routes.py

## Next Step

Kiểm tra tốc độ refill buffer.
```

---

# 5. Acceptance Criteria

Mỗi task lõi phải có điều kiện DONE rõ ràng trước khi code.

Ví dụ task Audio Streaming:

```text
DONE khi:

- ESP32 stream được MP3 từ Backend
- Không download toàn bộ File
- Không crash
- PLAY hoạt động
- STOP dừng đúng
- Buffer không underrun trong test cơ bản
- Có Status phản hồi
```

Task chỉ được chuyển DONE khi Acceptance Criteria chính đã đạt.

---

# 6. Development Workflow

Không dùng quy trình nặng cho mọi task.

## Module lõi

Áp dụng cho:

- MQTT Contract
- Audio Streaming
- ESP32 Playback
- Cloud Integration

Workflow:

```text
Requirement
↓
Define Contract
↓
Implementation
↓
Module Test
↓
Integration Test
↓
End-to-End Test
```

## Feature nhỏ

Ví dụ:

- GET danh sách Audio
- đổi UI
- thêm Metadata Field
- thêm Endpoint đơn giản

Workflow:

```text
Implementation
↓
Test thực tế
↓
Done
```

---

# 7. Test Priority

Ưu tiên test:

1. ESP32 kết nối WiFi
2. ESP32 kết nối Mosquitto
3. MQTT Command → ESP32
4. ESP32 Status → Backend
5. HTTP Audio Streaming
6. Decode + I2S Playback
7. PLAY / STOP race/ordering
8. Upload Audio
9. Metadata
10. Text-to-Speech
11. Cloud Database
12. Notification
13. Web UI
14. Full End-to-End

---

# 8. LOG.md

Sau khi hoàn thành một task hoặc checkpoint có ý nghĩa, agent phải APPEND vào:

```text
LOG.md
```

ở root project.

Không ghi đè toàn bộ File.

Format:

```md
### [YYYY-MM-DD HH:mm] - [Tên task ngắn gọn]

- Đã làm:
  - ...

- File đã sửa:
  - ...

- Test:
  - PASS / FAIL / PARTIAL / NOT TESTED
  - Mô tả ngắn kết quả test

- Còn thiếu / lưu ý:
  - ...
```

---

# 9. Ví dụ LOG.md

```md
### 2026-08-14 22:45 - Add MQTT LWT

- Đã làm:
  - Thêm Last Will cho ESP32 MQTT Client
  - Publish ONLINE sau khi connect thành công

- File đã sửa:
  - esp32/mqtt_manager.cpp
  - esp32/mqtt_manager.h

- Test:
  - PASS
  - Tắt ESP32 đột ngột, Broker publish OFFLINE đúng topic

- Còn thiếu / lưu ý:
  - Chưa nối DEVICE_OFFLINE với Push Notification
```

---

# 10. Quy tắc LOG.md

Không log:

- toàn bộ code
- toàn bộ terminal output
- stack trace dài
- reasoning nội bộ
- debug tạm thời

Chỉ log đủ để session sau biết:

- vừa làm gì
- sửa File nào
- test ra sao
- còn thiếu gì

Không cần log riêng cho:

- đổi tên biến
- sửa typo
- thêm import

Nên log sau:

- hoàn thành MQTT connection
- hoàn thành Audio Streaming
- thêm API Upload
- sửa lỗi Playback
- hoàn thành Cloud Integration
- hoàn thành bugfix quan trọng

---

# 11. Không được ghi log sai trạng thái

Không ghi:

```text
PASS
```

nếu chưa test.

Không ghi:

```text
DONE
```

nếu task chưa hoàn thành.

Không ghi:

```text
đã sửa
```

nếu mới chỉ đề xuất.

Nếu chưa test:

```text
NOT TESTED
```

Nếu test một phần:

```text
PARTIAL
```

---

# 12. Task chưa hoàn thành

Nếu session kết thúc khi task chưa xong, vẫn append LOG.md.

Ví dụ:

```md
### 2026-08-14 23:00 - Audio Streaming - IN PROGRESS

- Đã làm:
  - HTTP connection hoạt động
  - Đọc được chunk từ Backend

- File đã sửa:
  - esp32/audio_stream.cpp

- Test:
  - PARTIAL
  - Nhận được dữ liệu nhưng decoder chưa phát ổn định

- Còn thiếu / lưu ý:
  - Chưa nối stream hoàn chỉnh vào decoder
  - Cần kiểm tra buffer underrun
```

---

# 13. Quy trình sau khi hoàn thành task

Sau khi code:

1. Chạy test phù hợp
2. Đối chiếu Acceptance Criteria
3. Kiểm tra File thực sự đã sửa
4. Cập nhật `TASK.md`
5. APPEND `LOG.md`
6. Ghi rõ:
   - PASS
   - FAIL
   - PARTIAL
   - NOT TESTED
7. Không tuyên bố DONE nếu còn Acceptance Criteria chính chưa đạt

---

# 14. Quy tắc khi sửa code

Trong khi code:

- sửa tối thiểu đúng phạm vi task
- không đổi kiến trúc ngoài phạm vi
- không tự thêm service mới
- không tự đổi MQTT topic
- không tự đổi API contract
- không tự đổi Audio Streaming thành download toàn bộ
- không thêm dependency lớn nếu chưa cần
- không refactor diện rộng nếu task không yêu cầu
- ưu tiên fix root cause thay vì workaround tạm thời

Nếu cần thay đổi contract:

1. xác định các bên bị ảnh hưởng
2. cập nhật contract trước
3. cập nhật Backend
4. cập nhật ESP32/Web liên quan
5. integration test
6. log thay đổi rõ ràng

---

# 15. Không Over-Engineer

Version đầu KHÔNG cần:

- Microservices
- Kafka
- Redis
- Kubernetes
- Complex Event Bus
- Command Queue dài
- Audio upload lên Cloud Storage
- Multiple Database
- Multiple MQTT Broker
- Authentication phức tạp nếu bài không yêu cầu

Ưu tiên:

```text
Simple
↓
Working
↓
Testable
↓
Stable
↓
Optimize
```

---

# 16. Khi Agent gặp mâu thuẫn

Nếu:

- TASK.md
- LOG.md
- PROJECT_RULES.md
- Source Code

mâu thuẫn nhau:

Agent phải:

1. không tự đoán
2. kiểm tra Source Code + Test
3. ưu tiên `PROJECT_RULES.md` cho architecture/contract
4. cập nhật TASK.md theo trạng thái thật
5. ghi discrepancy vào LOG.md sau khi xử lý

Không tự sửa architecture chỉ để khớp code cũ.

---

# 17. Checklist đầu session

```text
[ ] Đọc TASK.md
[ ] Đọc phần PROJECT_RULES.md liên quan
[ ] Đọc 5–10 LOG entry gần nhất
[ ] Kiểm tra source code liên quan
[ ] Kiểm tra Git status
[ ] Xác định current issue
[ ] Xác định acceptance criteria
[ ] Bắt đầu task
```

---

# 18. Checklist cuối task

```text
[ ] Code đúng phạm vi
[ ] Không phá PROJECT_RULES.md
[ ] Test đã chạy
[ ] Acceptance Criteria đã đối chiếu
[ ] TASK.md đã cập nhật
[ ] LOG.md đã APPEND
[ ] Không ghi PASS nếu chưa test
[ ] Không ghi DONE nếu chưa hoàn thành
```

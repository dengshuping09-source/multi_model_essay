# Testing and live-service verification

The project has two intentionally separate test layers.

## 1. Offline automated tests

These tests are safe to run routinely and may use `FakeReviewProvider`,
`StaticOcrEngine`, mocks, and test data. They validate API behaviour,
database persistence, aggregation and disagreement logic, schemas, error
handling, and permissions. They do **not** prove that a third-party model or
OCR service is usable.

Run from `backend`:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
```

The correct conclusion is: **"离线自动测试通过"**.

## 2. Explicit real-service Smoke Test

`scripts/real_smoke_test.py` is not discovered by pytest. It contacts real
services only after the developer explicitly supplies `--confirm-live`, so it
can incur model/OCR charges. It never prints credentials or raw provider
responses.

Run the model and PostgreSQL checks:

```powershell
.\.venv\Scripts\python.exe scripts\real_smoke_test.py --confirm-live
```

Run the complete check, including real OCR on a real handwriting image:

```powershell
.\.venv\Scripts\python.exe scripts\real_smoke_test.py --confirm-live --image C:\path\to\handwriting.jpg
```

The script creates a temporary local smoke-test user and essays, then removes
only those records and uploaded artefacts. It reports each item as exactly one
of `PASS`, `FAIL`, `NOT CONFIGURED`, or `NOT VERIFIED`:

```text
数据库              PASS
DeepSeek            PASS
Qwen                PASS
豆包                FAIL - 账号当前未开通该模型
百度 OCR            PASS
PaddleOCR           NOT VERIFIED - 当前默认模式不启动 PaddleOCR
电子作文评测         PASS
图片 OCR            PASS
```

Only after the relevant explicit Smoke Test reports the required live services
as `PASS` may the project claim: **"真实核心服务已验证"**. `NOT CONFIGURED`
and `NOT VERIFIED` are never successes.

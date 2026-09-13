# 多模型协同作文智能评测系统

项目提供可从头走完的作文评测流程：账户注册与数据隔离、作文提交、多页图片上传、OpenCV 预处理、PaddleOCR/百度 OCR、OCR 校对与图文定位、三模型独立评审、分歧复核、综合报告、历史查看和教师参考评分录入。

## 项目结构

```text
.
|-- frontend/                 # Vue 3 + TypeScript + Vite
|-- backend/                  # FastAPI
|   |-- app/
|   |   |-- api/              # HTTP 路由
|   |   |-- core/             # 配置等基础能力
|   |   |-- db/               # 数据库连接和 ORM 模型
|   |   `-- modules/          # OCR、评审、作文等业务模块位置
|   |-- migrations/           # Alembic 数据库迁移
|   `-- tests/                # 后端测试
`-- compose.yaml              # PostgreSQL 本地开发服务
```

## 环境要求

- Node.js 20+
- Python 3.11+
- PostgreSQL 16+

## 配置并启动 PostgreSQL

项目根目录的环境变量供 Docker Compose 使用：

```powershell
Copy-Item .env.example .env
```

编辑根目录 `.env`，设置本地数据库名、用户和密码，然后启动 PostgreSQL：

```powershell
docker compose up -d postgres
```

后端使用 `backend/.env` 中的 `DATABASE_URL`。其中的数据库、用户和密码需要与根目录 `.env` 保持一致：

```powershell
cd backend
Copy-Item .env.example .env
```

示例格式：

```dotenv
DATABASE_URL=postgresql+asyncpg://essay_app:your_password@localhost:5432/essay_evaluation
```

## 执行数据库迁移

在 `backend` 目录、虚拟环境已激活的情况下运行：

```powershell
alembic upgrade head
alembic current
```

开发模型发生变化后，可创建新的迁移：

```powershell
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```

## 启动后端

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python app.py
```

后端健康检查地址：<http://localhost:8000/api/health>

数据库连通检查地址：<http://localhost:8000/api/health/database>

## Windows 一键启动

首次使用时，先完成一次环境准备：安装 PostgreSQL、在 `backend` 创建 `.env` 并设置 `DATABASE_URL`，再分别安装 Python 与前端依赖。脚本优先使用 Windows 本机 PostgreSQL 服务；若未发现本机服务，才尝试使用 Docker Compose。

之后在项目根目录执行：

```powershell
.\start.ps1
```

如果 PostgreSQL 是通过 `winget` 静默安装的、尚未设置管理员密码，请以管理员身份打开 PowerShell，在项目根目录先运行一次：

```powershell
.\setup-local-postgres.ps1
```

脚本会安全地临时调整本机认证规则、设置密码、创建项目数据库并恢复认证配置。之后不需要再次运行它。

脚本会依次启动或复用 PostgreSQL、FastAPI 和 Vue，等待 PostgreSQL 端口就绪、检查后端健康检查和数据库连通性、检查前端页面，然后输出以下地址：

- Vue：<http://127.0.0.1:5173>
- FastAPI：<http://127.0.0.1:8000>
- API 文档：<http://127.0.0.1:8000/api/docs>

若 PowerShell 限制本地脚本执行，可仅对当前终端运行：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\start.ps1
```

脚本不会改变现有单独启动方式。后端与前端启动日志保存在根目录 `logs/`。

## 启动前端

另开一个终端：

```powershell
cd frontend
npm install
Copy-Item .env.example .env
npm run dev
```

打开 <http://localhost:5173>。页面显示“后端连接正常”并展示健康检查结果，即表示前后端已经连通。

数据库连接正常时，连通检查返回：

```json
{"status":"ok","database":"postgresql"}
```

## 提交作文

前端首页提供作文提交表单，支持直接输入正文、选择多张图片和移动端拍照。图片通过 `multipart/form-data` 原始文件流上传，不使用 Base64。

后端提交接口：

```text
POST /api/essays
```

表单字段：

- `title`：作文标题，可选
- `original_text`：作文原始文本，可选
- `images`：图片文件，可重复传入并按传入顺序保存

必须提供正文或至少一张图片。默认最多上传 10 张图片，单张不超过 10 MB，支持 JPG、JPEG、PNG 和 WebP。原始图片保存在 `backend/storage/uploads/<essay_id>/`，数据库保存原始文件名、相对存储路径、实际 MIME、文件大小、宽高和页码。

上传限制可在 `backend/.env` 中通过以下变量调整：

```dotenv
UPLOAD_DIR=storage/uploads
MAX_UPLOAD_SIZE_MB=10
MAX_UPLOAD_FILES=10
MAX_IMAGE_PIXELS=40000000
MAX_ESSAY_TEXT_LENGTH=50000
OCR_DEVICE=cpu
OCR_DETECTION_MODEL=PP-OCRv5_server_det
OCR_RECOGNITION_MODEL=PP-OCRv5_server_rec
OCR_LOW_CONFIDENCE_THRESHOLD=0.65
```

## 图片质量检测与 OCR 前预处理

图片上传后会立即使用 OpenCV 分析清晰度、亮度、对比度、光照均匀度、方向、倾斜和页面边界。每张图片得到以下质量状态之一：

- `good`：质量良好，保留原图，不额外转码
- `improvable`：可以识别，并按需执行方向纠正、透视矫正、倾斜校正或光照改善
- `unusable`：严重模糊、曝光异常或无法判断有效页面，保留原图并提示重新拍摄，不生成处理图

处理过程不会覆盖原始文件。仅在确实应用了处理操作时，才在原图目录下的 `processed/` 保存独立 PNG。质量指标、提示、页面轮廓、处理动作和处理图路径保存在 `image_quality_analyses` 表中。

图片预览接口：

```text
GET /api/essays/sources/{source_id}/images/original
GET /api/essays/sources/{source_id}/images/processed
```

图像几何变换会同时保存正向和逆向 3×3 矩阵，供 OCR 区域坐标映射回原图。

## PaddleOCR 备用识别

作文图片提交成功后，前端会自动调用识别接口。后端按用户上传页序逐页处理，质量良好的页面使用原图，已完成必要优化的页面使用处理图；`unusable` 页面会跳过并提示重新拍摄。

```text
POST /api/essays/{essay_id}/ocr
GET  /api/essays/{essay_id}/ocr
```

每次识别记录保存在 `ocr_runs`，逐页状态和输入图版本保存在 `ocr_page_results`，识别文字、置信度、阅读顺序、识别图坐标和原图坐标保存在 `ocr_blocks`。多页纯文本只作为一次识别结果的组合视图，不覆盖用户直接输入的 `essays.original_text`。

PaddleOCR 保留为可人工启用的本地备用识别能力。默认的生产 OCR 提供方为百度手写文字识别，因此日常上传不会启动 Paddle Worker 或加载 Paddle 模型；只有明确将 `OCR_DEFAULT_ENGINE=paddle` 并启用 `paddle-worker` profile 时才会加载本地模型。

## OCR 校对与图文对齐

识别完成后，前端可进入校对工作区：左侧使用原始上传图片，右侧按阅读顺序展示对应页面的 OCR 文本区域。点击任一文字区域会定位并高亮原图坐标；点击原图叠加的识别区域则会选中、滚动到对应文本。页面页签始终按上传顺序排列。

低置信度文字会以轻量提示标识，用户可直接修改其文字。原始 OCR 结果保留在 `ocr_blocks.text`，不会被编辑操作覆盖。用户校对内容存储在以下两张表中：

- `ocr_corrections`：一份 OCR 运行对应一份校对草稿或已确认的校对文本。
- `ocr_block_corrections`：仅保存发生变化的文字区域，关联原 OCR 块，保留原始文本、原图坐标和用户修正文本之间的关系。

校对接口：

```text
GET  /api/essays/{essay_id}/ocr/correction
PUT  /api/essays/{essay_id}/ocr/correction
POST /api/essays/{essay_id}/ocr/correction/confirm
```

确认后，`ocr_corrections.corrected_text` 即为后续评测使用的校对文本；再次修改会回到草稿状态。

## DeepSeek 单模型评审

当前已接入 DeepSeek 的单模型结构化评审，不包含多模型综合评分。评审优先使用已确认的 OCR 校对文本；没有已确认校对稿时，使用提交时的直接输入文本。每次请求会创建独立的 `model_reviews` 记录，保留实际评审文本、文本来源、模型与提示词版本、状态、结构化结果和安全的错误摘要。

```text
POST /api/essays/{essay_id}/reviews/deepseek
GET  /api/essays/{essay_id}/reviews
```

输出固定包含 100 分制总分、四个 25 分评分维度、各维度理由和原文证据、问题批注以及可执行的修改建议。批注与评分证据还会分别写入 `ai_annotations`、`score_evidence`，便于未来与其他模型结果比较。

后端环境变量：

```dotenv
DEEPSEEK_API_KEY=replace_with_your_deepseek_api_key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_TIMEOUT_SECONDS=60
DEEPSEEK_MAX_OUTPUT_TOKENS=3000
```

## 可用产品流程

当前流程为：注册或登录 -> 提交作文和写作信息 -> OCR/校对 -> 发起评审批次 -> 分歧分析/必要时交叉复核 -> 查看综合报告 -> 从历史记录重新打开。

- 新作文会记录年级、文体、题目或写作要求以及题目满分；模型评分仍统一归一化到 100 分，便于模型之间比较。
- 每个用户通过 Bearer 会话访问自己的作文、图片、OCR、评审记录和报告。前端会将会话令牌保存在当前浏览器的本地存储中；生产部署应只通过 HTTPS 提供服务。
- 历史页只返回当前用户的作文。旧数据不会被删除，但没有归属用户的旧作文不会出现在任何新账户中。

认证接口：

```text
POST /api/auth/register
POST /api/auth/login
POST /api/auth/logout
GET  /api/auth/me
```

## 统一多模型评审

所有 Provider 使用 `cn-essay-v2` 评分标准和同一份结构化协议：内容立意、结构连贯、语言表达、书写规范四个维度各 25 分，总分为 100 分。每次 `review_batch` 固化评分标准版本、提示词版本、评审文本来源和每个 Provider 的独立尝试记录，因而可安全比较不同模型的结果。

```text
GET  /api/review-providers
POST /api/essays/{essay_id}/reviews/batches
GET  /api/essays/{essay_id}/reviews/batches
POST /api/essays/{essay_id}/reviews/batches/{batch_id}/retry
POST /api/essays/{essay_id}/reviews/rechecks/{recheck_id}/run
GET  /api/essays/{essay_id}/reports/latest
POST /api/essays/{essay_id}/reference-assessments
```

DeepSeek、Qwen 和豆包均通过独立 Provider 适配器接入同一份结构化评审协议。Qwen 与豆包均使用兼容的 Chat Completions 接口。缺少 API Key、网络超时、模型未开通或格式不合规都会作为该 Provider 的独立失败状态保存，不影响其他模型的结果或最终报告。`MODEL_REVIEW_MAX_RETRIES` 控制单 Provider 的基础重试次数。

豆包的 `ARK_API_KEY` 仅用于认证；还必须在火山方舟控制台开通目标模型，并将 `ARK_MODEL` 配置为该账号可调用的模型名称或推理接入点名称。系统会先使用 `ARK_*` 配置，未提供时才兼容读取旧的 `DOUBAO_*` 配置。模型未开通时，评审批次会记录“configured model is not available to this account”，而不会写入伪造的评审结果。

当前综合策略默认等权平均，并基于各维度分差、异常总分和完成覆盖率计算可信度。达到阈值的分歧会创建交叉复核记录；用户可从报告执行复核，系统会生成独立的复核批次和新的报告版本，同时保存复核前基线与复核后结果关联。

教师参考评分会作为校准样本使用：当每个参与综合的 Provider 都至少拥有 `MODEL_CALIBRATION_MIN_SAMPLES` 个有效教师总分样本时，系统按历史平均绝对误差生成冻结的可靠性权重；样本不足时继续采用等权，不会伪造权重。权重、样本量和误差摘要会随最终报告保存。

AI 批注会保存原文证据和字符偏移；对于已确认 OCR 文本，系统还会尝试关联对应 `ocr_block_id`，从而保留到原始图片区域的坐标链路。

新增环境变量：

```dotenv
QWEN_API_KEY=
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
QWEN_MODEL=qwen-turbo
DOUBAO_API_KEY=
DOUBAO_BASE_URL=
DOUBAO_MODEL=doubao-pro
ARK_API_KEY=
ARK_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
# Set this to a model or inference endpoint activated in your Ark account.
ARK_MODEL=doubao-seed-2-0-lite-260215
MODEL_REVIEW_TIMEOUT_SECONDS=45
MODEL_REVIEW_MAX_RETRIES=0
MODEL_CALIBRATION_MIN_SAMPLES=8
SESSION_TTL_HOURS=168
```

应用新版本前执行迁移：

```powershell
cd backend
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic check
```

## 双 OCR 引擎

本项目默认使用百度手写文字识别处理中文学生手写作文，并保留 PaddleOCR 作为人工启用的本地备用引擎。两者不会相互覆盖：每次运行都会在 `ocr_runs` 中记录 `engine_key`，并拥有各自的页面、文本区域、坐标、阅读顺序和置信度记录。

```text
POST /api/essays/{essay_id}/ocr?engine=paddle
POST /api/essays/{essay_id}/ocr?engine=baidu
GET  /api/essays/{essay_id}/ocr?engine=paddle
GET  /api/essays/{essay_id}/ocr?engine=baidu
```

上传和校对流程会优先读取默认百度 OCR 结果；历史作文若只保存了旧的 PaddleOCR 运行结果，仍可正常打开和校对。校对请求会携带实际 OCR 运行 ID，因此用户修改始终对应相应识别结果的原始坐标。

百度接口只在服务端调用；应用本身仍通过 multipart 上传原始文件。适配器按百度接口要求在调用前临时转为 Base64，并保留原始图片与既有坐标映射。请在 `backend/.env` 配置以下变量，勿提交真实凭据：

```dotenv
OCR_DEFAULT_ENGINE=baidu
BAIDU_OCR_APP_ID=replace_with_your_baidu_ocr_app_id
BAIDU_OCR_API_KEY=replace_with_your_baidu_ocr_api_key
BAIDU_OCR_SECRET_KEY=replace_with_your_baidu_ocr_secret_key
BAIDU_OCR_TOKEN_URL=https://aip.baidubce.com/oauth/2.0/token
BAIDU_HANDWRITING_URL=https://aip.baidubce.com/rest/2.0/ocr/v1/handwriting
BAIDU_OCR_TIMEOUT_SECONDS=30
```

如需人工切回本地 PaddleOCR，设置 `OCR_DEFAULT_ENGINE=paddle`、`OCR_WORKER_ENABLED=true`，并使用 `docker compose --profile paddle-worker up -d ocr-worker` 明确启动 Worker。百度请求失败不会自动切换到 PaddleOCR。
## Competition Demo Features

- The report page visualizes the aggregate score, confidence, four-dimension score spread, independent model results, detected anomalies, and source evidence.
- Confidence explains coverage, dimension agreement, and outlier handling rather than presenting an unexplained percentage.
- Cross-check records retain before/after scores, average disagreement, and whether the disagreement decreased.
- `GET /api/essays/{essay_id}/reports/latest.pdf` exports the persisted report without re-running OCR or any model.
- The one-click demo essay creates an unevaluated real text; it never preloads, fabricates, or simulates formal model results.
- The pre-review service panel presents student-safe readiness information; its
  separate cached readiness probe is not a substitute for the explicit live
  Smoke Test documented below.

## Test verification terminology

The project separates routine offline automated tests from explicit live-service
verification. Passing pytest means **"离线自动测试通过"** only; it does not
prove that real model or OCR accounts are available. See
[`backend/TESTING.md`](backend/TESTING.md) for the opt-in real Smoke Test.
Only a successful relevant Smoke Test may be described as
**"真实核心服务已验证"**.

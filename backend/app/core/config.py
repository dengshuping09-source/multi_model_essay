from functools import lru_cache
from pathlib import Path
from datetime import timedelta

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = "多模型协同作文智能评测系统 API"
    app_env: str = "development"
    api_prefix: str = "/api"
    cors_origins: str = "http://localhost:5173"
    database_url: str | None = None
    upload_dir: Path = Path("storage/uploads")
    max_upload_size_mb: int = 10
    max_upload_files: int = 10
    max_image_pixels: int = 40_000_000
    max_essay_text_length: int = 50_000
    ocr_device: str = "cpu"
    ocr_detection_model: str = "PP-OCRv5_mobile_det"
    ocr_recognition_model: str = "PP-OCRv5_mobile_rec"
    ocr_enable_mkldnn: bool = False
    ocr_cpu_threads: int = 4
    ocr_low_confidence_threshold: float = 0.65
    deepseek_api_key: SecretStr | None = None
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_api_url: str | None = None
    deepseek_model: str = "deepseek-chat"
    deepseek_timeout_seconds: float = 60.0
    deepseek_max_output_tokens: int = 3_000
    deep_analysis_max_output_tokens: int = 2_400
    qwen_api_key: SecretStr | None = None
    qwen_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    qwen_model: str = "qwen-turbo"
    doubao_api_key: SecretStr | None = None
    doubao_base_url: str | None = None
    doubao_model: str = "doubao-pro"
    ark_api_key: SecretStr | None = None
    ark_base_url: str = "https://ark.cn-beijing.volces.com/api/v3"
    # Keep fast core review and optional deep enrichment on purpose-built
    # routes. ARK_MODEL remains the legacy/on-demand fallback.
    ark_model: str = "doubao-seed-2-0-lite-260215"
    ark_quick_model: str = "doubao-seed-2-0-mini-260428"
    ark_quick_max_output_tokens: int = 1_200
    ark_deep_model: str = "doubao-seed-2-0-lite-260215"
    # A complete result may use the other independent reviews when one remote
    # service is slow.  Keep this comfortably above normal response time, but
    # do not turn one unavailable service into a two-minute page-level wait.
    model_review_timeout_seconds: float = 30.0
    model_review_quorum_grace_seconds: float = 12.0
    model_review_max_retries: int = 1
    model_calibration_min_samples: int = 8
    session_ttl_hours: int = 168
    baidu_ocr_api_key: SecretStr | None = None
    baidu_ocr_secret_key: SecretStr | None = None
    baidu_ocr_token_url: str = "https://aip.baidubce.com/oauth/2.0/token"
    baidu_handwriting_url: str = "https://aip.baidubce.com/rest/2.0/ocr/v1/handwriting"
    baidu_ocr_timeout_seconds: float = 30.0

    # Resolve this relative to the backend package, not the process working
    # directory.  Starting FastAPI from the repository root must read the same
    # backend/.env as starting it from backend/.
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env", env_file_encoding="utf-8"
    )

    @model_validator(mode="after")
    def reject_concatenated_api_key_settings(self) -> "Settings":
        """Fail fast when a malformed .env joined multiple assignments together.

        A value is intentionally never included in the error: it may be a real
        credential.  Continuing with such a value produces misleading provider
        failures and makes configuration mistakes much harder to diagnose.
        """
        markers = (
            "DEEPSEEK_API_KEY=",
            "QWEN_API_KEY=",
            "DOUBAO_API_KEY=",
            "ARK_API_KEY=",
            "BAIDU_OCR_API_KEY=",
            "BAIDU_OCR_SECRET_KEY=",
        )
        secret_fields = (
            "deepseek_api_key",
            "qwen_api_key",
            "doubao_api_key",
            "ark_api_key",
            "baidu_ocr_api_key",
            "baidu_ocr_secret_key",
        )
        for field_name in secret_fields:
            secret = getattr(self, field_name)
            if secret is not None and any(marker in secret.get_secret_value() for marker in markers):
                raise ValueError(
                    f"{field_name.upper()} contains another environment variable declaration; "
                    "repair backend/.env so each assignment occupies its own line"
                )
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    def require_database_url(self) -> str:
        if not self.database_url:
            raise RuntimeError("DATABASE_URL is not configured")
        return self.database_url

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def session_ttl(self) -> timedelta:
        return timedelta(hours=self.session_ttl_hours)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

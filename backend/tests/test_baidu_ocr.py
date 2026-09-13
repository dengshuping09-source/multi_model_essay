import sys

from app.modules.ocr.baidu import BaiduOcrError, user_facing_baidu_error
from app.modules.ocr.engine import get_baidu_ocr_engine


def test_baidu_errors_are_safe_and_actionable_for_students() -> None:
    assert "尚未配置" in user_facing_baidu_error(
        BaiduOcrError("Baidu OCR credentials are not configured")
    )
    assert "响应较慢" in user_facing_baidu_error(
        BaiduOcrError("Baidu handwriting OCR request timed out")
    )
    assert "当前较忙" in user_facing_baidu_error(
        BaiduOcrError("Baidu handwriting OCR returned error 18")
    )


def test_creating_baidu_engine_does_not_load_paddle_runtime() -> None:
    get_baidu_ocr_engine()
    assert "paddleocr" not in sys.modules

# Business modules

按业务边界扩展模块：

- `essays/`：作文管理
- `ocr/`：OpenCV 图片质量检测、OCR 前预处理、默认百度手写识别与可选 PaddleOCR 备用实现
- `reviews/`：多模型并行评审与结果汇总

多模型评审仍只保留模块边界，尚未实现具体业务。

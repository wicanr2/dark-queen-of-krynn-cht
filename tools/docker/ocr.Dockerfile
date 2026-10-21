# 本作第二條 OCR 工具鏈。取代本作低品質 Tesseract 草稿，不改前作 image。
# API 依 PaddleOCR 3.1.0 官方文件；原始掃描不放入 image。
FROM python@sha256:05cda9777409a9c3ffddd94a4c476b79f0769a0b4857f0c7ed9226b6800b0d6f
RUN apt-get update \
 && apt-get install -y --no-install-recommends libgomp1 libgl1 libglib2.0-0 \
 && rm -rf /var/lib/apt/lists/*
# PaddleX 3.1 使用 LangChain 0.3 的 docstore API；完整固定間接依賴。
COPY ocr-runtime-versions.txt /opt/ocr-runtime-versions.txt
RUN python -m pip install --no-cache-dir --requirement /opt/ocr-runtime-versions.txt \
 && python -m pip check
ENV HOME=/tmp OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
WORKDIR /work
CMD ["python3"]

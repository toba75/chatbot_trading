FROM quay.io/docling-project/docling-serve-cu130:v1.28.0

RUN python -m pip install --no-cache-dir \
      paddlepaddle-gpu==3.2.1 \
      --index-url https://www.paddlepaddle.org.cn/packages/stable/cu129/ \
    && python -m pip install --no-cache-dir "paddleocr[doc-parser]==3.5.0"

RUN python -m pip install --no-cache-dir --force-reinstall \
      torch==2.7.1+cpu \
      --index-url https://download.pytorch.org/whl/cpu

COPY run_model.py /opt/paddle-formula-spike/run_model.py
COPY run_structure.py /opt/paddle-formula-spike/run_structure.py
COPY run_pictures.py /opt/paddle-formula-spike/run_pictures.py

ENTRYPOINT ["python", "/opt/paddle-formula-spike/run_model.py"]

FROM quay.io/docling-project/docling-serve-cu130:v1.28.0@sha256:14ec55d69ff7782a44d6f26cd807fb50737d11a3f74f942c73b6738e9f719b1f

RUN python -m pip install --no-cache-dir \
      nltk==3.9.2 \
      python-Levenshtein==0.27.3

COPY run_model.py /opt/nougat-shadow/run_model.py

ENTRYPOINT ["python", "/opt/nougat-shadow/run_model.py"]

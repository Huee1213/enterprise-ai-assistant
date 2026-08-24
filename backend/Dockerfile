FROM python:3.11-slim

ENV LANG=C.UTF-8 LC_ALL=C.UTF-8 PYTHONIOENCODING=utf-8

# Pin HOME so Linux tools resolve ~/.cache correctly. Docker Desktop on
# Windows can leak the host HOME (e.g. "C:UsersX") into the container, which
# breaks cache lookups for tools like fastembed/huggingface_hub.
ENV HOME=/root

WORKDIR /app

COPY requirements.txt .
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple && \
    pip install --no-cache-dir --prefer-binary -r requirements.txt

# Bake the default embedding model into the image so no runtime download is
# needed (the runtime model cache is wiped on every container recreate, which
# previously blocked backend startup whenever the download failed).
# Try the primary HuggingFace hub first, then the hf-mirror fallback.
ARG EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
ENV HF_HUB_DISABLE_XET=1
RUN python -c "from fastembed import TextEmbedding; TextEmbedding(model_name='${EMBEDDING_MODEL}', cache_dir='/root/.cache/fastembed')" \
    || HF_ENDPOINT=https://hf-mirror.com python -c "from fastembed import TextEmbedding; TextEmbedding(model_name='${EMBEDDING_MODEL}', cache_dir='/root/.cache/fastembed')"

COPY . .

RUN mkdir -p /app/data/documents

EXPOSE 8000

CMD ["gunicorn", "app.main:app", "--worker-class", "uvicorn.workers.UvicornWorker", "--workers", "4", "--preload", "--bind", "0.0.0.0:8000", "--timeout", "120"]

FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    unzip \
    && rm -rf /var/lib/apt/lists/*

RUN curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o /usr/local/bin/yt-dlp \
    && chmod a+rx /usr/local/bin/yt-dlp

RUN curl -fsSL https://deno.land/install.sh | sh
ENV DENO_INSTALL="/root/.deno"
ENV PATH="$DENO_INSTALL/bin:$PATH"

COPY requirements.txt .
# librosa deps (llvmlite 55 MB, scipy 33 MB) need a long timeout on slow connections
RUN pip install --no-cache-dir --timeout 300 --retries 10 -r requirements.txt

# tflite-runtime has no ARM64 wheel on PyPI — try Google Coral repo, fall back silently
RUN pip install --no-cache-dir tflite-runtime \
        --extra-index-url https://google-coral.github.io/py-repo/ \
    || echo "INFO: tflite-runtime unavailable on this platform — inference disabled until installed"

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

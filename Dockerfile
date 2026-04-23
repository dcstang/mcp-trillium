FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY main.py .
ENV PYTHONUNBUFFERED=1
CMD ["uv", "run", "python", "main.py"]

ARG PYTHON_BASE_IMAGE=docker.arvancloud.ir/library/python:3.12-slim
FROM ${PYTHON_BASE_IMAGE}

ARG UV_INDEX_URL=https://mirror2.chabokan.net/pypi/simple/
ARG UV_EXTRA_INDEX_URL=

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_INDEX_URL=${UV_INDEX_URL} \
    PIP_EXTRA_INDEX_URL=${UV_EXTRA_INDEX_URL} \
    UV_INDEX_URL=${UV_INDEX_URL} \
    UV_EXTRA_INDEX_URL=${UV_EXTRA_INDEX_URL}

WORKDIR /app

RUN python -m pip install --no-cache-dir 'uv>=0.9,<1.0'

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY melodify_ts_bot ./melodify_ts_bot
RUN uv sync --frozen --no-dev

CMD ["uv", "run", "--no-dev", "python", "-m", "melodify_ts_bot.main"]

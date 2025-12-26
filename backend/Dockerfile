# 镜像源配置参数（可通过 build args 覆盖）
ARG DOCKER_REGISTRY=
ARG APT_MIRROR=
ARG PYPI_INDEX_URL=

# 使用 Python 3.10 作为基础镜像
FROM ${DOCKER_REGISTRY:-}python:3.10-slim

# 重新声明ARG（FROM之后ARG作用域失效，需要重新声明）
ARG APT_MIRROR=
ARG PYPI_INDEX_URL=

# 设置工作目录
WORKDIR /app

# 安装系统依赖（如果配置了 APT_MIRROR，先替换镜像源）
RUN if [ -n "$APT_MIRROR" ]; then \
        if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
            sed -i "s@deb.debian.org@$APT_MIRROR@g" /etc/apt/sources.list.d/debian.sources; \
        else \
            echo "Warning: /etc/apt/sources.list.d/debian.sources not found, skipping mirror setup." >&2; \
        fi; \
    fi && \
    apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 使用 pip 安装 uv（避免从 ghcr.io 拉取镜像的网络问题）
ARG PYPI_INDEX_URL
RUN if [ -n "$PYPI_INDEX_URL" ]; then \
        pip install --index-url "$PYPI_INDEX_URL" uv; \
    else \
        pip install uv; \
    fi

# 复制项目配置文件
COPY pyproject.toml ./
COPY uv.lock* ./

# 配置 PyPI 镜像源（如果指定）
ENV UV_INDEX_URL=${PYPI_INDEX_URL}

# 配置 uv 网络超时
ENV UV_HTTP_TIMEOUT=300

# 安装 Python 依赖
# 如果有 uv.lock 文件则使用 --frozen，否则生成新的锁定文件
RUN if [ -f uv.lock ]; then \
        uv sync --frozen; \
    else \
        uv sync; \
    fi

# 复制后端代码
COPY backend/ ./backend/

# 创建必要的目录
RUN mkdir -p /app/backend/instance /app/uploads

ENV PYTHONPATH=/app
ENV FLASK_APP=backend/app.py

# 暴露端口
EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD ["sh", "-c", "curl -f http://localhost:${PORT:-5000}/health || exit 1"]

# 启动应用
CMD ["sh", "-c", "uv run --directory backend alembic upgrade head && uv run --directory backend python app.py"]


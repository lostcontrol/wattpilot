FROM python:3.15-trixie

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

RUN apt-get update && \
    apt-get install -y --no-install-recommends swig && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /code
COPY . /code/
ENV PYPI=1
RUN uv sync --frozen --no-dev

ENV PATH="/code/.venv/bin:$PATH"

EXPOSE 8080

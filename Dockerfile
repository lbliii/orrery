# Orrery — Railway / container deploy.
#
# Chirp installs from GIT_REF (default: main), not a PyPI wheel, so the
# framework tracks the actively developed skill/MCP surface this host needs.
# GIT_REF deliberately avoids Chirp's reserved CHIRP_* runtime namespace.
#
# Build context is the repo root:
#     docker build -t orrery .
#
# Chirp reads PORT / RAILWAY_* via AppConfig.from_env().
FROM python:3.14-slim@sha256:a7fb1e634c4a578f9e0bd6327f11a3cde11b7a9395f48e24360c0988bcc5c2bc

COPY --from=ghcr.io/astral-sh/uv@sha256:2d890623d310b57771ce840f0da5eed5fc6d657da05ffaa45d82797b53fa3abc /uv /usr/local/bin/uv

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

RUN uv venv --python 3.14 /opt/venv

# Read the current commit metadata before installing so a moving main branch
# invalidates this layer on every image build.
ARG GIT_REF=main
ADD "https://api.github.com/repos/lbliii/chirp/commits/${GIT_REF}" /tmp/chirp-commit.json
RUN uv pip install --python /opt/venv/bin/python \
    "bengal-chirp[skill,sessions] @ git+https://github.com/lbliii/chirp.git@${GIT_REF}" \
    "itsdangerous>=2.2.0"

# The .dockerignore excludes local/editor artifacts while this copies every
# runtime module, page, template, and static asset added to the repository.
COPY . /app/

EXPOSE 8000
CMD ["python", "app.py"]

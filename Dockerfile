FROM python:3.12-slim

LABEL org.opencontainers.image.title="VulnoraIQ" \
      org.opencontainers.image.source="https://github.com/sharRahul/vulnoraiq" \
      org.opencontainers.image.licenses="Apache-2.0"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VULNORAIQ_IN_CONTAINER=1 \
    VULNORAIQ_CONFIG_DIR=/app/config \
    VULNORAIQ_WEB_OUTPUT_ROOT=/data/reports \
    VULNORAIQ_RUNTIME_TARGETS_PATH=/data/reports/runtime_targets.yaml \
    VULNORAIQ_JOB_STORE_PATH=/data/jobs.db \
    VULNORAIQ_EVIDENCE_DIR=/data/evidence \
    VULNORAIQ_TARGET_CONFIG=targets.docker.yaml \
    VULNORAIQ_AGENT_LAB_ROOT=/data/agent_lab \
    VULNORAIQ_AGENT_LAB_PROJECTS_ROOT=/data/agent_lab/projects

WORKDIR /app
RUN groupadd --system vulnoraiq \
    && useradd --system --gid vulnoraiq --home-dir /app --shell /usr/sbin/nologin vulnoraiq

# Only the Docker *client* is needed: Agent Lab shells out to it against the
# host socket mounted by docker-compose. Installing docker.io would pull an
# entire second engine into the image for nothing.
RUN apt-get update \
    && apt-get install -y --no-install-recommends docker-cli git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY . .

# Install VulnoraIQ plus the in-app assistant (Nora) runtime. Runtime
# dependencies only — the test and lint toolchain has no place in the shipped
# image. The prebuilt CPU wheels from the abetlen index are musl-linked and will
# not load on this Debian/glibc image, so llama-cpp-python is compiled here.
# GGML_NATIVE=OFF keeps the build portable across CPUs (it avoids AVX512
# illegal-instruction crashes on consumer hardware). The build toolchain is
# removed afterwards to keep the image lean.
RUN apt-get update && apt-get install -y --no-install-recommends build-essential cmake \
    && pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir . \
    && CMAKE_ARGS="-DGGML_NATIVE=OFF" pip install --no-cache-dir --no-binary llama-cpp-python "llama-cpp-python==0.3.19" \
    && apt-get purge -y --auto-remove build-essential cmake \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /data/reports /data/evidence /data/agent_lab/projects \
    && chown -R vulnoraiq:vulnoraiq /data /app

USER vulnoraiq
VOLUME ["/data"]
EXPOSE 8787
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import http.client; c=http.client.HTTPConnection('127.0.0.1',8787,timeout=3); c.request('GET','/healthz'); r=c.getresponse(); raise SystemExit(0 if r.status < 500 else 1)"
CMD ["vulnoraiq-web", "--host", "0.0.0.0", "--port", "8787"]

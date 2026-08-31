# Docker

How the VulnoraIQ image is built and validated. For *using* the containerised
lab, see [Lab Mode](../guides/lab-mode.md).

## The image

`Dockerfile` builds a single `python:3.12-slim` based image used by both the
`vulnoraiq-web` service and the optional `test-runner` service.

What it contains and why:

| Element | Reason |
| --- | --- |
| Non-root `vulnoraiq` user | The application never runs as root. |
| `docker-cli` only | Agent Lab shells out to the Docker *client* against the host socket. The full `docker.io` engine package is deliberately not installed. |
| `git` | Agent Lab's git import. |
| Runtime dependencies only | The image is a runtime artefact; pytest, ruff, and mypy are not installed into it. |
| `llama-cpp-python` built from source | The prebuilt CPU wheels are musl-linked and will not load on this glibc image. `GGML_NATIVE=OFF` keeps the build portable across CPUs. |
| Build toolchain purged after use | Keeps the final image small. |
| `HEALTHCHECK` on `/healthz` | Lets Compose wait for readiness. |
| `VOLUME /data` | All mutable state lives outside the image. |

`.dockerignore` keeps the build context free of the virtualenv, caches, tests,
docs, model training artefacts, and anything matching `.env*`.

## Build and validate

```bash
docker compose build
docker compose up -d
docker compose ps
```

A successful build does not prove runtime correctness. Verify the container
actually serves:

```bash
curl -fsS http://127.0.0.1:8787/healthz
curl -fsS http://127.0.0.1:8787/readyz
docker compose logs vulnoraiq-web
```

Smoke tests:

```bash
python scripts/container_smoke_test.py
python scripts/docker_smoke_test.py     # intended to run inside the test-runner service
```

## Compose topology

| Service | Role |
| --- | --- |
| `vulnoraiq-web` | The application. Published on `127.0.0.1:8787` only. |
| `test-runner` | Optional utility service under the `test` profile. |

Both run on the private `vulnoraiq-lab` bridge network with
`security_opt: no-new-privileges:true` and `cap_drop: ALL`. Neither uses host
networking or privileged mode.

`vulnoraiq-web` mounts `/var/run/docker.sock` so Agent Lab can build and run
agent containers. That is the deliberate trust decision described in
[sandboxing](../security/sandboxing.md).

Compose declares its settings inline. There is no `env_file`, because no file
starting with `.env` may be committed — see [secrets](../security/secrets.md).

`docker-compose.override.yml` is intentionally untracked: use it for local
developer overrides.

## Agent containers

Agent containers are started by the application, not by Compose. Their flags are
fixed in code (`--cap-drop ALL`, `--security-opt no-new-privileges:true`,
loopback-only port publishing, optional memory/CPU limits, GPU only on request).
See [sandboxing](../security/sandboxing.md).

## Clean up

```bash
docker compose down       # stop, keep data
docker compose down -v    # stop and delete the volume: jobs, reports, evidence, imports
```

## Related

- [Lab Mode](../guides/lab-mode.md)
- [Sandboxing](../security/sandboxing.md)
- [Environment variables](../reference/environment-variables.md)

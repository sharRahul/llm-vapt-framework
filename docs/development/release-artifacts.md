# Release artifacts

This document describes how VulnoraIQ release artifacts are built for Windows, Linux, and macOS.

## Trigger policy

Platform release artifacts must **not** be built on every commit, push, or pull request.

The `Build Release Artifacts` workflow in `.github/workflows/release-build.yml` runs only when:

1. a GitHub Release is published; or
2. a maintainer manually starts the workflow with `workflow_dispatch`.

Normal quality gates remain in `.github/workflows/ci.yml` and any Python-specific CI workflow.

## Artifacts produced

| Platform | Artifact | Start method |
| --- | --- | --- |
| Windows | `vulnoraiq-<version>-windows.zip` | Extract and double-click `launch-vulnoraiq-webui.bat`. |
| Linux | `vulnoraiq-<version>-linux.tar.gz` | Extract and double-click `VulnoraIQ.desktop` or run `launch-vulnoraiq-webui.sh`. |
| macOS | `vulnoraiq-<version>-macos.dmg` | Mount the DMG and double-click `launch-vulnoraiq-webui.command`. |

Each package includes:

- platform launcher files;
- self-bootstrapping `scripts/bootstrap_launch.py` for first-run `.venv` creation and dependency installation;
- Python source/package files;
- current React WebUI built static assets under `webui/static/console/`;
- safe configuration files;
- Docker and Docker Compose lab files where applicable;
- documentation;
- `LICENSE`, `NOTICE`, `SECURITY.md`, `ACCEPTABLE_USE.md`, and `THIRD_PARTY_NOTICES.md`;
- a generated `START_HERE.txt` with platform-specific startup and verification instructions.

Generated reports, local SQLite databases, secrets, keys, virtual environments, build output, local runtime target files, and local config files are excluded.

## First-run bootstrap behaviour

A release package ships both launcher sets.

The Desktop Mode launchers (`launch-vulnoraiq-webui.*`) call
`scripts/desktop_launch.py`, which uses only the Python standard library:

1. creates the local `scan-reports/`, `agent-lab/`, and `projects/` folders;
2. sets the Desktop Mode environment (loopback bind, local-admin auth, local
   output paths);
3. checks Docker is available and ensures the agent network exists;
4. starts `python -m webui.server` and opens the browser once it is healthy.

The Docker Lab launchers (`launch-vulnoraiq-docker-lab.*`) run Docker Compose
directly; `scripts/bootstrap_launch.py` is the equivalent Python entry point,
which builds and starts the Compose stack and waits for the health check.

Both give a double-click startup path. Desktop Mode needs Python 3.10 or newer
plus Docker; Lab Mode needs only Docker.

## Local package build command

```bash
python scripts/build_platform_release_package.py \
  --platform linux \
  --version 0.3.0 \
  --output-dir dist/release
```

Supported platform values:

- `windows` -> `.zip`
- `linux` -> `.tar.gz`
- `macos` -> `.dmg`

macOS `.dmg` creation uses `hdiutil`, so that target must run on macOS. The GitHub release workflow uses `macos-latest` for this job.

## On-demand signed release workflow

Go to **Actions -> Build Release Artifacts -> Run workflow** and provide:

- `version`: release tag/version to embed in artifact names;
- `upload_to_release`: whether to upload the final bundle to an existing GitHub Release with that tag;
- `signing_mode`:
  - `attestation-only`: generate GitHub artifact attestations and SHA256 checksums;
  - `gpg-if-configured`: also create detached `.asc` signatures when GPG secrets are configured;
  - `require-gpg`: fail the workflow unless GPG signing secrets are configured.

The signing/publishing job downloads all platform packages, creates:

- individual `.sha256` files;
- `SHA256SUMS.txt`;
- GitHub build-provenance artifact attestations;
- optional GPG detached `.asc` signatures.

Optional GPG signing secrets:

| Secret | Purpose |
| --- | --- |
| `RELEASE_GPG_PRIVATE_KEY` | ASCII-armored private key used only inside the signing job. |
| `RELEASE_GPG_PASSPHRASE` | Passphrase for the signing key, if required. |

## Required validation before artifact build

```bash
python scripts/validate_package_metadata.py
python scripts/validate_owasp_atlas_mappings.py
python scripts/validate_genai_readiness.py
python scripts/validate_production_testing_readiness.py --output-dir reports/output/production-readiness
```

For WebUI release confidence, the release workflow also rebuilds React assets before packaging:

```bash
cd webui/console
npm ci
npm run build
```

For Docker lab confidence, also run:

```bash
docker compose build
python scripts/docker_smoke_test.py
```

## Published release run

When a GitHub Release is published, the workflow should:

1. resolve the release tag as the artifact version;
2. build Windows, Linux, and macOS packages on matching hosted runners;
3. validate package metadata/readiness before packaging;
4. upload the raw platform packages as intermediate workflow artifacts;
5. collect packages in the signing job;
6. generate checksums, attestations, and optional GPG detached signatures;
7. upload the final signed release bundle as a workflow artifact;
8. upload the final bundle to the GitHub Release.

## Current limitations

The release artifacts are self-hosted Python packages with double-click launchers, checksums, GitHub artifact attestations, and optional GPG detached signatures. They are not yet native OS installers with platform certificate signing. Authenticode-signed Windows `.exe/.msi`, notarised macOS `.pkg/.app`, `.deb`, `.rpm`, Homebrew, Winget, container image signing, and SBOM-based supply-chain release flows remain future maturity items.

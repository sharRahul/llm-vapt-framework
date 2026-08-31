# Supply-chain pipeline

VulnoraIQ uses `.github/workflows/security-supply-chain.yml` to produce container build evidence, scan reports, SBOM files, and optional signed GHCR images.

## When it runs

- Pull requests to `main` build and scan the image locally.
- Pushes to `main` and `v*` tags publish and sign the GHCR image.
- Manual runs can publish/sign when `publish_image=true`.

## Outputs

| Output | Purpose |
| --- | --- |
| `trivy-filesystem.sarif` | Machine-readable source/dependency scan. |
| `trivy-filesystem.txt` | Human-readable source/dependency scan. |
| `trivy-image.sarif` | Machine-readable container scan. |
| `trivy-image.txt` | Human-readable container scan. |
| `vulnoraiq-filesystem.spdx.json` | Filesystem SBOM. |
| `vulnoraiq-image.cdx.json` | Container image SBOM. |
| `cosign-verify.txt` | Signature verification evidence when publishing is enabled. |

## Manual inputs

| Input | Default | Meaning |
| --- | --- | --- |
| `publish_image` | `false` | Push the built image to GHCR and sign it. |
| `enforce_security_gate` | `false` | Fail a manual run on high-impact findings. |
| `image_tag` | empty | Override the generated `sha-<commit>` tag. |

## Notes

The normal PR path is evidence-first and non-blocking so new database updates do not unexpectedly block all development. Release managers can use `enforce_security_gate=true` for a stricter manual run before shipping.

Cosign uses GitHub OIDC for keyless signing, so no long-lived signing key is stored in repository secrets.

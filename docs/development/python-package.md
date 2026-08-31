# Python package publishing

VulnoraIQ can be distributed as a Python package in addition to platform release artifacts.

## Current package metadata

| Field | Current value |
| --- | --- |
| Package | `vulnoraiq` |
| Version | `0.3.0` |
| Python | `>=3.10` |
| License | Apache-2.0 |
| Runtime dependencies | `PyYAML`, `requests`, `rich` |
| Dev dependencies | `pytest`, `ruff`, `mypy`, `pip-audit`, type stubs |
| Release dependencies | `build`, `twine` |

The package includes the built React WebUI assets from `webui/static/console/` as package data. Node is not required to serve the packaged WebUI at runtime.

## Console entry points

Current entry points include:

- `vulnoraiq`
- `vulnoraiq-web`
- `vulnoraiq-dashboard`
- `vulnoraiq-diff`
- `vulnoraiq-package`
- `vulnoraiq-platform-package`
- `vulnoraiq-benchmark`
- `vulnoraiq-functional-test`
- `vulnoraiq-production-readiness`
- `vulnoraiq-policy-trend`
- `vulnoraiq-diff-trend`
- `vulnoraiq-refresh-atlas`
- `vulnoraiq-generate-atlas-matrix`
- `vulnoraiq-html-export`
- `vulnoraiq-validate-package`
- `vulnoraiq-validate-owasp-atlas-mappings`
- `vulnoraiq-validate-genai-readiness`

## What gets built

The Python package workflow builds:

- source distribution: `vulnoraiq-<version>.tar.gz`
- wheel distribution: `vulnoraiq-<version>-py3-none-any.whl`

## Trigger policy

The package workflow must not run on every commit, push, or pull request. It should run only when:

1. a GitHub Release is published; or
2. a maintainer manually starts the workflow with `workflow_dispatch`.

Publishing to TestPyPI/PyPI should require explicit manual input.

## Local build

```bash
python -m pip install --upgrade pip
pip install -e .[dev,release]
python scripts/validate_package_metadata.py
python -m build
python -m twine check dist/*
```

## Required package validation

Before publishing, run:

```bash
ruff check .
mypy .
pytest -q
python -m pip check
pip-audit
python scripts/validate_package_metadata.py
python scripts/validate_owasp_atlas_mappings.py
python scripts/validate_genai_readiness.py
python scripts/validate_production_testing_readiness.py --output-dir reports/output/production-readiness
```

If WebUI assets changed, also run the React build and browser flow before packaging.

## Current limitations

The package is suitable for self-hosted/internal use and local lab operation. It is not a managed SaaS product, certified VAPT product, signed installer, or independently validated assurance tool.

# Security Policy for `insecure_tree`

## Introduction

Thank you for your interest in the security of this project. As an open-source side project maintained by a single
individual, I take security seriously and appreciate the community's help in keeping it safe.

This document outlines how to report vulnerabilities and provides guidance on managing security in your own usage of
this tool. This is not a commercial product, so there is no dedicated security team. Reports are handled on a
best-effort basis, similar to any other bug report.

## Supported Versions

Security updates will only be applied to the **most recent release** available on PyPI. Please ensure you are using
the latest release to receive security patches.

| Version | Supported |
|---------|-----------|
| latest | Yes |
| older | No |

## Reporting a Vulnerability

Please **do not** report security vulnerabilities through public GitHub issues.

You have two private reporting channels:

1. **GitHub private vulnerability reporting** —
   [submit a confidential report](https://github.com/matthewdeanmartin/insecure_tree/security/advisories/new)
   directly on GitHub. This is the preferred channel.

1. **Email** — contact **`matthewdeanmartin@gmail.com`** if you prefer not to use GitHub.

When reporting, please include as much of the following as possible:

- Version of the tool you are using
- Clear description of the vulnerability and its potential impact
- Steps to reproduce or a proof-of-concept
- Any suggested fix, if you have one

I will do my best to acknowledge your report within a few days and provide a resolution or status update within
30 days. Once a fix is released, I will credit you for the discovery unless you prefer to remain anonymous.

## Dependency Management

This project relies on third-party libraries. Both `uv audit` and `pip-audit` are run as part of the CI pipeline to
catch known CVEs early.

### For Library Users

If you use this project as a library you are responsible for auditing your own dependency tree. Tools like
`pip-audit`, `uv audit`, or GitHub's Dependabot can help.

### For CLI / Application Users

If you discover that a pinned transitive dependency has a known vulnerability you have two options:

1. **Override the dependency** — create a `requirements.txt` with the patched version pinned and install it
   alongside this tool.
1. **Open an issue or pull request** — a PR that bumps the dependency and keeps all tests green is the fastest
   path to a fix.

## Running in Docker (isolation)

For maximum isolation, run `insecure_tree` inside a container so it only has access to what you
explicitly mount.

```dockerfile
FROM python:3.12-slim

WORKDIR /app

RUN useradd --create-home appuser
USER appuser

RUN python -m venv /home/appuser/venv
ENV PATH="/home/appuser/venv/bin:$PATH"

RUN pip install --no-cache-dir insecure_tree

ENTRYPOINT ["insecure_tree"]
CMD ["--help"]
```

Build and run:

```bash
docker build -t insecure_tree .

# Mount the current directory into /data and pass it as an argument
docker run --rm -v "$(pwd):/data" insecure_tree /data
```

This ensures the tool cannot touch anything outside the directory you explicitly provide.

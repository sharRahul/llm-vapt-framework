# Secrets

VulnoraIQ handles three kinds of credential: console access tokens, credentials
for the systems it assesses, and model-provider API keys for imported agents.
None of them may ever be committed.

## The rule

**No file whose name begins with `.env` is tracked in this repository, and there
are no exceptions.** The `.gitignore` covers `.env`, `.env.*`, and the same
patterns in every subdirectory. There is no `!.env.example` escape hatch.

Verify at any time:

```bash
git ls-files | grep -E '(^|/)\.env($|\.)'
```

That must print nothing.

## Where values belong

| Mechanism | Use it for |
| --- | --- |
| OS environment variables | Local development and one-off runs. |
| A local, untracked `.env` | Convenience during development. Start from [`config/environment.template`](../../config/environment.template). |
| Docker Compose `environment:` | Non-secret Lab Mode settings. |
| Docker secrets or an injected environment | Secrets in Lab Mode. |
| GitHub Actions Secrets / your CI secret store | Anything CI needs. |
| A managed secret store | Production deployments. |

Every supported variable, and whether it is sensitive, is listed in
[environment variables](../reference/environment-variables.md).

## Console access tokens

In `local_admin` mode there is no token: the server binds loopback and treats the
local user as the single administrator. Any other mode requires tokens supplied
through the environment:

```bash
export VULNORAIQ_AUTH_MODE=token
export VULNORAIQ_ADMIN_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
```

Production mode (`VULNORAIQ_ENV=production`) refuses to start unless an admin
token of at least 20 characters is present, and rejects `local_admin` outright.
File-based users in `config/web_users.yaml` are a development convenience and are
refused in production.

There is no built-in, shipped, or default token that authenticates against
VulnoraIQ. A token exists only because an operator configured it.

## Target credentials

A target never stores a credential inline. It names the environment variable
that holds one:

```yaml
targets:
  my-agent:
    type: http_json
    base_url: http://127.0.0.1:8080
    endpoint_path: /chat
    auth_token_env: MY_AGENT_TOKEN
    auth_header: Authorization
    auth_prefix: "Bearer "
```

Saving a target whose URL embeds credentials (`https://user:pass@host/`) is
rejected. Real-environment target validation additionally refuses any config
carrying an inline `api_key`, `token`, `password`, or `authorization` key.

## Agent model-provider keys

An API key entered when deploying an agent is injected into that agent's
container as an environment variable and is redacted (`***redacted***`) from the
stored deployment record. It is not written to the deployment registry, the audit
log, or any report.

## Redaction

Outbound requests, responses, headers, and finding-action payloads pass through
redaction before being stored or logged. Header names matching `token`, `secret`,
`key`, `password`, or `authorization`, and values matching bearer-token or
`sk-...` patterns, are replaced. Audit records are field-truncated and stripped
of newlines so a crafted value cannot forge extra log entries.

Credentials, tokens, authentication headers, and passwords are never logged.

## If a credential is exposed

1. Rotate it at the source immediately — assume it is compromised.
2. Remove it from the working tree and replace it with a placeholder.
3. Check whether it reached a published artefact, image, or log.
4. Follow [incident response](incident-response.md).

Removing a secret from the current files does not remove it from git history.
Rewriting history is a deliberate, coordinated operation; rotate first.

## Related

- [Environment variables](../reference/environment-variables.md)
- [Security model](security-model.md)
- [Configuration files](../reference/configuration.md)

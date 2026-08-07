"""Azure CLI-only authentication helpers for local evaluations."""

from __future__ import annotations

import time
from threading import Lock

from azure.core.credentials import AccessToken, TokenRequestOptions
from azure.identity import AzureCliCredential


class CachedAzureCliCredential:
    """Cache Azure CLI tokens so parallel judges do not spawn concurrent CLI calls."""

    def __init__(self) -> None:
        self._credential = AzureCliCredential()
        self._lock = Lock()
        self._tokens: dict[tuple[str, ...], AccessToken] = {}

    def get_token(
        self,
        *scopes: str,
        claims: str | None = None,
        tenant_id: str | None = None,
        enable_cae: bool = False,
        **kwargs,
    ) -> AccessToken:
        del kwargs
        key = tuple(scopes)
        with self._lock:
            token = self._tokens.get(key)
            if token is None or token.expires_on <= time.time() + 300:
                token = self._credential.get_token(
                    *scopes,
                    claims=claims,
                    tenant_id=tenant_id,
                    enable_cae=enable_cae,
                )
                self._tokens[key] = token
            return token

    def get_token_info(
        self,
        *scopes: str,
        options: TokenRequestOptions | None = None,
    ) -> AccessToken:
        options = options or {}
        return self.get_token(
            *scopes,
            claims=options.get("claims"),
            tenant_id=options.get("tenant_id"),
            enable_cae=bool(options.get("enable_cae", False)),
        )

    def close(self) -> None:
        self._credential.close()

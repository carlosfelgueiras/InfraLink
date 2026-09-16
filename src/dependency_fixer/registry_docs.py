import functools
from typing import Literal

import httpx

_BASE_URL = "https://registry.terraform.io/v2"
_V1_BASE_URL = "https://registry.terraform.io/v1"
_TIMEOUT = 10.0

Category = Literal["resources", "data-sources"]
_CATEGORIES: tuple[Category, ...] = ("resources", "data-sources")


class ProviderDocNotFound(Exception):
    """No Terraform Registry documentation page exists for this provider/type."""


@functools.lru_cache(maxsize=None)
def _provider_version_id(namespace: str, provider: str) -> int:
    """Resolves (namespace, provider) to the numeric provider-version id of its
    latest published version. Cached per provider for the process lifetime —
    this is the only part of the lookup that needs more than one request."""
    latest = httpx.get(f"{_V1_BASE_URL}/providers/{namespace}/{provider}", timeout=_TIMEOUT)
    if latest.status_code == httpx.codes.NOT_FOUND:
        raise ProviderDocNotFound(f"no such provider: {namespace}/{provider}")
    latest.raise_for_status()
    latest_version = latest.json()["version"]

    providers = httpx.get(
        f"{_BASE_URL}/providers",
        params={"filter[namespace]": namespace, "filter[name]": provider},
        timeout=_TIMEOUT,
    )
    providers.raise_for_status()
    entries = providers.json()["data"]
    if not entries:
        raise ProviderDocNotFound(f"no such provider: {namespace}/{provider}")
    provider_id = entries[0]["id"]

    versions = httpx.get(
        f"{_BASE_URL}/providers/{provider_id}",
        params={"include": "provider-versions"},
        timeout=_TIMEOUT,
    )
    versions.raise_for_status()
    for entry in versions.json().get("included", []):
        if entry["attributes"]["version"] == latest_version:
            return int(entry["id"])

    raise ProviderDocNotFound(f"could not resolve version {latest_version} for {namespace}/{provider}")


def _doc_id(provider_version_id: int, category: Category, slug: str) -> int | None:
    response = httpx.get(
        f"{_BASE_URL}/provider-docs",
        params={
            "filter[provider-version]": provider_version_id,
            "filter[category]": category,
            "filter[slug]": slug,
        },
        timeout=_TIMEOUT,
    )
    response.raise_for_status()
    entries = response.json()["data"]
    return int(entries[0]["id"]) if entries else None


@functools.lru_cache(maxsize=None)
def fetch_resource_doc(namespace: str, provider: str, resource_type: str) -> str:
    """Fetches the official Terraform Registry documentation (as markdown) for a
    resource or data source type, e.g. namespace="hashicorp", provider="aws",
    resource_type="aws_db_instance". Tries the "resources" category first, then
    falls back to "data-sources". Raises ProviderDocNotFound if neither exists.
    Cached for the process lifetime — this is a live lookup, not a pre-built index,
    so repeat calls for the same type are free."""
    version_id = _provider_version_id(namespace, provider)
    slug = resource_type.removeprefix(f"{provider}_")

    for category in _CATEGORIES:
        doc_id = _doc_id(version_id, category, slug)
        if doc_id is not None:
            doc = httpx.get(f"{_BASE_URL}/provider-docs/{doc_id}", timeout=_TIMEOUT)
            doc.raise_for_status()
            return str(doc.json()["data"]["attributes"]["content"])

    raise ProviderDocNotFound(
        f"no resource or data-source doc found for {resource_type!r} in {namespace}/{provider}"
    )

"""Blob storage interface (knowledge-base source of truth) + Azure implementation."""
from __future__ import annotations

import abc
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.config import Settings
from app.core.errors import ConfigurationError


@dataclass
class BlobInfo:
    name: str
    etag: str
    size: int
    last_modified: datetime
    content_md5: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)

    @property
    def fingerprint(self) -> str:
        """Content fingerprint used for incremental ingestion (MD5 preferred, ETag fallback)."""
        return self.content_md5 or self.etag


class BlobStorage(abc.ABC):
    @abc.abstractmethod
    async def list_blobs(self) -> list[BlobInfo]: ...

    @abc.abstractmethod
    async def get_info(self, name: str) -> BlobInfo | None: ...

    @abc.abstractmethod
    async def download(self, name: str) -> bytes: ...

    async def upload(
        self, name: str, data: bytes, *, metadata: dict[str, str] | None = None
    ) -> BlobInfo:  # pragma: no cover
        raise NotImplementedError

    async def aclose(self) -> None:  # pragma: no cover
        return None


class AzureBlobStorage(BlobStorage):  # pragma: no cover - requires Azure
    def __init__(self, settings: Settings):
        self._settings = settings
        self._svc: Any = None
        self._container: Any = None
        self._rest: _RestAzureBlobClient | None = None

        conn = settings.azure_storage_connection_string.get_secret_value()
        try:
            from azure.storage.blob.aio import BlobServiceClient  # type: ignore[import-not-found]

            if conn:
                self._svc = BlobServiceClient.from_connection_string(conn)
            elif settings.azure_storage_account_url:
                from azure.identity.aio import DefaultAzureCredential  # type: ignore[import-not-found]

                self._svc = BlobServiceClient(settings.azure_storage_account_url, credential=DefaultAzureCredential())
            else:
                raise ConfigurationError("Blob storage is not configured.")
            self._container = self._svc.get_container_client(settings.blob_container)
        except ImportError:
            if not conn and not settings.azure_storage_account_url:
                raise ConfigurationError("Blob storage is not configured.")
            self._rest = _RestAzureBlobClient(conn, settings.azure_storage_account_url, settings.blob_container)

    @staticmethod
    def _info(p: Any) -> BlobInfo:
        md5 = None
        settings = getattr(p, "content_settings", None)
        if settings is not None and settings.content_md5:
            md5 = bytes(settings.content_md5).hex()
        return BlobInfo(
            name=p.name,
            etag=(p.etag or "").strip('"'),
            size=p.size or 0,
            last_modified=p.last_modified,
            content_md5=md5,
            metadata=dict(p.metadata or {}),
        )

    async def list_blobs(self) -> list[BlobInfo]:
        if self._rest is not None:
            return await self._rest.list_blobs()
        return [self._info(p) async for p in self._container.list_blobs(include=["metadata"])]

    async def get_info(self, name: str) -> BlobInfo | None:
        if self._rest is not None:
            return await self._rest.get_info(name)
        from azure.core.exceptions import ResourceNotFoundError  # type: ignore[import-not-found]

        try:
            props = await self._container.get_blob_client(name).get_blob_properties()
        except ResourceNotFoundError:
            return None
        return self._info(props)

    async def download(self, name: str) -> bytes:
        if self._rest is not None:
            return await self._rest.download(name)
        stream = await self._container.get_blob_client(name).download_blob()
        return await stream.readall()

    async def upload(
        self, name: str, data: bytes, *, metadata: dict[str, str] | None = None
    ) -> BlobInfo:
        if self._rest is not None:
            return await self._rest.upload(name, data, metadata=metadata)
        from azure.core.exceptions import ResourceExistsError  # type: ignore[import-not-found]

        try:
            await self._container.create_container()
        except ResourceExistsError:
            pass
        bc = self._container.get_blob_client(name)
        await bc.upload_blob(data, overwrite=True, metadata=metadata or {})
        props = await bc.get_blob_properties()
        return self._info(props)

    async def aclose(self) -> None:
        if self._rest is not None:
            await self._rest.aclose()
        elif self._svc is not None:
            await self._svc.close()


class _RestAzureBlobClient:  # pragma: no cover - lightweight httpx fallback when azure-storage-blob SDK isn't installed
    API_VERSION = "2021-12-02"

    def __init__(self, conn_str: str, account_url: str, container: str):
        import httpx

        self.container = container
        self.account_name = ""
        self.account_key = ""
        self.sas_token = ""
        self.base_url = account_url.rstrip("/")

        conn_str = (conn_str or "").strip().strip('"').strip("'")
        if conn_str:
            parts = dict(
                (k.strip().strip('"').strip("'"), v.strip().strip('"').strip("'"))
                for item in conn_str.split(";")
                if "=" in item
                for k, v in [item.split("=", 1)]
            )
            if parts.get("UseDevelopmentStorage", "").lower() == "true":
                self.account_name = "devstoreaccount1"
                self.account_key = (
                    "Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw=="
                )
                self.base_url = "http://127.0.0.1:10000/devstoreaccount1"
            else:
                self.account_name = parts.get("AccountName", "")
                self.account_key = parts.get("AccountKey", "")
                self.sas_token = parts.get("SharedAccessSignature", "").lstrip("?")
                suffix = parts.get("EndpointSuffix", "core.windows.net")
                self.base_url = parts.get("BlobEndpoint", f"https://{self.account_name}.blob.{suffix}").rstrip("/")
        elif "?" in self.base_url:
            self.base_url, self.sas_token = self.base_url.split("?", 1)

        if not self.base_url:
            raise ConfigurationError("Blob storage endpoint could not be determined.")
        self._client = httpx.AsyncClient(timeout=60.0)
        self._server_date: str | None = None

    async def _refresh_server_date(self) -> None:
        try:
            r = await self._client.get(f"{self.base_url}/?comp=properties")
            if "date" in r.headers:
                self._server_date = r.headers["date"]
        except Exception:
            self._server_date = None

    def _sign_headers(self, method: str, blob_path: str, query: dict[str, str], headers: dict[str, str], length: int) -> dict[str, str]:
        from email.utils import formatdate
        from urllib.parse import quote
        import base64
        import hashlib
        import hmac

        h = dict(headers)
        h["x-ms-date"] = self._server_date or formatdate(usegmt=True)
        h["x-ms-version"] = self.API_VERSION
        if not self.account_key:
            return h

        ms_headers = sorted((k.lower(), v.strip()) for k, v in h.items() if k.lower().startswith("x-ms-"))
        canon_headers = "".join(f"{k}:{v}\n" for k, v in ms_headers)
        encoded_blob = quote(blob_path, safe="/") if blob_path else ""
        res_path = f"/{self.account_name}/{self.container}" + (f"/{encoded_blob}" if encoded_blob else "")
        canon_res = res_path + "".join(f"\n{k.lower()}:{query[k]}" for k in sorted(query))
        content_len = str(length) if length > 0 else ""
        content_type = h.get("Content-Type", "")
        string_to_sign = "\n".join([
            method,
            "",
            "",
            content_len,
            "",
            content_type,
            "",
            "",
            "",
            "",
            "",
            "",
            f"{canon_headers}{canon_res}",
        ])
        sig = base64.b64encode(
            hmac.new(base64.b64decode(self.account_key), string_to_sign.encode("utf-8"), hashlib.sha256).digest()
        ).decode("ascii")
        h["Authorization"] = f"SharedKey {self.account_name}:{sig}"
        return h

    def _url(self, blob_path: str, query: dict[str, str]) -> str:
        from urllib.parse import quote, urlencode

        path = f"{self.base_url}/{self.container}" + (f"/{quote(blob_path, safe='/')}" if blob_path else "")
        q = urlencode(query)
        if self.sas_token:
            q = f"{q}&{self.sas_token}" if q else self.sas_token
        return f"{path}?{q}" if q else path

    async def upload(self, name: str, data: bytes, *, metadata: dict[str, str] | None = None) -> BlobInfo:
        from datetime import timezone
        import hashlib

        await self._refresh_server_date()

        # Ensure container exists
        cq = {"restype": "container"}
        ch = self._sign_headers("PUT", "", cq, {}, 0)
        await self._client.put(self._url("", cq), headers=ch, content=b"")

        headers: dict[str, str] = {
            "x-ms-blob-type": "BlockBlob",
            "Content-Type": "application/pdf" if name.lower().endswith(".pdf") else "application/octet-stream",
        }
        for k, v in (metadata or {}).items():
            if v:
                headers[f"x-ms-meta-{k.lower()}"] = str(v)
        sh = self._sign_headers("PUT", name, {}, headers, len(data))
        r = await self._client.put(self._url(name, {}), headers=sh, content=data)
        if r.status_code >= 400:
            raise RuntimeError(f"Azure Blob HTTP {r.status_code}: {r.text[:300]}")
        etag = r.headers.get("etag", "").strip('"') or hashlib.md5(data).hexdigest()
        return BlobInfo(
            name=name,
            etag=etag,
            size=len(data),
            last_modified=datetime.now(timezone.utc),
            content_md5=hashlib.md5(data).hexdigest(),
            metadata=dict(metadata or {}),
        )

    async def get_info(self, name: str) -> BlobInfo | None:
        from datetime import timezone
        from email.utils import parsedate_to_datetime

        sh = self._sign_headers("HEAD", name, {}, {}, 0)
        r = await self._client.head(self._url(name, {}), headers=sh)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        meta = {k[10:]: v for k, v in r.headers.items() if k.lower().startswith("x-ms-meta-")}
        lm_str = r.headers.get("last-modified")
        lm = parsedate_to_datetime(lm_str) if lm_str else datetime.now(timezone.utc)
        return BlobInfo(
            name=name,
            etag=r.headers.get("etag", "").strip('"'),
            size=int(r.headers.get("content-length", "0")),
            last_modified=lm,
            metadata=meta,
        )

    async def download(self, name: str) -> bytes:
        sh = self._sign_headers("GET", name, {}, {}, 0)
        r = await self._client.get(self._url(name, {}), headers=sh)
        r.raise_for_status()
        return r.content

    async def list_blobs(self) -> list[BlobInfo]:
        from datetime import timezone
        from email.utils import parsedate_to_datetime
        import xml.etree.ElementTree as ET

        q = {"restype": "container", "comp": "list", "include": "metadata"}
        sh = self._sign_headers("GET", "", q, {}, 0)
        r = await self._client.get(self._url("", q), headers=sh)
        if r.status_code == 404:
            return []
        r.raise_for_status()
        root = ET.fromstring(r.text)
        items: list[BlobInfo] = []
        for b in root.findall(".//Blob"):
            bname = b.findtext("Name") or ""
            props = b.find("Properties")
            etag = (props.findtext("Etag") if props is not None else "") or ""
            size = int((props.findtext("Content-Length") if props is not None else "0") or "0")
            lm_str = props.findtext("Last-Modified") if props is not None else None
            lm = parsedate_to_datetime(lm_str) if lm_str else datetime.now(timezone.utc)
            mnode = b.find("Metadata")
            meta = {child.tag: (child.text or "") for child in list(mnode)} if mnode is not None else {}
            items.append(BlobInfo(name=bname, etag=etag.strip('"'), size=size, last_modified=lm, metadata=meta))
        return items

    async def aclose(self) -> None:
        await self._client.aclose()


def build_storage(settings: Settings) -> BlobStorage:
    conn = settings.azure_storage_connection_string.get_secret_value()
    if conn or settings.azure_storage_account_url:
        return AzureBlobStorage(settings)
    if settings.mock_azure:
        from app.services.mock.storage import LocalFolderStorage

        return LocalFolderStorage()
    return AzureBlobStorage(settings)


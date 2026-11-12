"""In-memory blob storage seeded with the sample corpus.

Even when a file is named ``*.pdf`` in the sample corpus its bytes are UTF-8 text:
``extract_pages_sync`` is patched by ``LocalFolderStorage`` to fall back to UTF-8 text
when a ``.pdf`` is not a binary PDF (starts with ``%PDF``).
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from app.core.text import sha256
from app.services.mock.corpus import SAMPLE_BLOBS, SampleBlob
from app.services.storage import BlobInfo, BlobStorage

DEFAULT_LOCAL_BLOB_DIR = Path(__file__).resolve().parents[3] / "data" / "college-docs"


class LocalFolderStorage(BlobStorage):
    def __init__(self, initial: list[SampleBlob] | None = None, root_dir: Path | str | None = DEFAULT_LOCAL_BLOB_DIR):
        self._blobs: dict[str, tuple[bytes, BlobInfo]] = {}
        self._root = Path(root_dir) if root_dir is not None else None
        for b in initial if initial is not None else SAMPLE_BLOBS:
            self.put(b.name, b.content.encode("utf-8"), metadata=b.metadata, last_modified=b.last_modified)
        if initial is None and self._root is not None and self._root.exists():
            self._load_disk_blobs()

    def _load_disk_blobs(self) -> None:
        if self._root is None:
            return
        brochure_src = self._root.parents[3] / "Bennett-Brochure.pdf"
        brochure_dst = self._root / "admissions" / "Bennett-Brochure__2026-11-12__v1.pdf"
        if brochure_src.exists() and not brochure_dst.exists():
            brochure_dst.parent.mkdir(parents=True, exist_ok=True)
            brochure_dst.write_bytes(brochure_src.read_bytes())
        if not self._root.exists():
            return
        for path in sorted(self._root.rglob("*")):
            if not path.is_file() or path.name.endswith(".meta.json"):
                continue
            rel = path.relative_to(self._root).as_posix()
            meta_file = path.with_name(path.name + ".meta.json")
            meta: dict[str, str] = {}
            if meta_file.exists():
                try:
                    meta = json.loads(meta_file.read_text(encoding="utf-8"))
                except Exception:
                    meta = {}
            stat = path.stat()
            mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
            self.put(rel, path.read_bytes(), metadata=meta, last_modified=mtime)

    def put(
        self,
        name: str,
        data: bytes,
        *,
        metadata: dict[str, str] | None = None,
        last_modified: datetime | None = None,
    ) -> BlobInfo:
        digest = sha256(data)[:32]
        info = BlobInfo(
            name=name, etag=digest, size=len(data),
            last_modified=last_modified or datetime.now(timezone.utc),
            content_md5=digest, metadata=dict(metadata or {}),
        )
        self._blobs[name] = (data, info)
        return info

    async def upload(
        self,
        name: str,
        data: bytes,
        *,
        metadata: dict[str, str] | None = None,
    ) -> BlobInfo:
        norm_name = name.replace("\\", "/").lstrip("/")
        if self._root is not None:
            dest = self._root / norm_name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            if metadata:
                meta_file = dest.with_name(dest.name + ".meta.json")
                meta_file.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        return self.put(norm_name, data, metadata=metadata)

    def remove(self, name: str) -> None:
        self._blobs.pop(name, None)

    async def list_blobs(self) -> list[BlobInfo]:
        self._load_disk_blobs()
        return [info for _, info in self._blobs.values()]

    async def get_info(self, name: str) -> BlobInfo | None:
        self._load_disk_blobs()
        item = self._blobs.get(name)
        return item[1] if item else None

    async def download(self, name: str) -> bytes:
        self._load_disk_blobs()
        if name not in self._blobs:
            raise FileNotFoundError(name)
        return self._blobs[name][0]


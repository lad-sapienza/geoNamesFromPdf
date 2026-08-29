"""Minimal client for the Zotero local HTTP API (``http://localhost:23119/api``).

Read access is available in Zotero 7 and later. Write access (``PATCH`` an
item's tags) needs **Zotero 10.0+** and a local API key granted at runtime by
the user through a Zotero dialog. Everything here is offline: no network, no
``api.zotero.org``. The module is UI-free and testable against an injected
``httpx`` transport.

The local API mirrors the Zotero Web API v3, so the request/response shapes
below follow <https://www.zotero.org/support/dev/web_api/v3/>.

Parts that could only be confirmed against a running Zotero 10 are marked
``# VERIFY:``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterator, Optional
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname

import httpx

BASE_URL = "http://localhost:23119/api"
DONE_TAG = "geodone"
GEO_TAG_PREFIX = "@"

# Item types that are not stand-alone bibliographic records.
_NON_RECORD_TYPES = {"attachment", "note", "annotation"}


# --------------------------------------------------------------------------- #
# Errors
# --------------------------------------------------------------------------- #

class ZoteroError(Exception):
    """Base class for expected, user-facing Zotero errors."""


class ZoteroUnavailable(ZoteroError):
    """The local API is not reachable or not enabled in Zotero's preferences."""


class ZoteroWriteUnsupported(ZoteroError):
    """This Zotero version has no local write API (needs 10.0+)."""


class ZoteroAuthDenied(ZoteroError):
    """The user declined the write-authorization prompt."""


class ZoteroConflict(ZoteroError):
    """The item changed on disk since it was read (HTTP 412)."""


class ZoteroFileUnavailable(ZoteroError):
    """The attachment's file is not present on this machine.

    Typical for group libraries whose files are synced on demand: Zotero
    reports a local path but the PDF has not been downloaded yet.
    """


# --------------------------------------------------------------------------- #
# Value objects
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class Library:
    """A Zotero library: the personal one (``users/0``) or a group."""

    prefix: str          # "users/0" or "groups/<id>"
    label: str           # human-readable name

    @property
    def is_group(self) -> bool:
        return self.prefix.startswith("groups/")


@dataclass
class ZoteroItem:
    key: str
    version: int
    title: str
    creators_summary: str
    year: str
    item_type: str
    tags: list[str] = field(default_factory=list)
    num_children: int = 0

    @property
    def geo_tag_count(self) -> int:
        return sum(1 for t in self.tags if t.startswith(GEO_TAG_PREFIX))

    @property
    def citation(self) -> str:
        bits = [b for b in (self.creators_summary, self.year) if b]
        head = " ".join(bits)
        return f"{head} — {self.title}" if head else self.title


@dataclass(frozen=True)
class PdfAttachment:
    key: str
    filename: str
    content_type: str = "application/pdf"


# --------------------------------------------------------------------------- #
# Helpers for parsing Web-API item JSON
# --------------------------------------------------------------------------- #

_YEAR_RE = re.compile(r"(1\d{3}|20\d{2}|21\d{2})")


def _creators_summary(creators: list[dict]) -> str:
    names = []
    for c in creators:
        if c.get("name"):                       # single-field creator
            names.append(c["name"].split()[-1] if c["name"].split() else c["name"])
        elif c.get("lastName"):
            names.append(c["lastName"])
    if not names:
        return ""
    if len(names) <= 2:
        return ", ".join(names)
    return f"{names[0]} et al."


def _year(date_str: str) -> str:
    m = _YEAR_RE.search(date_str or "")
    return m.group(0) if m else ""


def _to_item(obj: dict) -> ZoteroItem:
    data = obj.get("data", obj)
    return ZoteroItem(
        key=obj.get("key") or data.get("key", ""),
        version=obj.get("version") or data.get("version", 0),
        title=(data.get("title") or data.get("caseName")
               or data.get("subject") or data.get("nameOfAct") or "(untitled)"),
        creators_summary=_creators_summary(data.get("creators", [])),
        year=_year(data.get("date", "")),
        item_type=data.get("itemType", ""),
        tags=[t["tag"] for t in data.get("tags", []) if t.get("tag")],
        num_children=obj.get("meta", {}).get("numChildren", 0),
    )


# --------------------------------------------------------------------------- #
# Client
# --------------------------------------------------------------------------- #

class ZoteroLocal:
    """Thin wrapper over the Zotero local HTTP API.

    Typical use::

        zot = ZoteroLocal()
        zot.ping()                          # raises ZoteroUnavailable if down
        libs = zot.libraries()
        tags = zot.geo_tags(libs[0])
        for item in zot.pending_items(libs[0]):
            ...
        zot.authorize_write()               # Zotero shows an allow/deny dialog
        zot.add_tags(libs[0], item.key, ["@Butrint", "geodone"])
    """

    def __init__(self, *, base_url: str = BASE_URL, timeout: float = 30.0,
                 transport: Optional[httpx.BaseTransport] = None):
        self._client = httpx.Client(
            base_url=base_url,
            timeout=timeout,
            transport=transport,
            follow_redirects=False,
            headers={"Zotero-API-Version": "3"},
        )
        self._server_id: Optional[str] = None
        self._api_key: Optional[str] = None
        self._key_remembered: bool = False

    # -- lifecycle ------------------------------------------------------- #

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "ZoteroLocal":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def _request(self, method: str, path: str, **kw) -> httpx.Response:
        try:
            r = self._client.request(method, path, **kw)
        except httpx.ConnectError as exc:
            raise ZoteroUnavailable(
                "Zotero is not running, or the local API is unreachable on "
                "localhost:23119."
            ) from exc
        except httpx.HTTPError as exc:                       # timeouts etc.
            raise ZoteroError(f"Zotero request failed: {exc}") from exc
        # Every Zotero response carries a stable instance id; it must be echoed
        # back on write requests (else HTTP 428).
        sid = r.headers.get("Zotero-Server-ID")
        if sid:
            self._server_id = sid
        return r

    def _ensure_server_id(self) -> None:
        if self._server_id is not None:
            return
        for path, params in (("/", None),
                             ("/users/0/items", {"limit": 1, "format": "keys"})):
            try:
                self._request("GET", path, params=params)
            except ZoteroError:
                pass
            if self._server_id is not None:
                return

    def _write_headers(self) -> dict:
        h = {}
        if self._api_key:
            h["Zotero-API-Key"] = self._api_key
        if self._server_id:
            h["Zotero-Server-ID"] = self._server_id
        return h

    # -- connection ---------------------------------------------------- #

    def ping(self) -> None:
        """Check that the local API answers. Raise :class:`ZoteroUnavailable`."""
        r = self._request("GET", "/users/0/items", params={"limit": 1, "format": "keys"})
        if r.status_code == 403:
            raise ZoteroUnavailable(
                "The local API is disabled. In Zotero: Settings -> Advanced -> "
                "enable 'Allow other applications on this computer to communicate "
                "with Zotero'."
            )
        if r.status_code >= 500:
            raise ZoteroUnavailable(f"Zotero returned HTTP {r.status_code}.")
        r.raise_for_status()

    def libraries(self) -> list[Library]:
        """The personal library plus every group the user belongs to."""
        libs = [Library("users/0", "My Library")]
        r = self._request("GET", "/users/0/groups", params={"limit": 100})
        if r.status_code == 200:
            try:
                for g in r.json():
                    gid = g.get("id") or g.get("data", {}).get("id")
                    name = g.get("data", {}).get("name") or f"Group {gid}"
                    if gid is not None:
                        libs.append(Library(f"groups/{gid}", name))
            except ValueError:
                pass
        return libs

    # -- write authorization --------------------------------------------- #

    @property
    def can_write(self) -> bool:
        return self._api_key is not None

    def authorize_write(self, *, app_name: str = "geoNamesFromPdf Zotero assistant") -> None:
        """Request a local API key. Zotero shows an allow/deny dialog.

        Raises:
            ZoteroWriteUnsupported: Zotero < 10 (endpoint missing).
            ZoteroAuthDenied: the user declined.
        """
        self._ensure_server_id()

        headers = {}
        if self._server_id:
            headers["Zotero-Server-ID"] = self._server_id

        r = self._request("POST", "/local/authorize",
                          json={"appName": app_name}, headers=headers)

        if r.status_code == 404:
            raise ZoteroWriteUnsupported(
                "Writing tags through the local API needs Zotero 10.0 or newer."
            )
        if r.status_code in (401, 403):
            raise ZoteroAuthDenied("Zotero denied write access.")
        r.raise_for_status()

        try:
            body = r.json()
        except ValueError:
            body = {}
        key = body.get("key") or body.get("apiKey")
        if not key:
            raise ZoteroAuthDenied("Zotero did not return a write key "
                                   "(request was probably declined).")
        self._api_key = key
        self._key_remembered = bool(body.get("remember"))

    # -- reads --------------------------------------------------------- #

    def _paginate(self, prefix: str, path: str, params: list[tuple]) -> Iterator[dict]:
        start, page = 0, 100
        while True:
            q = list(params) + [("limit", page), ("start", start)]
            r = self._request("GET", f"/{prefix}{path}", params=q)
            r.raise_for_status()
            rows = r.json()
            if not rows:
                return
            yield from rows
            if len(rows) < page:
                return
            start += page

    def geo_tags(self, lib: Library, *, prefix: str = GEO_TAG_PREFIX) -> list[str]:
        """Every tag in ``lib`` whose name starts with ``prefix`` (sorted)."""
        out = {row["tag"] for row in self._paginate(lib.prefix, "/tags", [])
               if row.get("tag", "").startswith(prefix)}
        return sorted(out, key=str.casefold)

    def _pending_params(self, done_tag: str) -> list[tuple]:
        return [("tag", f"-{done_tag}"),
                ("sort", "dateAdded"), ("direction", "asc")]

    def count_pending(self, lib: Library, *, done_tag: str = DONE_TAG) -> int:
        """Approximate number of records still missing ``done_tag``.

        Uses ``/items/top`` so child attachments/notes are excluded already;
        the count may be off by the number of stand-alone notes, which
        :meth:`pending_items` filters out.
        """
        q = self._pending_params(done_tag) + [("limit", 1), ("format", "keys")]
        r = self._request("GET", f"/{lib.prefix}/items/top", params=q)
        r.raise_for_status()
        return int(r.headers.get("Total-Results", 0))

    def pending_items(self, lib: Library, *, done_tag: str = DONE_TAG
                      ) -> Iterator[ZoteroItem]:
        """Yield top-level bibliographic records without ``done_tag``, oldest first."""
        for obj in self._paginate(lib.prefix, "/items/top",
                                  self._pending_params(done_tag)):
            data = obj.get("data", {})
            if data.get("itemType") in _NON_RECORD_TYPES:
                continue
            yield _to_item(obj)

    def get_item(self, lib: Library, item_key: str) -> ZoteroItem:
        """Fresh single-item read (used right before a write)."""
        r = self._request("GET", f"/{lib.prefix}/items/{item_key}")
        r.raise_for_status()
        return _to_item(r.json())

    def pdf_attachments(self, lib: Library, item_key: str) -> list[PdfAttachment]:
        r = self._request("GET", f"/{lib.prefix}/items/{item_key}/children")
        r.raise_for_status()
        out = []
        for obj in r.json():
            d = obj.get("data", {})
            if d.get("itemType") != "attachment":
                continue
            if d.get("contentType") != "application/pdf":
                continue
            out.append(PdfAttachment(
                key=obj.get("key", d.get("key", "")),
                filename=d.get("filename") or d.get("title") or "attachment.pdf",
                content_type="application/pdf",
            ))
        return out

    def attachment_bytes(self, lib: Library, att_key: str) -> bytes:
        """Raw bytes of an attachment file.

        The local API answers ``/file`` with a 302 redirect to a ``file://``
        URL on disk; we read that file directly. A plain 200 body is also
        handled in case the behaviour differs.

        Raises:
            ZoteroFileUnavailable: the file is not on this machine (e.g. a
                group library synced on demand, or a linked file that moved).
        """
        r = self._request("GET", f"/{lib.prefix}/items/{att_key}/file")
        if r.status_code in (301, 302, 303, 307, 308):
            loc = r.headers.get("Location", "")
            if loc.startswith("file:"):
                path = url2pathname(unquote(urlparse(loc).path))
                try:
                    with open(path, "rb") as fh:
                        return fh.read()
                except OSError as exc:
                    raise ZoteroFileUnavailable(
                        f"the PDF is not stored locally ({path}). In Zotero open "
                        f"the attachment once, or right-click it -> Download File, "
                        f"then retry. For a whole group: Settings -> Sync -> "
                        f"'Download files'."
                    ) from exc
            if loc.startswith(("http://", "https://")):
                follow = self._request("GET", loc)
                follow.raise_for_status()
                return follow.content
            raise ZoteroFileUnavailable(
                f"the PDF is not available offline (redirect to {loc or '?'})."
            )
        if r.status_code == 200:
            return r.content
        if r.status_code == 404:
            raise ZoteroFileUnavailable(
                f"Zotero has no downloadable file for attachment {att_key}."
            )
        raise ZoteroError(
            f"could not download attachment {att_key}: HTTP {r.status_code}"
        )

    # -- write --------------------------------------------------------- #

    def add_tags(self, lib: Library, item_key: str, new_tags,
                 *, retries: int = 1) -> ZoteroItem:
        """Add ``new_tags`` to an item, keeping every existing tag.

        Reads the item fresh, unions the existing and new tags, sorts the whole
        list alphabetically (case-insensitively) and ``PATCH``es it with a
        per-object ``version`` so a concurrent edit is rejected with 412 rather
        than silently overwritten.

        Returns the updated :class:`ZoteroItem`. A no-op (nothing new to add)
        returns the item unchanged without a write.

        Raises:
            ZoteroError: if :meth:`authorize_write` has not succeeded.
            ZoteroConflict: if the item kept changing under us.
        """
        if not self.can_write:
            raise ZoteroError("write not authorized; call authorize_write() first")

        item = self.get_item(lib, item_key)
        wanted = [t for t in new_tags if t]
        to_add = [t for t in wanted if t not in item.tags]
        if not to_add:
            return item

        self._ensure_server_id()
        merged = sorted({*item.tags, *to_add}, key=str.casefold)
        body = {"tags": [{"tag": t} for t in merged], "version": item.version}
        r = self._request(
            "PATCH", f"/{lib.prefix}/items/{item_key}",
            json=body,
            headers={**self._write_headers(), "Content-Type": "application/json"},
        )

        if r.status_code == 412:
            if retries > 0:
                return self.add_tags(lib, item_key, new_tags, retries=retries - 1)
            raise ZoteroConflict(
                f"item {item_key} keeps changing; try again"
            )
        if r.status_code == 428:
            raise ZoteroError(
                "Zotero rejected the write (428): could not identify the Zotero "
                "instance. Restart the assistant with Zotero already running."
            )
        if r.status_code in (401, 403):
            if not self._key_remembered:
                self._api_key = None            # single-use key was consumed
            raise ZoteroError(
                "the write key was rejected (it may have been single-use); "
                "authorize again, choosing 'Always Allow'."
            )
        if r.status_code not in (200, 204):
            raise ZoteroError(
                f"tag write failed for {item_key}: HTTP {r.status_code} {r.text[:200]}"
            )

        if not self._key_remembered:
            self._api_key = None                # consumed; next write re-prompts
        return self.get_item(lib, item_key)

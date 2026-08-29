"""Offline tests for zotero.py, driven by an injected httpx MockTransport.

No running Zotero is required. These pin the request shapes and the tag-merge
logic; the live behaviour of Zotero 10's ``/local/authorize`` and ``/file``
endpoints still needs a manual check against a real install.
"""

import json as jsonlib

import httpx
import pytest

import zotero
from zotero import Library, ZoteroLocal


# --------------------------------------------------------------------------- #
# A tiny fake Zotero server
# --------------------------------------------------------------------------- #

class FakeZotero:
    def __init__(self):
        self.enabled = True
        self.write_supported = True
        self.grant_key = "k" * 32
        self.remember = True
        self.groups = [{"id": 42, "data": {"id": 42, "name": "LAD"}}]
        self.tags = (
            [{"tag": f"kw{i}"} for i in range(100)]           # page 1 filler
            + [{"tag": "@Butrint"}, {"tag": "@Çuka e Ajtoit"}, {"tag": "survey"}]
        )
        self.items_top = [
            self._item("AAAA1111", 5, "Roman Epirus", "it",
                       creators=[{"lastName": "Bogdani"}], date="2019-05",
                       tags=["@Roma", "survey"]),
            self._item("NOTE0000", 3, "", "note", item_type="note"),
            self._item("BBBB2222", 8, "Butrint report", "en",
                       creators=[{"lastName": "Smith"}, {"lastName": "Jones"},
                                 {"lastName": "Doe"}], date="March 2021", tags=[]),
        ]
        self.items = {it["key"]: it for it in self.items_top}
        self.children = {
            "AAAA1111": [
                {"key": "ATT1", "data": {"itemType": "attachment",
                                         "contentType": "application/pdf",
                                         "filename": "epirus.pdf"}},
                {"key": "ATT2", "data": {"itemType": "attachment",
                                         "contentType": "text/html",
                                         "title": "snapshot"}},
            ],
        }
        self.patches = []          # (key, body) log
        self.last_patch_headers = None
        self._conflict_left = 0    # number of 412s to emit before succeeding
        self.file_payload = b"%PDF-1.4 fake"

    @staticmethod
    def _item(key, version, title, lang, *, creators=None, date="",
              tags=None, item_type="journalArticle"):
        return {
            "key": key, "version": version,
            "data": {
                "key": key, "version": version, "itemType": item_type,
                "title": title, "date": date,
                "creators": creators or [],
                "tags": [{"tag": t} for t in (tags or [])],
            },
        }

    # -- the transport handler --------------------------------------------- #
    def handler(self, request: httpx.Request) -> httpx.Response:
        resp = self._route(request)
        resp.headers.setdefault("Zotero-Server-ID", "srv1")   # every response carries it
        return resp

    def _route(self, request: httpx.Request) -> httpx.Response:
        m, url = request.method, request.url
        path = url.path
        if not self.enabled:
            return httpx.Response(403, text="forbidden")

        if path == "/api/users/0/items" and m == "GET":
            return httpx.Response(200, json=[])

        if path == "/api/" and m == "GET":
            return httpx.Response(200, json={})

        if path == "/api/users/0/groups" and m == "GET":
            return httpx.Response(200, json=self.groups)

        if path == "/api/local/authorize" and m == "POST":
            if not self.write_supported:
                return httpx.Response(404, text="no endpoint")
            body = jsonlib.loads(request.content)
            assert body.get("appName")
            if self.grant_key is None:
                return httpx.Response(200, json={})           # user declined
            return httpx.Response(200, json={"key": self.grant_key,
                                            "remember": self.remember})

        if path.endswith("/tags") and m == "GET":
            start = int(url.params.get("start", 0))
            limit = int(url.params.get("limit", 100))
            page = self.tags[start:start + limit]
            return httpx.Response(200, json=page)

        if path.endswith("/items/top") and m == "GET":
            assert url.params.get("tag") == "-geodone"
            assert url.params.get("sort") == "dateAdded"
            if url.params.get("format") == "keys":
                return httpx.Response(200, text="AAAA1111\nBBBB2222",
                                     headers={"Total-Results": "2"})
            start = int(url.params.get("start", 0))
            limit = int(url.params.get("limit", 100))
            return httpx.Response(200, json=self.items_top[start:start + limit])

        m_item = _match(path, "/api/users/0/items/")
        if m_item and m_item.endswith("/children") and m == "GET":
            key = m_item[: -len("/children")]
            return httpx.Response(200, json=self.children.get(key, []))
        if m_item and m_item.endswith("/file") and m == "GET":
            return httpx.Response(200, content=self.file_payload)
        if m_item and m == "GET":
            it = self.items.get(m_item)
            return httpx.Response(200 if it else 404, json=it or {})
        if m_item and m == "PATCH":
            self.last_patch_headers = dict(request.headers)
            if not request.headers.get("Zotero-Server-ID"):
                return httpx.Response(428, text="Zotero-Server-ID not provided")
            if self._conflict_left > 0:
                self._conflict_left -= 1
                self.items[m_item]["version"] += 1            # someone else edited
                self.items[m_item]["data"]["version"] += 1
                return httpx.Response(412, text="Precondition Failed")
            body = jsonlib.loads(request.content)
            self.patches.append((m_item, body))
            self.items[m_item]["data"]["tags"] = body["tags"]
            self.items[m_item]["version"] += 1
            self.items[m_item]["data"]["version"] += 1
            return httpx.Response(204)

        return httpx.Response(404, text=f"unhandled {m} {path}")


def _match(path: str, prefix: str):
    return path[len(prefix):] if path.startswith(prefix) else None


@pytest.fixture
def fake():
    return FakeZotero()


@pytest.fixture
def client(fake):
    zl = ZoteroLocal(transport=httpx.MockTransport(fake.handler))
    yield zl
    zl.close()


MY = Library("users/0", "My Library")


# --------------------------------------------------------------------------- #
# connection
# --------------------------------------------------------------------------- #

def test_ping_ok(client):
    client.ping()  # no raise


def test_ping_disabled(fake, client):
    fake.enabled = False
    with pytest.raises(zotero.ZoteroUnavailable):
        client.ping()


def test_ping_connection_refused():
    def boom(request):
        raise httpx.ConnectError("refused", request=request)
    zl = ZoteroLocal(transport=httpx.MockTransport(boom))
    with pytest.raises(zotero.ZoteroUnavailable):
        zl.ping()


def test_libraries_includes_groups(client):
    libs = client.libraries()
    assert libs[0] == MY
    assert Library("groups/42", "LAD") in libs
    assert libs[1].is_group


# --------------------------------------------------------------------------- #
# reads
# --------------------------------------------------------------------------- #

def test_geo_tags_filters_prefix_and_paginates(client):
    tags = client.geo_tags(MY)
    assert tags == ["@Butrint", "@Çuka e Ajtoit"]        # sorted, '@' only, no "survey"


def test_count_pending_reads_header(client):
    assert client.count_pending(MY) == 2


def test_pending_items_streams_and_filters_notes(client):
    items = list(client.pending_items(MY))
    assert [i.key for i in items] == ["AAAA1111", "BBBB2222"]   # NOTE0000 dropped
    assert items[0].creators_summary == "Bogdani"
    assert items[0].year == "2019"
    assert items[1].creators_summary == "Smith et al."
    assert items[1].year == "2021"


def test_pdf_attachments_only_pdf(client):
    atts = client.pdf_attachments(MY, "AAAA1111")
    assert [a.key for a in atts] == ["ATT1"]
    assert atts[0].filename == "epirus.pdf"


def test_attachment_bytes_plain_200(client, fake):
    assert client.attachment_bytes(MY, "ATT1") == fake.file_payload


def test_attachment_bytes_file_redirect(tmp_path):
    pdf = tmp_path / "x.pdf"
    pdf.write_bytes(b"%PDF-1.7 redirect")

    def handler(request):
        if request.url.path.endswith("/file"):
            return httpx.Response(302, headers={"Location": pdf.as_uri()})
        return httpx.Response(404)

    zl = ZoteroLocal(transport=httpx.MockTransport(handler))
    assert zl.attachment_bytes(MY, "ATT1") == b"%PDF-1.7 redirect"
    zl.close()


def test_attachment_bytes_missing_local_file(tmp_path):
    missing = tmp_path / "storage" / "KEY" / "gone.pdf"      # never created

    def handler(request):
        if request.url.path.endswith("/file"):
            return httpx.Response(302, headers={"Location": missing.as_uri()})
        return httpx.Response(404)

    zl = ZoteroLocal(transport=httpx.MockTransport(handler))
    with pytest.raises(zotero.ZoteroFileUnavailable):
        zl.attachment_bytes(MY, "ATT1")
    zl.close()


def test_attachment_bytes_404_is_unavailable(client):
    def handler(request):
        return httpx.Response(404)
    zl = ZoteroLocal(transport=httpx.MockTransport(handler))
    with pytest.raises(zotero.ZoteroFileUnavailable):
        zl.attachment_bytes(MY, "NOPE")
    zl.close()


# --------------------------------------------------------------------------- #
# write authorization
# --------------------------------------------------------------------------- #

def test_authorize_write_grants_key(client):
    assert not client.can_write
    client.authorize_write()
    assert client.can_write


def test_authorize_write_unsupported(fake, client):
    fake.write_supported = False
    with pytest.raises(zotero.ZoteroWriteUnsupported):
        client.authorize_write()


def test_authorize_write_declined(fake, client):
    fake.grant_key = None
    with pytest.raises(zotero.ZoteroAuthDenied):
        client.authorize_write()


# --------------------------------------------------------------------------- #
# tag writing
# --------------------------------------------------------------------------- #

def test_add_tags_requires_authorization(client):
    with pytest.raises(zotero.ZoteroError):
        client.add_tags(MY, "AAAA1111", ["@Butrint"])


def test_add_tags_merges_and_sorts(client, fake):
    client.authorize_write()
    client.add_tags(MY, "AAAA1111", ["@Butrint", "@Roma", "geodone"])
    key, body = fake.patches[-1]
    assert key == "AAAA1111"
    # existing (@Roma, survey) + new (@Butrint, geodone), sorted case-insensitively
    assert [t["tag"] for t in body["tags"]] == ["@Butrint", "@Roma", "geodone", "survey"]
    assert body["version"] == 5


def test_add_tags_sends_server_id_and_key_headers(client, fake):
    client.authorize_write()
    client.add_tags(MY, "AAAA1111", ["@Butrint"])
    h = fake.last_patch_headers
    assert h["zotero-server-id"] == "srv1"
    assert h["zotero-api-key"] == "k" * 32


def test_add_tags_428_without_server_id(fake):
    # a client that never sees a Zotero-Server-ID (stripped responses)
    def strip_sid(request):
        resp = fake._route(request)
        return resp

    zl = ZoteroLocal(transport=httpx.MockTransport(strip_sid))
    zl._api_key = "k" * 32               # pretend authorized
    with pytest.raises(zotero.ZoteroError):
        zl.add_tags(MY, "AAAA1111", ["@Butrint"])
    zl.close()


def test_add_tags_noop_when_nothing_new(client, fake):
    client.authorize_write()
    client.add_tags(MY, "AAAA1111", ["@Roma", "survey"])   # both already present
    assert fake.patches == []


def test_add_tags_retries_on_conflict(client, fake):
    client.authorize_write()
    fake._conflict_left = 1
    client.add_tags(MY, "AAAA1111", ["@Butrint"])
    assert len(fake.patches) == 1
    # version used in the successful PATCH is the post-conflict one
    assert fake.patches[-1][1]["version"] == 6


def test_add_tags_gives_up_after_retries(client, fake):
    client.authorize_write()
    fake._conflict_left = 5
    with pytest.raises(zotero.ZoteroConflict):
        client.add_tags(MY, "AAAA1111", ["@Butrint"], retries=1)

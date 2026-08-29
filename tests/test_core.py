"""Offline unit tests for core.py (no spaCy model downloads required).

Run with:  python -m pytest
"""

import json

import pytest

import core


# --------------------------------------------------------------------------- #
# parse_page_ranges
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("spec, expected", [
    ("", None),
    ("   ", None),
    ("5", {4}),
    ("5-10", {4, 5, 6, 7, 8, 9}),
    ("5-10, 12-14", {4, 5, 6, 7, 8, 9, 11, 12, 13}),
    ("3,3,3", {2}),
    ("1-1", {0}),
])
def test_parse_page_ranges_valid(spec, expected):
    assert core.parse_page_ranges(spec) == expected


@pytest.mark.parametrize("spec", ["0", "-3", "5-", "abc", "10-5", "5-abc", "1.5"])
def test_parse_page_ranges_invalid(spec):
    with pytest.raises(ValueError):
        core.parse_page_ranges(spec)


def test_parse_page_ranges_upper_bound():
    assert core.parse_page_ranges("1-3", max_pages=10) == {0, 1, 2}
    with pytest.raises(ValueError):
        core.parse_page_ranges("1-50", max_pages=10)
    with pytest.raises(ValueError):
        core.parse_page_ranges("99", max_pages=10)


# --------------------------------------------------------------------------- #
# GazetteerMatcher
# --------------------------------------------------------------------------- #

def _pages(text):
    return [core.PdfPage(number=1, text=text)]


def test_gazetteer_matcher_word_boundary_and_case():
    entries = [core.GazEntry(name="Como"), core.GazEntry(name="Butrint")]
    matcher = core.GazetteerMatcher(entries)

    # "Como" must not match inside "Comodo"
    assert matcher.find(_pages("L'imperatore Comodo regnò a lungo.")) == {}

    hits = matcher.find(_pages("Da COMO a butrint il viaggio è lungo."))
    assert {t.name for t in hits.values()} == {"Como", "Butrint"}
    # canonical spelling is preserved regardless of how it appeared
    assert sorted(t.name for t in hits.values()) == ["Butrint", "Como"]


def test_gazetteer_matcher_multiword_longest_wins():
    entries = [core.GazEntry(name="Çuka"), core.GazEntry(name="Çuka e Ajtoit")]
    matcher = core.GazetteerMatcher(entries)
    hits = matcher.find(_pages("Lo scavo di Çuka e Ajtoit è terminato."))
    assert {t.name for t in hits.values()} == {"Çuka e Ajtoit"}


def test_gazetteer_matcher_counts_and_pages():
    entries = [core.GazEntry(name="Roma")]
    matcher = core.GazetteerMatcher(entries)
    pages = [
        core.PdfPage(number=2, text="Roma e ancora Roma."),
        core.PdfPage(number=5, text="Di nuovo Roma."),
    ]
    hits = matcher.find(pages)
    topo = hits[core._key("Roma")]
    assert topo.count == 3
    assert topo.pages == {2, 5}
    assert topo.sources == {"gazetteer"}


def test_empty_gazetteer_matcher_is_falsy():
    matcher = core.GazetteerMatcher([])
    assert not matcher
    assert matcher.find(_pages("Roma, Milano, Napoli")) == {}


# --------------------------------------------------------------------------- #
# load_gazetteer
# --------------------------------------------------------------------------- #

def test_load_gazetteer_plain_txt(tmp_path):
    p = tmp_path / "gaz.txt"
    p.write_text("Butrint\n\n  Çuka e Ajtoit  \nButrint\n", encoding="utf-8")
    entries = core.load_gazetteer(p)
    assert [e.name for e in entries] == ["Butrint", "Çuka e Ajtoit"]  # de-duplicated


def test_load_gazetteer_tsv_with_coordinates(tmp_path):
    p = tmp_path / "gaz.tsv"
    p.write_text(
        "name\tid\tlat\tlon\n"
        "Butrint\tpleiades:530798\t39.7456\t20.0206\n"
        "Epirus\tpleiades:991380\t39.5\t20.5\n",
        encoding="utf-8",
    )
    entries = {e.name: e for e in core.load_gazetteer(p)}
    assert entries["Butrint"].id == "pleiades:530798"
    assert entries["Butrint"].lat == pytest.approx(39.7456)
    assert entries["Epirus"].lon == pytest.approx(20.5)


def test_load_gazetteer_csv_no_header(tmp_path):
    p = tmp_path / "gaz.csv"
    p.write_text("Butrint,foo\nEpirus,bar\n", encoding="utf-8")
    entries = core.load_gazetteer(p)
    assert [e.name for e in entries] == ["Butrint", "Epirus"]


# --------------------------------------------------------------------------- #
# analyze() end-to-end, gazetteer-only (no spaCy model needed)
# --------------------------------------------------------------------------- #

@pytest.fixture
def sample_pdf(tmp_path):
    pymupdf = pytest.importorskip("pymupdf")
    path = tmp_path / "sample.pdf"
    doc = pymupdf.open()
    page1 = doc.new_page()
    page1.insert_text((72, 72), "We surveyed Butrint and nearby Epirus in 2019.")
    page2 = doc.new_page()
    page2.insert_text((72, 72), "The road from Butrint to Rome is long.")
    doc.save(path)
    doc.close()
    return str(path)


def test_analyze_gazetteer_only(sample_pdf):
    gaz = [core.GazEntry(name=n) for n in ("Butrint", "Epirus", "Athens")]
    result = core.analyze(sample_pdf, gazetteer=gaz, use_ner=False)

    names = result.names
    assert "Butrint" in names and "Epirus" in names
    assert "Athens" not in names       # not in the document
    assert "Rome" not in names         # in the document but not in the gazetteer

    butrint = next(t for t in result.toponyms if t.name == "Butrint")
    assert butrint.count == 2
    assert butrint.pages == {1, 2}
    assert result.pages_processed == [1, 2]


def test_analyze_exclude_is_case_insensitive(sample_pdf):
    gaz = [core.GazEntry(name=n) for n in ("Butrint", "Epirus")]
    result = core.analyze(sample_pdf, gazetteer=gaz, use_ner=False,
                          exclude=["butrint"])
    assert result.names == ["Epirus"]


def test_analyze_pages_filter_and_skip_warning(sample_pdf):
    gaz = [core.GazEntry(name=n) for n in ("Butrint", "Rome")]
    result = core.analyze(sample_pdf, gazetteer=gaz, use_ner=False, pages="2")
    assert result.pages_processed == [2]
    assert "Rome" in result.names            # only appears on page 2


def test_analyze_missing_file_raises_filenotfound(tmp_path):
    with pytest.raises(FileNotFoundError):
        core.analyze(str(tmp_path / "nope.pdf"), gazetteer=[core.GazEntry(name="X")],
                     use_ner=False)


def test_analyze_no_ner_without_gazetteer_errors(sample_pdf):
    with pytest.raises(core.GeoNamesError):
        core.analyze(sample_pdf, use_ner=False)


def test_analyze_accepts_pdf_bytes(sample_pdf):
    import pathlib
    data = pathlib.Path(sample_pdf).read_bytes()
    gaz = [core.GazEntry(name=n) for n in ("Butrint", "Epirus")]
    result = core.analyze(data, gazetteer=gaz, use_ner=False,
                          source_name="item42:paper.pdf")
    assert result.pdf_path == "item42:paper.pdf"
    assert "Butrint" in result.names and "Epirus" in result.names
    assert result.pages_processed == [1, 2]


def test_analyze_rejects_bad_source_type():
    with pytest.raises(TypeError):
        core.analyze(1234, gazetteer=[core.GazEntry(name="X")], use_ner=False)


# --------------------------------------------------------------------------- #
# serializers
# --------------------------------------------------------------------------- #

def _result_with_coords():
    r = core.AnalysisResult(pdf_path="x.pdf", language="it", model="test")
    r.toponyms = [
        core.Toponym(name="Butrint", label="LOC", count=3, pages={1, 2},
                     sources={"gazetteer"}, gazetteer_id="pleiades:530798",
                     lat=39.7456, lon=20.0206),
        core.Toponym(name="Nowhere", label="GPE", count=1, pages={4},
                     sources={"ner:GPE"}),
    ]
    return r


def test_to_csv_has_header_and_rows():
    out = core.to_csv(_result_with_coords())
    lines = out.strip().splitlines()
    assert lines[0] == "name,label,count,pages,sources,gazetteer_id,lat,lon"
    assert lines[1].startswith("Butrint,LOC,3,1;2,gazetteer,pleiades:530798,")


def test_to_json_roundtrip():
    payload = json.loads(core.to_json(_result_with_coords()))
    assert payload["count"] == 2
    assert payload["toponyms"][0]["name"] == "Butrint"
    assert payload["toponyms"][0]["pages"] == [1, 2]


def test_to_geojson_only_emits_entries_with_coordinates():
    fc = json.loads(core.to_geojson(_result_with_coords()))
    assert fc["type"] == "FeatureCollection"
    assert len(fc["features"]) == 1
    feat = fc["features"][0]
    assert feat["geometry"]["coordinates"] == [20.0206, 39.7456]  # [lon, lat]
    assert feat["properties"]["name"] == "Butrint"


def test_serialize_unknown_format_raises():
    with pytest.raises(core.GeoNamesError):
        core.serialize(_result_with_coords(), "xml")

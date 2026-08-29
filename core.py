"""Core, side-effect-free logic for geoNamesFromPdf.

This module contains the reusable building blocks shared by the command-line
interface (``geoNamesFromPdf.py``) and the graphical interface (``gui.py``):

* PDF text extraction (optionally limited to page ranges)
* language detection
* spaCy NER extraction (NER-only pipeline, page-by-page streaming)
* gazetteer matching (single-pass, word-boundary, case-insensitive,
  multi-word aware, optionally carrying coordinates / identifiers)
* result model and serializers (txt / csv / json / geojson)

Nothing here prints, calls ``input()`` or ``sys.exit()`` -- callers decide how
to report progress and errors. Heavy third-party libraries (``pymupdf``,
``spacy``, ``langdetect``) are imported lazily so that ``--list-languages`` and
the first-run setup keep working before the dependencies are installed.
"""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass, field
from typing import Iterable, Optional

# --------------------------------------------------------------------------- #
# Language configuration
# --------------------------------------------------------------------------- #

# Default (CNN, "large") spaCy models, one per language code.
LANGUAGE_MODELS = {
    'en': 'en_core_web_lg',      # English
    'it': 'it_core_news_lg',     # Italian
    'es': 'es_core_news_lg',     # Spanish
    'fr': 'fr_core_news_lg',     # French
    'de': 'de_core_news_lg',     # German
    'pt': 'pt_core_news_lg',     # Portuguese
    'nl': 'nl_core_news_lg',     # Dutch
    'el': 'el_core_news_lg',     # Greek
    'pl': 'pl_core_news_lg',     # Polish
    'ro': 'ro_core_news_lg',     # Romanian
}

# Optional transformer models (better accuracy, heavier: needs
# ``pip install spacy-transformers`` and a GPU is recommended).
LANGUAGE_MODELS_TRF = {
    'en': 'en_core_web_trf',
    'it': 'it_core_news_lg',      # no official _trf for Italian yet
    'es': 'es_dep_news_trf',
    'fr': 'fr_dep_news_trf',
    'de': 'de_dep_news_trf',
}

DEFAULT_NER_LABELS = ("GPE", "LOC", "FAC")

# spaCy pipeline components we never need for toponym extraction. Removing them
# makes model loading and inference noticeably faster and lighter; ``ner`` still
# works because it listens to the shared ``tok2vec``. Names not present in a
# given pipeline are simply ignored by ``spacy.load``.
_DISABLED_PIPES = [
    "tagger", "parser", "lemmatizer", "trainable_lemmatizer",
    "attribute_ruler", "morphologizer", "senter",
]


class GeoNamesError(Exception):
    """Base class for expected, user-facing errors raised by this module."""


class MissingDependency(GeoNamesError):
    """A required third-party package is not installed."""


class ModelNotAvailable(GeoNamesError):
    """No usable spaCy model could be loaded for the requested language."""


# --------------------------------------------------------------------------- #
# Page ranges
# --------------------------------------------------------------------------- #

def parse_page_ranges(page_spec, max_pages: Optional[int] = None):
    """Parse a page specification into a set of 0-indexed page numbers.

    Args:
        page_spec: String such as ``"5"``, ``"5-10"`` or ``"5-10, 12-14"``.
            Page numbers are 1-indexed (user facing). ``None``/empty means
            "all pages".
        max_pages: If given, the total number of pages in the document. Any
            requested page above this value raises ``ValueError`` instead of
            being silently dropped later.

    Returns:
        A set of 0-indexed page indices, or ``None`` for "all pages".

    Raises:
        ValueError: if the specification is malformed or out of bounds.
    """
    if not page_spec or not page_spec.strip():
        return None

    def _page(token: str) -> int:
        token = token.strip()
        if not token.isdigit():
            raise ValueError(f"'{token}' is not a positive page number")
        value = int(token)
        if value < 1:
            raise ValueError(f"page numbers start at 1, got {value}")
        if max_pages is not None and value > max_pages:
            raise ValueError(
                f"page {value} is out of range (document has {max_pages} pages)"
            )
        return value - 1  # 0-indexed

    pages: set[int] = set()
    try:
        for part in page_spec.split(','):
            part = part.strip()
            if not part:
                continue
            if '-' in part:
                start, _, end = part.partition('-')
                start_idx, end_idx = _page(start), _page(end)
                if start_idx > end_idx:
                    raise ValueError(f"range '{part}' starts after it ends")
                pages.update(range(start_idx, end_idx + 1))
            else:
                pages.add(_page(part))
    except ValueError as exc:
        raise ValueError(f"invalid page specification '{page_spec}': {exc}") from exc

    if not pages:
        return None
    return pages


# --------------------------------------------------------------------------- #
# PDF text extraction
# --------------------------------------------------------------------------- #

@dataclass
class PdfPage:
    """A single extracted page. ``number`` is 1-indexed (user facing)."""

    number: int
    text: str


def _open_document(source):
    """Open a PDF from a filesystem path or from an in-memory byte string.

    Args:
        source: a path (``str`` / ``os.PathLike``) or the raw PDF bytes
            (``bytes`` / ``bytearray`` / ``memoryview``).

    Raises:
        MissingDependency: if PyMuPDF is not installed.
        FileNotFoundError: if ``source`` is a path that does not exist.
        TypeError: if ``source`` is neither a path nor bytes.
    """
    try:
        import pymupdf
    except ImportError as exc:  # pragma: no cover - exercised only without deps
        raise MissingDependency(
            "PyMuPDF is required to read PDF files (pip install PyMuPDF)"
        ) from exc

    import os
    if isinstance(source, (str, os.PathLike)):
        if not os.path.isfile(source):
            # PyMuPDF raises its own RuntimeError subclass here; normalise it to
            # the builtin so callers can rely on one well-known exception type.
            raise FileNotFoundError(source)
        return pymupdf.open(source)
    if isinstance(source, (bytes, bytearray, memoryview)):
        return pymupdf.open(stream=bytes(source), filetype="pdf")
    raise TypeError(f"unsupported PDF source type: {type(source).__name__}")


def _pages_from_doc(doc, page_ranges):
    """Pull the wanted pages out of an already-open PyMuPDF document."""
    pages: list[PdfPage] = []
    skipped: list[int] = []
    total = len(doc)
    wanted = range(total) if page_ranges is None else sorted(set(page_ranges))
    for idx in wanted:
        if idx < 0 or idx >= total:
            skipped.append(idx + 1)
            continue
        text = doc[idx].get_text()
        if text and text.strip():
            pages.append(PdfPage(number=idx + 1, text=text))
    return pages, skipped


def extract_pages(source, page_ranges: Optional[Iterable[int]] = None):
    """Extract text from a PDF, page by page.

    Args:
        source: path to the PDF file, or the raw PDF bytes.
        page_ranges: Iterable of 0-indexed page indices to keep, or ``None``
            for every page.

    Returns:
        ``(pages, skipped)`` where ``pages`` is a list of :class:`PdfPage`
        (only non-empty pages are kept) and ``skipped`` is a sorted list of
        1-indexed page numbers that were requested but do not exist.

    Raises:
        MissingDependency: if PyMuPDF is not installed.
        FileNotFoundError: if ``source`` is a path that does not exist.
    """
    doc = _open_document(source)
    try:
        return _pages_from_doc(doc, page_ranges)
    finally:
        doc.close()


# --------------------------------------------------------------------------- #
# Language detection
# --------------------------------------------------------------------------- #

def detect_language(text: str, default: str = "en") -> str:
    """Best-effort language detection for a block of text.

    Uses ``langdetect`` with a fixed seed for reproducibility. Returns
    ``default`` when the library is missing, the sample is too short, or
    detection fails. Note: ``langdetect`` has no model for Latin, Ancient
    Greek, etc. -- for historical documents pass an explicit language instead.
    """
    try:
        from langdetect import detect, DetectorFactory
    except ImportError:
        return default

    DetectorFactory.seed = 0
    sample = (text or "")[:2000].strip()
    if len(sample) < 50:
        return default
    try:
        return detect(sample)
    except Exception:
        return default


# --------------------------------------------------------------------------- #
# Extraction engines (all offline, no external services)
# --------------------------------------------------------------------------- #

_NLP_CACHE: dict[tuple, object] = {}


def load_nlp(language_code: str, *, prefer: str = "lg", fallback: bool = True):
    """Load and cache a NER-only spaCy pipeline for ``language_code``.

    Args:
        language_code: e.g. ``"en"``, ``"it"``.
        prefer: ``"lg"`` for the default CNN model, ``"trf"`` for the
            transformer variant (requires ``spacy-transformers``).
        fallback: if the requested model is missing, fall back to the English
            model rather than raising.

    Returns:
        A loaded ``spacy.Language`` object with only ``tok2vec`` + ``ner``.

    Raises:
        MissingDependency: if spaCy itself is not installed.
        ModelNotAvailable: if no model could be loaded.
    """
    cache_key = (language_code, prefer)
    if cache_key in _NLP_CACHE:
        return _NLP_CACHE[cache_key]

    try:
        import spacy
    except ImportError as exc:  # pragma: no cover
        raise MissingDependency(
            "spaCy is required for NER extraction (pip install spacy)"
        ) from exc

    table = LANGUAGE_MODELS_TRF if prefer == "trf" else LANGUAGE_MODELS
    model_name = table.get(language_code) or LANGUAGE_MODELS.get(language_code)

    candidates = []
    if model_name:
        candidates.append(model_name)
    if fallback and LANGUAGE_MODELS["en"] not in candidates:
        candidates.append(LANGUAGE_MODELS["en"])

    last_error: Optional[Exception] = None
    for name in candidates:
        try:
            nlp = spacy.load(name, exclude=_DISABLED_PIPES)
            _NLP_CACHE[cache_key] = nlp
            return nlp
        except OSError as exc:  # model not downloaded
            last_error = exc

    raise ModelNotAvailable(
        f"No spaCy model available for language '{language_code}'. "
        f"Install one with:  python -m spacy download "
        f"{model_name or LANGUAGE_MODELS['en']}"
    ) from last_error


def _build_gliner(language_code: str, labels):
    """Build a blank spaCy pipeline with a GLiNER component (optional engine)."""
    try:
        import spacy
        import gliner_spacy  # noqa: F401  (registers the factory)
    except ImportError as exc:
        raise MissingDependency(
            "The 'gliner' engine needs extra packages:  "
            "pip install gliner gliner-spacy"
        ) from exc

    nlp = spacy.blank(language_code if language_code in LANGUAGE_MODELS else "xx")
    nlp.add_pipe(
        "gliner_spacy",
        config={
            "gliner_model": "urchade/gliner_multi-v2.1",
            "labels": list(labels),
            "style": "ent",
        },
    )
    return nlp


def get_engine(engine: str, language_code: str, labels=DEFAULT_NER_LABELS):
    """Return a callable pipeline for the requested extraction ``engine``.

    ``"spacy"`` (default) and ``"spacy-trf"`` use the spaCy models; ``"gliner"``
    uses a local GLiNER model driven by ``labels``. All run fully offline.
    """
    if engine in ("spacy", "spacy-lg"):
        return load_nlp(language_code, prefer="lg")
    if engine in ("spacy-trf", "trf"):
        return load_nlp(language_code, prefer="trf")
    if engine == "gliner":
        return _build_gliner(language_code, labels)
    raise GeoNamesError(f"unknown extraction engine '{engine}'")


# --------------------------------------------------------------------------- #
# Result model
# --------------------------------------------------------------------------- #

@dataclass
class Toponym:
    """A place name found in the document, with provenance and (optionally) geo."""

    name: str
    label: str = ""
    count: int = 0
    pages: set[int] = field(default_factory=set)
    sources: set[str] = field(default_factory=set)
    gazetteer_id: str = ""
    lat: Optional[float] = None
    lon: Optional[float] = None

    def add_hit(self, page: Optional[int], source: str, label: str = "") -> None:
        self.count += 1
        if page is not None:
            self.pages.add(page)
        if source:
            self.sources.add(source)
        if label and not self.label:
            self.label = label

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "label": self.label,
            "count": self.count,
            "pages": sorted(self.pages),
            "sources": sorted(self.sources),
            "gazetteer_id": self.gazetteer_id,
            "lat": self.lat,
            "lon": self.lon,
        }


@dataclass
class AnalysisResult:
    """Everything a caller needs after :func:`analyze`."""

    pdf_path: str = ""
    language: str = ""
    model: str = ""
    engine: str = "spacy"
    toponyms: list[Toponym] = field(default_factory=list)
    pages_processed: list[int] = field(default_factory=list)
    pages_skipped: list[int] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def names(self) -> list[str]:
        return [t.name for t in self.toponyms]


# --------------------------------------------------------------------------- #
# NER extraction
# --------------------------------------------------------------------------- #

def _key(name: str) -> str:
    return name.strip().casefold()


def extract_ner(pages: list[PdfPage], nlp, labels=DEFAULT_NER_LABELS,
                into: Optional[dict] = None) -> dict:
    """Run the NER pipeline page by page and accumulate :class:`Toponym` hits.

    Args:
        pages: list of :class:`PdfPage`.
        nlp: a loaded spaCy (or GLiNER-backed) pipeline.
        labels: entity labels to keep; ``None`` keeps every entity.
        into: an existing ``{key: Toponym}`` dict to merge into.

    Returns:
        A dict mapping ``casefold(name) -> Toponym``.
    """
    found = into if into is not None else {}
    keep = set(labels) if labels else None

    # Raise the length guard: we still feed one page at a time, but a single
    # dense page can occasionally approach the default 1,000,000 char limit.
    try:
        nlp.max_length = max(getattr(nlp, "max_length", 1_000_000),
                             max((len(p.text) for p in pages), default=0) + 1000)
    except Exception:
        pass

    texts = [p.text for p in pages]
    for page, doc in zip(pages, nlp.pipe(texts)):
        for ent in doc.ents:
            if keep is not None and ent.label_ not in keep:
                continue
            name = " ".join(ent.text.split())  # collapse whitespace/newlines
            if not name:
                continue
            entry = found.setdefault(_key(name), Toponym(name=name))
            entry.add_hit(page.number, f"ner:{ent.label_}", ent.label_)
    return found


# --------------------------------------------------------------------------- #
# Gazetteer
# --------------------------------------------------------------------------- #

@dataclass
class GazEntry:
    name: str
    label: str = ""
    id: str = ""
    lat: Optional[float] = None
    lon: Optional[float] = None


_HEADER_HINTS = {
    "name", "toponym", "title", "place", "placename", "label", "type",
    "id", "pleiades_id", "geonameid", "uri",
    "lat", "latitude", "lon", "lng", "long", "longitude",
}


def _to_float(value: str) -> Optional[float]:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def load_gazetteer(path) -> list[GazEntry]:
    """Load a gazetteer file into a list of :class:`GazEntry`.

    Supported formats:

    * ``.txt`` -- one place name per line.
    * ``.csv`` / ``.tsv`` -- delimited. If the first row looks like a header,
      columns named (case-insensitively) ``name``/``toponym``/``title``,
      ``label``/``type``, ``id``/``uri``, ``lat``/``latitude`` and
      ``lon``/``longitude`` are used; otherwise the first column is the name.

    Duplicate names (case-insensitive) keep their first occurrence.
    """
    import os

    entries: list[GazEntry] = []
    seen: set[str] = set()
    ext = os.path.splitext(str(path))[1].lower()

    def _add(name, label="", _id="", lat=None, lon=None):
        name = (name or "").strip()
        if not name:
            return
        k = name.casefold()
        if k in seen:
            return
        seen.add(k)
        entries.append(GazEntry(name=name, label=(label or "").strip(),
                                id=(_id or "").strip(), lat=lat, lon=lon))

    with open(path, "r", encoding="utf-8", newline="") as handle:
        if ext in (".csv", ".tsv"):
            delimiter = "\t" if ext == ".tsv" else None
            sample = handle.read(4096)
            handle.seek(0)
            if delimiter is None:
                try:
                    delimiter = csv.Sniffer().sniff(sample, ",;\t").delimiter
                except csv.Error:
                    delimiter = ","
            reader = csv.reader(handle, delimiter=delimiter)
            rows = list(reader)
            if not rows:
                return entries
            first = [c.strip().lower() for c in rows[0]]
            has_header = any(c in _HEADER_HINTS for c in first)
            if has_header:
                def col(*names):
                    for n in names:
                        if n in first:
                            return first.index(n)
                    return None
                i_name = col("name", "toponym", "title", "place", "placename") or 0
                i_label = col("label", "type")
                i_id = col("id", "uri", "pleiades_id", "geonameid")
                i_lat = col("lat", "latitude")
                i_lon = col("lon", "lng", "long", "longitude")
                data = rows[1:]
            else:
                i_name, i_label, i_id, i_lat, i_lon = 0, None, None, None, None
                data = rows
            for row in data:
                if not row:
                    continue
                def get(i):
                    return row[i] if i is not None and i < len(row) else ""
                _add(get(i_name), get(i_label), get(i_id),
                     _to_float(get(i_lat)), _to_float(get(i_lon)))
        else:  # .txt / anything else: one name per line
            for line in handle:
                _add(line)
    return entries


class GazetteerMatcher:
    """Single-pass, word-boundary, case-insensitive gazetteer matcher.

    All entries are compiled into one alternation, so matching cost is roughly
    O(text length) regardless of gazetteer size. Multi-word entries are
    supported and the longest match wins. Matched text is reported using the
    gazetteer's canonical spelling.
    """

    def __init__(self, entries: Iterable[GazEntry]):
        self._by_key: dict[str, GazEntry] = {}
        for entry in entries:
            if entry.name:
                self._by_key.setdefault(entry.name.casefold(), entry)
        self._regex = self._compile(self._by_key)

    @staticmethod
    def _compile(by_key: dict[str, GazEntry]):
        if not by_key:
            return None
        # Longest first so "Çuka e Ajtoit" wins over a bare "Çuka".
        names = sorted((e.name for e in by_key.values()), key=len, reverse=True)
        alternation = "|".join(re.escape(n) for n in names)
        return re.compile(rf"(?<!\w)(?:{alternation})(?!\w)",
                          re.IGNORECASE | re.UNICODE)

    def __bool__(self) -> bool:
        return self._regex is not None

    def find(self, pages: list[PdfPage], into: Optional[dict] = None) -> dict:
        """Accumulate gazetteer hits over ``pages`` into a ``{key: Toponym}`` dict."""
        found = into if into is not None else {}
        if self._regex is None:
            return found
        for page in pages:
            for match in self._regex.finditer(page.text):
                entry = self._by_key[match.group(0).casefold()]
                topo = found.get(_key(entry.name))
                if topo is None:
                    topo = Toponym(name=entry.name, label=entry.label,
                                   gazetteer_id=entry.id,
                                   lat=entry.lat, lon=entry.lon)
                    found[_key(entry.name)] = topo
                else:
                    # NER saw it first: enrich with gazetteer metadata.
                    topo.gazetteer_id = topo.gazetteer_id or entry.id
                    if topo.lat is None:
                        topo.lat, topo.lon = entry.lat, entry.lon
                    if not topo.label:
                        topo.label = entry.label
                topo.add_hit(page.number, "gazetteer")
        return found


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #

def analyze(source, *, language: Optional[str] = None,
            pages: Optional[str] = None, gazetteer=None,
            exclude: Optional[Iterable[str]] = None,
            engine: str = "spacy", use_ner: bool = True,
            labels=DEFAULT_NER_LABELS,
            source_name: Optional[str] = None) -> AnalysisResult:
    """Run the full extraction pipeline on a single PDF.

    Args:
        source: path to the PDF file, or the raw PDF bytes.
        language: force a language code; ``None`` auto-detects.
        pages: page specification string (see :func:`parse_page_ranges`).
        gazetteer: path to a gazetteer file, a pre-loaded list of
            :class:`GazEntry`, or ``None``.
        exclude: iterable of place names to drop from the results
            (case-insensitive).
        engine: ``"spacy"``, ``"spacy-trf"`` or ``"gliner"``.
        use_ner: set to ``False`` for gazetteer-only extraction (no model
            download or language detection needed).
        labels: entity labels to keep (spaCy) / to ask for (GLiNER).
        source_name: label for the result / logs when ``source`` is bytes.

    Returns:
        An :class:`AnalysisResult`.
    """
    import os
    if source_name:
        display = source_name
    elif isinstance(source, (str, os.PathLike)):
        display = str(source)
    else:
        display = "<pdf bytes>"
    result = AnalysisResult(pdf_path=display, engine=engine)

    # -- open once, read the wanted pages -------------------------------- #
    doc = _open_document(source)  # FileNotFoundError / MissingDependency / TypeError
    try:
        total_pages = len(doc)
        page_ranges = (parse_page_ranges(pages, max_pages=total_pages)
                       if pages else None)
        pdf_pages, skipped = _pages_from_doc(doc, page_ranges)
    finally:
        doc.close()
    result.pages_processed = [p.number for p in pdf_pages]
    result.pages_skipped = skipped
    if skipped:
        result.warnings.append(
            f"{len(skipped)} requested page(s) do not exist and were ignored: "
            f"{', '.join(map(str, skipped))}"
        )
    if not pdf_pages:
        result.warnings.append("no extractable text found (scanned PDF?)")
        return result

    full_text = "\n".join(p.text for p in pdf_pages)

    gaz_entries = None
    if gazetteer is not None:
        gaz_entries = (gazetteer if isinstance(gazetteer, list)
                       else load_gazetteer(gazetteer))

    if not use_ner and gaz_entries is None:
        raise GeoNamesError(
            "nothing to do: NER is disabled and no gazetteer was provided"
        )

    found: dict[str, Toponym] = {}

    if use_ner:
        result.language = language.lower() if language else detect_language(full_text)
        nlp = get_engine(engine, result.language, labels)
        try:
            result.model = f"{nlp.meta['name']} v{nlp.meta['version']}"
        except Exception:
            result.model = engine
        extract_ner(pdf_pages, nlp, labels, into=found)
    elif language:
        result.language = language.lower()

    if gaz_entries is not None:
        GazetteerMatcher(gaz_entries).find(pdf_pages, into=found)

    exclude_keys = {_key(x) for x in exclude} if exclude else set()
    result.toponyms = sorted(
        (t for k, t in found.items() if k not in exclude_keys),
        key=lambda t: t.name.casefold(),
    )
    return result


# --------------------------------------------------------------------------- #
# Serializers
# --------------------------------------------------------------------------- #

def to_txt(result: AnalysisResult, *, details: bool = False) -> str:
    """Plain-text list (the historical output format)."""
    lines = []
    for t in result.toponyms:
        if details:
            pg = ",".join(map(str, sorted(t.pages))) or "-"
            extra = f"  [{t.label or '?'}; x{t.count}; p.{pg}]"
            if t.lat is not None:
                extra += f"  ({t.lat:.4f}, {t.lon:.4f})"
            lines.append(f"- {t.name}{extra}")
        else:
            lines.append(f"- {t.name}")
    return "\n".join(lines)


def to_csv(result: AnalysisResult) -> str:
    import io
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["name", "label", "count", "pages", "sources",
                     "gazetteer_id", "lat", "lon"])
    for t in result.toponyms:
        writer.writerow([
            t.name, t.label, t.count,
            ";".join(map(str, sorted(t.pages))),
            ";".join(sorted(t.sources)),
            t.gazetteer_id,
            "" if t.lat is None else t.lat,
            "" if t.lon is None else t.lon,
        ])
    return buf.getvalue()


def to_json(result: AnalysisResult, *, indent: int = 2) -> str:
    payload = {
        "pdf": result.pdf_path,
        "language": result.language,
        "model": result.model,
        "engine": result.engine,
        "pages_processed": result.pages_processed,
        "pages_skipped": result.pages_skipped,
        "warnings": result.warnings,
        "count": len(result.toponyms),
        "toponyms": [t.as_dict() for t in result.toponyms],
    }
    return json.dumps(payload, ensure_ascii=False, indent=indent)


def to_geojson(result: AnalysisResult, *, indent: int = 2) -> str:
    features = []
    for t in result.toponyms:
        if t.lat is None or t.lon is None:
            continue
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [t.lon, t.lat]},
            "properties": {
                "name": t.name, "label": t.label, "count": t.count,
                "pages": sorted(t.pages), "sources": sorted(t.sources),
                "gazetteer_id": t.gazetteer_id,
            },
        })
    return json.dumps({"type": "FeatureCollection", "features": features},
                      ensure_ascii=False, indent=indent)


SERIALIZERS = {
    "txt": to_txt,
    "csv": to_csv,
    "json": to_json,
    "geojson": to_geojson,
}


def serialize(result: AnalysisResult, fmt: str) -> str:
    try:
        return SERIALIZERS[fmt](result)
    except KeyError:
        raise GeoNamesError(
            f"unknown output format '{fmt}' (choose from: "
            f"{', '.join(SERIALIZERS)})"
        )

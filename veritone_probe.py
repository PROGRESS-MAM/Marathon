# --------- IMPORTS ---------
import configparser
import json
import re
import time
import traceback
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

# --------- STATIC ---------
token_keys = ("vt_api_token", "api_key", "apiKey", "token", "access_token")
pair_name_keys = ("name", "fieldName")
pair_value_keys = ("value", "values")
deep_offset = 10000  # common result window limit of search engines

# --------- CONFIG ---------
app_name = "Veritone-Probe"
app_version = "0.4"
project_dir = Path(__file__).resolve().parent
res_dir = project_dir / "res"
probe_dir = project_dir / "probe"
raw_dir = probe_dir / "raw"
timeout = 120
# Web search: /search;sortId=913;filterIds=10196,10236 (Source DEFA, Genre Dokumentarfilm)
sort_id = 913
filter_ids = "10196,10236"
barcode_field = "Supplier.Barcode"
sample_size = 10
full_details = 3
max_page_size = 200
value_width = 120


# --------- FUNC: SETTINGS ---------
def _read_token(path: Path) -> str:
    if not path.is_file():
        raise SystemExit(f"Zugangsdatei {path} fehlt.")
    text = path.read_text(encoding="utf-8-sig").strip()
    if text.startswith("{"):
        try:
            values = json.loads(text)
        except ValueError as exc:
            raise SystemExit(f"{path}: kein gültiges JSON ({exc}).") from None
        if not isinstance(values, dict):
            raise SystemExit(f"{path}: JSON muss ein Objekt sein.")
    else:
        values = {}
        for line in text.splitlines():
            key, separator, value = line.strip().removeprefix("export ").partition("=")
            if separator:
                values.setdefault(key.strip(), value.strip().strip("\"'"))
    token = next((str(values[key]).strip() for key in token_keys if str(values.get(key) or "").strip()), "")
    if not token:
        raise SystemExit(f"{path}: keiner der Einträge {', '.join(token_keys)} vorhanden oder alle leer.")
    return token


def _load_settings() -> tuple[str, str]:
    config_path = res_dir / "config.ini"
    if not config_path.is_file():
        raise SystemExit(f"{config_path} fehlt.")
    parser = configparser.ConfigParser(interpolation=None)
    parser.read(config_path, encoding="utf-8-sig")
    values = {key: parser.get("veritone", key, fallback="").strip() for key in ("base_url", "token_file")}
    missing = [key for key, value in values.items() if not value]
    if missing:
        raise SystemExit(f"{config_path}: [veritone] {', '.join(missing)} fehlt oder ist leer.")
    return values["base_url"].rstrip("/"), _read_token(res_dir / values["token_file"])


# --------- FUNC: API ---------
class Api:
    """Read-only GET client for the Assets API; records every call without the token."""

    def __init__(self, base_url: str, token: str):
        self.base_url, self.token, self.calls, self.files = base_url, token, [], []

    def mask(self, text: str) -> str:
        for secret in {self.token, quote(self.token, safe="")}:
            text = text.replace(secret, "***")
        return text

    def get(self, name: str, path: str, params: dict | None = None):
        """Returns (status, parsed JSON or text, raw file name, ms). Status 0 = not reachable."""
        params = {key: value for key, value in (params or {}).items() if value is not None}
        # Never print or store the URL, it contains the token.
        url = f"{self.base_url}{path}?{urlencode({**params, 'api_key': self.token})}"
        started = time.monotonic()
        try:
            with urlopen(Request(url, headers={"Accept": "application/json"}), timeout=timeout) as response:
                status, raw = response.status, response.read()
        except HTTPError as exc:
            status, raw = exc.code, exc.read()
        except (URLError, OSError) as exc:
            status, raw = 0, str(exc).encode("utf-8")
        ms = round((time.monotonic() - started) * 1000)
        text = self.mask(raw.decode("utf-8", "replace"))
        try:
            data = json.loads(text)
        except ValueError:
            data = text
        file = self._save(name, {"request": {"path": path, "params": params}, "status": status, "ms": ms, "response": data})
        self.calls.append((path, params, status, ms, file))
        return status, data, file, ms

    def _save(self, name: str, data) -> str:
        raw_dir.mkdir(parents=True, exist_ok=True)
        safe_name = re.sub(r"[^\w-]+", "_", name)[:80]
        file_name = f"{len(self.files) + 1:03d}_{safe_name}.json"
        (raw_dir / file_name).write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        self.files.append(file_name)
        return file_name


# --------- FUNC: ANALYSIS ---------
def _leaves(data, path: str = "", field: str = ""):
    """Yield (path, field, value) for every scalar; name/value pairs yield the pair name as field and path <name>."""
    if isinstance(data, dict):
        name_key = next((key for key in pair_name_keys if isinstance(data.get(key), str)), None)
        value_key = next((key for key in pair_value_keys if key in data), None)
        values = data.get(value_key) if value_key else None
        values = values if isinstance(values, list) else [values]
        skip = set()
        if name_key and value_key and not any(isinstance(value, (dict, list)) for value in values):
            skip = {name_key, value_key}
            for value in values:
                yield f"{path}<{data[name_key]}>", data[name_key], value
        for key, value in data.items():
            if key not in skip:
                yield from _leaves(value, f"{path}.{key}" if path else str(key), str(key))
    elif isinstance(data, list):
        for index, value in enumerate(data):
            yield from _leaves(value, f"{path}[{index}]", field)
    else:
        yield path, field, data


def _field_values(data, field: str) -> list[str]:
    return list(dict.fromkeys(str(value).strip() for _, name, value in _leaves(data) if name == field and str(value or "").strip()))


def _items(data) -> list:
    items = data.get("items") if isinstance(data, dict) else None
    return items if isinstance(items, list) else []


def _clips(data) -> list:
    """Clip objects of a byIds or clip response."""
    if isinstance(data, dict) and isinstance(data.get("list"), list):
        return data["list"]
    if isinstance(data, list):
        return data
    return [data] if isinstance(data, dict) and "id" in data else []


def _asset_id(item) -> str | None:
    return next((str(item[key]) for key in ("assetId", "id", "clipId") if isinstance(item, dict) and item.get(key) is not None), None)


def _title(item) -> str:
    values = {field.casefold(): str(value) for _, field, value in _leaves(item) if field.casefold() in ("title", "name") and value}
    return values.get("title") or values.get("name", "")


def _total(data):
    return data.get("totalCount") if isinstance(data, dict) else None


def _page_info(data) -> dict:
    return {key: data.get(key) for key in ("currentPage", "pageSize", "numberOfPages", "hasNextPage")} if isinstance(data, dict) else {}


# --------- FUNC: REPORT ---------
def _short(value, width: int = value_width) -> str:
    text = " ".join((value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)).split())
    return text if len(text) <= width else text[:width - 1] + "…"


def _cell(value) -> str:
    return "–" if value is None or value == "" or value == [] else _short(value).replace("|", "\\|")


class Report:
    def __init__(self, mask):
        self.mask, self.head, self.sections = mask, [], []

    def section(self, title: str) -> None:
        self.sections.append({"title": title, "status": "", "lines": []})

    def line(self, text: str = "") -> None:
        self.sections[-1]["lines"].append(self.mask(str(text)))

    def table(self, headers: tuple, rows: list) -> None:
        if not rows:
            return self.line("_(keine Einträge)_\n")
        self.line()
        self.line("| " + " | ".join(headers) + " |")
        self.line("|" + "---|" * len(headers))
        for row in rows:
            self.line("| " + " | ".join(_cell(value) for value in row) + " |")
        self.line()

    def render(self) -> str:
        overview = [f"- {number}. {section['title']}: **{section['status']}**"
                    for number, section in enumerate(self.sections, 1) if section["status"]]
        parts = [*self.head, "", "**Übersicht**", "", *overview]
        for number, section in enumerate(self.sections, 1):
            status = f" – {section['status']}" if section["status"] else ""
            parts += ["", f"## {number}. {section['title']}{status}", "", *section["lines"]]
        return "\n".join(parts) + "\n"


class Skip(Exception):
    """Step cannot run because a prerequisite is missing."""


# --------- FUNC: PROBE ---------
class Probe:
    def __init__(self, api: Api, base_url: str):
        self.api, self.out = api, Report(api.mask)
        self.out.head = [f"# {app_name} {app_version} – Report", "", f"- Zeitpunkt: {datetime.now():%Y-%m-%d %H:%M:%S}",
                         f"- base_url: {base_url}", f"- Websuche: /search;sortId={sort_id};filterIds={filter_ids}",
                         f"- API-Abfrage: GET /v1/search?sortId={sort_id}&filterIds={filter_ids}", f"- Identifier-Feld: {barcode_field}"]
        self.params = {"q": "", "sortId": sort_id, "filterIds": filter_ids}
        self.total, self.sample, self.barcodes, self.path, self.paging = None, [], {}, None, "nicht geprüft"

    def _search(self, name: str, size: int, page: int = 0, **params):
        return self.api.get(name, "/v1/search", {**self.params, **params, "n": size, "i": page})

    def step_search(self) -> str:
        status, data, file, ms = self._search("search_filter", sample_size)
        self.total, items = _total(data), _items(data) if status == 200 else []
        self.out.line(f"HTTP {status}, totalCount={self.total}, {len(items)} Treffer auf Seite 0, {ms} ms ({file})")
        if status != 200:
            self.out.line(f"Fehler: {_short(data, 300)}")
            return "FEHLER"
        self.out.line(f"Seitenfelder: {', '.join(key for key in data if key != 'items')}; Seiteninfo: {_page_info(data)}")
        self.sample = [(asset_id, item) for item in items if (asset_id := _asset_id(item))]
        self.out.table(("#", "assetId", "Titel"), [(number, asset_id, _title(item)) for number, (asset_id, item) in enumerate(self.sample, 1)])
        rows = []
        for label, params in (("ohne sortId", {"sortId": None}), *((f"nur filterIds={part}", {"filterIds": part}) for part in filter_ids.split(",")),
                              ("ohne Filter", {"filterIds": None, "sortId": None})):
            code, page, file, _ = self._search(f"count_{label}", 1, **params)
            rows.append((label, code, _total(page), file))
        self.out.line("Vergleich der Trefferzahl (n=1):")
        self.out.table(("Variante", "HTTP", "totalCount", "Rohdaten"), rows)
        return "OK" if self.sample else "UNKLAR"

    def step_hit_fields(self) -> str:
        if not self.sample:
            raise Skip("Keine Suchtreffer (siehe Schritt 1).")
        fields = list(dict.fromkeys(field for _, item in self.sample for _, field, _ in _leaves(item)))
        rows = [(asset_id, _field_values(item, barcode_field)) for asset_id, item in self.sample]
        self.out.line(f"Felder in den Suchtreffern: {', '.join(fields)}")
        self.out.table(("assetId", barcode_field), rows)
        found = sum(bool(values) for _, values in rows)
        self.out.line(f"{barcode_field} in {found} von {len(rows)} Suchtreffern.")
        if found == len(rows):
            self.barcodes["Suchtreffer"] = dict(rows)
            self.path = self.path or "Suchtreffer"
        return "OK" if found == len(rows) else "UNKLAR"

    def step_clip_fields(self) -> str:
        if not self.sample:
            raise Skip("Keine Suchtreffer (siehe Schritt 1).")
        ids = [asset_id for asset_id, _ in self.sample]
        first = ids[0]
        requests = (("byIds+fields", "/v1/clip/byIds", {"ids": ",".join(ids), "fields": barcode_field}),
                    ("byIds", "/v1/clip/byIds", {"ids": ",".join(ids[:full_details])}),
                    ("clip+fields", f"/v1/clip/{first}", {"fields": barcode_field}),
                    ("clip", f"/v1/clip/{first}", None))
        rows, results = [], {}
        for label, path, params in requests:
            status, data, file, ms = self.api.get(f"barcode_{label}", path, params)
            clips = _clips(data) if status == 200 else []
            found = {str(clip.get("id")): _field_values(clip, barcode_field) for clip in clips if isinstance(clip, dict)}
            results[label] = found
            asked = len(params["ids"].split(",")) if params and "ids" in params else 1
            fields = len(list(_leaves(clips[0]))) if clips else 0
            rows.append((label, path, status, asked, len(clips), sum(bool(values) for values in found.values()), fields, ms,
                         "" if status == 200 else _short(data, 100), file))
        self.out.table(("Abfrage", "Pfad", "HTTP", "IDs angefragt", "Clips erhalten", "mit Barcode", "Felder je Clip", "ms", "Fehler", "Rohdaten"), rows)
        self.out.line("Barcode je Clip:")
        self.out.table(("assetId", *results), [(asset_id, *(results[label].get(asset_id) for label in results)) for asset_id in ids])
        for label, path, params in requests:
            asked = params["ids"].split(",") if params and "ids" in params else [first]
            if asked and all(results[label].get(asset_id) for asset_id in asked):
                self.barcodes[label] = results[label]
                self.path = self.path or label
        self.out.line(f"Erster vollständiger Pfad: **{self.path or 'keiner'}**")
        return "OK" if self.path else "FEHLER"

    def step_bulk(self) -> str:
        if self.path != "byIds+fields":
            raise Skip("Nur nötig, wenn der Barcode über byIds+fields kommt.")
        status, data, file, ms = self._search("search_max_page", max_page_size)
        ids = [asset_id for item in _items(data) if (asset_id := _asset_id(item))] if status == 200 else []
        self.out.line(f"Suche n={max_page_size}: HTTP {status}, {len(ids)} assetIds, {ms} ms ({file})")
        if not ids:
            return "FEHLER"
        code, clips, file, ms = self.api.get("barcode_bulk", "/v1/clip/byIds", {"ids": ",".join(ids), "fields": barcode_field})
        found = [clip for clip in _clips(clips) if isinstance(clip, dict) and _field_values(clip, barcode_field)] if code == 200 else []
        self.out.line(f"byIds+fields mit {len(ids)} IDs: HTTP {code}, {len(_clips(clips)) if code == 200 else 0} Clips, "
                      f"{len(found)} mit Barcode, {ms} ms ({file})" + ("" if code == 200 else f"; Fehler: {_short(clips, 200)}"))
        return "OK" if len(found) == len(ids) else "UNKLAR"

    def step_paging(self) -> str:
        if not self.total:
            raise Skip("Keine Trefferzahl (siehe Schritt 1).")
        rows, pages = [], []
        for page in (0, 1):
            status, data, file, _ = self._search(f"paging_{page}", 5, page)
            ids = [_asset_id(item) for item in _items(data)]
            pages.append(ids)
            rows.append((f"i={page}, n=5", status, len(ids), ids, _page_info(data), file))
        last = (self.total - 1) // max_page_size
        checks = [("letzte Seite", last, self.total - last * max_page_size)]
        if self.total > deep_offset:
            checks.insert(0, (f"über {deep_offset}", deep_offset // max_page_size + 1, max_page_size))
        results = []
        for label, page, expected in checks:
            status, data, file, _ = self._search(f"paging_{label}", max_page_size, page)
            count = len(_items(data)) if status == 200 else 0
            results.append(count == expected)
            rows.append((f"{label}: i={page}, n={max_page_size} (erwartet {expected})", status, count, "", _page_info(data) or _short(data, 100), file))
        self.out.table(("Abfrage", "HTTP", "Treffer", "IDs", "Seiteninfo", "Rohdaten"), rows)
        distinct = bool(pages[0]) and not set(pages[0]) & set(pages[1])
        self.paging = f"i=0/i=1 überschneidungsfrei: {'ja' if distinct else 'nein'}; tiefe Seiten vollständig: {'ja' if all(results) else 'nein'}"
        self.out.line(f"**{self.paging}**")
        return "OK" if distinct and all(results) else "UNKLAR"

    def step_result(self) -> str:
        self.out.table(("Punkt", "Ergebnis"), [
            ("Websuche als API-Abfrage", f"/v1/search?sortId={sort_id}&filterIds={filter_ids}: totalCount={self.total}"),
            ("Barcode-Pfad", self.path or "nicht gefunden"), ("Blättern", self.paging),
            ("Beispiel", next(((asset_id, values) for asset_id, values in self.barcodes.get(self.path, {}).items()), None))])
        return "OK" if self.total and self.path else "UNKLAR"

    def appendix(self) -> None:
        self.out.section("Anhang: Aufrufe")
        self.out.table(("#", "Pfad", "Parameter", "HTTP", "ms", "Rohdaten"),
                       [(number, path, params, status, ms, file) for number, (path, params, status, ms, file) in enumerate(self.api.calls, 1)])

    def run(self) -> Path:
        steps = (("Suche mit Web-Filter", self.step_search), ("Barcode im Suchtreffer", self.step_hit_fields),
                 ("Barcode über Clip-Abfragen", self.step_clip_fields), ("Barcode in Masse", self.step_bulk),
                 ("Blättern", self.step_paging), ("Ergebnis", self.step_result))
        for number, (title, step) in enumerate(steps, 1):
            print(f"{number}/{len(steps)} {title} …", flush=True)
            self.out.section(title)
            try:
                status = step()
            except Skip as exc:
                status = "ÜBERSPRUNGEN"
                self.out.line(str(exc))
            except Exception as exc:
                status = "FEHLER"
                self.out.line(f"Unerwarteter Fehler: {type(exc).__name__}: {exc}")
                for line in ("~~~", *traceback.format_exc().splitlines(), "~~~"):
                    self.out.line(line)
            self.out.sections[-1]["status"] = status
            print(f"    {status}")
        self.appendix()
        probe_dir.mkdir(exist_ok=True)
        target = probe_dir / "report.md"
        target.write_text(self.out.render(), encoding="utf-8")
        return target


# --------- MAIN ---------
def main() -> None:
    base_url, token = _load_settings()
    print(f"{app_name} {app_version}: filterIds={filter_ids}, sortId={sort_id}")
    print(f"Report: {Probe(Api(base_url, token), base_url).run()}")


# --------- EXEC ---------
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        raise SystemExit("Abgebrochen.") from None

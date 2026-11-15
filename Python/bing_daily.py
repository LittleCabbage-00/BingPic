"""Fetch recent Bing wallpapers or update the repository's weekly gallery."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from html import escape
from io import BytesIO
import json
from pathlib import Path
import re
from tempfile import NamedTemporaryFile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request, urlopen

from PIL import Image


MARKETS = {"US": "US-en", "CN": "CN-zh", "JP": "JP-ja"}
TIERS = {"1080p": "1920x1080", "4k": "UHD"}
FIRST_UHD_DATE = date(2019, 5, 1)
DHASH_THRESHOLD = 12
BEIJING = timezone(timedelta(hours=8))
README = Path(__file__).resolve().parents[1] / "README.md"
GALLERY_ASSETS = Path("assets/bing-week")
GALLERY_DAYS = 7
DOWNLOAD_DAYS = 5
START = "<!-- bing-daily:start -->"
END = "<!-- bing-daily:end -->"


@dataclass(frozen=True)
class Picture:
    url: str
    data: bytes
    pixels: int
    fingerprint: tuple[bool, ...]


def fetch(url, limit=None):
    request = Request(url, headers={"User-Agent": "BingPic daily wallpaper"})
    for attempt in range(3):
        try:
            with urlopen(request, timeout=20) as response:
                return response.read() if limit is None else response.read(limit)
        except HTTPError as error:
            if error.code in (404, 410):
                return None
            if error.code not in (429, 500, 502, 503, 504) or attempt == 2:
                raise
        except (URLError, TimeoutError):
            if attempt == 2:
                raise
        time.sleep(2 ** attempt)


def recent_entries(days):
    months = sorted({day.strftime("%Y.%m") for day in days})
    wanted = {day.isoformat() for day in days}
    entries = {region: {} for region in MARKETS}
    for region, market in MARKETS.items():
        for month in months:
            url = f"https://bing.npanuhin.me/{market}.{month}.min.json"
            data = fetch(url)
            if data:
                entries[region].update(
                    (row["date"], row) for row in json.loads(data) if row["date"] in wanted
                )
    return entries


def is_uhd(size):
    return min(size) >= 2160 and max(size) >= 3840


def inspect_picture(data, tier, url=""):
    with Image.open(BytesIO(data), formats=["JPEG"]) as image:
        width, height = image.size
        if tier == "1080p" and image.size != (1920, 1080):
            return None
        if tier == "4k" and not is_uhd(image.size):
            return None

        # Match the 16×16 grayscale comparison in the Raspberry Pi deduplicator.
        image.draft("L", (16, 16))
        gray = image.convert("L").resize((16, 16)).tobytes()
    fingerprint = tuple(left > right for left, right in zip(gray[::2], gray[1::2]))
    return Picture(url, data, width * height, fingerprint)


def bing_image_url(entry, tier):
    if tier == "4k" and date.fromisoformat(entry["date"]) < FIRST_UHD_DATE:
        return None

    source = urlsplit(entry.get("bing_url") or "")
    image_id = parse_qs(source.query).get("id", [""])[0]
    match = re.fullmatch(r"(OHR\.[A-Za-z0-9_.-]+)_(?:UHD|1920x1080)\.jpg", image_id)
    if match:
        return f"https://www.bing.com/th?id={match[1]}_{TIERS[tier]}.jpg"
    return None


def fetch_picture(entry, tier):
    original = bing_image_url(entry, tier)
    urls = [original] if original else []
    if tier == "1080p":
        archive = urlsplit(entry["url"])
        if archive.scheme == "https" and archive.netloc == "bing.npanuhin.me":
            urls.append(archive.geturl())

    for url in urls:
        data = fetch(url)
        if data:
            picture = inspect_picture(data, tier, url)
            if picture:
                return picture
    return None


def is_duplicate(picture, baseline):
    return (
        baseline is not None
        and baseline.pixels >= picture.pixels
        and sum(a != b for a, b in zip(picture.fingerprint, baseline.fingerprint))
        <= DHASH_THRESHOLD
    )


def filename_prefix(day, tier, region):
    tag = "-4k" if tier == "4k" else ""
    return f"bing_pic_{day}{tag}_{region}_"


def title(entry):
    return entry.get("title") or entry.get("caption") or entry["date"]


def download(entries, days, output):
    for day in days:
        for tier in TIERS:
            baseline = None
            for region, rows in entries.items():
                folder = output / tier / region
                prefix = filename_prefix(day, tier, region)
                existing = min(folder.glob(f"{prefix}*.jpg"), default=None)
                if existing:
                    if region == "US":
                        baseline = inspect_picture(existing.read_bytes(), tier)
                    continue

                entry = rows.get(str(day))
                picture = fetch_picture(entry, tier) if entry else None
                if picture is None or is_duplicate(picture, baseline):
                    continue
                if region == "US":
                    baseline = picture

                safe_title = re.sub(r'[<>:"/\\|?*\x00-\x1f\s]+', "_", title(entry))
                path = folder / (prefix + safe_title[:72].rstrip(". ") + ".jpg")
                folder.mkdir(parents=True, exist_ok=True)
                pending = NamedTemporaryFile(dir=folder, suffix=".part", delete=False)
                temp_path = Path(pending.name)
                try:
                    with pending:
                        pending.write(picture.data)
                    temp_path.replace(path)
                finally:
                    temp_path.unlink(missing_ok=True)
                print(path)


def verified_uhd_url(entry):
    url = bing_image_url(entry, "4k")
    if url is None:
        return None
    data = fetch(url, limit=256 * 1024)
    if data is None:
        return None
    try:
        with Image.open(BytesIO(data), formats=["JPEG"]) as image:
            return url if is_uhd(image.size) else None
    except OSError:
        # A JPEG with a large metadata header may need more than the first chunk.
        picture = fetch_picture(entry, "4k")
        return picture.url if picture else None


def gallery_cell(entry, region, day, thumbnails):
    if entry is None:
        return "<td>暂未收录</td>"

    preview = fetch_picture(entry, "1080p")
    uhd = verified_uhd_url(entry)
    caption = escape(" ".join(title(entry).split()))
    parts = []
    if preview:
        thumbnail = BytesIO()
        with Image.open(BytesIO(preview.data)) as image:
            image.draft("RGB", (448, 252))
            image.thumbnail((448, 252), Image.Resampling.LANCZOS)
            image.convert("RGB").save(thumbnail, format="JPEG", quality=78, optimize=True)
        binary = thumbnail.getvalue()
        name = f"{sha256(binary).hexdigest()[:20]}.jpg"
        thumbnails[name] = binary
        parts.append(
            f'<a href="{escape(preview.url)}"><img src="{GALLERY_ASSETS.as_posix()}/{name}" '
            f'alt="{region} {day} · {caption}" width="224"></a>'
        )
    parts.append(caption)
    links = []
    if preview:
        links.append(f'<a href="{escape(preview.url)}">1080p</a>')
    if uhd:
        links.append(f'<a href="{escape(uhd)}">4K 原图</a>')
    if links:
        parts.append(" · ".join(links))
    if entry.get("copyright"):
        parts.append(f'<sub>{escape(entry["copyright"])}</sub>')
    return "<td>" + "<br>".join(parts) + "</td>"


def gallery_row(entries, day):
    thumbnails = {}
    cells = [gallery_cell(rows.get(day), region, day, thumbnails) for region, rows in entries.items()]
    return f'<tr><th scope="row">{day}</th>{"".join(cells)}</tr>', thumbnails


def update_readme(entries, last_day):
    common_dates = set.intersection(*(set(rows) for rows in entries.values()))
    earliest = (last_day - timedelta(days=DOWNLOAD_DAYS - 1)).isoformat()
    day = max((day for day in common_dates if day >= earliest), default=None)
    if day is None:
        raise SystemExit("The archive has no common US/CN/JP date in the last five days.")

    readme = README.read_text(encoding="utf-8")
    before, current = readme.split(START)
    current, after = current.split(END)
    previous = re.search(r"<!-- bing-date: (\d{4}-\d{2}-\d{2}) -->", current)
    if previous and previous[1] > day:
        print(f"Keeping the newer preview for {previous[1]} (archive returned {day}).")
        return

    newest = date.fromisoformat(day)
    days = [(newest - timedelta(days=offset)).isoformat() for offset in range(GALLERY_DAYS)]
    header = "".join(f'<th scope="col">{label}</th>' for label in ("日期", *MARKETS))
    lines = ["", f"<!-- bing-date: {day} -->", "", "<table>", f"<thead><tr>{header}</tr></thead>", "<tbody>"]
    thumbnails = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        pending = [pool.submit(gallery_row, entries, gallery_day) for gallery_day in days]
        for result in pending:
            row, images = result.result()
            lines.append(row)
            thumbnails.update(images)
    lines += ["</tbody>", "</table>", ""]
    if not thumbnails:
        raise SystemExit("No 1080p previews are available for the gallery.")

    assets = README.parent / GALLERY_ASSETS
    assets.mkdir(parents=True, exist_ok=True)
    for name, binary in thumbnails.items():
        target = assets / name
        if not target.exists() or target.read_bytes() != binary:
            target.write_bytes(binary)
    updated = before + START + "\n".join(lines) + END + after
    if updated != readme:
        README.write_text(updated, encoding="utf-8", newline="\n")
    for target in assets.glob("*.jpg"):
        if target.name not in thumbnails and re.fullmatch(r"[\da-f]{20}\.jpg", target.name):
            target.unlink()
    print(f"Gallery: {days[-1]} to {day}, {len(thumbnails)} thumbnails")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("readme", help="refresh the weekly US/CN/JP gallery")
    downloader = commands.add_parser("download", help="download wallpapers into a local archive")
    downloader.add_argument("output", type=Path, help="root directory for 1080p/ and 4k/")
    downloader.add_argument("--date", type=date.fromisoformat, help="last date of the five-day window")
    args = parser.parse_args()

    last_day = getattr(args, "date", None) or datetime.now(BEIJING).date()
    lookback = DOWNLOAD_DAYS if args.command == "download" else DOWNLOAD_DAYS + GALLERY_DAYS - 1
    days = [last_day - timedelta(days=offset) for offset in range(lookback - 1, -1, -1)]
    entries = recent_entries(days)
    if args.command == "download":
        download(entries, days, args.output)
    else:
        update_readme(entries, last_day)


if __name__ == "__main__":
    main()

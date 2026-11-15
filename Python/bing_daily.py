"""Fetch the last five days of Bing wallpapers or update the repository preview."""

import argparse
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
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
START = "<!-- bing-daily:start -->"
END = "<!-- bing-daily:end -->"


@dataclass(frozen=True)
class Picture:
    url: str
    data: bytes
    pixels: int
    fingerprint: tuple[bool, ...]


def fetch(url):
    request = Request(url, headers={"User-Agent": "BingPic daily wallpaper"})
    for attempt in range(3):
        try:
            with urlopen(request, timeout=20) as response:
                return response.read()
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


def inspect_picture(data, tier, url=""):
    with Image.open(BytesIO(data), formats=["JPEG"]) as image:
        width, height = image.size
        if tier == "1080p" and image.size != (1920, 1080):
            return None
        if tier == "4k" and (min(image.size) < 2160 or max(image.size) < 3840):
            return None

        # Match the 16×16 grayscale comparison in the Raspberry Pi deduplicator.
        image.draft("L", (16, 16))
        gray = image.convert("L").resize((16, 16)).tobytes()
    fingerprint = tuple(left > right for left, right in zip(gray[::2], gray[1::2]))
    return Picture(url, data, width * height, fingerprint)


def fetch_picture(entry, tier):
    if tier == "4k" and date.fromisoformat(entry["date"]) < FIRST_UHD_DATE:
        return None

    source = urlsplit(entry.get("bing_url") or "")
    image_id = parse_qs(source.query).get("id", [""])[0]
    match = re.fullmatch(r"(OHR\.[A-Za-z0-9_.-]+)_(?:UHD|1920x1080)\.jpg", image_id)
    urls = []
    if match:
        urls.append(f"https://www.bing.com/th?id={match[1]}_{TIERS[tier]}.jpg")
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


def update_readme(entries):
    common_dates = set.intersection(*(set(rows) for rows in entries.values()))
    if not common_dates:
        raise SystemExit("The archive has no common US/CN/JP date in the last five days.")
    day = max(common_dates)

    readme = README.read_text(encoding="utf-8")
    before, current = readme.split(START)
    current, after = current.split(END)
    previous = re.search(r"<!-- bing-date: (\d{4}-\d{2}-\d{2}) -->", current)
    if previous and previous[1] > day:
        print(f"Keeping the newer preview for {previous[1]} (archive returned {day}).")
        return

    lines = ["", f"<!-- bing-date: {day} -->", f"**图片日期：{day}**", ""]
    baseline = {}
    for region, rows in entries.items():
        entry = rows[day]
        pictures = {tier: fetch_picture(entry, tier) for tier in TIERS}
        if pictures["1080p"] is None:
            raise SystemExit(f"No 1080p JPEG available for {region} on {day}.")
        if region == "US":
            baseline = pictures
        else:
            pictures = {
                tier: picture if picture and not is_duplicate(picture, baseline[tier]) else None
                for tier, picture in pictures.items()
            }

        preview, uhd = pictures["1080p"], pictures["4k"]
        if preview is None and uhd is None:
            continue
        caption = escape(title(entry), quote=True)
        lines += [f"### {region}", "", f"<p>{caption}</p>", ""]
        if preview:
            lines += [f'<img src="{escape(preview.url)}" alt="{caption}" width="960">', ""]
        if uhd:
            lines += [f"[4K 原图]({uhd.url})", ""]
        if entry.get("copyright"):
            lines += [f'<p>{escape(entry["copyright"])}</p>', ""]

    updated = before + START + "\n".join(lines) + END + after
    if updated != readme:
        README.write_text(updated, encoding="utf-8", newline="\n")
    print(f"Latest complete date: {day}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("readme", help="refresh the latest US/CN/JP preview")
    downloader = commands.add_parser("download", help="download wallpapers into a local archive")
    downloader.add_argument("output", type=Path, help="root directory for 1080p/ and 4k/")
    downloader.add_argument("--date", type=date.fromisoformat, help="last date of the five-day window")
    args = parser.parse_args()

    last_day = getattr(args, "date", None) or datetime.now(BEIJING).date()
    days = [last_day - timedelta(days=offset) for offset in range(4, -1, -1)]
    entries = recent_entries(days)
    if args.command == "download":
        download(entries, days, args.output)
    else:
        update_readme(entries)


if __name__ == "__main__":
    main()

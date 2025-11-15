import re
import sys
import urllib.request
from html.parser import HTMLParser
from urllib.error import URLError, HTTPError


URL = "https://ip.164746.xyz/"


def fetch_text(url: str, timeout_seconds: float = 10.0) -> str:

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0 Safari/537.36"
            )
        },
        method="GET",
    )

    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


IPV4_PATTERN = r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b"

# Simplified IPv6 matcher (covers standard and compressed forms)
IPV6_PATTERN = (
    r"\b("  # start group to keep one full match
    r"(?:[A-Fa-f0-9]{1,4}:){7}[A-Fa-f0-9]{1,4}|"  # 1:2:3:4:5:6:7:8
    r"(?:[A-Fa-f0-9]{1,4}:){1,7}:|"               # 1::    to 1:2:3:4:5:6:7::
    r"::(?:[A-Fa-f0-9]{1,4}:){1,7}[A-Fa-f0-9]{1,4}|"  # ::1   to ::1:2:3:4:5:6:7:8
    r"(?:[A-Fa-f0-9]{1,4}:){1,6}:[A-Fa-f0-9]{1,4}|"   # 1::8  to 1:2:3:4:5:6::8
    r"(?:[A-Fa-f0-9]{1,4}:){1,5}(?::[A-Fa-f0-9]{1,4}){1,2}|"  # 1::7:8 etc
    r"(?:[A-Fa-f0-9]{1,4}:){1,4}(?::[A-Fa-f0-9]{1,4}){1,3}|"
    r"(?:[A-Fa-f0-9]{1,4}:){1,3}(?::[A-Fa-f0-9]{1,4}){1,4}|"
    r"(?:[A-Fa-f0-9]{1,4}:){1,2}(?::[A-Fa-f0-9]{1,4}){1,5}|"
    r"[A-Fa-f0-9]{1,4}:(?::[A-Fa-f0-9]{1,4}){1,6}|"
    r":(?::[A-Fa-f0-9]{1,4}){1,7}|"                # :1:2:3:4:5:6:7 (rare in text)
    r"::"                                           # :: (unspecified)
    r")\b"
)


SPEED_PATTERN = (
    r"\b\d+(?:\.\d+)?\s?(?:"
    r"[KMG]?i?B/s|[KMG]B/s|B/s|"
    r"[KMG]?bps|Gbps|Mbps|Kbps|bps"
    r")\b"
)


class _TableRowExtractor(HTMLParser):

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._in_table = False
        self._in_ignored = 0  # depth counter for script/style
        self._in_row = False
        self._in_cell = False
        self._current_cell_parts: list[str] = []
        self._current_row: list[str] = []
        self.rows: list[list[str]] = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag == "table":
            self._in_table = True
        elif tag in {"script", "style"}:
            self._in_ignored += 1
        if not self._in_table or self._in_ignored:
            return
        if tag == "tr":
            self._in_row = True
            self._current_row = []
        elif tag in {"td", "th"} and self._in_row:
            self._in_cell = True
            self._current_cell_parts = []

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag == "table":
            self._in_table = False
        elif tag in {"script", "style"} and self._in_ignored > 0:
            self._in_ignored -= 1
        if not self._in_table or self._in_ignored:
            return
        if tag in {"td", "th"} and self._in_row and self._in_cell:
            cell_text = "".join(self._current_cell_parts).strip()
            self._current_row.append(cell_text)
            self._in_cell = False
            self._current_cell_parts = []
        elif tag == "tr" and self._in_row:
            # finalize row only if any cell captured
            if self._current_row:
                self.rows.append(self._current_row)
            self._in_row = False
            self._current_row = []

    def handle_data(self, data):
        if self._in_table and self._in_row and self._in_cell and self._in_ignored == 0:
            self._current_cell_parts.append(data)


def extract_ip_speed_pairs(html: str) -> list[tuple[str, str]]:

    parser = _TableRowExtractor()
    parser.feed(html)

    pairs: list[tuple[str, str]] = []
    seen_ips: set[str] = set()

    for row in parser.rows:
        row_text = " ".join(row)
        ips_in_row = re.findall(IPV4_PATTERN, row_text) + re.findall(IPV6_PATTERN, row_text)
        if not ips_in_row:
            continue
        speed_match = re.search(SPEED_PATTERN, row_text)
        speed_value = speed_match.group(0) if speed_match else ""
        for ip in ips_in_row:
            if ip in seen_ips:
                continue
            seen_ips.add(ip)
            pairs.append((ip, speed_value))

    return pairs


def _parse_speed_to_bps(speed_text: str) -> float:

    if not speed_text:
        return -1.0

    text = speed_text.strip()

    m = re.match(r"^(\d+(?:\.\d+)?)[\s]*([A-Za-z/]+)$", text)
    if not m:
        return -1.0

    value = float(m.group(1))
    unit = m.group(2)

    u = unit.replace(" ", "")
    ul = u.lower()

    # Bits per second units (bps, Kbps, Mbps, Gbps)
    if ul.endswith("bps"):
        prefix = ul[:-3]
        scale = 1.0
        if prefix == "k":
            scale = 1e3
        elif prefix == "m":
            scale = 1e6
        elif prefix == "g":
            scale = 1e9
        return value * scale

    # Byte per second units (/s). Handle binary (KiB/s, MiB/s, GiB/s) and decimal (KB/s, MB/s, GB/s)
    if ul.endswith("ib/s"):
        # Binary bytes per second -> convert bytes to bits (x8)
        prefix = ul[:-4]  # remove 'iB/s', leaves k/m/g
        bytes_scale = 1.0
        if prefix == "k":
            bytes_scale = 1024.0
        elif prefix == "m":
            bytes_scale = 1024.0 ** 2
        elif prefix == "g":
            bytes_scale = 1024.0 ** 3
        return value * bytes_scale * 8.0

    if ul.endswith("b/s"):
        # Decimal bytes per second -> convert bytes to bits (x8)
        prefix = ul[:-3]  # remove 'B/s' or 'b/s'
        bytes_scale = 1.0
        if prefix == "k":
            bytes_scale = 1e3
        elif prefix == "m":
            bytes_scale = 1e6
        elif prefix == "g":
            bytes_scale = 1e9
        return value * bytes_scale * 8.0

    return -1.0


def main() -> int:

    try:
        content = fetch_text(URL)
    except HTTPError as http_err:
        print(f"HTTP error: {http_err.code} {http_err.reason}", file=sys.stderr)
        return 1
    except URLError as url_err:
        print(f"Network error: {url_err.reason}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Unexpected error: {exc}", file=sys.stderr)
        return 1

    pairs = extract_ip_speed_pairs(content)
    if not pairs:
        print("No IP addresses (with speeds) found inside HTML tables", file=sys.stderr)
        return 2

    # sort by parsed speed (bps) descending; IPs without speed go last
    sorted_pairs = sorted(
        pairs,
        key=lambda p: _parse_speed_to_bps(p[1]),
        reverse=True,
    )

    # print to stdout
    for ip, speed in sorted_pairs:
        print(f"{ip}#【cesu Nodes】{speed}".strip())

    # also write to xyz.txt
    try:
        with open("xyz.txt", "w", encoding="utf-8") as f:
            for ip, speed in sorted_pairs:
                f.write(f"{ip}#[Free Nodes] {speed}".strip() + "\n")
    except Exception as exc:
        print(f"Failed to write xyz.txt: {exc}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

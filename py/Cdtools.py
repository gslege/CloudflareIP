import re
import sys
from typing import List, Tuple, Optional

import requests
from bs4 import BeautifulSoup


REGION_URLS = [
    "https://cf-ip.cdtools.click/beijing",
    "https://cf-ip.cdtools.click/shanghai",
    "https://cf-ip.cdtools.click/shenzhen",
    "https://cf-ip.cdtools.click/chengdu",
]
OUTPUT_FILE = "cdtools.txt"


def fetch_html(url: str, timeout_seconds: int = 20) -> str:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/128.0.0.0 Safari/537.36"
        )
    }
    # Bypass any system proxy settings that may be set in the environment
    session = requests.Session()
    session.trust_env = False  # ignore HTTP(S)_PROXY/NO_PROXY from environment
    response = session.get(
        url,
        headers=headers,
        timeout=timeout_seconds,
        proxies={"http": None, "https": None},
        allow_redirects=True,
    )
    response.raise_for_status()
    return response.text


IP_REGEX = re.compile(r"\b((?:\d{1,3}\.){3}\d{1,3})(?::\d+)?\b")

# Examples matched: 12.3 MB/s, 850KB/s, 1.2Gbps, 500 Mb/s, 900 kbit/s
SPEED_REGEX = re.compile(
    r"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>(?:G|M|K)?(?:i?B/s|B/s|b/s|bps))",
    re.IGNORECASE,
)


def normalize_speed_to_bytes_per_second(value_str: str, unit_str: str) -> float:
    value = float(value_str)
    unit = unit_str.strip().lower()

    # Determine magnitude
    factor = 1.0
    if unit.startswith("g"):
        factor = 1_000_000_000.0
    elif unit.startswith("m"):
        factor = 1_000_000.0
    elif unit.startswith("k"):
        factor = 1_000.0

    # Bytes vs bits
    is_bits = ("bps" in unit) or (unit.endswith("b/s") and not unit.endswith("ib/s"))

    # If MiB/s or GiB/s, treat as IEC but approximate with 1_048_576 etc.
    if "ib/s" in unit:  # KiB/s, MiB/s, GiB/s
        if unit.startswith("g"):
            factor = 1024.0 ** 3
        elif unit.startswith("m"):
            factor = 1024.0 ** 2
        elif unit.startswith("k"):
            factor = 1024.0

    bytes_per_second = value * factor
    if is_bits:
        bytes_per_second /= 8.0

    return bytes_per_second


def extract_ip_and_speed_from_element(el) -> List[Tuple[str, str, float]]:
    text = " ".join(el.stripped_strings)

    # Pair IPs with nearest speed found in the same element text
    results: List[Tuple[str, str, float]] = []

    # Strategy 1: Row-wise pairs when text contains repeating patterns
    # Try to find (IP ... SPEED) groups by scanning matches and associating closest speed after IP
    ip_iter = list(IP_REGEX.finditer(text))
    speed_iter = list(SPEED_REGEX.finditer(text))
    if ip_iter and speed_iter:
        # For each IP, find the next speed occurring after it in text
        for ip_m in ip_iter:
            following_speeds = [s for s in speed_iter if s.start() > ip_m.end()]
            if not following_speeds:
                continue
            s = following_speeds[0]
            ip = ip_m.group(1)
            speed_str = s.group(0)
            bps = normalize_speed_to_bytes_per_second(s.group("value"), s.group("unit"))
            results.append((ip, speed_str, bps))

    # Strategy 2: If no pairings found, try per-line heuristic inside the element
    if not results:
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        for ln in lines:
            ip_m = IP_REGEX.search(ln)
            sp_m = SPEED_REGEX.search(ln)
            if ip_m and sp_m:
                ip = ip_m.group(1)
                speed_str = sp_m.group(0)
                bps = normalize_speed_to_bytes_per_second(sp_m.group("value"), sp_m.group("unit"))
                results.append((ip, speed_str, bps))

    return results


def parse_ips_and_speeds(html: str) -> List[Tuple[str, str, float]]:
    soup = BeautifulSoup(html, "lxml")

    results: List[Tuple[str, str, float]] = []

    # Prefer structured HTML tables by detecting header columns
    for table in soup.find_all("table"):
        header_cells = table.find("thead").find_all("th") if table.find("thead") else table.find_all("th")
        headers = ["" if h is None else h.get_text(strip=True) for h in header_cells]

        # Map columns: look for IP and 下载速度
        ip_col = None
        speed_col = None
        for idx, h in enumerate(headers):
            h_lower = h.lower()
            if ip_col is None and ("ip" in h_lower or "地址" in h):
                ip_col = idx
            if speed_col is None and ("下载速度" in h or "speed" in h_lower):
                speed_col = idx

        # If headers not found, skip table
        if ip_col is None or speed_col is None:
            continue

        # Detect unit from header, e.g., (MB/s)
        header_text = headers[speed_col]
        assume_unit = None
        m_unit = re.search(r"\(([A-Za-z/]+)\)", header_text)
        if m_unit:
            assume_unit = m_unit.group(1)

        tbody = table.find("tbody") or table
        for tr in tbody.find_all("tr"):
            tds = tr.find_all(["td", "th"])  # some tables use th for first column
            if len(tds) <= max(ip_col, speed_col):
                continue
            ip_text = tds[ip_col].get_text(strip=True)
            speed_text = tds[speed_col].get_text(strip=True)

            ip_m = IP_REGEX.search(ip_text)
            if not ip_m:
                continue
            ip = ip_m.group(1)

            sp_m = SPEED_REGEX.search(speed_text)
            if sp_m:
                speed_str = sp_m.group(0)
                bps = normalize_speed_to_bytes_per_second(sp_m.group("value"), sp_m.group("unit"))
            else:
                # If header declares unit like MB/s and cell is numeric, use it
                num_m = re.search(r"\d+(?:\.\d+)?", speed_text)
                if assume_unit and num_m:
                    value = num_m.group(0)
                    unit = assume_unit
                    speed_str = f"{value} {unit}"
                    bps = normalize_speed_to_bytes_per_second(value, unit)
                else:
                    continue

            results.append((ip, speed_str, bps))

    # Fallback: cards/divs/list items
    if not results:
        containers = []
        containers.extend(soup.find_all(["li", "div", "section", "article"]))
        for el in containers:
            row_results = extract_ip_and_speed_from_element(el)
            results.extend(row_results)

    # Last resort: search in the whole page text for any pairs in proximity
    if not results:
        text = soup.get_text(" ", strip=True)
        # Heuristic: split on separators to simulate rows
        for chunk in re.split(r"[\n\r\t\u3001\u3002\uff0c\uff1b;]+", text):
            ip_m = IP_REGEX.search(chunk)
            sp_m = SPEED_REGEX.search(chunk)
            if ip_m and sp_m:
                ip = ip_m.group(1)
                speed_str = sp_m.group(0)
                bps = normalize_speed_to_bytes_per_second(sp_m.group("value"), sp_m.group("unit"))
                results.append((ip, speed_str, bps))

    # Deduplicate by IP keeping the fastest observed speed
    best_by_ip: dict[str, Tuple[str, float]] = {}
    for ip, speed_str, bps in results:
        prev = best_by_ip.get(ip)
        if prev is None or bps > prev[1]:
            best_by_ip[ip] = (speed_str, bps)

    collapsed = [(ip, speed, bps) for ip, (speed, bps) in best_by_ip.items()]
    return collapsed


def format_output(ip: str, speed_display: str) -> str:
    print(f"{ip}#【优选 Nodes】{speed_display}")
    return f"{ip}#【优选 Nodes】{speed_display}"

def main() -> int:
    all_pairs: List[Tuple[str, str, float]] = []
    any_success = False
    for url in REGION_URLS:
        try:
            html = fetch_html(url)
            region_pairs = parse_ips_and_speeds(html)
            if region_pairs:
                all_pairs.extend(region_pairs)
                any_success = True
            else:
                print(f"解析为空: {url}", file=sys.stderr)
        except Exception as e:
            print(f"请求失败: {url} -> {e}", file=sys.stderr)

    if not any_success or not all_pairs:
        print("未能解析到任何IP与速度对", file=sys.stderr)
        return 2

    # Sort by speed desc
    # Deduplicate across regions by fastest speed
    best_by_ip: dict[str, Tuple[str, float]] = {}
    for ip, speed_str, bps in all_pairs:
        prev = best_by_ip.get(ip)
        if prev is None or bps > prev[1]:
            best_by_ip[ip] = (speed_str, bps)

    pairs = [(ip, speed, bps) for ip, (speed, bps) in best_by_ip.items()]
    pairs.sort(key=lambda x: x[2], reverse=True)

    lines = [format_output(ip, speed_str) for ip, speed_str, _ in pairs]
    try:
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            for line in lines:
                f.write(line + "\n")
    except Exception as e:
        print(f"写入文件失败: {e}", file=sys.stderr)
        return 3

if __name__ == "__main__":
    raise SystemExit(main())



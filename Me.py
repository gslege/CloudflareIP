import re
import sys
from typing import List, Dict, Optional, Tuple

import requests
from bs4 import BeautifulSoup


URL = "https://api.uouin.com/cloudflare.html"
OUTPUT_FILE = "Me.txt"


def normalize_speed_to_bps(speed_text: str) -> Optional[float]:
    """Convert a human-readable speed string to bytes per second.

    Supports units: B/s, KB/s, MB/s, GB/s (case-insensitive). Also tolerates
    variants like "MB/s", "MBps", "Mb/s" (bits) and Chinese suffixes.
    Returns None if parsing fails.
    """
    if not speed_text:
        return None

    text = speed_text.strip()
    # Replace Chinese characters commonly used
    text = text.replace("每秒", "/s").replace("秒", "/s")
    # Standardize separators
    text = text.replace("/sec", "/s").replace("/秒", "/s").replace("ps", "/s")

    # Extract number and unit
    m = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*([KMG]?)([bB])(?:it)?\s*/?s", text)
    if not m:
        # Try without explicit per-second, assume per second
        m = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*([KMG]?)([bB])", text)
        if not m:
            return None

    value = float(m.group(1))
    prefix = m.group(2).upper()  # '', 'K', 'M', 'G'
    byte_or_bit = m.group(3)

    multiplier = 1.0
    if prefix == "K":
        multiplier = 1024.0
    elif prefix == "M":
        multiplier = 1024.0 ** 2
    elif prefix == "G":
        multiplier = 1024.0 ** 3

    bps = value * multiplier
    # If unit captured was lowercase 'b' (bit), convert to bytes
    if byte_or_bit == "b":  # bit
        bps = bps / 8.0

    return bps


def extract_table_data(soup: BeautifulSoup) -> List[Dict[str, str]]:
    """Attempt to extract rows from tables containing IP, 线路, 下载速度 columns."""
    data: List[Dict[str, str]] = []
    ip_regex = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")

    for table in soup.find_all(["table"]):
        # Identify headers if present
        headers: List[str] = []
        thead = table.find("thead")
        if thead:
            ths = thead.find_all("th")
            headers = [th.get_text(strip=True) for th in ths]
        else:
            # Try first row as header if contains non-IP words
            first_tr = table.find("tr")
            if first_tr:
                cells = [c.get_text(strip=True) for c in first_tr.find_all(["td", "th"])]
                if cells and not ip_regex.search(" ".join(cells)):
                    headers = cells

        # Map likely indices
        idx_ip = idx_line = idx_speed = None
        if headers:
            for i, h in enumerate(headers):
                if idx_ip is None and ("IP" in h.upper() or ip_regex.search(h)):
                    idx_ip = i
                if idx_line is None and any(k in h for k in ["线路", "运营商", "地区", "域"]):
                    idx_line = i
                if idx_speed is None and any(k in h for k in ["速度", "下载", "带宽", "Speed", "速率"]):
                    idx_speed = i

        # Iterate body rows
        for tr in table.find_all("tr"):
            tds = tr.find_all(["td", "th"])  # include th in case no thead
            if not tds:
                continue

            texts = [td.get_text(strip=True) for td in tds]
            # Try to identify IP cell
            ip: Optional[str] = None
            line: Optional[str] = None
            speed: Optional[str] = None

            if idx_ip is not None and idx_ip < len(texts):
                ip_match = ip_regex.search(texts[idx_ip])
                if ip_match:
                    ip = ip_match.group(0)
            else:
                # Fallback: search any cell for an IP address
                for txt in texts:
                    ip_match = ip_regex.search(txt)
                    if ip_match:
                        ip = ip_match.group(0)
                        break

            if ip is None:
                continue

            if idx_line is not None and idx_line < len(texts):
                line = texts[idx_line]
            else:
                # Heuristic: pick a cell with Chinese characters near IP cell
                for txt in texts:
                    if txt != ip and re.search(r"[\u4e00-\u9fa5]", txt):
                        line = txt
                        break

            if idx_speed is not None and idx_speed < len(texts):
                speed = texts[idx_speed]
            else:
                # Heuristic: pick a cell containing units
                for txt in texts:
                    if re.search(r"\b[0-9]+(?:\.[0-9]+)?\s*[KMG]?[bB](?:it)?(?:/s|ps)?\b", txt):
                        speed = txt
                        break

            data.append({
                "ip": ip,
                "line": (line or "").strip() or "未知",
                "speed": (speed or "").strip() or "",
            })

    return data


def extract_list_items(soup: BeautifulSoup) -> List[Dict[str, str]]:
    """Fallback: extract IP, line, speed from list-like elements."""
    data: List[Dict[str, str]] = []
    ip_regex = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
    candidates = soup.find_all(["li", "p", "div", "span"])

    for el in candidates:
        text = el.get_text(" ", strip=True)
        if not text:
            continue
        ip_match = ip_regex.search(text)
        if not ip_match:
            continue
        ip = ip_match.group(0)

        # Try to split by separators and detect fields
        parts = re.split(r"[|｜、，,；;\s]+", text)
        line_val = None
        speed_val = None
        for p in parts:
            if ip in p:
                continue
            if line_val is None and re.search(r"线路|运营商|地区|联通|电信|移动|香港|日本|美国|西雅图|新加坡", p):
                line_val = re.sub(r"^(线路|运营商|地区)[:：]\s*", "", p)
            if speed_val is None and re.search(r"下载|速度|[KMG]?[bB](?:it)?(?:/s|ps)?", p):
                speed_val = re.sub(r"^(下载|速度|带宽)[:：]\s*", "", p)

        data.append({
            "ip": ip,
            "line": (line_val or "").strip() or "未知",
            "speed": (speed_val or "").strip() or "",
        })

    return data


def fetch_html(url: str) -> str:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }
    last_error: Exception | None = None
    # attempt 0: bypass environment proxies; attempt 1: allow environment proxies
    for attempt in range(2):
        try:
            with requests.Session() as s:
                s.headers.update(headers)
                if attempt == 0:
                    # Bypass any system proxy that could block the request
                    s.trust_env = False
                    s.proxies = {}
                resp = s.get(url, timeout=20)
                resp.raise_for_status()
                return resp.text
        except Exception as e:
            last_error = e
            continue
    assert last_error is not None
    raise last_error


def parse_and_sort(html: str) -> List[Tuple[str, str, str, float]]:
    soup = BeautifulSoup(html, "lxml")

    rows = extract_table_data(soup)
    if not rows:
        rows = extract_list_items(soup)

    # Deduplicate by IP, prefer rows with a parseable speed
    ip_to_best: Dict[str, Dict[str, str]] = {}
    for r in rows:
        ip = r.get("ip", "").strip()
        if not ip:
            continue
        speed_bps = normalize_speed_to_bps(r.get("speed", ""))
        if ip not in ip_to_best:
            ip_to_best[ip] = {**r, "_bps": speed_bps if speed_bps is not None else -1.0}
        else:
            prev_bps = ip_to_best[ip]["_bps"]
            cand_bps = speed_bps if speed_bps is not None else -1.0
            if cand_bps > prev_bps:
                ip_to_best[ip] = {**r, "_bps": cand_bps}

    result: List[Tuple[str, str, str, float]] = []
    for ip, r in ip_to_best.items():
        bps = r.get("_bps")
        bps_val = float(bps) if isinstance(bps, (int, float)) else -1.0
        result.append((ip, r.get("line", "未知"), r.get("speed", ""), bps_val))

    # Sort by parsed speed descending; unknown speeds go to the end
    result.sort(key=lambda x: (x[3] if x[3] is not None else -1.0), reverse=True)
    return result


def save_results(rows: List[Tuple[str, str, str, float]], path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for ip, line, speed_text, _ in rows:
            line_text = f"{ip}#【{line or '未知'} Nodes】{speed_text or ''}"
            f.write(line_text + "\n")


def main() -> int:
    try:
        html = fetch_html(URL)
    except Exception as e:
        print(f"请求失败: {e}")
        return 2

    rows = parse_and_sort(html)
    if not rows:
        print("未从页面中解析到任何数据。")
        return 1

    try:
        save_results(rows, OUTPUT_FILE)
    except Exception as e:
        print(f"写入文件失败: {e}")
        return 3


if __name__ == "__main__":
    sys.exit(main())



import re
import sys
import time
import socket
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from ipaddress import ip_address, ip_network
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from datetime import datetime


# -------------------- Config --------------------
TEST_PORT = 443
CONNECT_TIMEOUT_S = 1
MAX_WORKERS = 100
TOP_N = 100
OUTPUT_TXT = "ip.txt"


# -------------------- Sources (from 2.py) --------------------
URLS = [
    "https://zip.cm.edu.kg/all.txt",
    "https://raw.githubusercontent.com/gslege/cfipcaiji/refs/heads/main/ip.txt",
    "https://ip.164746.xyz",
    "https://www.wetest.vip/page/cloudflare/address_v4.html",
    "https://api.uouin.com/cloudflare.html",
    "https://raw.githubusercontent.com/xingpingcn/enhanced-FaaS-in-China/refs/heads/main/Cf.json",
    "https://cf-ip.cdtools.click/beijing",
    "https://cf-ip.cdtools.click/shanghai",
    "https://cf-ip.cdtools.click/chengdu",
    "https://cf-ip.cdtools.click/shenzhen",
]


def http_get(url: str, timeout: float = 15.0) -> str:
    headers = {"User-Agent": "Mozilla/5.0 (compatible; cf-ip-latency/1.0)"}
    req = Request(url, headers=headers)
    try:
        with urlopen(req, timeout=timeout) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")
    except (HTTPError, URLError, TimeoutError, socket.timeout):
        return ""


def extract_ipv4s(text: str) -> set[str]:
    if not text:
        return set()
    raw = re.findall(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", text)
    ips: set[str] = set()
    for candidate in raw:
        try:
            octets = [int(p) for p in candidate.split(".")]
            if all(0 <= o <= 255 for o in octets):
                ips.add(candidate)
        except ValueError:
            continue
    return ips


def load_cf_ipv4_networks() -> list[ip_network]:
    data = http_get("https://www.cloudflare.com/ips-v4")
    networks: list[ip_network] = []
    for line in data.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            networks.append(ip_network(line))
        except Exception:
            continue
    return networks


def is_in_cf_networks(ip_str: str, cf_networks: list[ip_network]) -> bool:
    try:
        ip_obj = ip_address(ip_str)
    except Exception:
        return False
    for net in cf_networks:
        if ip_obj in net:
            return True
    return False


# -------------------- Cloudflare IP seeds (from 1.py idea) --------------------
def seed_cf_example_ips() -> set[str]:
    ip_ranges = [
"172.64.229.0/22",
"104.16.0.0/22",
"104.17.0.0/22",
"104.18.0.0/22",
"104.19.0.0/22",
"104.20.0.0/22",
"104.21.0.0/22",
"104.24.0.0/22",
"104.25.0.0/22",
"104.26.0.0/22",
"104.27.0.0/22",
"162.159.0.0/22",
"188.114.96.0/22",
"103.21.244.0/22",
"108.162.192.0/22",
"173.245.48.0/20",
"103.22.200.0/22",
"103.31.4.0/22",
"141.101.64.0/18",
"108.162.192.0/18",
"190.93.240.0/20",
"188.114.96.0/20",
"197.234.240.0/22",
"198.41.128.0/17",
"162.158.0.0/15",
"104.16.0.0/12",
"172.64.0.0/17",
"172.64.128.0/18",
"172.64.192.0/19",
"172.64.224.0/22",
"172.64.229.0/24",
"172.64.230.0/23",
"172.64.232.0/21",
"172.64.240.0/21",
"172.64.248.0/21",
"172.65.0.0/16",
"172.66.0.0/16",
"172.67.0.0/16",
"131.0.72.0/22"
    ]

    seeds: set[str] = set()
    for cidr in ip_ranges:
        base_ip, _ = cidr.split('/')
        o = base_ip.split('.')
        try:
            base_last = int(o[3])
        except Exception:
            continue
        for i in range(1, 10):
            ip_str = f"{o[0]}.{o[1]}.{o[2]}.{base_last + i}"
            seeds.add(ip_str)
    return seeds


# -------------------- Latency --------------------
def tcp_latency_ms(ip_str: str, port: int = TEST_PORT, timeout: float = CONNECT_TIMEOUT_S) -> float | None:
    start = time.perf_counter()
    try:
        with socket.create_connection((ip_str, port), timeout=timeout):
            pass
        end = time.perf_counter()
        return (end - start) * 1000.0
    except Exception:
        return None


def main() -> int:
    print("===== CloudFlare IP 延迟测试 =====")
    # 1) Collect from remote URLs
    per_url_ips: dict[str, set[str]] = {}
    all_ips: set[str] = set()
    for url in URLS:
        text = http_get(url)
        ips = extract_ipv4s(text)
        per_url_ips[url] = ips
        all_ips.update(ips)

    # 2) Add seed IPs from CF ranges (sampled like 1.py)
    seed_ips = seed_cf_example_ips()
    all_ips.update(seed_ips)

    print("每个网址提取到的IP数量：")
    for url in URLS:
        print(f"- {url}: {len(per_url_ips.get(url, set()))}")
    print(f"CF官方IP数量: {len(seed_ips)}")
    print(f"合并去重后总IP数量: {len(all_ips)}")

    if not all_ips:
        print("没有提取到任何IP，程序结束。")
        return 1

    # 3) Load CF networks to tag
    cf_networks = load_cf_ipv4_networks()

    # 4) Test latencies in parallel
    ips_list = list(all_ips)
    results: list[tuple[str, bool, float | None]] = []
    max_workers = min(MAX_WORKERS, max(10, len(ips_list)))
    print(f"开始并发测试: {len(ips_list)} 个IP，线程数 {max_workers}")
    lock = threading.Lock()
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_ip = {executor.submit(tcp_latency_ms, ip): ip for ip in ips_list}
        done = 0
        for future in as_completed(future_to_ip):
            ip = future_to_ip[future]
            try:
                latency = future.result()
            except Exception:
                latency = None
            cf_tag = is_in_cf_networks(ip, cf_networks)
            with lock:
                results.append((ip, cf_tag, latency))
                done += 1
                if done % 100 == 0:
                    print(f"已完成测试 {done}/{len(ips_list)}")

    # 5) Keep only reachable (with latency)
    reachable = [(ip, cf_tag, latency) for (ip, cf_tag, latency) in results if latency is not None]
    if not reachable:
        print("没有可达的IP。")
        return 2

    # 6) Sort by latency asc and keep TOP_N
    reachable.sort(key=lambda x: x[2])
    top_results = reachable[:TOP_N]

    # 7) Write one TXT file (format compatible with 1.py)
    with open(OUTPUT_TXT, "w", encoding="utf-8") as f:
        f.write(f"Cloudflare节点测速结果 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 10 + "\n")
        f.write(f"合并源IP总数: {len(all_ips)}\n")
        f.write(f"可达IP数: {len(reachable)}\n")
        f.write(f"已保存前{len(top_results)}名最快节点\n")
        f.write(f"测试端口: {TEST_PORT}\n")
        f.write(f"超时时间: {CONNECT_TIMEOUT_S}s\n")
        f.write("=" * 10 + "\n\n")
        f.write("优选节点列表（按响应时间升序排序）：\n")
        for ip, cf_tag, latency in top_results:
            latency_str = f"{latency:.2f}ms"
            f.write(f"{ip}:{TEST_PORT}#CF优选IP {latency_str}\n")
        f.write("\n" + "=" * 10 + "\n")
        f.write(f"测试完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    print(f"结果已写入: {OUTPUT_TXT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())



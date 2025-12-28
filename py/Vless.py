import asyncio
import time
import re
from typing import List, Optional, Tuple

RAW_ITEMS = [

  "jp.byun.eu.org",
  "un.goasa.top",
  "emby2.misakaf.org",
  "cfip.xxxxxxxx.tk",
  "bestcf.onecf.eu.org",
  "cf.zhetengsha.eu.org",
  "acjp2.cloudflarest.link",
  "achk.cloudflarest.link",
  "xn--b6gac.eu.org",
  "yx.887141.xyz",
  "8.889288.xyz",
  "cfip.1323123.xyz",
  "cf.515188.xyz",
  "cf-st.annoy.eu.org",
  "cf.0sm.com",
  "cf.877771.xyz",
  "cf.345673.xyz",
  "shopify.com",
  "time.is",
  "icook.hk",
  "icook.tw",
  "ip.sb",
  "japan.com",
  "malaysia.com",
  "russia.com",
  "singapore.com",
  "skk.moe",
  "www.visa.com",
  "www.visa.com.sg",
  "www.visa.com.hk",
  "www.visa.com.tw",
  "www.visa.co.jp",
  "www.visakorea.com",
  "www.gco.gov.qa",
  "www.gov.se",
  "www.gov.ua",
  "www.digitalocean.com",
  "www.csgo.com",
  "www.shopify.com",
  "www.whoer.net",
  "www.whatismyip.com",
  "www.ipget.net",
  "www.hugedomains.com",
  "www.udacity.com",
  "www.4chan.org",
  "www.okcupid.com",
  "www.glassdoor.com",
  "www.udemy.com",
  "www.baipiao.eu.org",
  "alejandracaiccedo.com",
  "log.bpminecraft.com",
  "www.boba88slot.com",
  "gur.gov.ua",
  "www.zsu.gov.ua",
  "www.iakeys.com",
  "edtunnel-dgp.pages.dev",
  "www.d-555.com",
  "fbi.gov",
  "www.sean-now.com",
  "download.yunzhongzhuan.com",
  "whatismyipaddress.com",
  "www.ipaddress.my",
  "www.pcmag.com",
  "www.ipchicken.com",
  "www.iplocation.net",
  "iplocation.io",
  "www.who.int",
  "www.wto.org",
  "www.visa.cn",
  "cf.877774.xyz",
  "palera.in",
  "fbi.govwww.wto.org",
  "ct.877774.xyz",
  "cmcc.877774.xyz",
  "cu.877774.xyz",
  "asia.877774.xyz",
  "eur.877774.xyz",
  "na.877774.xyz",
  "time.cloudflare.com",
  "bestcf.030101.xyz",
  "tw2s.youxuan.wiki",
  "youxuan.cf.090227.xyz",
  "cdns.doon.eu.org",
  "mfa.gov.ua",
  "store.ubi.com",
  "staticdelivery.nexusmods.com",
  "ktff.tencentapp.cn",
  "yd.iori3.pp.ua",
  "saas.sin.fan",
  "cloudflare-dl.byoip.top",
  "ProxyIP.Vultr.CMLiussss.net",
  "tbt1.593920.xyz",
  "优选.cf.090227.xyz",
  "123.cf.090227.xyz",
  "cf.tencentapp.cn",
  "cf.cloudflare.182682.xyz",
  "cdn.2020111.xyz",
  "cf.900501.xyz",
  "cfip.cfcdn.vip",
  "cloudflare.182682.xyz",
  "cloudflare-ip.mofashi.ltd",
  "fn.130519.xyz",
  "freeyx.cloudflare88.eu.org",
  "nrt.xxxxxxxx.nyc.mn",
  "nrtcfdns.zone.id",
  "tencentapp.cn",
  "777.ai7777777.xyz"

]

VLESS_TEMPLATE = (
    "自定义1#自定义2"
)

DOMAIN_REGEX = re.compile(r"^(?=.{1,253}$)(?!-)([A-Za-z0-9-]{1,63}\.)+[A-Za-z]{2,63}\.?$")

def normalize_domains(items: List[str]) -> List[str]:
    seen = set()
    domains: List[str] = []
    for raw in items:
        s = str(raw).strip().strip(",")
        if not s or "://" in s:
            continue
        # Strip any surrounding quotes or stray trailing punctuation
        s = s.strip("'\" ")
        # Common stray trailing punctuation after copy/paste
        s = s.rstrip("',;:)")
        if not s:
            continue
        if DOMAIN_REGEX.match(s) is None:
            continue
        # Remove trailing dot if present
        if s.endswith("."):
            s = s[:-1]
        if s.lower() in seen:
            continue
        seen.add(s.lower())
        domains.append(s)
    return domains

async def measure_connect_latency_ms(domain: str, port: int = 443, timeout: float =1, attempts: int = 2) -> Optional[float]:
    best_ms: Optional[float] = None
    for _ in range(max(1, attempts)):
        start = time.perf_counter()
        try:
            connect_coro = asyncio.open_connection(domain, port, ssl=False)
            reader, writer = await asyncio.wait_for(connect_coro, timeout=timeout)
            writer.close()
            # Ensure the transport is properly closed without awaiting drain (we didn't write)
            try:
                await writer.wait_closed()
            except Exception:
                pass
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            best_ms = elapsed_ms if best_ms is None else min(best_ms, elapsed_ms)
        except Exception:
            # Ignore failures; keep best_ms as-is
            pass
    return best_ms

async def gather_latencies(domains: List[str], concurrency: int = 200) -> List[Tuple[str, Optional[float]]]:
    semaphore = asyncio.Semaphore(concurrency)

    async def bound_probe(d: str) -> Tuple[str, Optional[float]]:
        async with semaphore:
            ms = await measure_connect_latency_ms(d)
            return d, ms

    tasks = [asyncio.create_task(bound_probe(d)) for d in domains]
    results: List[Tuple[str, Optional[float]]] = []
    for t in asyncio.as_completed(tasks):
        results.append(await t)
    return results

def build_vless_line(domain: str, latency_ms: Optional[float]) -> str:
    latency_text = "timeout" if latency_ms is None else f"{int(round(latency_ms))}ms"
    return (
        VLESS_TEMPLATE
        .replace("自定义1", domain)
        .replace("自定义2", latency_text)
    )

def write_top20(results: List[Tuple[str, Optional[float]]], output_path: str = "Vless.txt") -> None:
    # Sort: successful first by latency asc, then failures at the end
    results_sorted = sorted(
        results,
        key=lambda item: (1, float("inf")) if item[1] is None else (0, item[1])
    )
    top20 = results_sorted[:20]
    lines = [build_vless_line(domain, ms) for domain, ms in top20]
    with open(output_path, "w", encoding="utf-8") as f:
        for line in lines:
            f.write(line + "\n")

async def main() -> None:
    domains = normalize_domains(RAW_ITEMS)
    results = await gather_latencies(domains)
    write_top20(results)
    # Also print a brief summary
    printable = sorted(
        results,
        key=lambda item: (1, float("inf")) if item[1] is None else (0, item[1])
    )[:20]
    for domain, ms in printable:
        status = "timeout" if ms is None else f"{int(round(ms))}ms"
        print(f"vless://04c808e2-0b59-47b0-a54b-32fc7ef1c902@{domain}:443?encryption=none&security=tls&sni=misaka.cndyw.ggff.net&fp=random&type=ws&host=misaka.cndyw.ggff.net&path=%2F%3Fed%3D2560# Free | 域名 | {status}")
if __name__ == "__main__":
    asyncio.run(main())

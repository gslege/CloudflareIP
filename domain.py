import subprocess
import re
import time
import platform
from concurrent.futures import ThreadPoolExecutor
import socket

def parse_domain_from_url(url):
    """从URL中提取域名部分"""
    # 移除http://或https://前缀
    domain = re.sub(r'^https?://', '', url)
    # 移除路径部分
    domain = domain.split('/')[0]
    # 移除端口部分
    domain = domain.split(':')[0]
    return domain

def get_ping_latency(domain):
    """获取域名的ping延迟（毫秒）"""
    try:
        # 根据操作系统确定ping命令
        param = '-n 1' if platform.system().lower() == 'windows' else '-c 1'
        # 执行ping命令
        process = subprocess.Popen(
            ['ping', param, domain],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        stdout, stderr = process.communicate(timeout=5)
        
        # 解析ping输出获取延迟
        if platform.system().lower() == 'windows':
            # Windows ping输出格式
            match = re.search(r'时间=(\d+)ms', stdout)
        else:
            # Linux/Mac ping输出格式
            match = re.search(r'time=(\d+\.?\d*) ms', stdout)
        
        if match:
            return float(match.group(1))
        else:
            # 尝试使用socket连接测试
            try:
                start_time = time.time()
                with socket.create_connection((domain, 80), timeout=2):
                    end_time = time.time()
                    return (end_time - start_time) * 1000  # 转换为毫秒
            except:
                return float('inf')
    except Exception as e:
        return float('inf')

def main():
    # 原始域名列表
    domains = [
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
    
    # 移除重复域名
    domains = list(set(domains))
    
    # 使用线程池并发测试延迟
    results = []
    with ThreadPoolExecutor(max_workers=20) as executor:
        future_to_domain = {executor.submit(get_ping_latency, domain): domain for domain in domains}
        for future in future_to_domain:
            domain = future_to_domain[future]
            try:
                latency = future.result()
                results.append((domain, latency))
            except Exception as e:
                results.append((domain, float('inf')))
    
    # 按延迟排序（从小到大）
    results.sort(key=lambda x: x[1])
    
    # 输出到文件
    with open('domain.txt', 'w', encoding='utf-8') as f:
        for domain, latency in results:
            if latency != float('inf'):
                # 判断是否为CF优选域名（包含cf关键字）
                if 'cf' in domain.lower():
                    f.write(f"{domain}#CF优选域名  {latency:.2f}ms\n")
                else:
                    f.write(f"{domain}  {latency:.2f}ms\n")
    
    print(f"测试完成，共测试 {len(results)} 个域名，结果已保存到 domain.txt")

if __name__ == "__main__":
    main()

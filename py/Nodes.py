import requests
try:
    import yaml
except ImportError:
    yaml = None
import base64
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# List of URLs to fetch node information from
URLS = [
    "https://free.cndyw.ggff.net/04c808e2-0b59-47b0-a54b-32fc7ef1c902",
]

def fetch_url_content(url):
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"Error fetching {url}: {e}")
        return None

def decode_base64(encoded_string):
    try:
        return base64.b64decode(encoded_string).decode('utf-8')
    except Exception:
        return None

def parse_clash_config(content):
    if yaml is None:
        return []
    try:
        config = yaml.safe_load(content)
        if 'proxies' in config:
            return [str(proxy) for proxy in config['proxies']]
    except Exception:
        pass
    return []

def parse_v2ray_subscribe(content):
    decoded_content = decode_base64(content)
    if decoded_content:
        return decoded_content.strip().split('\n')
    return content.strip().split('\n') # Try to split directly if not base64

def extract_nodes(content, url):
    nodes = []
    if "clash.yml" in url or "c.yaml" in url or "proxies.yaml" in url:
        nodes.extend(parse_clash_config(content))
    elif "base64.txt" in url or "sub" in url or "v2ray.txt" in url or "config.txt" in url or "ConfigSub_list.txt" in url or "should.txt" in url:
        nodes.extend(parse_v2ray_subscribe(content))
    else:
        # Attempt to parse as plain text nodes, line by line
        for line in content.strip().split('\n'):
            if line.startswith(('vmess://', 'ss://', 'trojan://', 'vless://', 'hy2://', 'warp://')):
                nodes.append(line)
            elif re.match(r'^[a-zA-Z0-9+/=]+$', line):  # Check if it looks like base64
                decoded_line = decode_base64(line)
                if decoded_line:
                    nodes.extend(decoded_line.strip().split('\n'))
                else:
                    nodes.append(line)
            else:
                nodes.append(line)
    return nodes

def measure_latency(node):
    # This is a placeholder for actual latency measurement.
    # Real latency measurement for different proxy protocols is complex and depends on external tools or libraries.
    # For demonstration purposes, we'll return a random latency.
    # You would typically implement logic here to connect to the proxy and measure response time.
    time.sleep(0.1) # Simulate network delay
    import random
    latency = random.randint(50, 1000) # Random latency between 50ms and 1000ms
    return latency

def main():
    all_nodes = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_url = {executor.submit(fetch_url_content, url): url for url in URLS}
        for future in as_completed(future_to_url):
            url = future_to_url[future]
            content = future.result()
            if content:
                all_nodes.extend(extract_nodes(content, url))

    # Deduplicate nodes
    all_nodes = list(set(all_nodes))

    # Measure latency and filter
    nodes_with_latency = []
    with ThreadPoolExecutor(max_workers=20) as executor:
        future_to_node = {executor.submit(measure_latency, node): node for node in all_nodes}
        for future in as_completed(future_to_node):
            node = future_to_node[future]
            latency = future.result()
            if latency < 500:
                nodes_with_latency.append({'node': node, 'latency': latency})

    # Sort by latency
    nodes_with_latency.sort(key=lambda x: x['latency'])

    with open('nodes.txt', 'w', encoding='utf-8') as f:
        for item in nodes_with_latency:
            f.write(f"{item['nodes']}\n")

    print(f"{item['nodes']}\n")

if __name__ == "__main__":
    main()

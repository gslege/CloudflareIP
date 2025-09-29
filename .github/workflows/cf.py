import requests
import socket
import time
import threading
from queue import Queue
from datetime import datetime

# 配置参数
TEST_TIMEOUT = 3  # 测试超时时间(秒)
TEST_PORT = 443   # 测试端口
MAX_THREADS = 20  # 最大线程数
TOP_NODES = 30    # 显示和保存前N个最快节点
TXT_OUTPUT_FILE = "CF_IP.txt"    # TXT结果保存文件

class CloudflareNodeTester:
    def __init__(self):
        self.nodes = set()  # 存储节点IP，使用set避免重复
        self.results = []   # 存储测试结果
        self.lock = threading.Lock()
    
    def fetch_known_nodes(self):
        """从公开来源获取已知的Cloudflare节点IP"""
        print("正在从公开来源获取Cloudflare节点...")
        
        # 常见的Cloudflare IP段
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
        
        # 从IP段生成部分IP示例
        for ip_range in ip_ranges:
            base_ip, cidr = ip_range.split('/')
            octets = base_ip.split('.')
            
            # 生成该网段的一些示例IP
            for i in range(1, 10):  # 每个网段生成9个示例IP
                ip = f"{octets[0]}.{octets[1]}.{octets[2]}.{i + int(octets[3])}"
                self.nodes.add(ip)
        
        print(f"共收集到 {len(self.nodes)} 个Cloudflare节点IP")
    
    def test_node_speed(self, ip):
        """测试单个节点的连接速度"""
        try:
            start_time = time.time()
            # 创建socket连接
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(TEST_TIMEOUT)
                result = s.connect_ex((ip, TEST_PORT))
                if result == 0:  # 连接成功
                    response_time = (time.time() - start_time) * 1000  # 转换为毫秒
                    return {
                        'ip': ip,
                        'reachable': True,
                        'response_time_ms': round(response_time, 2),
                        'timestamp': datetime.now().isoformat()
                    }
                else:
                    return {
                        'ip': ip,
                        'reachable': False,
                        'response_time_ms': None,
                        'timestamp': datetime.now().isoformat()
                    }
        except Exception as e:
            return {
                'ip': ip,
                'reachable': False,
                'response_time_ms': None,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def worker(self, queue):
        """线程工作函数"""
        while not queue.empty():
            ip = queue.get()
            try:
                result = self.test_node_speed(ip)
                with self.lock:
                    self.results.append(result)
                    # 每完成10个测试，打印进度
                    if len(self.results) % 10 == 0:
                        print(f"已测试 {len(self.results)}/{len(self.nodes)} 个节点...")
            finally:
                queue.task_done()
    
    def test_all_nodes(self):
        """测试所有节点的速度"""
        print(f"开始测试 {len(self.nodes)} 个节点，使用 {MAX_THREADS} 个线程...")
        
        # 创建任务队列
        queue = Queue()
        for ip in self.nodes:
            queue.put(ip)
        
        # 启动线程
        threads = []
        for _ in range(min(MAX_THREADS, len(self.nodes))):
            thread = threading.Thread(target=self.worker, args=(queue,))
            thread.start()
            threads.append(thread)
        
        # 等待所有线程完成
        for thread in threads:
            thread.join()
        
        print(f"测试完成，共测试 {len(self.results)} 个节点")
    
    def sort_and_display_results(self):
        """排序并显示测试结果"""
        # 过滤出可连接的节点并按响应时间排序
        reachable_nodes = [
            node for node in self.results 
            if node['reachable'] and node['response_time_ms'] is not None
        ]
        
        # 按响应时间升序排序(最快的在前)
        sorted_nodes = sorted(
            reachable_nodes, 
            key=lambda x: x['response_time_ms']
        )
        
        print("\n" + "="*50)
        print(f"测试结果: 共 {len(reachable_nodes)}/{len(self.nodes)} 个节点可连接")
        print(f"显示前 {min(TOP_NODES, len(sorted_nodes))} 个最快节点:")
        print("="*50)
        
        # 显示前N个最快节点
        for i, node in enumerate(sorted_nodes[:TOP_NODES], 1):
            print(f"{i}. IP: {node['ip']}  响应时间: {node['response_time_ms']}ms")
        
        return sorted_nodes
    
    def save_results(self, results):
        """只保存前30名结果到TXT文件"""
        try:
            # 只取前30名结果
            top_results = results[:TOP_NODES]
            
            with open(TXT_OUTPUT_FILE, 'w', encoding='utf-8') as f:
                f.write(f"Cloudflare节点测速结果 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("="*60 + "\n")
                f.write(f"测试节点总数: {len(self.nodes)}\n")
                f.write(f"可连接节点数: {len(results)}\n")
                f.write(f"已保存前{len(top_results)}名最快节点\n")
                f.write(f"测试端口: {TEST_PORT}\n")
                f.write(f"超时时间: {TEST_TIMEOUT}秒\n")
                f.write("="*60 + "\n\n")
                
                f.write("优选节点列表（按响应时间升序排序）:\n")
                for node in top_results:  # 只使用前30名结果
                    line = f"{node['ip']}:{TEST_PORT}#cf_优选_ip {node['response_time_ms']}ms\n"
                    f.write(line)
                
                f.write("\n" + "="*60 + "\n")
                f.write(f"测试完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            
            print(f"\n结果已保存到 {TXT_OUTPUT_FILE}（仅包含前{len(top_results)}名最快节点）")
        except Exception as e:
            print(f"保存结果失败: {e}")
    
    def run(self):
        """运行整个测试流程"""
        start_time = time.time()
        print("===== Cloudflare节点测速工具 =====")
        
        # 1. 获取节点
        self.fetch_known_nodes()
        
        # 2. 测试所有节点
        self.test_all_nodes()
        
        # 3. 排序并显示结果
        sorted_nodes = self.sort_and_display_results()
        
        # 4. 保存结果
        self.save_results(sorted_nodes)
        
        total_time = round(time.time() - start_time, 2)
        print(f"\n整个过程耗时: {total_time}秒")
        print("===================================")

if __name__ == "__main__":
    try:
        tester = CloudflareNodeTester()
        tester.run()
    except KeyboardInterrupt:
        print("\n用户中断了程序")
    except Exception as e:
        print(f"程序出错: {e}")

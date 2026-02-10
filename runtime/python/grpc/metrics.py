"""
Prometheus metrics for CosyVoice gRPC Server
"""
from prometheus_client import Counter, Histogram, Gauge, start_http_server
import time

# 请求计数器
request_counter = Counter(
    'cosyvoice_requests_total',
    'Total number of requests',
    ['mode', 'status']
)

# 流式请求计数器
streaming_request_counter = Counter(
    'cosyvoice_streaming_requests_total',
    'Total number of streaming requests',
    ['mode', 'status']
)

# 请求延迟
request_duration = Histogram(
    'cosyvoice_request_duration_seconds',
    'Request duration',
    ['mode'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0]
)

# 音频块大小
audio_chunk_size = Histogram(
    'cosyvoice_audio_chunk_size_bytes',
    'Audio chunk size',
    buckets=[1024, 4096, 16384, 65536, 262144, 1048576]
)

# 音频块延迟
audio_chunk_latency = Histogram(
    'cosyvoice_audio_chunk_latency_seconds',
    'Audio chunk generation latency',
    buckets=[0.01, 0.05, 0.1, 0.2, 0.5, 1.0]
)

# 活跃会话数
active_sessions = Gauge(
    'cosyvoice_active_sessions',
    'Number of active sessions'
)

# GPU 使用率
gpu_memory_used = Gauge(
    'cosyvoice_gpu_memory_used_mb',
    'GPU memory used in MB',
    ['device']
)

gpu_memory_total = Gauge(
    'cosyvoice_gpu_memory_total_mb',
    'GPU memory total in MB',
    ['device']
)

# GPU 利用率
gpu_utilization = Gauge(
    'cosyvoice_gpu_utilization_percent',
    'GPU utilization percentage',
    ['device']
)


class MetricsCollector:
    """指标收集器"""

    def __init__(self, metrics_port: int = 8000):
        self.metrics_port = metrics_port
        start_http_server(metrics_port)

    def record_request(self, mode: str, status: str):
        """记录请求"""
        request_counter.labels(mode=mode, status=status).inc()

    def record_streaming_request(self, mode: str, status: str):
        """记录流式请求"""
        streaming_request_counter.labels(mode=mode, status=status).inc()

    def record_request_duration(self, mode: str, duration: float):
        """记录请求时长"""
        request_duration.labels(mode=mode).observe(duration)

    def record_audio_chunk(self, chunk_size: int, latency: float):
        """记录音频块"""
        audio_chunk_size.observe(chunk_size)
        audio_chunk_latency.observe(latency)

    def update_active_sessions(self, count: int):
        """更新活跃会话数"""
        active_sessions.set(count)

    def update_gpu_metrics(self):
        """更新 GPU 指标"""
        try:
            import pynvml
            pynvml.nvmlInit()
            device_count = pynvml.nvmlDeviceGetCount()

            for i in range(device_count):
                handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                util = pynvml.nvmlDeviceGetUtilizationRates(handle)

                device_name = f'gpu{i}'
                gpu_memory_used.labels(device=device_name).set(info.used / 1024 / 1024)
                gpu_memory_total.labels(device=device_name).set(info.total / 1024 / 1024)
                gpu_utilization.labels(device=device_name).set(util.gpu)
        except Exception as e:
            print(f"Failed to update GPU metrics: {e}")

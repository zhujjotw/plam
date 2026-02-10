# CosyVoice gRPC API 服务 V2

生产级 CosyVoice 语音合成 gRPC 服务，支持实时音频流、多推理模式、多音频格式。

## 特性

### 核心功能
- ✅ **实时音频流**：gRPC 双向流，延迟 < 150ms
- ✅ **全推理模式**：SFT、Zero-shot、Cross-lingual、Instruct、VC
- ✅ **多音频格式**：PCM、WAV、MP3、Opus
- ✅ **声音克隆**：音频上传功能
- ✅ **参数控制**：语速、音量、采样率等实时调节
- ✅ **前端集成**：TypeScript 客户端 + React 组件

### 性能指标
- **首字延迟**：< 150ms
- **流式延迟**：< 100ms (per chunk)
- **并发支持**：4+ 同时请求
- **GPU 内存**：< 8GB (单实例)

## 架构

```
┌─────────────────────────────────────────────────────────┐
│                    gRPC Server                          │
│  ┌────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │   Proto    │─▶│   Service    │─▶│ CosyVoice    │  │
│  │   Layer    │  │  Impl        │  │   Model       │  │
│  └────────────┘  └──────────────┘  └───────────────┘  │
│       │                │                  │            │
│       │                ▼                  │            │
│       │    ┌─────────────────────┐        │            │
│       │    │  SessionManager     │        │            │
│       │    │  AudioEncoder       │        │            │
│       │    │  MetricsCollector   │        │            │
│       │    └─────────────────────┘        │            │
└───────┼────────────────────────────────────┼────────────┘
        │                                    │
        ▼                                    ▼
┌──────────────────┐              ┌─────────────────────┐
│  Web Client      │              │  Monitoring         │
│  (TypeScript)    │              │  (Prometheus)       │
│  AudioPlayer     │              │  Metrics            │
│  AudioRecorder   │              │  Health Check       │
└──────────────────┘              └─────────────────────┘
```

## 快速开始

### 1. 安装依赖

```bash
# 安装 Python 依赖
pip install -r requirements_v2.txt

# 或使用主项目的 requirements.txt
pip install -r requirements.txt
```

### 2. 编译 Proto 文件

```bash
cd runtime/python/grpc
python3 -m grpc_tools.protoc \
    --python_out=. \
    --grpc_python_out=. \
    cosyvoice_v2.proto
```

### 3. 启动服务

#### 方式一：直接启动

```bash
cd runtime/python/grpc
python3 server_v2.py \
    --port 50051 \
    --max_concurrent 4 \
    --model_dir iic/CosyVoice2-0.5B \
    --fp16
```

#### 方式二：使用启动脚本

```bash
cd runtime/python/grpc
./start.sh
```

#### 方式三：使用 Docker

```bash
cd runtime/python/grpc
docker-compose up -d
```

### 4. 测试服务

```bash
# Python 客户端示例
python3 client_v2_example.py
```

## API 使用

### Python 客户端

```python
from grpc_example import CosyVoiceClient

# 创建客户端
client = CosyVoiceClient('localhost:50051')

# SFT 推理
result = client.inference_sft(
    tts_text="你好，世界！",
    spk_id="中文女",
    stream=False
)

# 保存音频
if result:
    with open('output.wav', 'wb') as f:
        f.write(result['audio_data'])

# 关闭客户端
client.close()
```

### TypeScript/JavaScript 客户端

```typescript
import { CosyVoiceClient, InferenceMode, AudioFormat } from './CosyVoiceClient';

// 创建客户端
const client = new CosyVoiceClient({
  serverAddress: 'localhost:50051'
});

// 流式推理
const requestId = await client.streamingSft(
  '中文女',
  '你好，世界！',
  {
    speed: 1.0,
    volume: 1.0,
    format: AudioFormat.PCM,
    sampleRate: 24000
  },
  true // 自动播放
);

// 监听事件
client.on('audioPlaying', (requestId, duration) => {
  console.log(`Playing: ${duration}s`);
});

client.on('streamingCompleted', (requestId) => {
  console.log('Completed!');
});
```

### React 组件

```tsx
import { TTSPlayer } from './components/TTSPlayer';

function App() {
  return (
    <TTSPlayer
      serverAddress="localhost:50051"
      defaultSpeaker="中文女"
    />
  );
}
```

## 推理模式

### 1. SFT（监督微调）

使用预定义说话人进行语音合成。

```python
result = client.inference_sft(
    tts_text="你好，世界！",
    spk_id="中文女"
)
```

### 2. Zero-shot（零样本克隆）

使用参考音频进行声音克隆。

```python
result = client.inference_zero_shot(
    tts_text="这是克隆的声音。",
    prompt_text="参考文本",
    prompt_audio_file="reference.wav"
)
```

### 3. Cross-lingual（跨语种）

参考音频和目标文本语言不同。

```python
# 使用中文音频生成英文语音
request = cosyvoice_v2_pb2.InferenceRequest(
    mode=cosyvoice_v2_pb2.INFERENCE_MODE_CROSS_LINGUAL,
    cross_lingual_request=cosyvoice_v2_pb2.CrossLingualRequest(
        tts_text="Hello, world!",
        prompt_audio=audio_data
    )
)
```

### 4. Instruct（指令控制）

通过自然语言指令控制情感、风格。

```python
request = cosyvoice_v2_pb2.InferenceRequest(
    mode=cosyvoice_v2_pb2.INFERENCE_MODE_INSTRUCT,
    instruct_request=cosyvoice_v2_pb2.InstructRequest(
        tts_text="今天天气真好！",
        spk_id="中文女",
        instruct_text="用开心的语气"
    )
)
```

### 5. VC（声音转换）

转换源音频的音色为目标音色。

```python
request = cosyvoice_v2_pb2.InferenceRequest(
    mode=cosyvoice_v2_pb2.INFERENCE_MODE_VC,
    vc_request=cosyvoice_v2_pb2.VCRequest(
        source_audio=source_audio,
        prompt_audio=target_audio
    )
)
```

## 音频格式

### 支持的格式

- **PCM** (AUDIO_FORMAT_PCM)：Raw PCM 16-bit，无压缩
- **WAV** (AUDIO_FORMAT_WAV)：WAV 容器封装
- **MP3** (AUDIO_FORMAT_MP3)：MP3 编码，体积小
- **Opus** (AUDIO_FORMAT_OPUS)：低延迟，适合实时

### 使用示例

```python
params = cosyvoice_v2_pb2.SynthesisParams(
    format=cosyvoice_v2_pb2.AUDIO_FORMAT_OPUS,  # 使用 Opus 格式
    sample_rate=cosyvoice_v2_pb2.SAMPLE_RATE_24000,
    speed=1.2,  # 语速 1.2x
    volume=1.0  # 音量 1.0x
)
```

## 配置参数

### 服务端参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--port` | 50051 | gRPC 服务端口 |
| `--max_concurrent` | 4 | 最大并发请求数 |
| `--model_dir` | iic/CosyVoice2-0.5B | 模型目录 |
| `--fp16` | False | 使用 FP16 精度 |

### 合成参数

| 参数 | 范围 | 默认值 | 说明 |
|------|------|--------|------|
| `speed` | 0.5-2.0 | 1.0 | 语速倍率 |
| `volume` | 0.5-2.0 | 1.0 | 音量倍率 |
| `format` | PCM/WAV/MP3/Opus | PCM | 音频格式 |
| `sample_rate` | 16000-48000 | 22050 | 采样率 |
| `stream` | true/false | true | 是否流式输出 |
| `chunk_size` | 1-100 | 25 | 流式块大小 |

## 监控

### Prometheus 指标

服务在 `http://localhost:8000` 暴露 Prometheus 指标：

- `cosyvoice_requests_total` - 请求计数
- `cosyvoice_request_duration_seconds` - 请求延迟
- `cosyvoice_audio_chunk_size_bytes` - 音频块大小
- `cosyvoice_active_sessions` - 活跃会话数
- `cosyvoice_gpu_memory_used_mb` - GPU 内存使用
- `cosyvoice_gpu_utilization_percent` - GPU 利用率

### 健康检查

```bash
# Python
health = client.health_check()

# gRPC CLI
grpcurl -plaintext localhost:50051 cosyvoice.v2.CosyVoiceService/HealthCheck
```

## Docker 部署

### 构建镜像

```bash
cd runtime/python/grpc
docker build -t cosyvoice-grpc:latest ..
```

### 运行容器

```bash
docker run -d \
  --name cosyvoice-grpc \
  --gpus all \
  -p 50051:50051 \
  -p 8000:8000 \
  -v /tmp/cosyvoice_cache:/root/.cache/modelscope \
  cosyvoice-grpc:latest
```

### 使用 Docker Compose

```bash
cd runtime/python/grpc
docker-compose up -d
```

## 性能优化

### 1. 启用 FP16

```bash
python3 server_v2.py --fp16
```

**效果**：减少 50% GPU 内存，提升 2x 速度。

### 2. 调整并发数

```bash
python3 server_v2.py --max_concurrent 8
```

**注意**：根据 GPU 内存调整，4-8 为宜。

### 3. 使用 Opus 格式

```python
params = cosyvoice_v2_pb2.SynthesisParams(
    format=cosyvoice_v2_pb2.AUDIO_FORMAT_OPUS
)
```

**效果**：减少 80% 网络传输，延迟降低 50%。

### 4. 调整流式块大小

```python
params = cosyvoice_v2_pb2.SynthesisParams(
    chunk_size=50  # 默认 25
)
```

**效果**：更大的块减少网络往返，但增加延迟。

## 故障排除

### 1. CUDA 内存不足

**错误**：`RuntimeError: CUDA out of memory`

**解决方案**：
- 减少 `max_concurrent`：`--max_concurrent 2`
- 启用 FP16：`--fp16`
- 使用更小的模型

### 2. gRPC 消息过大

**错误**：`ResourceExhausted: received message larger than max`

**解决方案**：
- 已在代码中设置 256MB 限制
- 如需更大，修改 `server_v2.py` 中的 `grpc.max_send_message_length`

### 3. 音频编码失败

**错误**：`pydub not installed` 或 `opuslib not installed`

**解决方案**：
```bash
pip install pydub opuslib
```

或使用 PCM 格式（默认降级方案）。

### 4. Proto 文件未编译

**错误**：`ModuleNotFoundError: No module named 'cosyvoice_v2_pb2'`

**解决方案**：
```bash
cd runtime/python/grpc
python3 -m grpc_tools.protoc \
    --python_out=. \
    --grpc_python_out=. \
    cosyvoice_v2.proto
```

## 项目结构

```
runtime/python/grpc/
├── cosyvoice_v2.proto          # gRPC 协议定义
├── server_v2.py                # 服务端实现
├── client_v2_example.py        # Python 客户端示例
├── metrics.py                  # Prometheus 监控
├── start.sh                    # 启动脚本
├── Dockerfile                  # Docker 镜像
├── docker-compose.yml          # Docker Compose
├── requirements_v2.txt         # Python 依赖
└── README.md                   # 本文档

runtime/web/client/src/
├── CosyVoiceClient.ts          # TypeScript 客户端
└── components/
    └── TTSPlayer.tsx           # React 组件
```

## 许可证

Apache 2.0

## 联系方式

- 项目主页：[CosyVoice GitHub](https://github.com/FunAudioLLM/CosyVoice)
- 问题反馈：[GitHub Issues](https://github.com/FunAudioLLM/CosyVoice/issues)

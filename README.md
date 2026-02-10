# CosyVoice

**CosyVoice** 是一个基于大语言模型的多语言零样本文本转语音（TTS）合成系统。

## 版本

- **Fun-CosyVoice 3.0**: [论文](https://arxiv.org/pdf/2505.17589) | [ModelScope](https://www.modelscope.cn/models/FunAudioLLM/Fun-CosyVoice3-0.5B-2512) | [HuggingFace](https://huggingface.co/FunAudioLLM/Fun-CosyVoice3-0.5B-2512)
- **CosyVoice 2.0**: [论文](https://arxiv.org/pdf/2412.10117) | [ModelScope](https://www.modelscope.cn/models/iic/CosyVoice2-0.5B) | [HuggingFace](https://huggingface.co/FunAudioLLM/CosyVoice2-0.5B)
- **CosyVoice 1.0**: [论文](https://funaudiollm.github.io/pdf/CosyVoice_v1.pdf) | [ModelScope](https://www.modelscope.cn/models/iic/CosyVoice-300M) | [HuggingFace](https://huggingface.co/FunAudioLLM/CosyVoice-300M)

## 核心功能

### Fun-CosyVoice 3.0

- **语言覆盖**：支持 9 种主要语言（中文、英语、日语、韩语、德语、西班牙语、法语、意大利语、俄语），18+ 种中文方言/口音（粤语、闽南语、四川话、东北话等）
- **内容一致性与自然度**：在内容一致性、说话人相似度和韵律自然度方面达到领先水平
- **发音修复**：支持中文拼音和英文 CMU 音素的发音修复，提供更强的可控性
- **文本正则化**：支持数字、特殊符号和各种文本格式的朗读，无需传统前端模块
- **双向流式**：支持文本输入流和音频输出流，延迟低至 150ms
- **指令控制**：支持语言、方言、情感、语速、音量等多种指令

### 新增：生产级 gRPC API 服务 ✨

- **gRPC 双向流**：支持实时音频流传输，延迟 < 150ms
- **全推理模式**：SFT、Zero-shot、Cross-lingual、Instruct、VC
- **多音频格式**：PCM、WAV、MP3、Opus（客户端可选）
- **前端集成**：TypeScript 客户端 + React 组件
- **完整部署**：Docker 容器化、Prometheus 监控

详细文档：[runtime/python/grpc/README.md](runtime/python/grpc/README.md)

## 性能评估

| Model | Open-Source | Model Size | test-zh<br>CER (%) ↓ | test-zh<br>SS (%) ↑ | test-en<br>WER (%) ↓ | test-en<br>SS (%) ↑ |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| Human | - | - | 1.26 | 75.5 | 2.14 | 73.4 |
| CosyVoice2 | ✅ | 0.5B | 1.45 | 75.7 | 2.57 | 65.9 |
| Fun-CosyVoice3-0.5B-2512 | ✅ | 0.5B | 1.21 | 78.0 | 2.24 | 71.8 |
| Fun-CosyVoice3-0.5B-2512_RL | ✅ | 0.5B | 0.81 | 77.4 | 1.68 | 69.5 |

## 安装

### 克隆仓库并安装依赖

```bash
git clone --recursive https://github.com/FunAudioLLM/CosyVoice.git
cd CosyVoice

# 如果子模块克隆失败，请运行以下命令直到成功
git submodule update --init --recursive
```

### 创建 Conda 环境

```bash
# 创建环境
conda create -n cosyvoice python=3.10
conda activate cosyvoice

# 安装依赖
pip install -r requirements.txt

# Ubuntu 用户
sudo apt-get install sox libsox-dev

# CentOS 用户
sudo yum install sox sox-devel
```

### 下载预训练模型

推荐下载 `Fun-CosyVoice3-0.5B` 模型以获得最佳性能。

```python
# 使用 ModelScope SDK
from modelscope import snapshot_download
snapshot_download('FunAudioLLM/Fun-CosyVoice3-0.5B-2512', local_dir='pretrained_models/Fun-CosyVoice3-0.5B')
snapshot_download('iic/CosyVoice2-0.5B', local_dir='pretrained_models/CosyVoice2-0.5B')
snapshot_download('iic/CosyVoice-300M', local_dir='pretrained_models/CosyVoice-300M')
snapshot_download('iic/CosyVoice-300M-SFT', local_dir='pretrained_models/CosyVoice-300M-SFT')
snapshot_download('iic/CosyVoice-300M-Instruct', local_dir='pretrained_models/CosyVoice-300M-Instruct')
snapshot_download('iic/CosyVoice-ttsfrd', local_dir='pretrained_models/CosyVoice-ttsfrd')

# 或使用 HuggingFace SDK（海外用户）
from huggingface_hub import snapshot_download
snapshot_download('FunAudioLLM/Fun-CosyVoice3-0.5B-2512', local_dir='pretrained_models/Fun-CosyVoice3-0.5B')
snapshot_download('FunAudioLLM/CosyVoice2-0.5B', local_dir='pretrained_models/CosyVoice2-0.5B')
snapshot_download('FunAudioLLM/CosyVoice-300M', local_dir='pretrained_models/CosyVoice-300M')
snapshot_download('FunAudioLLM/CosyVoice-300M-SFT', local_dir='pretrained_models/CosyVoice-300M-SFT')
snapshot_download('FunAudioLLM/CosyVoice-300M-Instruct', local_dir='pretrained_models/CosyVoice-300M-Instruct')
snapshot_download('FunAudioLLM/CosyVoice-ttsfrd', local_dir='pretrained_models/CosyVoice-ttsfrd')
```

可选：安装 `ttsfrd` 包以获得更好的文本正则化性能。

```bash
cd pretrained_models/CosyVoice-ttsfrd/
unzip resource.zip -d .
pip install ttsfrd_dependency-0.1-py3-none-any.whl
pip install ttsfrd-0.4.2-cp310-cp310-linux_x86_64.whl
```

## 使用方法

### 基础用法

推荐使用 `Fun-CosyVoice3-0.5B` 以获得更好的性能。

```bash
python example.py
```

### vLLM 加速

CosyVoice2/3 支持 **vLLM 0.11.x+ (V1 engine)** 和 **vLLM 0.9.0 (legacy)**。

```bash
# 创建新环境（推荐）
conda create -n cosyvoice_vllm --clone cosyvoice
conda activate cosyvoice_vllm

# 安装 vLLM
pip install vllm==v0.11.0 transformers==4.57.1 numpy==1.26.4

# 运行
python vllm_example.py
```

### Web 界面

启动 Web 演示页面：

```bash
# SFT 推理
python3 webui.py --port 50000 --model_dir pretrained_models/Fun-CosyVoice3-0.5B

# Instruct 推理
python3 webui.py --port 50000 --model_dir pretrained_models/CosyVoice-300M-Instruct
```

### 高级用法

高级用户可参考 `examples/libritts` 中的训练和推理脚本。

## 服务部署

### 方式 1：gRPC API 服务（推荐）

生产级 gRPC 服务，支持实时音频流和多推理模式。

```bash
# 安装 gRPC 依赖
pip install -r runtime/python/grpc/requirements_v2.txt

# 编译 Proto 文件
cd runtime/python/grpc
python3 -m grpc_tools.protoc --python_out=. --grpc_python_out=. cosyvoice_v2.proto

# 启动服务
python3 server_v2.py --port 50051 --max_concurrent 4 --model_dir iic/CosyVoice2-0.5B

# 测试客户端
python3 client_v2_example.py
```

**Docker 部署：**

```bash
cd runtime/python/grpc
docker-compose up -d
```

详细文档：[runtime/python/grpc/README.md](runtime/python/grpc/README.md)

### 方式 2：FastAPI 服务

```bash
cd runtime/python
docker build -t cosyvoice:v1.0 .

# gRPC 模式
docker run -d --runtime=nvidia -p 50000:50000 cosyvoice:v1.0 \
  /bin/bash -c "cd /opt/CosyVoice/CosyVoice/runtime/python/grpc && \
  python3 server.py --port 50000 --max_conc 4 --model_dir iic/CosyVoice-300M"

# FastAPI 模式
docker run -d --runtime=nvidia -p 50000:50000 cosyvoice:v1.0 \
  /bin/bash -c "cd /opt/CosyVoice/CosyVoice/runtime/python/fastapi && \
  python3 server.py --port 50000 --model_dir iic/CosyVoice-300M"
```

### 方式 3：NVIDIA TensorRT-LLM

使用 TensorRT-LLM 加速，可获得 4x 性能提升。

```bash
cd runtime/triton_trtllm
docker compose up -d
```

## 项目结构

```
CosyVoice/
├── cosyvoice/              # 核心模型代码
│   ├── cli/               # 命令行接口
│   ├── llm/               # 语言模型
│   ├── flow/              # Flow Matching 模型
│   ├── hifigan/           # HiFi-GAN 声码器
│   └── utils/             # 工具函数
├── runtime/               # 部署相关
│   ├── python/
│   │   ├── grpc/         # gRPC 服务（推荐）
│   │   ├── fastapi/      # FastAPI 服务
│   │   └── triton_trtllm/ # TensorRT-LLM
│   └── web/              # Web 客户端
├── examples/             # 示例代码
└── tools/                # 特征提取工具
```

## 致谢

1. [FunASR](https://github.com/modelscope/FunASR)
2. [FunCodec](https://github.com/modelscope/FunCodec)
3. [Matcha-TTS](https://github.com/shivammehta25/Matcha-TTS)
4. [AcademiCodec](https://github.com/yangdongchao/AcademiCodec)
5. [WeNet](https://github.com/wenet-e2e/wenet)

## 引用

如果您在研究中使用了 CosyVoice，请引用：

```bibtex
@article{du2024cosyvoice,
  title={Cosyvoice: A scalable multilingual zero-shot text-to-speech synthesizer based on supervised semantic tokens},
  author={Du, Zhihao and Chen, Qian and Zhang, Shiliang and Hu, Kai and Lu, Heng and Yang, Yexin and Hu, Hangrui and Zheng, Siqi and Gu, Yue and Ma, Ziyang and others},
  journal={arXiv preprint arXiv:2407.05407},
  year={2024}
}

@article{du2024cosyvoice2,
  title={Cosyvoice 2: Scalable streaming speech synthesis with large language models},
  author={Du, Zhihao and Wang, Yuxuan and Chen, Qian and Shi, Xian and Lv, Xiang and Zhao, Tianyu and Gao, Zhifu and Yang, Yexin and Gao, Changfeng and Wang, Hui and others},
  journal={arXiv preprint arXiv:2412.10117},
  year={2024}
}

@article{du2025cosyvoice3,
  title={CosyVoice 3: Towards In-the-wild Speech Generation via Scaling-up and Post-training},
  author={Du, Zhihao and Gao, Changfeng and Wang, Yuxuan and Yu, Fan and Zhao, Tianyu and Wang, Hao and Lv, Xiang and Wang, Hui and Shi, Xian and An, Keyu and others},
  journal={arXiv preprint arXiv:2505.17589},
  year={2025}
}
```

## 许可证

本项目采用 Apache 2.0 许可证。详见 [LICENSE](LICENSE) 文件。

## 免责声明

以上内容仅供学术目的使用，旨在展示技术能力。部分示例来源于网络，如任何内容侵犯您的权益，请联系我们删除。

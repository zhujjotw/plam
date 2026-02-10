# CosyVoice gRPC Server Docker Image
FROM nvidia/cuda:12.1.0-runtime-ubuntu22.04

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3-pip \
    ffmpeg \
    libsndfile1 \
    git \
    wget \
    && rm -rf /var/lib/apt/lists/*

# 复制项目文件
COPY requirements.txt /app/
COPY cosyvoice /app/cosyvoice/
COPY runtime/python/grpc /app/runtime/python/grpc/

# 安装 Python 依赖
RUN pip3 install --no-cache-dir -r requirements.txt

# 编译 Proto 文件
RUN cd /app/runtime/python/grpc && \
    python3 -m grpc_tools.protoc \
    --python_out=. \
    --grpc_python_out=. \
    cosyvoice_v2.proto

# 设置环境变量
ENV PYTHONPATH=/app:$PYTHONPATH
ENV CUDA_VISIBLE_DEVICES=0

# 暴露端口
EXPOSE 50051 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python3 -c "import grpc; channel = grpc.insecure_channel('localhost:50051'); stub = cosyvoice_v2_pb2_grpc.CosyVoiceServiceStub(channel); stub.HealthCheck({}); print('Healthy')" || exit 1

# 启动服务
CMD ["python3", "/app/runtime/python/grpc/server_v2.py", \
     "--port", "50051", \
     "--max_concurrent", "4", \
     "--model_dir", "iic/CosyVoice2-0.5B"]

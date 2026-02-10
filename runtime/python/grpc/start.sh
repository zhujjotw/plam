#!/bin/bash

# CosyVoice gRPC Server 启动脚本

set -e

# 配置
PORT=${PORT:-50051}
MAX_CONCURRENT=${MAX_CONCURRENT:-4}
MODEL_DIR=${MODEL_DIR:-iic/CosyVoice2-0.5B}
FP16=${FP16:-false}
LOG_LEVEL=${LOG_LEVEL:-INFO}

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查 CUDA
log_info "Checking CUDA availability..."
if command -v nvidia-smi &> /dev/null; then
    nvidia-smi
    log_info "CUDA is available"
else
    log_warn "CUDA is not available, using CPU"
    MAX_CONCURRENT=1
fi

# 检查模型
log_info "Checking model directory..."
if [ ! -d "$MODEL_DIR" ] && [[ ! "$MODEL_DIR" =~ ^iic/ ]]; then
    log_error "Model directory not found: $MODEL_DIR"
    exit 1
fi

# 编译 Proto 文件
log_info "Compiling Proto files..."
cd "$(dirname "$0")"
python3 -m grpc_tools.protoc \
    --python_out=. \
    --grpc_python_out=. \
    cosyvoice_v2.proto

# 创建日志目录
mkdir -p logs

# 启动服务
log_info "Starting CosyVoice gRPC Server..."
log_info "Port: $PORT"
log_info "Max Concurrent: $MAX_CONCURRENT"
log_info "Model: $MODEL_DIR"
log_info "FP16: $FP16"

python3 server_v2.py \
    --port $PORT \
    --max_concurrent $MAX_CONCURRENT \
    --model_dir $MODEL_DIR \
    $( [ "$FP16" = "true" ] && echo "--fp16" )

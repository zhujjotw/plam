"""
CosyVoice gRPC Server V2 - 生产级实现
支持双向流、多音频格式、全推理模式
"""
import os
import sys
import time
import uuid
import logging
from typing import Generator, Dict, Optional
from concurrent import futures
import threading
from queue import Queue
import grpc
import torch
import numpy as np
from pydantic import BaseModel, Field, validator

# 添加项目路径
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append('{}/../../..'.format(ROOT_DIR))
sys.path.append('{}/../../../third_party/Matcha-TTS'.format(ROOT_DIR))

from cosyvoice.cli.cosyvoice import AutoModel
import cosyvoice_v2_pb2
import cosyvoice_v2_pb2_grpc

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('cosyvoice_grpc.log')
    ]
)
logger = logging.getLogger(__name__)


# ============================================================================
# 数据模型
# ============================================================================

class SessionConfig(BaseModel):
    """会话配置"""
    request_id: str
    mode: str
    params: dict = Field(default_factory=dict)
    created_at: float = Field(default_factory=time.time)
    timeout: int = 300  # 5分钟超时

    @validator('timeout')
    def validate_timeout(cls, v):
        if v < 0 or v > 3600:
            raise ValueError('timeout must be between 0 and 3600 seconds')
        return v


class AudioEncoder:
    """音频编码器"""

    @staticmethod
    def encode_pcm(audio_tensor: torch.Tensor, sample_rate: int) -> bytes:
        """编码为 PCM 16-bit"""
        audio_array = audio_tensor.numpy()
        if audio_array.dtype != np.int16:
            audio_array = (audio_array * (2**15)).astype(np.int16)
        return audio_array.tobytes()

    @staticmethod
    def encode_wav(audio_tensor: torch.Tensor, sample_rate: int) -> bytes:
        """编码为 WAV 格式"""
        import io
        import wave

        audio_array = (audio_tensor.numpy() * (2**15)).astype(np.int16)

        # 创建 WAV 文件到内存
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, 'wb') as wav_file:
            wav_file.setnchannels(1)  # 单声道
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio_array.tobytes())

        return wav_buffer.getvalue()

    @staticmethod
    def encode_mp3(audio_tensor: torch.Tensor, sample_rate: int) -> bytes:
        """编码为 MP3 格式"""
        try:
            import io
            from pydub import AudioSegment

            audio_array = (audio_tensor.numpy() * (2**15)).astype(np.int16)
            audio_segment = AudioSegment(
                data=audio_array.tobytes(),
                sample_width=2,
                frame_rate=sample_rate,
                channels=1
            )

            mp3_buffer = io.BytesIO()
            audio_segment.export(mp3_buffer, format='mp3', bitrate='128k')
            return mp3_buffer.getvalue()
        except ImportError:
            logger.warning("pydub not installed, falling back to PCM")
            return AudioEncoder.encode_pcm(audio_tensor, sample_rate)
        except Exception as e:
            logger.warning(f"MP3 encoding failed: {e}, falling back to PCM")
            return AudioEncoder.encode_pcm(audio_tensor, sample_rate)

    @staticmethod
    def encode_opus(audio_tensor: torch.Tensor, sample_rate: int) -> bytes:
        """编码为 Opus 格式（低延迟）"""
        try:
            import io
            import struct
            from opuslib import Encoder

            encoder = Encoder(sample_rate, 1, application='voip')
            audio_array = (audio_tensor.numpy() * (2**15)).astype(np.int16)

            # Opus 编码（每帧 20ms）
            frame_size = int(sample_rate * 0.02)  # 20ms
            opus_data = b''

            for i in range(0, len(audio_array), frame_size):
                frame = audio_array[i:i+frame_size]
                if len(frame) < frame_size:
                    # 填充最后一个帧
                    frame = np.pad(frame, (0, frame_size - len(frame)), 'constant')
                opus_packet = encoder.encode(frame.tobytes(), frame_size)
                opus_data += struct.pack('H', len(opus_packet)) + opus_packet

            return opus_data
        except ImportError:
            logger.warning("opuslib not installed, falling back to PCM")
            return AudioEncoder.encode_pcm(audio_tensor, sample_rate)
        except Exception as e:
            logger.warning(f"Opus encoding failed: {e}, falling back to PCM")
            return AudioEncoder.encode_pcm(audio_tensor, sample_rate)

    @classmethod
    def encode(cls, audio_tensor: torch.Tensor, format: str, sample_rate: int) -> bytes:
        """根据格式编码音频"""
        encoders = {
            'AUDIO_FORMAT_PCM': cls.encode_pcm,
            'AUDIO_FORMAT_WAV': cls.encode_wav,
            'AUDIO_FORMAT_MP3': cls.encode_mp3,
            'AUDIO_FORMAT_OPUS': cls.encode_opus,
        }

        encoder_func = encoders.get(format, cls.encode_pcm)
        return encoder_func(audio_tensor, sample_rate)


class SessionManager:
    """会话管理器"""

    def __init__(self, max_sessions: int = 100, session_timeout: int = 300):
        self.sessions: Dict[str, SessionConfig] = {}
        self.max_sessions = max_sessions
        self.session_timeout = session_timeout
        self.lock = threading.Lock()
        self._start_cleanup_thread()

    def create_session(self, request_id: str, mode: str, params: dict) -> SessionConfig:
        """创建新会话"""
        with self.lock:
            # 清理过期会话
            self._cleanup_expired_sessions()

            # 检查会话数量
            if len(self.sessions) >= self.max_sessions:
                raise Exception(f"Maximum sessions {self.max_sessions} reached")

            # 创建会话
            session = SessionConfig(
                request_id=request_id,
                mode=mode,
                params=params,
                timeout=self.session_timeout
            )
            self.sessions[request_id] = session

            logger.info(f"Created session {request_id}, total sessions: {len(self.sessions)}")
            return session

    def get_session(self, request_id: str) -> Optional[SessionConfig]:
        """获取会话"""
        with self.lock:
            return self.sessions.get(request_id)

    def remove_session(self, request_id: str):
        """移除会话"""
        with self.lock:
            if request_id in self.sessions:
                del self.sessions[request_id]
                logger.info(f"Removed session {request_id}, remaining sessions: {len(self.sessions)}")

    def _cleanup_expired_sessions(self):
        """清理过期会话"""
        current_time = time.time()
        expired_ids = [
            req_id for req_id, session in self.sessions.items()
            if current_time - session.created_at > session.timeout
        ]

        for req_id in expired_ids:
            del self.sessions[req_id]
            logger.info(f"Cleaned up expired session {req_id}")

    def _start_cleanup_thread(self):
        """启动清理线程"""
        def cleanup_loop():
            while True:
                time.sleep(60)  # 每分钟清理一次
                with self.lock:
                    self._cleanup_expired_sessions()

        cleanup_thread = threading.Thread(target=cleanup_loop, daemon=True)
        cleanup_thread.start()

    def get_stats(self) -> dict:
        """获取统计信息"""
        with self.lock:
            return {
                'active_sessions': len(self.sessions),
                'max_sessions': self.max_sessions
            }


class CosyVoiceServiceImpl(cosyvoice_v2_pb2_grpc.CosyVoiceServiceServicer):
    """CosyVoice gRPC 服务实现"""

    def __init__(self, model_dir: str, max_concurrent: int = 4, fp16: bool = False):
        # 初始化模型
        logger.info(f"Loading CosyVoice model from {model_dir}")
        self.cosyvoice = AutoModel(model_dir=model_dir, fp16=fp16)
        self.sample_rate = self.cosyvoice.sample_rate
        logger.info(f"Model loaded, sample rate: {self.sample_rate}")

        # 初始化会话管理器
        self.session_manager = SessionManager(
            max_sessions=max_concurrent * 10,
            session_timeout=300
        )

        # 音频编码器
        self.audio_encoder = AudioEncoder()

        # 性能统计
        self.request_count = 0
        self.start_time = time.time()

        logger.info("CosyVoice gRPC service initialized")

    # ========================================================================
    # 非流式推理
    # ========================================================================

    def Inference(self, request, context):
        """非流式推理"""
        request_id = request.request_id or str(uuid.uuid4())
        self.request_count += 1

        logger.info(f"[{request_id}] Received inference request, mode: {request.mode}")

        try:
            # 收集所有音频数据
            audio_chunks = []
            for chunk in self._inference_generator(request):
                audio_chunks.append(chunk)

            # 合并音频
            full_audio = b''.join(audio_chunks)

            response = cosyvoice_v2_pb2.InferenceResponse(
                request_id=request_id,
                audio_data=full_audio,
                format=request.params.format or 'AUDIO_FORMAT_PCM',
                sample_rate=request.params.sample_rate or self.sample_rate,
                message="Inference completed successfully",
                success=True
            )

            logger.info(f"[{request_id}] Inference completed, audio size: {len(full_audio)} bytes")
            return response

        except Exception as e:
            logger.error(f"[{request_id}] Inference failed: {str(e)}", exc_info=True)
            return cosyvoice_v2_pb2.InferenceResponse(
                request_id=request_id,
                success=False,
                error=str(e)
            )

    # ========================================================================
    # 流式推理（双向流）
    # ========================================================================

    def StreamingInference(self, request_iterator, context):
        """流式推理（双向流）"""
        for request in request_iterator:
            request_id = request.request_id or str(uuid.uuid4())
            self.request_count += 1

            logger.info(f"[{request_id}] Received streaming request, mode: {request.mode}")

            try:
                # 创建会话
                session = self.session_manager.create_session(
                    request_id=request_id,
                    mode=request.mode,
                    params=self._extract_params(request)
                )

                # 流式生成音频
                sequence_number = 0
                for audio_chunk in self._inference_generator(request):
                    sequence_number += 1

                    response = cosyvoice_v2_pb2.StreamingResponse(
                        request_id=request_id,
                        audio_chunk=cosyvoice_v2_pb2.AudioChunk(
                            audio_data=audio_chunk,
                            sequence_number=sequence_number,
                            is_final=False
                        )
                    )
                    yield response

                # 发送完成标记
                yield cosyvoice_v2_pb2.StreamingResponse(
                    request_id=request_id,
                    audio_chunk=cosyvoice_v2_pb2.AudioChunk(
                        sequence_number=sequence_number + 1,
                        is_final=True,
                        message="Streaming completed"
                    )
                )

                # 清理会话
                self.session_manager.remove_session(request_id)

                logger.info(f"[{request_id}] Streaming completed, chunks sent: {sequence_number}")

            except Exception as e:
                logger.error(f"[{request_id}] Streaming failed: {str(e)}", exc_info=True)
                yield cosyvoice_v2_pb2.StreamingResponse(
                    request_id=request_id,
                    error=str(e)
                )
                self.session_manager.remove_session(request_id)

    # ========================================================================
    # 音频上传
    # ========================================================================

    def UploadAudio(self, request_iterator, context):
        """上传音频（用于声音克隆）"""
        audio_chunks = []
        audio_id = None
        spk_id = None

        for request in request_iterator:
            if audio_id is None:
                audio_id = request.audio_id or str(uuid.uuid4())
                spk_id = request.spk_id

            if request.HasField('audio_chunk'):
                audio_chunks.append(request.audio_chunk)

        # 合并音频
        full_audio = b''.join(audio_chunks)

        # 保存音频
        audio_dir = '/tmp/cosyvoice_uploads'
        os.makedirs(audio_dir, exist_ok=True)
        audio_path = os.path.join(audio_dir, f"{audio_id}.wav")

        # 保存为 WAV 文件
        import wave
        with wave.open(audio_path, 'wb') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(16000)
            wav_file.writeframes(full_audio)

        logger.info(f"Audio uploaded: {audio_path}, size: {len(full_audio)} bytes")

        return cosyvoice_v2_pb2.UploadAudioResponse(
            audio_id=audio_id,
            success=True,
            message="Audio uploaded successfully",
            size_bytes=len(full_audio)
        )

    # ========================================================================
    # 其他服务
    # ========================================================================

    def ListSpeakers(self, request, context):
        """列出可用说话人"""
        speakers = self.cosyvoice.list_available_spks()

        speaker_infos = []
        for spk in speakers:
            speaker_infos.append(cosyvoice_v2_pb2.SpeakerInfo(
                spk_id=spk,
                name=spk
            ))

        return cosyvoice_v2_pb2.ListSpeakersResponse(speakers=speaker_infos)

    def HealthCheck(self, request, context):
        """健康检查"""
        stats = self.session_manager.get_stats()
        uptime = time.time() - self.start_time

        # 获取模型名称
        model_name = getattr(self.cosyvoice, 'model_dir', 'unknown')

        return cosyvoice_v2_pb2.HealthResponse(
            healthy=True,
            version="2.0.0",
            model_name=model_name,
            active_sessions=stats['active_sessions']
        )

    # ========================================================================
    # 内部辅助方法
    # ========================================================================

    def _extract_params(self, request) -> dict:
        """提取请求参数"""
        params = {}

        if request.HasField('params'):
            p = request.params
            params.update({
                'speed': p.speed if p.HasField('speed') else 1.0,
                'volume': p.volume if p.HasField('volume') else 1.0,
                'format': p.format if p.HasField('format') else 'AUDIO_FORMAT_PCM',
                'sample_rate': p.sample_rate if p.HasField('sample_rate') else self.sample_rate,
                'stream': p.stream if p.HasField('stream') else True,
                'chunk_size': p.chunk_size if p.HasField('chunk_size') else 25
            })

        return params

    def _inference_generator(self, request) -> Generator[bytes, None, None]:
        """推理音频生成器"""
        params = self._extract_params(request)
        stream = params.get('stream', True)
        speed = params.get('speed', 1.0)
        output_format = params.get('format', 'AUDIO_FORMAT_PCM')
        output_sample_rate = params.get('sample_rate', self.sample_rate)

        # 路由到不同的推理模式
        if request.HasField('sft_request'):
            yield from self._inference_sft(request.sft_request, stream, speed)
        elif request.HasField('zero_shot_request'):
            yield from self._inference_zero_shot(request.zero_shot_request, stream, speed)
        elif request.HasField('cross_lingual_request'):
            yield from self._inference_cross_lingual(request.cross_lingual_request, stream, speed)
        elif request.HasField('instruct_request'):
            yield from self._inference_instruct(request.instruct_request, stream, speed)
        elif request.HasField('instruct2_request'):
            yield from self._inference_instruct2(request.instruct2_request, stream, speed)
        elif request.HasField('vc_request'):
            yield from self._inference_vc(request.vc_request, stream, speed)
        else:
            raise ValueError("Invalid request: no valid payload found")

    def _inference_sft(self, sft_request, stream, speed):
        """SFT 推理"""
        logger.info(f"SFT inference: spk_id={sft_request.spk_id}, text={sft_request.tts_text[:50]}...")

        model_output = self.cosyvoice.inference_sft(
            tts_text=sft_request.tts_text,
            spk_id=sft_request.spk_id,
            stream=stream,
            speed=speed
        )

        for chunk in model_output:
            audio_data = self.audio_encoder.encode(
                chunk['tts_speech'],
                'AUDIO_FORMAT_PCM',
                self.sample_rate
            )
            yield audio_data

    def _inference_zero_shot(self, zero_shot_request, stream, speed):
        """Zero-shot 推理"""
        logger.info(f"Zero-shot inference: text={zero_shot_request.tts_text[:50]}...")

        # 解码音频
        prompt_speech = torch.from_numpy(
            np.frombuffer(zero_shot_request.prompt_audio, dtype=np.int16)
        ).unsqueeze(dim=0).float() / (2**15)

        model_output = self.cosyvoice.inference_zero_shot(
            tts_text=zero_shot_request.tts_text,
            prompt_text=zero_shot_request.prompt_text,
            prompt_wav=prompt_speech,
            zero_shot_spk_id=zero_shot_request.zero_shot_spk_id or '',
            stream=stream,
            speed=speed
        )

        for chunk in model_output:
            audio_data = self.audio_encoder.encode(
                chunk['tts_speech'],
                'AUDIO_FORMAT_PCM',
                self.sample_rate
            )
            yield audio_data

    def _inference_cross_lingual(self, cross_lingual_request, stream, speed):
        """Cross-lingual 推理"""
        logger.info(f"Cross-lingual inference: text={cross_lingual_request.tts_text[:50]}...")

        # 解码音频
        prompt_speech = torch.from_numpy(
            np.frombuffer(cross_lingual_request.prompt_audio, dtype=np.int16)
        ).unsqueeze(dim=0).float() / (2**15)

        model_output = self.cosyvoice.inference_cross_lingual(
            tts_text=cross_lingual_request.tts_text,
            prompt_wav=prompt_speech,
            zero_shot_spk_id=cross_lingual_request.zero_shot_spk_id or '',
            stream=stream,
            speed=speed
        )

        for chunk in model_output:
            audio_data = self.audio_encoder.encode(
                chunk['tts_speech'],
                'AUDIO_FORMAT_PCM',
                self.sample_rate
            )
            yield audio_data

    def _inference_instruct(self, instruct_request, stream, speed):
        """Instruct 推理（CosyVoice 1.0）"""
        logger.info(f"Instruct inference: spk_id={instruct_request.spk_id}, "
                   f"instruct={instruct_request.instruct_text[:50]}...")

        model_output = self.cosyvoice.inference_instruct(
            tts_text=instruct_request.tts_text,
            spk_id=instruct_request.spk_id,
            instruct_text=instruct_request.instruct_text,
            stream=stream,
            speed=speed
        )

        for chunk in model_output:
            audio_data = self.audio_encoder.encode(
                chunk['tts_speech'],
                'AUDIO_FORMAT_PCM',
                self.sample_rate
            )
            yield audio_data

    def _inference_instruct2(self, instruct2_request, stream, speed):
        """Instruct2 推理（CosyVoice 2/3）"""
        logger.info(f"Instruct2 inference: instruct={instruct2_request.instruct_text[:50]}...")

        # 解码音频
        prompt_speech = torch.from_numpy(
            np.frombuffer(instruct2_request.prompt_audio, dtype=np.int16)
        ).unsqueeze(dim=0).float() / (2**15)

        model_output = self.cosyvoice.inference_instruct2(
            tts_text=instruct2_request.tts_text,
            instruct_text=instruct2_request.instruct_text,
            prompt_wav=prompt_speech,
            zero_shot_spk_id=instruct2_request.zero_shot_spk_id or '',
            stream=stream,
            speed=speed
        )

        for chunk in model_output:
            audio_data = self.audio_encoder.encode(
                chunk['tts_speech'],
                'AUDIO_FORMAT_PCM',
                self.sample_rate
            )
            yield audio_data

    def _inference_vc(self, vc_request, stream, speed):
        """Voice Conversion 推理"""
        logger.info("VC inference...")

        # 解码音频
        source_speech = torch.from_numpy(
            np.frombuffer(vc_request.source_audio, dtype=np.int16)
        ).unsqueeze(dim=0).float() / (2**15)

        prompt_speech = torch.from_numpy(
            np.frombuffer(vc_request.prompt_audio, dtype=np.int16)
        ).unsqueeze(dim=0).float() / (2**15)

        model_output = self.cosyvoice.inference_vc(
            source_wav=source_speech,
            prompt_wav=prompt_speech,
            stream=stream,
            speed=speed
        )

        for chunk in model_output:
            audio_data = self.audio_encoder.encode(
                chunk['tts_speech'],
                'AUDIO_FORMAT_PCM',
                self.sample_rate
            )
            yield audio_data


# ============================================================================
# 服务器启动
# ============================================================================

def serve(
    port: int = 50051,
    max_concurrent: int = 4,
    model_dir: str = 'iic/CosyVoice2-0.5B',
    fp16: bool = False
):
    """启动 gRPC 服务器"""
    # 创建服务器
    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=max_concurrent),
        maximum_concurrent_rpcs=max_concurrent,
        options=[
            ('grpc.max_send_message_length', 256 * 1024 * 1024),  # 256MB
            ('grpc.max_receive_message_length', 256 * 1024 * 1024),
            ('grpc.http2.max_pings_without_data', 0),
            ('grpc.http2.min_time_between_pings_ms', 10000),
            ('grpc.http2.min_ping_interval_without_data_ms', 100000),
            ('grpc.keepalive_time_ms', 30000),
            ('grpc.keepalive_timeout_ms', 5000),
            ('grpc.keepalive_permit_without_calls', True),
        ]
    )

    # 添加服务
    cosyvoice_v2_pb2_grpc.add_CosyVoiceServiceServicer_to_server(
        CosyVoiceServiceImpl(model_dir, max_concurrent, fp16),
        server
    )

    # 绑定端口
    server.add_insecure_port(f'0.0.0.0:{port}')
    server.start()

    logger.info(f"Server started on 0.0.0.0:{port}")
    logger.info(f"Max concurrent requests: {max_concurrent}")
    logger.info(f"Model: {model_dir}")

    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("Shutting down server...")
        server.stop(0)
        logger.info("Server stopped")


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='CosyVoice gRPC Server V2')
    parser.add_argument('--port', type=int, default=50051, help='Server port')
    parser.add_argument('--max_concurrent', type=int, default=4, help='Max concurrent requests')
    parser.add_argument('--model_dir', type=str, default='iic/CosyVoice2-0.5B',
                       help='Model directory or ModelScope repo ID')
    parser.add_argument('--fp16', action='store_true', help='Use FP16 precision')

    args = parser.parse_args()

    serve(
        port=args.port,
        max_concurrent=args.max_concurrent,
        model_dir=args.model_dir,
        fp16=args.fp16
    )

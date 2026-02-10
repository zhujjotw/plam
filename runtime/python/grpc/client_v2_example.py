"""
CosyVoice gRPC Client V2 - Python 示例
演示如何使用 gRPC 客户端调用 CosyVoice 服务
"""
import grpc
import numpy as np
import cosyvoice_v2_pb2
import cosyvoice_v2_pb2_grpc


class CosyVoiceClient:
    """CosyVoice gRPC 客户端"""

    def __init__(self, server_address='localhost:50051'):
        """初始化客户端"""
        self.channel = grpc.insecure_channel(
            server_address,
            options=[
                ('grpc.max_send_message_length', 256 * 1024 * 1024),
                ('grpc.max_receive_message_length', 256 * 1024 * 1024),
            ]
        )
        self.stub = cosyvoice_v2_pb2_grpc.CosyVoiceServiceStub(self.channel)

    def close(self):
        """关闭连接"""
        self.channel.close()

    def list_speakers(self):
        """列出可用说话人"""
        try:
            response = self.stub.ListSpeakers(cosyvoice_v2_pb2.Empty())
            speakers = []
            for speaker in response.speakers:
                speakers.append({
                    'spk_id': speaker.spk_id,
                    'name': speaker.name
                })
            return speakers
        except grpc.RpcError as e:
            print(f"Error listing speakers: {e}")
            return []

    def health_check(self):
        """健康检查"""
        try:
            response = self.stub.HealthCheck(cosyvoice_v2_pb2.Empty())
            return {
                'healthy': response.healthy,
                'version': response.version,
                'model_name': response.model_name,
                'active_sessions': response.active_sessions
            }
        except grpc.RpcError as e:
            print(f"Health check failed: {e}")
            return None

    def inference_sft(self, tts_text, spk_id, stream=False):
        """SFT 模式推理"""
        # 构建参数
        params = cosyvoice_v2_pb2.SynthesisParams(
            speed=1.0,
            volume=1.0,
            format=cosyvoice_v2_pb2.AUDIO_FORMAT_PCM,
            sample_rate=cosyvoice_v2_pb2.SAMPLE_RATE_22050,
            stream=stream
        )

        # 构建请求
        request = cosyvoice_v2_pb2.InferenceRequest(
            request_id="test_sft_001",
            mode=cosyvoice_v2_pb2.INFERENCE_MODE_SFT,
            sft_request=cosyvoice_v2_pb2.SFTRequest(
                spk_id=spk_id,
                tts_text=tts_text,
                params=params
            )
        )

        try:
            # 非流式调用
            if not stream:
                response = self.stub.Inference(request)
                if response.success:
                    return {
                        'audio_data': response.audio_data,
                        'format': response.format,
                        'sample_rate': response.sample_rate
                    }
                else:
                    print(f"Inference failed: {response.error}")
                    return None
            else:
                # 流式调用
                audio_chunks = []
                for response in self.stub.StreamingInference(iter([request])):
                    if response.audio_chunk:
                        if response.audio_chunk.audio_data:
                            audio_chunks.append(response.audio_chunk.audio_data)
                        if response.audio_chunk.is_final:
                            break
                    elif response.error:
                        print(f"Streaming error: {response.error}")
                        return None

                return {
                    'audio_data': b''.join(audio_chunks),
                    'format': 'AUDIO_FORMAT_PCM',
                    'sample_rate': 22050
                }

        except grpc.RpcError as e:
            print(f"gRPC error: {e}")
            return None

    def inference_zero_shot(self, tts_text, prompt_text, prompt_audio_file, stream=False):
        """Zero-shot 模式推理"""
        # 读取提示音频
        try:
            with open(prompt_audio_file, 'rb') as f:
                prompt_audio = f.read()
        except FileNotFoundError:
            print(f"Audio file not found: {prompt_audio_file}")
            return None

        # 构建参数
        params = cosyvoice_v2_pb2.SynthesisParams(
            speed=1.0,
            volume=1.0,
            format=cosyvoice_v2_pb2.AUDIO_FORMAT_PCM,
            sample_rate=cosyvoice_v2_pb2.SAMPLE_RATE_22050,
            stream=stream
        )

        # 构建请求
        request = cosyvoice_v2_pb2.InferenceRequest(
            request_id="test_zero_shot_001",
            mode=cosyvoice_v2_pb2.INFERENCE_MODE_ZERO_SHOT,
            zero_shot_request=cosyvoice_v2_pb2.ZeroShotRequest(
                tts_text=tts_text,
                prompt_text=prompt_text,
                prompt_audio=prompt_audio,
                zero_shot_spk_id="",
                params=params
            )
        )

        try:
            # 非流式调用
            if not stream:
                response = self.stub.Inference(request)
                if response.success:
                    return {
                        'audio_data': response.audio_data,
                        'format': response.format,
                        'sample_rate': response.sample_rate
                    }
                else:
                    print(f"Inference failed: {response.error}")
                    return None
            else:
                # 流式调用
                audio_chunks = []
                for response in self.stub.StreamingInference(iter([request])):
                    if response.audio_chunk:
                        if response.audio_chunk.audio_data:
                            audio_chunks.append(response.audio_chunk.audio_data)
                        if response.audio_chunk.is_final:
                            break
                    elif response.error:
                        print(f"Streaming error: {response.error}")
                        return None

                return {
                    'audio_data': b''.join(audio_chunks),
                    'format': 'AUDIO_FORMAT_PCM',
                    'sample_rate': 22050
                }

        except grpc.RpcError as e:
            print(f"gRPC error: {e}")
            return None

    def upload_audio(self, audio_file):
        """上传音频文件"""
        try:
            # 读取音频
            with open(audio_file, 'rb') as f:
                audio_data = f.read()

            # 分块上传（每块 64KB）
            CHUNK_SIZE = 64 * 1024
            call = self.stub.UploadAudio()

            for i in range(0, len(audio_data), CHUNK_SIZE):
                chunk = audio_data[i:i+CHUNK_SIZE]

                request = cosyvoice_v2_pb2.UploadAudioRequest(
                    audio_id=f"audio_{i}",
                    spk_id="",
                    audio_chunk=chunk
                )

                call.write(request)

            # 结束发送并接收响应
            response = call.done()
            return {
                'audio_id': response.audio_id,
                'success': response.success,
                'size_bytes': response.size_bytes
            }

        except FileNotFoundError:
            print(f"Audio file not found: {audio_file}")
            return None
        except grpc.RpcError as e:
            print(f"gRPC error: {e}")
            return None


def save_audio(audio_data, output_file, sample_rate=22050):
    """保存音频到文件"""
    try:
        import wave
        import struct

        # PCM 16-bit 解码
        num_samples = len(audio_data) // 2
        with wave.open(output_file, 'wb') as wav_file:
            wav_file.setnchannels(1)  # 单声道
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio_data)

        print(f"Audio saved to: {output_file}")
        return True
    except Exception as e:
        print(f"Failed to save audio: {e}")
        return False


def main():
    """主函数 - 示例用法"""
    # 创建客户端
    client = CosyVoiceClient('localhost:50051')

    try:
        # 1. 健康检查
        print("=" * 60)
        print("1. Health Check")
        print("=" * 60)
        health = client.health_check()
        if health:
            print(f"Healthy: {health['healthy']}")
            print(f"Version: {health['version']}")
            print(f"Model: {health['model_name']}")
            print(f"Active Sessions: {health['active_sessions']}")
        else:
            print("Health check failed")
            return

        # 2. 列出可用说话人
        print("\n" + "=" * 60)
        print("2. List Speakers")
        print("=" * 60)
        speakers = client.list_speakers()
        if speakers:
            print(f"Found {len(speakers)} speakers:")
            for i, speaker in enumerate(speakers[:10]):  # 只显示前 10 个
                print(f"  {i+1}. {speaker['spk_id']}: {speaker['name']}")
        else:
            print("No speakers found")
            return

        # 3. SFT 推理（非流式）
        print("\n" + "=" * 60)
        print("3. SFT Inference (Non-streaming)")
        print("=" * 60)
        result = client.inference_sft(
            tts_text="你好，这是CosyVoice语音合成测试。",
            spk_id=speakers[0]['spk_id'],
            stream=False
        )

        if result:
            print(f"Audio format: {result['format']}")
            print(f"Sample rate: {result['sample_rate']}")
            print(f"Audio size: {len(result['audio_data'])} bytes")

            # 保存音频
            output_file = 'output_sft.wav'
            if save_audio(result['audio_data'], output_file, result['sample_rate']):
                print(f"✓ SFT inference completed")
        else:
            print("✗ SFT inference failed")
            return

        # 4. SFT 推理（流式）
        print("\n" + "=" * 60)
        print("4. SFT Inference (Streaming)")
        print("=" * 60)
        result = client.inference_sft(
            tts_text="这是流式语音合成测试。",
            spk_id=speakers[0]['spk_id'],
            stream=True
        )

        if result:
            output_file = 'output_sft_stream.wav'
            if save_audio(result['audio_data'], output_file, result['sample_rate']):
                print(f"✓ Streaming SFT inference completed")
        else:
            print("✗ Streaming SFT inference failed")

        print("\n" + "=" * 60)
        print("All tests completed!")
        print("=" * 60)

    finally:
        # 关闭客户端
        client.close()


if __name__ == '__main__':
    main()

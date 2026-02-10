/**
 * CosyVoice gRPC Client for Web Applications
 * 支持实时流式播放、录音上传、参数调节
 */

import grpc, { ClientReadableStream, ClientWritableStream } from '@grpc/grpc-js';
import { loadSync } from '@grpc/proto-loader';
import { EventEmitter } from 'events';

// Proto 加载配置
const PROTO_PATH = __dirname + '/../../../protos/cosyvoice_v2.proto';
const packageDefinition = loadSync(PROTO_PATH, {
  keepCase: true,
  longs: String,
  enums: String,
  defaults: true,
  oneofs: true
});

const cosyvoiceProto = grpc.loadPackageDefinition(packageDefinition).cosyvoice.v2;

// 音频格式枚举
export enum AudioFormat {
  UNKNOWN = 'AUDIO_FORMAT_UNKNOWN',
  PCM = 'AUDIO_FORMAT_PCM',
  WAV = 'AUDIO_FORMAT_WAV',
  MP3 = 'AUDIO_FORMAT_MP3',
  OPUS = 'AUDIO_FORMAT_OPUS'
}

// 采样率枚举
export enum SampleRate {
  RATE_16000 = 16000,
  RATE_22050 = 22050,
  RATE_24000 = 24000,
  RATE_44100 = 44100,
  RATE_48000 = 48000
}

// 推理模式枚举
export enum InferenceMode {
  SFT = 'INFERENCE_MODE_SFT',
  ZERO_SHOT = 'INFERENCE_MODE_ZERO_SHOT',
  CROSS_LINGUAL = 'INFERENCE_MODE_CROSS_LINGUAL',
  INSTRUCT = 'INFERENCE_MODE_INSTRUCT',
  INSTRUCT2 = 'INFERENCE_MODE_INSTRUCT2',
  VC = 'INFERENCE_MODE_VC'
}

// 合成参数接口
export interface SynthesisParams {
  speed?: number;        // 语速，默认 1.0，范围 0.5-2.0
  volume?: number;       // 音量，默认 1.0，范围 0.5-2.0
  format?: AudioFormat;  // 输出音频格式
  sampleRate?: SampleRate; // 输出采样率
  stream?: boolean;      // 是否流式输出
  chunkSize?: number;    // 流式输出块大小
}

// 客户端配置接口
export interface ClientConfig {
  serverAddress: string; // gRPC 服务器地址
  maxReceiveMessageLength?: number; // 最大接收消息大小
  maxSendMessageLength?: number; // 最大发送消息大小
}

// 音频播放器类
class AudioPlayer extends EventEmitter {
  private audioContext: AudioContext;
  private audioQueue: AudioBuffer[] = [];
  private isPlaying: boolean = false;
  private sampleRate: number;

  constructor(sampleRate: number = 24000) {
    super();
    this.audioContext = new AudioContext({ sampleRate: 48000 });
    this.sampleRate = sampleRate;
  }

  /**
   * 添加音频数据到队列
   */
  addAudioData(audioData: Buffer, format: AudioFormat): void {
    this.decodeAudio(audioData, format).then(audioBuffer => {
      this.audioQueue.push(audioBuffer);
      this.playNext();
    }).catch(error => {
      this.emit('error', error);
    });
  }

  /**
   * 解码音频数据
   */
  private async decodeAudio(audioData: Buffer, format: AudioFormat): Promise<AudioBuffer> {
    if (format === AudioFormat.PCM) {
      // PCM 16-bit 解码
      const int16Array = new Int16Array(
        audioData.buffer,
        audioData.byteOffset,
        audioData.byteLength / Int16Array.BYTES_PER_ELEMENT
      );
      const float32Array = new Float32Array(int16Array.length);
      for (let i = 0; i < int16Array.length; i++) {
        float32Array[i] = int16Array[i] / 32768.0;
      }
      const audioBuffer = this.audioContext.createBuffer(1, float32Array.length, this.sampleRate);
      audioBuffer.copyToChannel(float32Array, 0);
      return audioBuffer;
    } else {
      // 其他格式使用 AudioContext 解码
      return await this.audioContext.decodeAudioData(
        audioData.buffer.slice(audioData.byteOffset, audioData.byteOffset + audioData.byteLength)
      );
    }
  }

  /**
   * 播放下一个音频
   */
  private playNext(): void {
    if (this.isPlaying || this.audioQueue.length === 0) {
      return;
    }

    this.isPlaying = true;
    const audioBuffer = this.audioQueue.shift();

    const source = this.audioContext.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(this.audioContext.destination);

    source.onended = () => {
      this.isPlaying = false;
      this.emit('chunkPlayed', audioBuffer.duration);
      this.playNext();
    };

    source.start();
    this.emit('chunkPlaying', audioBuffer.duration);
  }

  /**
   * 停止播放
   */
  stop(): void {
    this.audioQueue = [];
    this.isPlaying = false;
    if (this.audioContext.state !== 'closed') {
      this.audioContext.suspend();
    }
  }

  /**
   * 恢复播放
   */
  resume(): void {
    if (this.audioContext.state === 'suspended') {
      this.audioContext.resume();
    }
    this.playNext();
  }

  /**
   * 销毁播放器
   */
  destroy(): void {
    this.stop();
    this.audioContext.close();
  }
}

// CosyVoice 客户端类
export class CosyVoiceClient extends EventEmitter {
  private client: any;
  private config: ClientConfig;
  private players: Map<string, AudioPlayer> = new Map();

  constructor(config: ClientConfig) {
    super();
    this.config = config;
    this.client = new cosyvoiceProto.CosyVoiceService(
      config.serverAddress,
      grpc.credentials.createInsecure(),
      {
        'grpc.max_receive_message_length': config.maxReceiveMessageLength || 256 * 1024 * 1024,
        'grpc.max_send_message_length': config.maxSendMessageLength || 256 * 1024 * 1024,
      }
    );
  }

  /**
   * 非流式推理
   */
  async inference(
    mode: InferenceMode,
    payload: any,
    params: SynthesisParams = {}
  ): Promise<Buffer> {
    return new Promise((resolve, reject) => {
      const request = {
        request_id: this.generateRequestId(),
        mode: mode,
        params: this.buildParams(params),
        ...this.buildPayload(mode, payload)
      };

      this.client.inference(request, (error: Error, response: any) => {
        if (error) {
          this.emit('error', error);
          return reject(error);
        }

        if (!response.success) {
          const error = new Error(response.error || 'Inference failed');
          this.emit('error', error);
          return reject(error);
        }

        this.emit('completed', response.request_id);
        resolve(Buffer.from(response.audio_data));
      });
    });
  }

  /**
   * 流式推理（实时播放）
   */
  async streamingInference(
    mode: InferenceMode,
    payload: any,
    params: SynthesisParams = {},
    autoPlay: boolean = true
  ): Promise<string> {
    const requestId = this.generateRequestId();

    // 创建音频播放器
    if (autoPlay) {
      const player = new AudioPlayer(params.sampleRate || 24000);
      player.on('chunkPlaying', (duration) => {
        this.emit('audioPlaying', requestId, duration);
      });
      player.on('chunkPlayed', (duration) => {
        this.emit('audioPlayed', requestId, duration);
      });
      player.on('error', (error) => {
        this.emit('error', error);
      });
      this.players.set(requestId, player);
    }

    // 创建流式调用
    const call = this.client.streamingInference();

    // 监听响应
    call.on('data', (response: any) => {
      if (response.error) {
        this.emit('error', new Error(response.error));
        return;
      }

      if (response.status) {
        this.emit('status', requestId, response.status);
        return;
      }

      if (response.audio_chunk) {
        const { audio_data, is_final, sequence_number } = response.audio_chunk;

        if (audio_data && audio_data.length > 0) {
          const audioBuffer = Buffer.from(audio_data);

          // 自动播放
          if (autoPlay) {
            const player = this.players.get(requestId);
            if (player) {
              player.addAudioData(audioBuffer, params.format || AudioFormat.PCM);
            }
          }

          // 触发事件
          this.emit('audioChunk', requestId, audioBuffer, sequence_number);
        }

        if (is_final) {
          this.emit('streamingCompleted', requestId);
          this.players.delete(requestId);
        }
      }
    });

    call.on('end', () => {
      this.emit('streamingEnded', requestId);
      this.players.delete(requestId);
    });

    call.on('error', (error: Error) => {
      this.emit('error', error);
      this.players.delete(requestId);
    });

    // 发送请求
    const request = {
      request_id: requestId,
      mode: mode,
      params: this.buildParams(params),
      ...this.buildPayload(mode, payload)
    };

    call.write(request);
    call.end();

    this.emit('streamingStarted', requestId);
    return requestId;
  }

  /**
   * SFT 模式推理
   */
  async sft(
    spkId: string,
    ttsText: string,
    params: SynthesisParams = {}
  ): Promise<Buffer> {
    return this.inference(InferenceMode.SFT, { spk_id: spkId, tts_text: ttsText }, params);
  }

  /**
   * 流式 SFT 推理
   */
  async streamingSft(
    spkId: string,
    ttsText: string,
    params: SynthesisParams = {},
    autoPlay: boolean = true
  ): Promise<string> {
    return this.streamingInference(
      InferenceMode.SFT,
      { spk_id: spkId, tts_text: ttsText },
      params,
      autoPlay
    );
  }

  /**
   * Zero-shot 模式推理
   */
  async zeroShot(
    ttsText: string,
    promptText: string,
    promptAudio: Buffer,
    params: SynthesisParams = {}
  ): Promise<Buffer> {
    return this.inference(
      InferenceMode.ZERO_SHOT,
      {
        tts_text: ttsText,
        prompt_text: promptText,
        prompt_audio: promptAudio
      },
      params
    );
  }

  /**
   * 流式 Zero-shot 推理
   */
  async streamingZeroShot(
    ttsText: string,
    promptText: string,
    promptAudio: Buffer,
    params: SynthesisParams = {},
    autoPlay: boolean = true
  ): Promise<string> {
    return this.streamingInference(
      InferenceMode.ZERO_SHOT,
      {
        tts_text: ttsText,
        prompt_text: promptText,
        prompt_audio: promptAudio
      },
      params,
      autoPlay
    );
  }

  /**
   * 上传音频（用于声音克隆）
   */
  async uploadAudio(
    audioData: Buffer,
    audioId?: string,
    spkId?: string
  ): Promise<{ audioId: string; success: boolean }> {
    return new Promise((resolve, reject) => {
      const call = this.client.uploadAudio();

      call.on('data', (response: any) => {
        if (response.success) {
          this.emit('audioUploaded', response.audio_id);
          resolve({
            audioId: response.audio_id,
            success: response.success
          });
        } else {
          reject(new Error(response.message || 'Upload failed'));
        }
      });

      call.on('error', (error: Error) => {
        this.emit('error', error);
        reject(error);
      });

      // 分块上传（每块 64KB）
      const CHUNK_SIZE = 64 * 1024;
      for (let i = 0; i < audioData.length; i += CHUNK_SIZE) {
        const chunk = audioData.slice(i, Math.min(i + CHUNK_SIZE, audioData.length));

        const request = {
          audio_id: audioId || this.generateRequestId(),
          spk_id: spkId || '',
          audio_chunk: chunk
        };

        call.write(request);
      }

      call.end();
    });
  }

  /**
   * 列出可用说话人
   */
  async listSpeakers(): Promise<Array<{ spkId: string; name: string }>> {
    return new Promise((resolve, reject) => {
      this.client.listSpeakers({}, (error: Error, response: any) => {
        if (error) {
          this.emit('error', error);
          return reject(error);
        }

        const speakers = response.speakers.map((s: any) => ({
          spkId: s.spk_id,
          name: s.name
        }));

        resolve(speakers);
      });
    });
  }

  /**
   * 健康检查
   */
  async healthCheck(): Promise<{
    healthy: boolean;
    version: string;
    modelName: string;
    activeSessions: number;
  }> {
    return new Promise((resolve, reject) => {
      this.client.healthCheck({}, (error: Error, response: any) => {
        if (error) {
          this.emit('error', error);
          return reject(error);
        }

        resolve({
          healthy: response.healthy,
          version: response.version,
          modelName: response.model_name,
          activeSessions: response.active_sessions
        });
      });
    });
  }

  /**
   * 停止播放
   */
  stopPlayback(requestId: string): void {
    const player = this.players.get(requestId);
    if (player) {
      player.stop();
      this.players.delete(requestId);
    }
  }

  /**
   * 生成请求 ID
   */
  private generateRequestId(): string {
    return `req_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  /**
   * 构建参数对象
   */
  private buildParams(params: SynthesisParams): any {
    return {
      speed: params.speed || 1.0,
      volume: params.volume || 1.0,
      format: params.format || AudioFormat.PCM,
      sample_rate: params.sampleRate || 24000,
      stream: params.stream !== false,
      chunk_size: params.chunkSize || 25
    };
  }

  /**
   * 构建请求负载
   */
  private buildPayload(mode: InferenceMode, payload: any): any {
    switch (mode) {
      case InferenceMode.SFT:
        return { sft_request: payload };
      case InferenceMode.ZERO_SHOT:
        return { zero_shot_request: payload };
      case InferenceMode.CROSS_LINGUAL:
        return { cross_lingual_request: payload };
      case InferenceMode.INSTRUCT:
        return { instruct_request: payload };
      case InferenceMode.INSTRUCT2:
        return { instruct2_request: payload };
      case InferenceMode.VC:
        return { vc_request: payload };
      default:
        throw new Error(`Invalid inference mode: ${mode}`);
    }
  }

  /**
   * 关闭客户端
   */
  close(): void {
    this.players.forEach(player => player.destroy());
    this.players.clear();
    grpc.closeClient(this.client);
  }
}

// 导出录音工具类
export class AudioRecorder {
  private mediaRecorder: MediaRecorder | null = null;
  private audioChunks: Blob[] = [];

  /**
   * 开始录音
   */
  async startRecording(constraints: MediaStreamConstraints = { audio: true }): Promise<void> {
    try {
      const stream = await navigator.mediaDevices.getUserMedia(constraints);
      this.mediaRecorder = new MediaRecorder(stream);
      this.audioChunks = [];

      this.mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          this.audioChunks.push(event.data);
        }
      };

      this.mediaRecorder.start();
    } catch (error) {
      throw new Error(`Failed to start recording: ${error}`);
    }
  }

  /**
   * 停止录音
   */
  async stopRecording(): Promise<Buffer> {
    return new Promise((resolve, reject) => {
      if (!this.mediaRecorder) {
        return reject(new Error('No active recording'));
      }

      this.mediaRecorder.onstop = async () => {
        const audioBlob = new Blob(this.audioChunks, { type: 'audio/webm' });
        const audioBuffer = await audioBlob.arrayBuffer();
        resolve(Buffer.from(audioBuffer));

        // 停止所有音频轨道
        this.mediaRecorder!.stream.getTracks().forEach(track => track.stop());
        this.mediaRecorder = null;
      };

      this.mediaRecorder.stop();
    });
  }

  /**
   * 取消录音
   */
  cancelRecording(): void {
    if (this.mediaRecorder && this.mediaRecorder.state !== 'inactive') {
      this.mediaRecorder.stop();
      this.mediaRecorder.stream.getTracks().forEach(track => track.stop());
      this.mediaRecorder = null;
    }
    this.audioChunks = [];
  }
}

/**
 * CosyVoice TTS 播放器组件
 * 实时文字转语音、参数调节、录音上传
 */

import React, { useState, useEffect, useRef } from 'react';
import {
  CosyVoiceClient,
  AudioRecorder,
  InferenceMode,
  AudioFormat,
  SampleRate
} from '../CosyVoiceClient';

interface TTSPlayerProps {
  serverAddress: string;
  defaultSpeaker?: string;
}

export const TTSPlayer: React.FC<TTSPlayerProps> = ({
  serverAddress,
  defaultSpeaker = '中文女'
}) => {
  // 状态管理
  const [text, setText] = useState('');
  const [isPlaying, setIsPlaying] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [speakers, setSpeakers] = useState<Array<{ spkId: string; name: string }>>([]);
  const [selectedSpeaker, setSelectedSpeaker] = useState(defaultSpeaker);
  const [speed, setSpeed] = useState(1.0);
  const [volume, setVolume] = useState(1.0);
  const [format, setFormat] = useState(AudioFormat.PCM);
  const [sampleRate, setSampleRate] = useState(SampleRate.RATE_24000);
  const [status, setStatus] = useState('');
  const [uploadedAudioId, setUploadedAudioId] = useState('');

  // 客户端和录音器引用
  const clientRef = useRef<CosyVoiceClient | null>(null);
  const recorderRef = useRef<AudioRecorder | null>(null);
  const currentRequestIdRef = useRef<string>('');

  // 初始化客户端
  useEffect(() => {
    const client = new CosyVoiceClient({
      serverAddress: serverAddress
    });

    clientRef.current = client;
    recorderRef.current = new AudioRecorder();

    // 加载说话人列表
    loadSpeakers(client);

    // 监听事件
    client.on('audioPlaying', (requestId, duration) => {
      if (requestId === currentRequestIdRef.current) {
        setStatus(`正在播放... (${duration.toFixed(2)}s)`);
      }
    });

    client.on('streamingCompleted', (requestId) => {
      if (requestId === currentRequestIdRef.current) {
        setIsPlaying(false);
        setStatus('播放完成');
      }
    });

    client.on('error', (error) => {
      console.error('TTS Error:', error);
      setStatus(`错误: ${error.message}`);
      setIsPlaying(false);
    });

    return () => {
      client.close();
    };
  }, [serverAddress]);

  // 加载说话人列表
  const loadSpeakers = async (client: CosyVoiceClient) => {
    try {
      const speakerList = await client.listSpeakers();
      setSpeakers(speakerList);
    } catch (error) {
      console.error('Failed to load speakers:', error);
    }
  };

  // 开始语音合成
  const handleStart = async () => {
    if (!text.trim()) {
      setStatus('请输入文本');
      return;
    }

    if (!clientRef.current) return;

    setIsPlaying(true);
    setStatus('正在生成语音...');

    try {
      // 流式 SFT 推理
      const requestId = await clientRef.current.streamingSft(
        selectedSpeaker,
        text,
        {
          speed,
          volume,
          format,
          sampleRate
        },
        true // 自动播放
      );

      currentRequestIdRef.current = requestId;
      setStatus('开始流式播放...');
    } catch (error: any) {
      console.error('TTS failed:', error);
      setStatus(`合成失败: ${error.message}`);
      setIsPlaying(false);
    }
  };

  // 停止播放
  const handleStop = () => {
    if (clientRef.current && currentRequestIdRef.current) {
      clientRef.current.stopPlayback(currentRequestIdRef.current);
      setIsPlaying(false);
      setStatus('已停止');
    }
  };

  // 开始录音
  const handleStartRecording = async () => {
    if (!recorderRef.current) return;

    try {
      await recorderRef.current.startRecording();
      setIsRecording(true);
      setStatus('正在录音...');
    } catch (error: any) {
      console.error('Failed to start recording:', error);
      setStatus(`录音失败: ${error.message}`);
    }
  };

  // 停止录音
  const handleStopRecording = async () => {
    if (!recorderRef.current || !clientRef.current) return;

    try {
      const audioBuffer = await recorderRef.current.stopRecording();
      setIsRecording(false);
      setStatus('正在上传音频...');

      // 上传音频
      const result = await clientRef.current.uploadAudio(audioBuffer);
      setUploadedAudioId(result.audioId);
      setStatus(`音频已上传: ${result.audioId}`);
    } catch (error: any) {
      console.error('Failed to upload audio:', error);
      setStatus(`上传失败: ${error.message}`);
      setIsRecording(false);
    }
  };

  // 使用录音进行 Zero-shot 合成
  const handleZeroShotWithRecording = async () => {
    if (!text.trim() || !uploadedAudioId) {
      setStatus('请输入文本并先上传录音');
      return;
    }

    setStatus('Zero-shot 合成需要提示文本，请在下方输入');
  };

  return (
    <div className="tts-player">
      <h2>CosyVoice 文字转语音</h2>

      {/* 文本输入 */}
      <div className="text-input-section">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="请输入要转换的文本..."
          rows={6}
          disabled={isPlaying}
        />
      </div>

      {/* 说话人选择 */}
      <div className="speaker-section">
        <label>说话人:</label>
        <select
          value={selectedSpeaker}
          onChange={(e) => setSelectedSpeaker(e.target.value)}
          disabled={isPlaying}
        >
          {speakers.map((speaker) => (
            <option key={speaker.spkId} value={speaker.spkId}>
              {speaker.name}
            </option>
          ))}
        </select>
      </div>

      {/* 参数调节 */}
      <div className="params-section">
        <div className="param-control">
          <label>语速: {speed.toFixed(1)}x</label>
          <input
            type="range"
            min="0.5"
            max="2.0"
            step="0.1"
            value={speed}
            onChange={(e) => setSpeed(parseFloat(e.target.value))}
            disabled={isPlaying}
          />
        </div>

        <div className="param-control">
          <label>音量: {volume.toFixed(1)}x</label>
          <input
            type="range"
            min="0.5"
            max="2.0"
            step="0.1"
            value={volume}
            onChange={(e) => setVolume(parseFloat(e.target.value))}
            disabled={isPlaying}
          />
        </div>

        <div className="param-control">
          <label>音频格式:</label>
          <select
            value={format}
            onChange={(e) => setFormat(e.target.value as AudioFormat)}
            disabled={isPlaying}
          >
            <option value={AudioFormat.PCM}>PCM</option>
            <option value={AudioFormat.WAV}>WAV</option>
            <option value={AudioFormat.MP3}>MP3</option>
            <option value={AudioFormat.OPUS}>Opus</option>
          </select>
        </div>

        <div className="param-control">
          <label>采样率:</label>
          <select
            value={sampleRate}
            onChange={(e) => setSampleRate(Number(e.target.value) as SampleRate)}
            disabled={isPlaying}
          >
            <option value={SampleRate.RATE_16000}>16000 Hz</option>
            <option value={SampleRate.RATE_22050}>22050 Hz</option>
            <option value={SampleRate.RATE_24000}>24000 Hz</option>
            <option value={SampleRate.RATE_44100}>44100 Hz</option>
            <option value={SampleRate.RATE_48000}>48000 Hz</option>
          </select>
        </div>
      </div>

      {/* 控制按钮 */}
      <div className="controls-section">
        <button
          onClick={handleStart}
          disabled={isPlaying || !text.trim()}
          className="start-button"
        >
          {isPlaying ? '播放中...' : '开始合成'}
        </button>

        <button
          onClick={handleStop}
          disabled={!isPlaying}
          className="stop-button"
        >
          停止
        </button>

        <button
          onClick={handleStartRecording}
          disabled={isRecording}
          className="record-button"
        >
          {isRecording ? '录音中...' : '录音'}
        </button>

        <button
          onClick={handleStopRecording}
          disabled={!isRecording}
          className="stop-record-button"
        >
          停止录音
        </button>
      </div>

      {/* 状态显示 */}
      <div className="status-section">
        <p>状态: {status}</p>
      </div>

      {/* 样式 */}
      <style jsx>{`
        .tts-player {
          max-width: 600px;
          margin: 0 auto;
          padding: 20px;
          font-family: Arial, sans-serif;
        }

        .text-input-section textarea {
          width: 100%;
          padding: 10px;
          font-size: 16px;
          border: 1px solid #ccc;
          border-radius: 4px;
          resize: vertical;
        }

        .speaker-section,
        .params-section {
          margin-top: 20px;
        }

        .param-control {
          margin-bottom: 10px;
        }

        .param-control label {
          display: inline-block;
          width: 100px;
        }

        .param-control input[type="range"] {
          width: 200px;
        }

        .controls-section {
          margin-top: 20px;
        }

        .controls-section button {
          margin-right: 10px;
          padding: 10px 20px;
          font-size: 16px;
          border: none;
          border-radius: 4px;
          cursor: pointer;
        }

        .start-button {
          background-color: #4CAF50;
          color: white;
        }

        .stop-button {
          background-color: #f44336;
          color: white;
        }

        .record-button {
          background-color: #2196F3;
          color: white;
        }

        .stop-record-button {
          background-color: #FF9800;
          color: white;
        }

        .controls-section button:disabled {
          background-color: #cccccc;
          cursor: not-allowed;
        }

        .status-section {
          margin-top: 20px;
          padding: 10px;
          background-color: #f5f5f5;
          border-radius: 4px;
        }
      `}</style>
    </div>
  );
};

export default TTSPlayer;

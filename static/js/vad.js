/**
 * VAD (Voice Activity Detection) 模块
 * 基于 Web Audio API 的 RMS 音量检测
 * 
 * 流程：
 * 1. 开始录音 → 启动超时计时器
 * 2. 静音 > 特定秒 → 结束录音 → TTS 开始 → 关闭麦克风 + 关闭超时计时器
 * 3. TTS 播放结束 → 开始录音 + 启动超时计时器
 * 4. 如此循环
 */

class VADDetector {
    constructor() {
        this.audioContext = null;
        this.analyser = null;
        this.mediaStream = null;
        this.isListening = false;
        this.isSpeaking = false;
        this.animationFrameId = null;

        this.config = {
            silenceThreshold: 0.03,
            speechThreshold: 0.03,
            silenceDuration: 1500,
            minSpeechDuration: 400,
            sampleRate: 16000,
            noSpeechTimeout: 10000  // 10秒无声音超时
        };

        this.silenceTimer = null;
        this.speechStartTime = null;
        this.audioChunks = [];
        this.mediaRecorder = null;
        this.listeningStartTime = null;
        this.hasSpoken = false;
        this.noSpeechTimeoutId = null;  // 超时计时器 ID

        // 标准模式麦克风按钮
        this.recordBtn = document.getElementById('record-btn');
        this.recordIconEl = document.getElementById('record-icon-i');
        this.statusIndicator = document.getElementById('vad-status-indicator');
        this.statusText = this.statusIndicator?.querySelector('.vad-status-text');

        // 沉浸式模式麦克风按钮
        this.immersiveRecordBtn = document.getElementById('immersive-record-btn');
        this.immersiveRecordIcon = document.getElementById('immersive-record-icon');

        this.onSpeechStart = null;
        this.onSpeechEnd = null;
        this.onError = null;

        this.bindEvents();
    }

    bindEvents() {
        // 标准模式麦克风
        if (this.recordBtn) {
            this.recordBtn.addEventListener('click', () => this.toggle());
        }
        // 沉浸式模式麦克风
        if (this.immersiveRecordBtn) {
            this.immersiveRecordBtn.addEventListener('click', () => this.toggle());
        }
    }

    async toggle() {
        // 如果 TTS 正在播放，强制打断并开始新的录音
        if (window.ttsPlayer && window.ttsPlayer.ttsStarted) {
            console.log('🎯 用户点击麦克风，强制打断 TTS');
            // 打断 TTS
            window.ttsPlayer.interrupt();
            // 等待一小段时间让 TTS 完全停止
            await new Promise(resolve => setTimeout(resolve, 100));
            // 开始新的录音
            await this.start();
            return;
        }
        
        if (this.isListening) {
            await this.stop();
        } else {
            await this.start();
        }
    }

    async start() {
        if (this.isListening) return;

        try {
            this.updateStatus('requesting', '请求麦克风权限...');
            
            this.mediaStream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    sampleRate: this.config.sampleRate,
                    channelCount: 1,
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true
                }
            });

            this.audioContext = new (window.AudioContext || window.webkitAudioContext)({
                sampleRate: this.config.sampleRate
            });

            const source = this.audioContext.createMediaStreamSource(this.mediaStream);
            this.analyser = this.audioContext.createAnalyser();
            this.analyser.fftSize = 512;
            this.analyser.smoothingTimeConstant = 0.3;
            source.connect(this.analyser);

            this.setupMediaRecorder();

            this.isListening = true;
            this.isSpeaking = false;
            this.updateStatus('listening', '监听中...');
            console.log('🎤 VAD 开始监听 (RMS)');

            // 启动超时计时器
            this.startNoSpeechTimeout();

            this.detect();

        } catch (error) {
            console.error('VAD 启动失败:', error);
            this.updateStatus('error', '麦克风权限被拒绝');
            if (this.onError) this.onError(error);
        }
    }

    setupMediaRecorder() {
        const mimeType = this.getSupportedMimeType();
        this.mediaRecorder = new MediaRecorder(this.mediaStream, { mimeType });
        this.audioChunks = [];

        this.mediaRecorder.ondataavailable = (event) => {
            if (event.data.size > 0) {
                this.audioChunks.push(event.data);
            }
        };

        this.mediaRecorder.onstop = () => {
            this.processAudio();
        };
    }

    getSupportedMimeType() {
        const types = [
            'audio/webm;codecs=opus',
            'audio/webm',
            'audio/ogg;codecs=opus',
            'audio/mp4',
            'audio/wav'
        ];
        for (const type of types) {
            if (MediaRecorder.isTypeSupported(type)) return type;
        }
        return 'audio/webm';
    }

    detect() {
        if (!this.isListening || !this.analyser) return;

        const dataArray = new Float32Array(this.analyser.fftSize);
        this.analyser.getFloatTimeDomainData(dataArray);

        const rms = this.calculateRMS(dataArray);
        const now = Date.now();

        if (rms > this.config.speechThreshold) {
            if (!this.isSpeaking) {
                if (!this.speechStartTime) {
                    this.speechStartTime = now;
                } else if (now - this.speechStartTime >= this.config.minSpeechDuration) {
                    this.onSpeechDetected();
                }
            } else {
                this.silenceTimer = null;
            }
        } else if (rms < this.config.silenceThreshold && this.isSpeaking) {
            if (!this.silenceTimer) {
                this.silenceTimer = now;
            } else if (now - this.silenceTimer >= this.config.silenceDuration) {
                this.onSilenceDetected();
            }
        } else if (rms >= this.config.silenceThreshold && rms <= this.config.speechThreshold) {
            if (this.isSpeaking && !this.silenceTimer) {
                this.silenceTimer = now;
            }
        }

        this.animationFrameId = requestAnimationFrame(() => this.detect());
    }

    calculateRMS(dataArray) {
        let sum = 0;
        for (let i = 0; i < dataArray.length; i++) {
            sum += dataArray[i] * dataArray[i];
        }
        return Math.sqrt(sum / dataArray.length);
    }

    startNoSpeechTimeout() {
        this.listeningStartTime = Date.now();
        this.hasSpoken = false;
        
        // 清除之前的计时器
        if (this.noSpeechTimeoutId) {
            clearTimeout(this.noSpeechTimeoutId);
        }
        
        console.log('⏱️ 启动超时计时器 (10秒)');
        this.noSpeechTimeoutId = setTimeout(() => {
            if (!this.hasSpoken && this.isListening) {
                console.log('⏰ 10秒无声音，自动推进面试');
                this.onNoSpeechTimeout();
            }
        }, this.config.noSpeechTimeout);
    }

    stopNoSpeechTimeout() {
        if (this.noSpeechTimeoutId) {
            clearTimeout(this.noSpeechTimeoutId);
            this.noSpeechTimeoutId = null;
            console.log('⏹️ 停止超时计时器');
        }
    }

    onSpeechDetected() {
        this.isSpeaking = true;
        this.speechStartTime = null;
        this.silenceTimer = null;
        this.hasSpoken = true;
        
        console.log('🎯 检测到用户说话');
        
        // 用户说话了，停止超时计时器
        this.stopNoSpeechTimeout();
        
        this.updateStatus('speaking', '说话中...');
        
        if (this.mediaRecorder && this.mediaRecorder.state === 'inactive') {
            this.audioChunks = [];
            this.mediaRecorder.start(100);
            console.log('🔴 开始录音');
        }

        if (this.onSpeechStart) {
            this.onSpeechStart();
        }
    }

    onSilenceDetected() {
        this.isSpeaking = false;
        this.silenceTimer = null;
        this.speechStartTime = null;

        this.updateStatus('processing', '识别中...');

        if (this.mediaRecorder && this.mediaRecorder.state === 'recording') {
            this.mediaRecorder.stop();
            console.log('⏹️ 停止录音，准备识别');
        }
    }

    onNoSpeechTimeout() {
        console.log('⏰ 10秒无声音，自动推进面试');
        
        // 停止超时计时器
        this.stopNoSpeechTimeout();
        
        // 发送一个提示消息，让面试官推进面试
        if (window.chat) {
            window.chat.sendMessage('（用户没有回答，请继续提问或推进面试）');
        }
    }

    async processAudio() {
        if (this.audioChunks.length === 0) {
            this.updateStatus('listening', '监听中...');
            // 重新启动超时计时器
            this.startNoSpeechTimeout();
            return;
        }

        const audioBlob = new Blob(this.audioChunks, { type: 'audio/webm' });
        this.audioChunks = [];

        window.app?.showLoading('正在识别语音...');

        try {
            const formData = new FormData();
            formData.append('file', audioBlob, 'recording.webm');

            const response = await fetch('/api/asr', {
                method: 'POST',
                body: formData
            });
            const result = await response.json();

            if (result.status === 'ok' && result.text && result.text.trim()) {
                console.log('✅ 识别结果:', result.text);
                if (window.chat) {
                    window.chat.sendMessage(result.text);
                }
                if (this.onSpeechEnd) {
                    this.onSpeechEnd(result.text);
                }
            } else {
                console.log('⚠️ 未识别到有效内容');
                // 重新启动超时计时器
                this.startNoSpeechTimeout();
            }
        } catch (error) {
            console.error('ASR 请求失败:', error);
            if (this.onError) {
                this.onError(error);
            }
            // 重新启动超时计时器
            this.startNoSpeechTimeout();
        } finally {
            window.app?.hideLoading();
            if (this.isListening) {
                this.updateStatus('listening', '监听中...');
            }
        }
    }

    updateStatus(state, text) {
        // 更新标准模式UI
        if (this.statusIndicator) {
            this.statusIndicator.className = 'vad-status-badge';
            if (state) {
                this.statusIndicator.classList.add(state);
            }
        }
        if (this.statusText) {
            this.statusText.textContent = text;
        }

        if (this.recordBtn) {
            this.recordBtn.className = 'record-orb';
            if (state === 'listening') {
                this.recordBtn.classList.add('listening');
            } else if (state === 'speaking') {
                this.recordBtn.classList.add('speaking');
            } else if (state === 'processing') {
                this.recordBtn.classList.add('processing');
            } else if (state === 'tts-playing') {
                this.recordBtn.classList.add('tts-playing');
            }
        }

        if (this.recordIconEl) {
            if (state === 'speaking') {
                this.recordIconEl.className = 'fas fa-microphone';
            } else if (state === 'processing') {
                this.recordIconEl.className = 'fas fa-spinner fa-spin';
            } else if (state === 'tts-playing') {
                this.recordIconEl.className = 'fas fa-volume-up';
            } else if (state === 'listening') {
                this.recordIconEl.className = 'fas fa-microphone';
            } else {
                this.recordIconEl.className = 'fas fa-microphone';
            }
        }

        // 更新沉浸式模式UI
        if (this.immersiveRecordBtn) {
            this.immersiveRecordBtn.classList.remove('listening', 'speaking', 'processing', 'tts-playing');
            if (state === 'listening') {
                this.immersiveRecordBtn.classList.add('listening');
            } else if (state === 'speaking') {
                this.immersiveRecordBtn.classList.add('speaking');
            } else if (state === 'processing') {
                this.immersiveRecordBtn.classList.add('processing');
            } else if (state === 'tts-playing') {
                this.immersiveRecordBtn.classList.add('tts-playing');
            }
        }

        if (this.immersiveRecordIcon) {
            if (state === 'speaking') {
                this.immersiveRecordIcon.className = 'fas fa-microphone';
            } else if (state === 'processing') {
                this.immersiveRecordIcon.className = 'fas fa-spinner fa-spin';
            } else if (state === 'tts-playing') {
                this.immersiveRecordIcon.className = 'fas fa-volume-up';
            } else if (state === 'listening') {
                this.immersiveRecordIcon.className = 'fas fa-microphone';
            } else {
                this.immersiveRecordIcon.className = 'fas fa-microphone';
            }
        }

        // 更新沉浸式模式状态文字
        if (window.app?.isImmersiveMode()) {
            window.app.updateImmersiveStatus(text);
        }
    }

    // TTS 开始时调用：关闭麦克风和超时计时器
    pauseForTTSPlayback() {
        console.log('⏸️ TTS 开始播放，关闭麦克风和超时计时器');
        
        // 停止超时计时器
        this.stopNoSpeechTimeout();
        
        // 关闭麦克风
        if (this.mediaStream) {
            this.mediaStream.getTracks().forEach(track => track.stop());
            this.mediaStream = null;
        }
        
        // 关闭 AudioContext
        if (this.audioContext) {
            this.audioContext.close();
            this.audioContext = null;
        }
        
        // 停止检测循环
        if (this.animationFrameId) {
            cancelAnimationFrame(this.animationFrameId);
            this.animationFrameId = null;
        }
        
        this.analyser = null;
        this.isListening = false;
        this.isSpeaking = false;
        
        this.updateStatus('tts-playing', 'AI 说话中...');
    }

    // TTS 结束时调用：重新打开麦克风和超时计时器
    async resumeAfterTTS() {
        console.log('▶️ TTS 播放结束，重新打开麦克风');
        
        // 重新启动
        await this.start();
    }

    async stop() {
        if (!this.isListening) return;

        this.isListening = false;
        this.isSpeaking = false;

        // 停止超时计时器
        this.stopNoSpeechTimeout();

        if (this.animationFrameId) {
            cancelAnimationFrame(this.animationFrameId);
            this.animationFrameId = null;
        }

        if (this.silenceTimer) {
            this.silenceTimer = null;
        }

        if (this.mediaRecorder && this.mediaRecorder.state === 'recording') {
            this.mediaRecorder.stop();
        }

        if (this.mediaStream) {
            this.mediaStream.getTracks().forEach(track => track.stop());
            this.mediaStream = null;
        }

        if (this.audioContext) {
            await this.audioContext.close();
            this.audioContext = null;
        }

        this.analyser = null;
        this.mediaRecorder = null;
        this.audioChunks = [];

        this.updateStatus('', '点击麦克风开始');
        console.log('🛑 VAD 停止监听');
    }

    setConfig(config) {
        this.config = { ...this.config, ...config };
    }
}

window.vadDetector = new VADDetector();

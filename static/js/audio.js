/**
 * 音频录制模块 — Cybernetic Command
 * Web Audio API 录音，适配新 UI
 * 注意：沉浸式模式现在由 vad.js 统一处理，与标准模式行为一致
 */

class AudioRecorder {
    constructor() {
        this.mediaRecorder = null;
        this.audioChunks = [];
        this.isRecording = false;
        this.stream = null;

        // 标准模式麦克风按钮（备用，主要由VAD处理）
        this.recordBtn = document.getElementById('record-btn');
        this.recordIconEl = document.getElementById('record-icon-i');
        this.recordingIndicator = document.getElementById('recording-indicator');

        // 沉浸式模式麦克风按钮（现在由VAD统一处理）
        this.immersiveRecordBtn = document.getElementById('immersive-record-btn');
        this.immersiveRecordIcon = document.getElementById('immersive-record-icon');

        // 不再绑定点击事件，由vad.js统一处理
    }

    async toggleRecording() {
        if (this.isRecording) {
            await this.stopRecording();
        } else {
            await this.startRecording();
        }
    }

    async startRecording() {
        try {
            this.stream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    sampleRate: 16000,
                    channelCount: 1,
                    echoCancellation: true,
                    noiseSuppression: true
                }
            });

            this.mediaRecorder = new MediaRecorder(this.stream, {
                mimeType: this.getSupportedMimeType()
            });

            this.audioChunks = [];

            this.mediaRecorder.addEventListener('dataavailable', (event) => {
                if (event.data.size > 0) this.audioChunks.push(event.data);
            });

            this.mediaRecorder.addEventListener('stop', () => {
                this.processRecording();
            });

            this.mediaRecorder.start();
            this.isRecording = true;
            this.updateUI(true);
            this.updateImmersiveStatus('录音中...');
            console.log('🎤 开始录音');
        } catch (error) {
            console.error('无法访问麦克风:', error);
            this.updateImmersiveStatus('麦克风访问失败');
            alert('无法访问麦克风，请确保已授权浏览器访问麦克风权限。');
        }
    }

    async stopRecording() {
        if (this.mediaRecorder && this.isRecording) {
            this.mediaRecorder.stop();
            this.isRecording = false;
            if (this.stream) {
                this.stream.getTracks().forEach(track => track.stop());
            }
            this.updateUI(false);
            this.updateImmersiveStatus('正在识别...');
            console.log('🛑 停止录音');
        }
    }

    async processRecording() {
        if (this.audioChunks.length === 0) return;

        const audioBlob = new Blob(this.audioChunks, { type: 'audio/wav' });
        
        // 根据模式显示不同的加载提示
        const isImmersive = window.app?.isImmersiveMode();
        if (!isImmersive) {
            window.app?.showLoading('正在识别语音...');
        }

        try {
            const formData = new FormData();
            formData.append('file', audioBlob, 'recording.wav');

            const response = await fetch('/api/asr', {
                method: 'POST',
                body: formData
            });
            const result = await response.json();

            if (result.status === 'ok' && result.text) {
                console.log('✅ 识别结果:', result.text);
                this.updateImmersiveStatus('识别成功，正在发送...');
                if (window.chat) window.chat.sendMessage(result.text);
            } else {
                this.updateImmersiveStatus('识别失败，请重试');
                if (!isImmersive) {
                    alert('语音识别失败: ' + (result.message || '未识别到有效内容'));
                }
            }
        } catch (error) {
            console.error('ASR 请求失败:', error);
            this.updateImmersiveStatus('网络错误，请重试');
            if (!isImmersive) {
                alert('语音识别请求失败，请检查网络连接。');
            }
        } finally {
            if (!isImmersive) {
                window.app?.hideLoading();
            }
        }
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

    updateUI(recording) {
        // 更新标准模式UI
        if (this.recordBtn) {
            this.recordBtn.classList.toggle('recording', recording);
        }
        if (this.recordIconEl) {
            this.recordIconEl.className = recording ? 'fas fa-stop' : 'fas fa-microphone';
        }
        if (this.recordingIndicator) {
            this.recordingIndicator.classList.toggle('show', recording);
        }

        // 更新沉浸式模式UI
        if (this.immersiveRecordBtn) {
            this.immersiveRecordBtn.classList.toggle('recording', recording);
        }
        if (this.immersiveRecordIcon) {
            this.immersiveRecordIcon.className = recording ? 'fas fa-stop' : 'fas fa-microphone';
        }
    }

    // 更新沉浸式模式状态文字
    updateImmersiveStatus(text) {
        if (window.app?.isImmersiveMode()) {
            window.app.updateImmersiveStatus(text);
        }
    }
}

window.audioRecorder = new AudioRecorder();

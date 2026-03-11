/**
 * 音频录制模块
 * 使用 Web Audio API 进行浏览器录音
 */

class AudioRecorder {
    constructor() {
        this.mediaRecorder = null;
        this.audioChunks = [];
        this.isRecording = false;
        this.stream = null;
        
        // UI 元素
        this.recordBtn = document.getElementById('record-btn');
        this.recordText = this.recordBtn?.querySelector('.record-text');
        this.recordIcon = this.recordBtn?.querySelector('.record-icon');
        this.recordingIndicator = document.getElementById('recording-indicator');
        
        this.bindEvents();
    }
    
    /**
     * 绑定录音按钮事件
     */
    bindEvents() {
        if (this.recordBtn) {
            this.recordBtn.addEventListener('click', () => this.toggleRecording());
        }
    }
    
    /**
     * 切换录音状态
     */
    async toggleRecording() {
        if (this.isRecording) {
            await this.stopRecording();
        } else {
            await this.startRecording();
        }
    }
    
    /**
     * 开始录音
     */
    async startRecording() {
        try {
            // 请求麦克风权限
            this.stream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    sampleRate: 16000,
                    channelCount: 1,
                    echoCancellation: true,
                    noiseSuppression: true
                }
            });
            
            // 创建 MediaRecorder
            this.mediaRecorder = new MediaRecorder(this.stream, {
                mimeType: this.getSupportedMimeType()
            });
            
            this.audioChunks = [];
            
            // 数据可用时收集
            this.mediaRecorder.addEventListener('dataavailable', (event) => {
                if (event.data.size > 0) {
                    this.audioChunks.push(event.data);
                }
            });
            
            // 录音停止时处理
            this.mediaRecorder.addEventListener('stop', () => {
                this.processRecording();
            });
            
            // 开始录音
            this.mediaRecorder.start();
            this.isRecording = true;
            this.updateUI(true);
            
            console.log('🎤 开始录音');
            
        } catch (error) {
            console.error('无法访问麦克风:', error);
            alert('无法访问麦克风，请确保已授权浏览器访问麦克风权限。');
        }
    }
    
    /**
     * 停止录音
     */
    async stopRecording() {
        if (this.mediaRecorder && this.isRecording) {
            this.mediaRecorder.stop();
            this.isRecording = false;
            
            // 停止所有音轨
            if (this.stream) {
                this.stream.getTracks().forEach(track => track.stop());
            }
            
            this.updateUI(false);
            console.log('🛑 停止录音');
        }
    }
    
    /**
     * 处理录音数据
     */
    async processRecording() {
        if (this.audioChunks.length === 0) {
            console.warn('没有录音数据');
            return;
        }
        
        // 创建 Blob
        const audioBlob = new Blob(this.audioChunks, { type: 'audio/wav' });
        
        // 显示加载状态
        window.app?.showLoading('正在识别语音...');
        
        try {
            // 上传到服务器进行 ASR
            const formData = new FormData();
            formData.append('file', audioBlob, 'recording.wav');
            
            const response = await fetch('/api/asr', {
                method: 'POST',
                body: formData
            });
            
            const result = await response.json();
            
            if (result.status === 'ok' && result.text) {
                console.log('✅ 识别结果:', result.text);
                // 发送识别的文字到聊天
                if (window.chat) {
                    window.chat.sendMessage(result.text);
                }
            } else {
                console.error('ASR 识别失败:', result.message);
                alert('语音识别失败: ' + (result.message || '未识别到有效内容'));
            }
            
        } catch (error) {
            console.error('ASR 请求失败:', error);
            alert('语音识别请求失败，请检查网络连接。');
        } finally {
            window.app?.hideLoading();
        }
    }
    
    /**
     * 获取支持的 MIME 类型
     */
    getSupportedMimeType() {
        const types = [
            'audio/webm;codecs=opus',
            'audio/webm',
            'audio/ogg;codecs=opus',
            'audio/mp4',
            'audio/wav'
        ];
        
        for (const type of types) {
            if (MediaRecorder.isTypeSupported(type)) {
                return type;
            }
        }
        
        return 'audio/webm';
    }
    
    /**
     * 更新 UI 状态
     * @param {boolean} recording - 是否正在录音
     */
    updateUI(recording) {
        if (this.recordBtn) {
            this.recordBtn.classList.toggle('recording', recording);
        }
        
        if (this.recordText) {
            this.recordText.textContent = recording ? '点击停止录音' : '点击开始录音';
        }
        
        if (this.recordIcon) {
            this.recordIcon.textContent = recording ? '⏹️' : '🎤';
        }
        
        if (this.recordingIndicator) {
            this.recordingIndicator.classList.toggle('show', recording);
        }
    }
}

// 创建全局实例
window.audioRecorder = new AudioRecorder();

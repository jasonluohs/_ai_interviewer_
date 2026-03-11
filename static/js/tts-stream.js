/**
 * 流式 TTS 播放器
 * 实现真正的流式 TTS：LLM 生成一句就立即播放一句
 */

class StreamingTTSPlayer {
    constructor() {
        this.audioQueue = [];        // 音频数据队列 [{base64, sentence}]
        this.isPlaying = false;      // 是否正在播放
        this.isPaused = false;       // 是否暂停
        this.currentIndex = 0;       // 当前播放索引
        this.totalCount = 0;         // 总句子数
        this.audioElement = null;    // 当前音频元素
        
        // UI 元素
        this.statusEl = document.getElementById('tts-status');
        this.progressBar = document.getElementById('tts-progress-bar');
        this.playBtn = document.getElementById('tts-play');
        this.pauseBtn = document.getElementById('tts-pause');
        this.stopBtn = document.getElementById('tts-stop');
        
        this.bindEvents();
    }
    
    /**
     * 绑定控制按钮事件
     */
    bindEvents() {
        if (this.playBtn) {
            this.playBtn.addEventListener('click', () => this.play());
        }
        if (this.pauseBtn) {
            this.pauseBtn.addEventListener('click', () => this.pause());
        }
        if (this.stopBtn) {
            this.stopBtn.addEventListener('click', () => this.stop());
        }
    }
    
    /**
     * 添加新的音频数据（LLM 生成一句就调用一次）
     * @param {string} base64Data - Base64 编码的音频数据
     * @param {string} sentence - 对应的句子文本
     */
    addAudio(base64Data, sentence = '') {
        this.audioQueue.push({
            base64: base64Data,
            sentence: sentence,
            index: this.totalCount
        });
        this.totalCount++;
        
        console.log(`🔊 添加音频 #${this.totalCount}: ${sentence.substring(0, 30)}...`);
        
        // 如果不在播放中，立即开始播放
        if (!this.isPlaying && !this.isPaused) {
            this.play();
        }
        
        this.updateStatus();
    }
    
    /**
     * 开始/恢复播放
     */
    play() {
        if (this.isPaused && this.audioElement) {
            // 从暂停恢复
            this.audioElement.play();
            this.isPaused = false;
            console.log('▶️ 恢复播放');
        } else if (!this.isPlaying && this.audioQueue.length > 0) {
            // 开始新的播放
            this.isPlaying = true;
            this.isPaused = false;
            this.playNext();
            console.log('▶️ 开始播放');
        }
        this.updateStatus();
    }
    
    /**
     * 播放下一句
     */
    playNext() {
        if (this.currentIndex >= this.audioQueue.length) {
            // 检查是否还有更多音频待生成
            if (this.currentIndex >= this.totalCount) {
                this.isPlaying = false;
                this.updateStatus('播放完成');
                console.log('✅ 播放完成');
                return;
            }
            // 等待更多音频
            setTimeout(() => this.playNext(), 100);
            return;
        }
        
        const audioData = this.audioQueue[this.currentIndex];
        const audioSrc = `data:audio/mpeg;base64,${audioData.base64}`;
        
        // 创建新的音频元素
        this.audioElement = new Audio(audioSrc);
        
        // 播放结束事件
        this.audioElement.addEventListener('ended', () => {
            this.currentIndex++;
            this.updateProgress();
            this.playNext();
        });
        
        // 播放错误事件
        this.audioElement.addEventListener('error', (e) => {
            console.error('音频播放错误:', e);
            this.currentIndex++;
            this.playNext();
        });
        
        // 开始播放
        this.audioElement.play().then(() => {
            console.log(`🔊 正在播放 #${this.currentIndex + 1}/${this.totalCount}`);
            this.updateStatus(`播放中 (${this.currentIndex + 1}/${this.totalCount})`);
        }).catch(error => {
            console.error('播放失败:', error);
            // 浏览器可能阻止自动播放，显示提示
            this.updateStatus('点击播放按钮开始');
        });
        
        this.updateProgress();
    }
    
    /**
     * 暂停播放
     */
    pause() {
        if (this.isPlaying && this.audioElement && !this.isPaused) {
            this.audioElement.pause();
            this.isPaused = true;
            console.log('⏸️ 暂停播放');
            this.updateStatus('已暂停');
        }
    }
    
    /**
     * 停止播放
     */
    stop() {
        if (this.audioElement) {
            this.audioElement.pause();
            this.audioElement.currentTime = 0;
            this.audioElement = null;
        }
        this.isPlaying = false;
        this.isPaused = false;
        this.currentIndex = 0;
        console.log('⏹️ 停止播放');
        this.updateStatus('已停止');
        this.updateProgress();
    }
    
    /**
     * 重置播放器
     */
    reset() {
        this.stop();
        this.audioQueue = [];
        this.totalCount = 0;
        this.currentIndex = 0;
        this.updateStatus('等待中');
        this.updateProgress();
        console.log('🔄 播放器已重置');
    }
    
    /**
     * 更新状态显示
     * @param {string} text - 状态文本
     */
    updateStatus(text = null) {
        if (!this.statusEl) return;
        
        if (text) {
            this.statusEl.textContent = `(${text})`;
        } else if (this.isPlaying) {
            this.statusEl.textContent = `(${this.currentIndex + 1}/${this.totalCount} 句)`;
        } else if (this.audioQueue.length > 0) {
            this.statusEl.textContent = `(${this.audioQueue.length} 句待播放)`;
        } else {
            this.statusEl.textContent = '(等待中)';
        }
    }
    
    /**
     * 更新进度条
     */
    updateProgress() {
        if (!this.progressBar) return;
        
        if (this.totalCount === 0) {
            this.progressBar.style.width = '0%';
        } else {
            const progress = (this.currentIndex / this.totalCount) * 100;
            this.progressBar.style.width = `${progress}%`;
        }
    }
    
    /**
     * 获取播放状态
     * @returns {Object} 当前状态
     */
    getStatus() {
        return {
            isPlaying: this.isPlaying,
            isPaused: this.isPaused,
            currentIndex: this.currentIndex,
            totalCount: this.totalCount,
            queueLength: this.audioQueue.length
        };
    }
}

// 创建全局实例
window.ttsPlayer = new StreamingTTSPlayer();

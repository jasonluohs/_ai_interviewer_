/**
 * 聊天模块
 * 处理消息发送、SSE 流式响应、历史记录管理
 */

class ChatModule {
    constructor() {
        this.history = [];              // 对话历史
        this.isStreaming = false;       // 是否正在流式接收
        this.currentEventSource = null; // 当前的 SSE 连接
        this.currentPhase = 0;          // 当前面试阶段
        this.ideVisible = false;        // IDE面板是否可见
        
        // UI 元素
        this.chatForm = document.getElementById('chat-form');
        this.chatInput = document.getElementById('chat-input');
        this.chatHistory = document.getElementById('chat-history');
        this.voiceHistory = document.getElementById('voice-history');
        this.msgCountEl = document.getElementById('msg-count');
        this.idePanel = document.getElementById('ide-panel');
        
        this.bindEvents();
        this.loadHistory();
    }
    
    /**
     * 检测AI输出中是否包含 /next() 或 \next() 流程切换标记
     * @param {string} text - AI输出的文本
     * @returns {object|null} - 返回 {phase: number} 或 null
     */
    detectNextPhase(text) {
        // 匹配 /next[数字]、/next(数字)、\next[数字]、\next(数字) 等格式
        // 注意：同时支持正斜杠 / 和反斜杠 \
        const patterns = [
            /[/\\]next\[\s*(\d+)\s*\]/i,    // /next[6] 或 \next[6]
            /[/\\]next\(\s*(\d+)\s*\)/i,    // /next(6) 或 \next(6)
            /[/\\]next\s*\[\s*(\d+)\s*\]/i, // /next [6] 或 \next [6]
            /[/\\]next\s*\(\s*(\d+)\s*\)/i  // /next (6) 或 \next (6)
        ];
        
        for (const pattern of patterns) {
            const match = text.match(pattern);
            if (match) {
                const phase = parseInt(match[1], 10);
                console.log(`🔍 检测到流程切换: next(${phase})`);
                return { phase };
            }
        }
        return null;
    }
    
    /**
     * 检查是否应该显示IDE面板
     * @param {number} phase - 当前阶段编号
     * @returns {boolean}
     */
    shouldShowIDE(phase) {
        // 流程6是代码题目环节，需要显示IDE
        return phase === 6;
    }
    
    /**
     * 显示IDE面板
     */
    showIDEPanel() {
        if (this.idePanel && !this.ideVisible) {
            this.idePanel.classList.add('show');
            this.ideVisible = true;
            console.log('💻 IDE面板已显示 - 进入代码题目环节');
            
            // 调整主内容区布局
            const mainContent = document.querySelector('.main-content');
            if (mainContent) {
                mainContent.classList.add('with-ide');
            }
        }
    }
    
    /**
     * 隐藏IDE面板
     */
    hideIDEPanel() {
        if (this.idePanel && this.ideVisible) {
            this.idePanel.classList.remove('show');
            this.ideVisible = false;
            console.log('💻 IDE面板已隐藏');
            
            // 恢复主内容区布局
            const mainContent = document.querySelector('.main-content');
            if (mainContent) {
                mainContent.classList.remove('with-ide');
            }
        }
    }
    
    /**
     * 切换IDE面板显示状态
     */
    toggleIDEPanel() {
        if (this.ideVisible) {
            this.hideIDEPanel();
        } else {
            this.showIDEPanel();
        }
    }
    
    /**
     * 处理阶段切换
     * @param {number} phase - 新阶段编号
     */
    handlePhaseChange(phase) {
        this.currentPhase = phase;
        
        // 如果进入代码题目环节(流程6)，自动显示IDE
        if (this.shouldShowIDE(phase)) {
            this.showIDEPanel();
        }
        
        // 更新阶段显示
        this.updatePhaseDisplay(phase);
    }
    
    /**
     * 更新阶段显示
     * @param {number} phase - 阶段编号
     */
    updatePhaseDisplay(phase) {
        const phaseNames = {
            0: '面试开始',
            1: '自我介绍',
            2: '自我介绍问答',
            3: '项目介绍',
            4: '项目问答',
            5: '技术基础问题',
            6: '代码题目',
            7: '候选人反问',
            8: '面试结束'
        };
        
        const phaseIndicator = document.getElementById('phase-indicator');
        if (phaseIndicator) {
            phaseIndicator.textContent = `当前阶段: ${phaseNames[phase] || `阶段${phase}`}`;
            phaseIndicator.classList.add('show');
        }
    }
    
    /**
     * 绑定事件
     */
    bindEvents() {
        if (this.chatForm) {
            this.chatForm.addEventListener('submit', (e) => {
                e.preventDefault();
                const message = this.chatInput?.value?.trim();
                if (message) {
                    this.sendMessage(message);
                    this.chatInput.value = '';
                }
            });
        }
        
        // IDE面板事件绑定
        this.bindIDEEvents();
    }
    
    /**
     * 绑定IDE面板事件
     */
    bindIDEEvents() {
        // 关闭IDE按钮
        const closeBtn = document.getElementById('ide-close-btn');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => {
                this.hideIDEPanel();
            });
        }
        
        // 提交代码按钮
        const submitBtn = document.getElementById('submit-code-btn');
        if (submitBtn) {
            submitBtn.addEventListener('click', () => {
                this.submitCode();
            });
        }
        
        // 清空代码按钮
        const clearBtn = document.getElementById('clear-code-btn');
        if (clearBtn) {
            clearBtn.addEventListener('click', () => {
                const editor = document.getElementById('code-editor');
                if (editor) {
                    editor.value = '';
                    this.updateLineNumbers();
                }
            });
        }
        
        // 代码编辑器行号更新
        const codeEditor = document.getElementById('code-editor');
        if (codeEditor) {
            codeEditor.addEventListener('input', () => {
                this.updateLineNumbers();
            });
            codeEditor.addEventListener('scroll', () => {
                this.syncLineNumbersScroll();
            });
        }
    }
    
    /**
     * 更新行号显示
     */
    updateLineNumbers() {
        const editor = document.getElementById('code-editor');
        const lineNumbers = document.getElementById('line-numbers');
        if (editor && lineNumbers) {
            const lines = editor.value.split('\n').length;
            let numbersHtml = '';
            for (let i = 1; i <= lines; i++) {
                numbersHtml += i + '\n';
            }
            lineNumbers.textContent = numbersHtml;
        }
    }
    
    /**
     * 同步行号滚动
     */
    syncLineNumbersScroll() {
        const editor = document.getElementById('code-editor');
        const lineNumbers = document.getElementById('line-numbers');
        if (editor && lineNumbers) {
            lineNumbers.scrollTop = editor.scrollTop;
        }
    }
    
    /**
     * 提交代码
     */
    submitCode() {
        const editor = document.getElementById('code-editor');
        const language = document.getElementById('code-language');
        
        if (!editor || !editor.value.trim()) {
            alert('请先编写代码');
            return;
        }
        
        const code = editor.value;
        const lang = language ? language.value : 'python';
        
        // 保存到提交历史
        this.saveCodeSubmission(code, lang);
        
        // 将代码作为消息发送
        const message = `【我的代码】
\`\`\`${lang}
${code}
\`\`\`

请点评这段代码。`;
        
        this.sendMessage(message);
        
        console.log('✅ 代码已提交');
    }
    
    /**
     * 保存代码提交记录
     */
    saveCodeSubmission(code, language) {
        if (!this.codeHistory) {
            this.codeHistory = [];
        }
        
        const submission = {
            code: code,
            language: language,
            timestamp: new Date().toLocaleTimeString(),
            index: this.codeHistory.length + 1
        };
        
        this.codeHistory.push(submission);
        this.updateCodeHistoryDisplay();
    }
    
    /**
     * 更新代码提交历史显示
     */
    updateCodeHistoryDisplay() {
        const historyList = document.getElementById('history-list');
        if (!historyList || !this.codeHistory || this.codeHistory.length === 0) {
            return;
        }
        
        let html = '';
        for (let i = this.codeHistory.length - 1; i >= 0; i--) {
            const item = this.codeHistory[i];
            html += `
                <div class="history-item" data-index="${item.index}">
                    <span>第 ${item.index} 次提交 (${item.language})</span>
                    <span class="time">${item.timestamp}</span>
                </div>
            `;
        }
        
        historyList.innerHTML = html;
        
        // 绑定点击事件
        const items = historyList.querySelectorAll('.history-item');
        items.forEach(item => {
            item.addEventListener('click', () => {
                const index = parseInt(item.dataset.index);
                const submission = this.codeHistory.find(s => s.index === index);
                if (submission) {
                    const editor = document.getElementById('code-editor');
                    const language = document.getElementById('code-language');
                    if (editor) editor.value = submission.code;
                    if (language) language.value = submission.language;
                    this.updateLineNumbers();
                }
            });
        });
    }
    
    /**
     * 加载历史记录
     */
    async loadHistory() {
        try {
            const response = await fetch('/api/history');
            const data = await response.json();
            this.history = data.history || [];
            this.renderHistory();
            this.updateMsgCount();
        } catch (error) {
            console.error('加载历史记录失败:', error);
        }
    }
    
    /**
     * 发送消息并处理流式响应
     * @param {string} message - 用户消息
     */
    async sendMessage(message) {
        if (this.isStreaming) {
            console.warn('正在处理中，请稍候...');
            return;
        }
        
        // 获取设置
        const settings = window.app?.getSettings() || {};
        
        // 添加用户消息到历史
        this.history.push({ role: 'user', content: message });
        this.renderHistory();
        
        // 创建助手消息占位
        const assistantMsgId = `msg-${Date.now()}`;
        this.addAssistantPlaceholder(assistantMsgId);
        
        // 重置 TTS 播放器
        if (settings.enable_tts && window.ttsPlayer) {
            window.ttsPlayer.reset();
        }
        
        this.isStreaming = true;
        
        try {
            // 使用 fetch + SSE 流式请求
            const response = await fetch('/api/chat/stream', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    message: message,
                    history: this.history.slice(0, -1), // 不包含刚添加的用户消息
                    system_prompt: settings.system_prompt || '',
                    enable_tts: settings.enable_tts !== false,
                    enable_rag: settings.enable_rag !== false,
                    rag_domain: settings.rag_domain || 'cs',
                    rag_top_k: settings.rag_top_k || 6
                })
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            // 读取 SSE 流
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            let fullResponse = '';
            
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                
                buffer += decoder.decode(value, { stream: true });
                
                // 处理完整的 SSE 事件
                const lines = buffer.split('\n');
                buffer = lines.pop() || ''; // 保留未完成的行
                
                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const data = JSON.parse(line.slice(6));
                            
                            if (data.type === 'text') {
                                // 更新文本内容
                                fullResponse = data.content;
                                this.updateAssistantMessage(assistantMsgId, fullResponse);
                                
                                // 检测是否包含流程切换标记
                                const phaseResult = this.detectNextPhase(fullResponse);
                                if (phaseResult) {
                                    this.handlePhaseChange(phaseResult.phase);
                                }
                            } else if (data.type === 'audio') {
                                // 收到音频数据，添加到 TTS 播放器
                                if (settings.enable_tts && window.ttsPlayer) {
                                    window.ttsPlayer.addAudio(data.data, data.sentence);
                                }
                            } else if (data.type === 'done') {
                                // 流式结束
                                fullResponse = data.full_response || fullResponse;
                                console.log('✅ 流式响应完成');
                            } else if (data.type === 'error') {
                                console.error('服务器错误:', data.message);
                                this.updateAssistantMessage(assistantMsgId, `错误: ${data.message}`);
                            }
                        } catch (e) {
                            console.error('解析 SSE 数据失败:', e, line);
                        }
                    }
                }
            }
            
            // 添加助手消息到历史
            this.history.push({ role: 'assistant', content: fullResponse });
            this.updateMsgCount();
            
        } catch (error) {
            console.error('发送消息失败:', error);
            this.updateAssistantMessage(assistantMsgId, `发送失败: ${error.message}`);
        } finally {
            this.isStreaming = false;
        }
    }
    
    /**
     * 渲染聊天历史
     */
    renderHistory() {
        if (!this.chatHistory) return;
        
        if (this.history.length === 0) {
            this.chatHistory.innerHTML = '<div class="empty-hint">暂无聊天记录，在下方输入文字开始对话。</div>';
            if (this.voiceHistory) {
                this.voiceHistory.innerHTML = '<div class="empty-hint">点击上方麦克风开始语音面试</div>';
            }
            return;
        }
        
        let html = '';
        for (const msg of this.history) {
            html += this.createMessageHTML(msg.role, msg.content);
        }
        
        this.chatHistory.innerHTML = html;
        this.scrollToBottom();
        
        // 更新语音 Tab 的最近对话（最后 4 条）
        if (this.voiceHistory) {
            const recent = this.history.slice(-4);
            let voiceHtml = '';
            for (const msg of recent) {
                voiceHtml += this.createMessageHTML(msg.role, msg.content);
            }
            this.voiceHistory.innerHTML = voiceHtml || '<div class="empty-hint">点击上方麦克风开始语音面试</div>';
        }
    }
    
    /**
     * 创建消息 HTML
     * @param {string} role - 角色（user/assistant）
     * @param {string} content - 消息内容
     * @param {string} id - 可选的消息 ID
     */
    createMessageHTML(role, content, id = '') {
        const cssClass = role === 'user' ? 'user' : 'assistant';
        const idAttr = id ? `id="${id}"` : '';
        return `<div class="chat-message ${cssClass}" ${idAttr}><p>${this.escapeHtml(content)}</p></div>`;
    }
    
    /**
     * 添加助手消息占位符
     * @param {string} id - 消息 ID
     */
    addAssistantPlaceholder(id) {
        if (!this.chatHistory) return;
        
        // 移除空提示
        const emptyHint = this.chatHistory.querySelector('.empty-hint');
        if (emptyHint) emptyHint.remove();
        
        // 添加用户消息
        const userMsg = this.history[this.history.length - 1];
        if (userMsg) {
            this.chatHistory.innerHTML += this.createMessageHTML('user', userMsg.content);
        }
        
        // 添加助手占位
        this.chatHistory.innerHTML += this.createMessageHTML('assistant', '思考中...', id);
        this.scrollToBottom();
    }
    
    /**
     * 更新助手消息内容
     * @param {string} id - 消息 ID
     * @param {string} content - 新内容
     */
    updateAssistantMessage(id, content) {
        const msgEl = document.getElementById(id);
        if (msgEl) {
            msgEl.querySelector('p').textContent = content;
            this.scrollToBottom();
        }
    }
    
    /**
     * 滚动到底部
     */
    scrollToBottom() {
        if (this.chatHistory) {
            this.chatHistory.scrollTop = this.chatHistory.scrollHeight;
        }
    }
    
    /**
     * 更新消息计数
     */
    updateMsgCount() {
        if (this.msgCountEl) {
            this.msgCountEl.textContent = this.history.length;
        }
    }
    
    /**
     * 清空历史
     */
    async clearHistory() {
        try {
            await fetch('/api/history', { method: 'DELETE' });
            this.history = [];
            this.renderHistory();
            this.updateMsgCount();
            
            // 重置 TTS 播放器
            if (window.ttsPlayer) {
                window.ttsPlayer.reset();
            }
            
            console.log('✅ 历史已清空');
        } catch (error) {
            console.error('清空历史失败:', error);
        }
    }
    
    /**
     * 获取历史记录
     * @returns {Array} 历史记录数组
     */
    getHistory() {
        return this.history;
    }
    
    /**
     * HTML 转义
     * @param {string} text - 原始文本
     * @returns {string} 转义后的文本
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// 创建全局实例
window.chat = new ChatModule();

/**
 * 聊天模块 — Cybernetic Command
 * SSE 流式响应、对话历史、IDE 面板、阶段检测
 */

class ChatModule {
    constructor() {
        this.history = [];
        this.isStreaming = false;
        this.currentEventSource = null;
        this.currentPhase = 0;
        this.ideVisible = false;

        this.chatForm = document.getElementById('chat-form');
        this.chatInput = document.getElementById('chat-input');
        this.chatHistory = document.getElementById('chat-history');
        this.voiceHistory = document.getElementById('voice-history');
        this.msgCountEl = document.getElementById('msg-count');
        this.idePanel = document.getElementById('ide-panel');

        this.bindEvents();
        this.loadHistory();
    }

    /* ==================== Phase Detection ==================== */
    detectNextPhase(text) {
        const patterns = [
            /[/\\]next\[\s*(\d+)\s*\]/i,
            /[/\\]next\(\s*(\d+)\s*\)/i,
            /[/\\]next\s*\[\s*(\d+)\s*\]/i,
            /[/\\]next\s*\(\s*(\d+)\s*\)/i
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

    shouldShowIDE(phase) {
        return phase === 6;
    }

    showIDEPanel() {
        if (this.idePanel && !this.ideVisible) {
            this.idePanel.classList.add('show');
            this.ideVisible = true;
            console.log('💻 IDE面板已显示');
        }
    }

    hideIDEPanel() {
        if (this.idePanel && this.ideVisible) {
            this.idePanel.classList.remove('show');
            this.ideVisible = false;
            console.log('💻 IDE面板已隐藏');
        }
    }

    toggleIDEPanel() {
        if (this.ideVisible) this.hideIDEPanel();
        else this.showIDEPanel();
    }

    handlePhaseChange(phase) {
        this.currentPhase = phase;
        if (this.shouldShowIDE(phase)) {
            this.showIDEPanel();
        }
        // Update timeline via app
        window.app?.updatePhaseTimeline(phase);
    }

    /* ==================== Events ==================== */
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
        this.bindIDEEvents();
    }

    bindIDEEvents() {
        const closeBtn = document.getElementById('ide-close-btn');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => this.hideIDEPanel());
        }

        const submitBtn = document.getElementById('submit-code-btn');
        if (submitBtn) {
            submitBtn.addEventListener('click', () => this.submitCode());
        }

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

        const codeEditor = document.getElementById('code-editor');
        if (codeEditor) {
            codeEditor.addEventListener('input', () => this.updateLineNumbers());
            codeEditor.addEventListener('scroll', () => this.syncLineNumbersScroll());
        }
    }

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

    syncLineNumbersScroll() {
        const editor = document.getElementById('code-editor');
        const lineNumbers = document.getElementById('line-numbers');
        if (editor && lineNumbers) {
            lineNumbers.scrollTop = editor.scrollTop;
        }
    }

    submitCode() {
        const editor = document.getElementById('code-editor');
        const language = document.getElementById('code-language');
        if (!editor || !editor.value.trim()) {
            alert('请先编写代码');
            return;
        }
        const code = editor.value;
        const lang = language ? language.value : 'python';
        this.saveCodeSubmission(code, lang);

        const message = `【我的代码】\n\`\`\`${lang}\n${code}\n\`\`\`\n\n请点评这段代码。`;
        this.sendMessage(message);
    }

    saveCodeSubmission(code, language) {
        if (!this.codeHistory) this.codeHistory = [];
        this.codeHistory.push({
            code, language,
            timestamp: new Date().toLocaleTimeString(),
            index: this.codeHistory.length + 1
        });
        this.updateCodeHistoryDisplay();
    }

    updateCodeHistoryDisplay() {
        const historyList = document.getElementById('history-list');
        if (!historyList || !this.codeHistory || this.codeHistory.length === 0) return;

        let html = '';
        for (let i = this.codeHistory.length - 1; i >= 0; i--) {
            const item = this.codeHistory[i];
            html += `
                <div class="history-item" data-index="${item.index}">
                    <span>第 ${item.index} 次提交 (${item.language})</span>
                    <span class="time">${item.timestamp}</span>
                </div>`;
        }
        historyList.innerHTML = html;

        historyList.querySelectorAll('.history-item').forEach(item => {
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

    /* ==================== History & Messages ==================== */
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

    async sendMessage(message) {
        if (this.isStreaming) return;

        const settings = window.app?.getSettings() || {};
        this.history.push({ role: 'user', content: message });
        this.renderHistory();

        const assistantMsgId = `msg-${Date.now()}`;
        this.addAssistantPlaceholder(assistantMsgId);

        if (settings.enable_tts && window.ttsPlayer) {
            window.ttsPlayer.reset();
        }

        this.isStreaming = true;

        try {
            const response = await fetch('/api/chat/stream', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message,
                    history: this.history.slice(0, -1),
                    system_prompt: settings.system_prompt || '',
                    enable_tts: settings.enable_tts !== false,
                    enable_rag: settings.enable_rag !== false,
                    rag_domain: settings.rag_domain || 'cs',
                    rag_top_k: settings.rag_top_k || 6
                })
            });

            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            let fullResponse = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                buffer += decoder.decode(value, { stream: true });

                const lines = buffer.split('\n');
                buffer = lines.pop() || '';

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const data = JSON.parse(line.slice(6));
                            if (data.type === 'text') {
                                fullResponse = data.content;
                                this.updateAssistantMessage(assistantMsgId, fullResponse);
                                const phaseResult = this.detectNextPhase(fullResponse);
                                if (phaseResult) this.handlePhaseChange(phaseResult.phase);
                            } else if (data.type === 'audio') {
                                if (settings.enable_tts && window.ttsPlayer) {
                                    window.ttsPlayer.addAudio(data.data, data.sentence);
                                }
                            } else if (data.type === 'done') {
                                fullResponse = data.full_response || fullResponse;
                            } else if (data.type === 'error') {
                                this.updateAssistantMessage(assistantMsgId, `错误: ${data.message}`);
                            }
                        } catch (e) {
                            console.error('解析 SSE 数据失败:', e, line);
                        }
                    }
                }
            }

            this.history.push({ role: 'assistant', content: fullResponse });
            this._streamingEl = null;
            this._streamingTarget = null;
            this.renderHistory();   // 流式结束后重新渲染，确保 Markdown 干净渲染
            this.updateMsgCount();

        } catch (error) {
            console.error('发送消息失败:', error);
            this.updateAssistantMessage(assistantMsgId, `发送失败: ${error.message}`);
        } finally {
            this.isStreaming = false;
        }
    }

    renderHistory() {
        if (!this.chatHistory) return;

        if (this.history.length === 0) {
            this.chatHistory.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon"><i class="fas fa-satellite"></i></div>
                    <h3>准备就绪</h3>
                    <p>输入文字或点击麦克风，开始你的面试之旅</p>
                </div>`;
            return;
        }

        let html = '';
        for (const msg of this.history) {
            html += this.createMessageHTML(msg.role, msg.content);
        }
        this.chatHistory.innerHTML = html;

        // 对已渲染的代码块应用语法高亮
        if (typeof hljs !== 'undefined') {
            this.chatHistory.querySelectorAll('pre code').forEach(block => {
                try { hljs.highlightElement(block); } catch(_) {}
            });
        }
        this.scrollToBottom();

        // Voice history (last 4)
        if (this.voiceHistory) {
            const recent = this.history.slice(-4);
            this.voiceHistory.innerHTML = recent.map(msg =>
                this.createMessageHTML(msg.role, msg.content)
            ).join('');
        }
    }

    createMessageHTML(role, content, id = '') {
        const cssClass = role === 'user' ? 'user' : 'assistant';
        const idAttr = id ? `id="${id}"` : '';
        if (role === 'assistant') {
            let rendered = '';
            try {
                if (window.mdRenderer && window.mdRenderer.ready) {
                    rendered = window.mdRenderer.render(content);
                } else if (typeof marked !== 'undefined' && typeof marked.parse === 'function') {
                    rendered = marked.parse(content);
                }
            } catch (e) {
                console.error('[Chat] createMessageHTML markdown 渲染失败:', e);
            }
            if (rendered) {
                return `<div class="chat-message ${cssClass}" ${idAttr}><div class="md-body">${rendered}</div></div>`;
            }
        }
        return `<div class="chat-message ${cssClass}" ${idAttr}><p>${this.escapeHtml(content)}</p></div>`;
    }

    addAssistantPlaceholder(id) {
        if (!this.chatHistory) return;
        const emptyHint = this.chatHistory.querySelector('.empty-state');
        if (emptyHint) emptyHint.remove();

        // 使用 insertAdjacentHTML 避免 innerHTML += 导致的 DOM 序列化问题
        const placeholderHTML = `<div class="chat-message assistant" id="${id}"><div class="md-body"><p>思考中...</p></div></div>`;
        this.chatHistory.insertAdjacentHTML('beforeend', placeholderHTML);

        // 存储直接引用，避免后续查找失败
        this._streamingEl = document.getElementById(id);
        this._streamingTarget = this._streamingEl ? this._streamingEl.querySelector('.md-body') : null;
        this.scrollToBottom();
    }

    updateAssistantMessage(id, content) {
        // 优先使用存储的直接引用
        const target = this._streamingTarget || (() => {
            const el = document.getElementById(id);
            return el ? (el.querySelector('.md-body') || el.querySelector('p')) : null;
        })();

        if (!target) return;

        // 多级回退策略确保 Markdown 一定被渲染
        try {
            if (window.mdRenderer && window.mdRenderer.ready) {
                window.mdRenderer.renderTo(target, content);
            } else if (typeof marked !== 'undefined' && typeof marked.parse === 'function') {
                target.innerHTML = marked.parse(content);
            } else {
                target.textContent = content;
            }
        } catch (e) {
            console.error('[Chat] Markdown 渲染失败，降级为纯文本:', e);
            target.textContent = content;
        }
        this.scrollToBottom();
    }

    scrollToBottom() {
        if (this.chatHistory) {
            this.chatHistory.scrollTop = this.chatHistory.scrollHeight;
        }
    }

    updateMsgCount() {
        if (this.msgCountEl) {
            this.msgCountEl.textContent = this.history.length;
        }
    }

    async clearHistory() {
        try {
            await fetch('/api/history', { method: 'DELETE' });
            this.history = [];
            this.currentPhase = 0;
            this.renderHistory();
            this.updateMsgCount();
            this.hideIDEPanel();
            if (window.ttsPlayer) window.ttsPlayer.reset();
        } catch (error) {
            console.error('清空历史失败:', error);
        }
    }

    getHistory() {
        return this.history;
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

window.chat = new ChatModule();

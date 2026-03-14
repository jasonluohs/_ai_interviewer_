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
        this.compactMode = false;  // 精简对话模式
        this.codeEditor = null;    // CodeMirror 实例
        this.isCodeRunning = false; // 代码执行状态

        this.chatForm = document.getElementById('chat-form');
        this.chatInput = document.getElementById('chat-input');
        this.chatHistory = document.getElementById('chat-history');
        this.voiceHistory = document.getElementById('voice-history');
        this.msgCountEl = document.getElementById('msg-count');
        this.idePanel = document.getElementById('ide-panel');

        this.bindEvents();
        this.loadHistory();
        this.initCodeMirror();
    }

    /* ==================== Compact Mode ==================== */
    setCompactMode(enabled) {
        this.compactMode = enabled;
        this.renderHistory();
        // 模式切换时重置音频队列
        if (window.ttsPlayer) {
            window.ttsPlayer.reset();
        }
    }

    getCompactMode() {
        return this.compactMode;
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
        return phase === 4;
    }

    showIDEPanel() {
        if (this.idePanel && !this.ideVisible) {
            this.idePanel.classList.add('show');
            this.ideVisible = true;
            this.syncIDEToggle(true);
            // CodeMirror 在隐藏容器中初始化时无法计算 gutter 宽度，
            // 面板 CSS transition 结束后必须调用 refresh() 修复行号陷盖代码的问题
            if (this.codeEditor) {
                setTimeout(() => {
                    this.codeEditor.refresh();
                }, 350);
            }
            // 提取并显示题目
            this.extractAndShowProblem();
            console.log('💻 IDE面板已显示');
        }
    }

    // 提取并显示题目
    extractAndShowProblem() {
        // 从对话历史中查找最近的AI回复（包含题目的消息）
        const lastAssistantMsg = this.findLastProblemMessage();
        if (lastAssistantMsg) {
            this.updateProblemContent(lastAssistantMsg);
        }
    }

    // 查找最近的包含题目的AI消息
    findLastProblemMessage() {
        // 从后往前查找最近的assistant消息
        for (let i = this.history.length - 1; i >= 0; i--) {
            const msg = this.history[i];
            if (msg.role === 'assistant') {
                // 返回最近的AI回复作为题目
                return msg.content;
            }
        }
        return null;
    }

    // 更新题目内容
    updateProblemContent(content) {
        const problemContent = document.getElementById('ide-problem-content');
        if (!problemContent) return;

        // 清理题目内容，移除一些不需要的内容
        let cleanedContent = content;
        
        // 移除可能的流程指令（如 /next[4] 等）
        cleanedContent = cleanedContent.replace(/[\/\\]next\[?\(?\s*\d+\s*\]?\)?/gi, '').trim();

        // 使用 Markdown 渲染
        try {
            let rendered = '';
            if (window.mdRenderer && window.mdRenderer.ready) {
                rendered = window.mdRenderer.render(cleanedContent);
            } else if (typeof marked !== 'undefined' && typeof marked.parse === 'function') {
                rendered = marked.parse(cleanedContent);
            }
            
            if (rendered) {
                problemContent.innerHTML = `<div class="md-body">${rendered}</div>`;
            } else {
                problemContent.innerHTML = `<div class="md-body"><p>${this.escapeHtml(cleanedContent)}</p></div>`;
            }
        } catch (e) {
            console.error('[IDE] 题目渲染失败:', e);
            problemContent.innerHTML = `<div class="md-body"><p>${this.escapeHtml(cleanedContent)}</p></div>`;
        }

        // 对代码块应用语法高亮
        if (typeof hljs !== 'undefined') {
            problemContent.querySelectorAll('pre code').forEach(block => {
                try { hljs.highlightElement(block); } catch(_) {}
            });
        }

        console.log('📝 题目已更新到IDE面板');
    }

    // 清空题目内容
    clearProblemContent() {
        const problemContent = document.getElementById('ide-problem-content');
        if (problemContent) {
            problemContent.innerHTML = `
                <div class="ide-problem-placeholder">
                    <i class="fas fa-hourglass-half"></i>
                    <span>等待面试官出题...</span>
                </div>
            `;
        }
    }

    hideIDEPanel() {
        if (this.idePanel && this.ideVisible) {
            this.idePanel.classList.remove('show');
            this.ideVisible = false;
            this.syncIDEToggle(false);
            console.log('💻 IDE面板已隐藏');
        }
    }

    toggleIDEPanel() {
        if (this.ideVisible) this.hideIDEPanel();
        else this.showIDEPanel();
    }

    syncIDEToggle(state) {
        // 同步侧栏 toggle 开关
        const idePanelToggle = document.getElementById('ide-panel-toggle');
        if (idePanelToggle) idePanelToggle.checked = state;
        // 同步顶部命令栏按钮状态
        const toggleIdeBtn = document.getElementById('toggle-ide-btn');
        if (toggleIdeBtn) toggleIdeBtn.classList.toggle('active', state);
    }

    handlePhaseChange(phase) {
        this.currentPhase = phase;
        if (this.shouldShowIDE(phase)) {
            this.showIDEPanel();
        }
        // Update timeline via app
        window.app?.updatePhaseTimeline(phase);
        // Update immersive mode phase display
        window.app?.updateImmersivePhase(phase);
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
    
        // 运行按钮
        const runBtn = document.getElementById('run-code-btn');
        if (runBtn) {
            runBtn.addEventListener('click', () => this.runCode());
        }
    
        // 提交按钮
        const submitBtn = document.getElementById('submit-code-btn');
        if (submitBtn) {
            submitBtn.addEventListener('click', () => this.submitCode());
        }
    
        // 清空按钮
        const clearBtn = document.getElementById('clear-code-btn');
        if (clearBtn) {
            clearBtn.addEventListener('click', () => this.clearCodeEditor());
        }
    
        // 语言切换
        const langSelect = document.getElementById('code-language');
        if (langSelect) {
            langSelect.addEventListener('change', () => this.changeLanguage(langSelect.value));
        }
    
        // I/O 标签页切换
        const ioTabs = document.querySelectorAll('.io-tab');
        ioTabs.forEach(tab => {
            tab.addEventListener('click', () => this.switchIOTab(tab.dataset.tab));
        });

        // 顶部命令栏 IDE 按钮
        const toggleIdeBtn = document.getElementById('toggle-ide-btn');
        if (toggleIdeBtn) {
            toggleIdeBtn.addEventListener('click', () => this.toggleIDEPanel());
        }

        // 侧栏 IDE toggle 开关
        const idePanelToggle = document.getElementById('ide-panel-toggle');
        if (idePanelToggle) {
            idePanelToggle.addEventListener('change', () => {
                if (idePanelToggle.checked) this.showIDEPanel();
                else this.hideIDEPanel();
            });
        }

        // 题目区域折叠/展开
        const problemSection = document.getElementById('ide-problem-section');
        const problemToggle = document.getElementById('ide-problem-toggle');
        const problemHeader = document.querySelector('.ide-problem-header');
        
        if (problemHeader && problemSection) {
            problemHeader.addEventListener('click', () => {
                problemSection.classList.toggle('collapsed');
            });
        }
    }
    
    /* ==================== CodeMirror 编辑器 ==================== */
    initCodeMirror() {
        const container = document.getElementById('code-editor-container');
        if (!container || typeof CodeMirror === 'undefined') {
            console.warn('CodeMirror 未加载或容器不存在');
            return;
        }
    
        this.codeEditor = CodeMirror(container, {
            mode: 'python',
            theme: 'material-darker',
            lineNumbers: true,
            matchBrackets: true,
            autoCloseBrackets: true,
            indentUnit: 4,
            tabSize: 4,
            indentWithTabs: false,
            lineWrapping: false,
            foldGutter: true,
            gutters: ['CodeMirror-linenumbers', 'CodeMirror-foldgutter'],
            extraKeys: {
                'Tab': 'indentMore',
                'Shift-Tab': 'indentLess',
                'Ctrl-Enter': () => this.runCode(),
                'Cmd-Enter': () => this.runCode()
            },
            placeholder: '# 在这里编写你的代码...\n\ndef solution():\n    pass'
        });
    
        // 设置默认代码
        this.codeEditor.setValue('# 在这里编写你的代码\n\ndef solution():\n    pass\n');
            
        console.log('✅ CodeMirror 初始化完成');
    }
    
    changeLanguage(lang) {
        if (!this.codeEditor) return;
            
        const modeMap = {
            'python': 'python',
            'javascript': 'javascript',
            'java': 'text/x-java',
            'cpp': 'text/x-c++src'
        };
            
        const defaultCode = {
            'python': '# 在这里编写你的代码\n\ndef solution():\n    pass\n',
            'javascript': '// 在这里编写你的代码\n\nfunction solution() {\n    \n}\n',
            'java': '// 在这里编写你的代码\n\npublic class Main {\n    public static void main(String[] args) {\n        \n    }\n}\n',
            'cpp': '// 在这里编写你的代码\n\n#include <iostream>\nusing namespace std;\n\nint main() {\n    \n    return 0;\n}\n'
        };
            
        this.codeEditor.setOption('mode', modeMap[lang] || 'python');
            
        // 如果编辑器为空或是默认代码，切换到新语言的默认代码
        const currentCode = this.codeEditor.getValue().trim();
        const isDefault = Object.values(defaultCode).some(code => 
            currentCode === code.trim() || currentCode === '' || currentCode.startsWith('# 在这里') || currentCode.startsWith('// 在这里')
        );
            
        if (isDefault) {
            this.codeEditor.setValue(defaultCode[lang] || defaultCode['python']);
        }
    }
    
    clearCodeEditor() {
        if (this.codeEditor) {
            const lang = document.getElementById('code-language')?.value || 'python';
            const defaultCode = {
                'python': '# 在这里编写你的代码\n\ndef solution():\n    pass\n',
                'javascript': '// 在这里编写你的代码\n\nfunction solution() {\n    \n}\n',
                'java': '// 在这里编写你的代码\n\npublic class Main {\n    public static void main(String[] args) {\n        \n    }\n}\n',
                'cpp': '// 在这里编写你的代码\n\n#include <iostream>\nusing namespace std;\n\nint main() {\n    \n    return 0;\n}\n'
            };
            this.codeEditor.setValue(defaultCode[lang] || defaultCode['python']);
        }
        // 清空输出
        const outputEl = document.getElementById('code-output');
        if (outputEl) {
            outputEl.textContent = '点击"运行"执行代码...';
            outputEl.className = 'code-output';
        }
    }
    
    switchIOTab(tabName) {
        // 更新标签激活状态
        document.querySelectorAll('.io-tab').forEach(tab => {
            tab.classList.toggle('active', tab.dataset.tab === tabName);
        });
        // 更新面板显示
        document.querySelectorAll('.io-panel').forEach(panel => {
            panel.classList.toggle('active', panel.id === `${tabName}-panel`);
        });
    }
    
    /* ==================== 代码执行 ==================== */
    async runCode() {
        if (!this.codeEditor || this.isCodeRunning) return;
            
        const code = this.codeEditor.getValue();
        const language = document.getElementById('code-language')?.value || 'python';
        const stdin = document.getElementById('code-input')?.value || '';
        const outputEl = document.getElementById('code-output');
        const runBtn = document.getElementById('run-code-btn');
            
        if (!code.trim()) {
            alert('请先编写代码');
            return;
        }
            
        // 切换到输出标签页
        this.switchIOTab('output');
            
        // 显示运行状态
        this.isCodeRunning = true;
        if (outputEl) {
            outputEl.textContent = '⚙️ 正在执行...';
            outputEl.className = 'code-output running';
        }
        if (runBtn) {
            runBtn.disabled = true;
            runBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 运行中';
        }
            
        try {
            const response = await fetch('/api/code/execute', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ code, language, stdin })
            });
            const result = await response.json();
                
            if (result.status === 'ok') {
                let output = result.output || '(无输出)';
                if (result.stderr && result.stderr.trim()) {
                    output += '\n\n[stderr]\n' + result.stderr;
                }
                if (result.return_code !== 0) {
                    output += `\n\n[返回码: ${result.return_code}]`;
                }
                if (outputEl) {
                    outputEl.textContent = output;
                    outputEl.className = result.return_code === 0 ? 'code-output success' : 'code-output error';
                }
            } else {
                if (outputEl) {
                    let errorMsg = '❌ 错误: ' + result.message;
                    if (result.stderr) {
                        errorMsg += '\n\n' + result.stderr;
                    }
                    outputEl.textContent = errorMsg;
                    outputEl.className = 'code-output error';
                }
            }
        } catch (error) {
            if (outputEl) {
                outputEl.textContent = '❌ 执行失败: ' + error.message;
                outputEl.className = 'code-output error';
            }
        } finally {
            this.isCodeRunning = false;
            if (runBtn) {
                runBtn.disabled = false;
                runBtn.innerHTML = '<i class="fas fa-play"></i> 运行';
            }
        }
    }
    
    submitCode() {
        if (!this.codeEditor) return;
            
        const code = this.codeEditor.getValue();
        const language = document.getElementById('code-language')?.value || 'python';
            
        if (!code.trim()) {
            alert('请先编写代码');
            return;
        }
            
        this.saveCodeSubmission(code, language);
        const message = `【我的代码】\n\`\`\`${language}\n${code}\n\`\`\`\n\n请点评这段代码。`;
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
                if (submission && this.codeEditor) {
                    this.codeEditor.setValue(submission.code);
                    const langSelect = document.getElementById('code-language');
                    if (langSelect) {
                        langSelect.value = submission.language;
                        this.changeLanguage(submission.language);
                    }
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
        const isImmersive = window.app?.isImmersiveMode();

        this.history.push({ role: 'user', content: message });
        
        // 沉浸式模式不渲染聊天历史
        if (!isImmersive) {
            this.renderHistory();
        }

        const assistantMsgId = `msg-${Date.now()}`;
        
        // 沉浸式模式不添加占位符
        if (!isImmersive) {
            this.addAssistantPlaceholder(assistantMsgId);
        } else {
            // 更新沉浸式状态
            window.app?.updateImmersiveStatus('AI 正在思考...');
        }

        // 精简模式下，新消息开始时重置音频队列
        if (this.compactMode && window.ttsPlayer) {
            window.ttsPlayer.reset();
        } else if (settings.enable_tts && window.ttsPlayer) {
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
            let ttsStarted = false;

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
                                // 沉浸式模式不更新文字消息
                                if (!isImmersive) {
                                    this.updateAssistantMessage(assistantMsgId, fullResponse);
                                }
                            } else if (data.type === 'phase') {
                                if (Number.isInteger(data.phase)) {
                                    this.handlePhaseChange(data.phase);
                                }
                            } else if (data.type === 'audio') {
                                if (settings.enable_tts && window.ttsPlayer) {
                                    window.ttsPlayer.addAudio(data.data, data.sentence);
                                    // 沉浸式模式显示TTS指示器
                                    if (isImmersive && !ttsStarted) {
                                        ttsStarted = true;
                                        window.app?.showImmersiveTTSIndicator();
                                        window.app?.updateImmersiveStatus('AI 正在回复...');
                                    }
                                }
                            } else if (data.type === 'done') {
                                fullResponse = data.full_response || fullResponse;
                            } else if (data.type === 'error') {
                                if (!isImmersive) {
                                    this.updateAssistantMessage(assistantMsgId, `错误: ${data.message}`);
                                } else {
                                    window.app?.updateImmersiveStatus(`错误: ${data.message}`);
                                }
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
            
            // 沉浸式模式不渲染历史
            if (!isImmersive) {
                this.renderHistory();   // 流式结束后重新渲染，确保 Markdown 干净渲染
            }
            this.updateMsgCount();

            // 沉浸式模式：等待TTS播放完成后更新状态
            if (isImmersive) {
                this.waitForTTSComplete();
            }

        } catch (error) {
            console.error('发送消息失败:', error);
            if (!isImmersive) {
                this.updateAssistantMessage(assistantMsgId, `发送失败: ${error.message}`);
            } else {
                window.app?.updateImmersiveStatus(`发送失败: ${error.message}`);
                window.app?.hideImmersiveTTSIndicator();
            }
        } finally {
            this.isStreaming = false;
        }
    }

    // 等待TTS播放完成（仅用于沉浸式模式的UI状态更新）
    // 注意：VAD的恢复由tts-stream.js统一处理
    waitForTTSComplete() {
        const checkTTS = () => {
            if (window.ttsPlayer && window.ttsPlayer.isPlaying) {
                setTimeout(checkTTS, 500);
            } else {
                // 只隐藏TTS指示器，VAD恢复由tts-stream.js处理
                window.app?.hideImmersiveTTSIndicator();
            }
        };
        setTimeout(checkTTS, 1000);
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
        let messagesToRender = this.history;

        // 精简模式：只显示最后一轮对话（最新的 user + assistant）
        if (this.compactMode && this.history.length > 0) {
            // 添加精简模式指示器
            html += `
                <div class="compact-mode-indicator">
                    <i class="fas fa-compress-alt"></i>
                    <span>精简模式 - 仅显示当前轮次</span>
                    <span class="compact-total">共 ${Math.ceil(this.history.length / 2)} 轮对话</span>
                </div>`;

            // 找到最后一轮对话
            const lastMessages = [];
            for (let i = this.history.length - 1; i >= 0; i--) {
                lastMessages.unshift(this.history[i]);
                if (this.history[i].role === 'user') {
                    break;
                }
            }
            messagesToRender = lastMessages;
        }

        for (const msg of messagesToRender) {
            const animClass = this.compactMode ? ' compact-animate' : '';
            html += this.createMessageHTML(msg.role, msg.content, '', animClass);
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

    createMessageHTML(role, content, id = '', extraClass = '') {
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
                return `<div class="chat-message ${cssClass}${extraClass}" ${idAttr}><div class="md-body">${rendered}</div></div>`;
            }
        }
        return `<div class="chat-message ${cssClass}${extraClass}" ${idAttr}><p>${this.escapeHtml(content)}</p></div>`;
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
        // 同步更新沉浸式模式的消息计数
        window.app?.updateImmersiveMsgCount();
    }

    async clearHistory() {
        try {
            await fetch('/api/history', { method: 'DELETE' });
            this.history = [];
            this.currentPhase = 0;
            this.renderHistory();
            this.updateMsgCount();
            this.hideIDEPanel();
            this.clearProblemContent();  // 清空题目
            if (window.ttsPlayer) window.ttsPlayer.reset();
            // 沉浸式模式重置
            window.app?.updateImmersivePhase(0);
            window.app?.hideImmersiveTTSIndicator();
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

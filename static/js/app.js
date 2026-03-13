/**
 * AI 面试官 — Cybernetic Command
 * 主应用逻辑：初始化、设置管理、抽屉面板、报告生成
 */

class App {
    constructor() {
        this.settings = {
            prompt_choice: '正常型面试官（默认）',
            system_prompt: '',
            enable_tts: true,
            enable_rag: true,
            rag_domain: 'cs',
            rag_top_k: 6,
            compact_mode: false  // 精简对话模式
        };

        this.presets = {};
        this.reportContent = '';
        this.resumeUploaded = false;
        this.resumeFileName = '';

        this.loadingOverlay = document.getElementById('loading-overlay');
        this.loadingText = document.getElementById('loading-text');

        this.init();
    }

    async init() {
        console.log('🚀 初始化 Cybernetic Command...');

        this.bindSidebarEvents();
        this.bindSettingsEvents();
        this.bindDrawerEvents();
        this.bindReportEvents();
        this.bindResumeEvents();

        await this.loadPresets();
        await this.loadSettings();
        await this.loadRagDomains();
        await this.loadRagHistory();
        await this.loadResumeStatus();

        console.log('✅ 初始化完成');
    }

    /* ==================== Sidebar ==================== */
    bindSidebarEvents() {
        const sidebarToggle = document.getElementById('sidebar-toggle');
        const sidebar = document.getElementById('sidebar');

        if (sidebarToggle && sidebar) {
            sidebarToggle.addEventListener('click', () => {
                if (window.innerWidth <= 900) {
                    sidebar.classList.toggle('show');
                } else {
                    sidebar.classList.toggle('hidden');
                }
                sidebarToggle.classList.toggle('active');
            });

            // 移动端点击主区域关闭侧边栏
            const mainStage = document.querySelector('.main-stage');
            if (mainStage) {
                mainStage.addEventListener('click', () => {
                    if (window.innerWidth <= 900) {
                        sidebar.classList.remove('show');
                        sidebarToggle.classList.remove('active');
                    }
                });
            }
        }

        // New chat
        const newChatBtn = document.getElementById('new-chat-btn');
        if (newChatBtn) {
            newChatBtn.addEventListener('click', () => {
                if (confirm('确定要开始新对话吗？当前对话历史将被清空。')) {
                    window.chat?.clearHistory();
                    this.reportContent = '';
                    const rc = document.getElementById('report-content');
                    if (rc) rc.textContent = '';
                    const rd = document.getElementById('report-download');
                    if (rd) rd.style.display = 'none';
                    // Reset phase timeline
                    this.resetPhaseTimeline();
                }
            });
        }

        // Collapsible prompt
        const promptToggle = document.getElementById('prompt-toggle');
        const promptContent = document.getElementById('prompt-content');
        if (promptToggle && promptContent) {
            promptToggle.addEventListener('click', () => {
                promptToggle.classList.toggle('active');
                promptContent.classList.toggle('show');
            });
        }
    }

    /* ==================== Drawer Panels ==================== */
    bindDrawerEvents() {
        // RAG drawer
        const ragBtn = document.getElementById('toggle-rag-btn');
        const ragDrawer = document.getElementById('rag-drawer');
        const ragClose = document.getElementById('rag-close-btn');

        if (ragBtn && ragDrawer) {
            ragBtn.addEventListener('click', () => {
                const isOpen = ragDrawer.classList.contains('show');
                this.closeAllDrawers();
                if (!isOpen) {
                    ragDrawer.classList.add('show');
                    ragBtn.classList.add('active');
                    this.loadRagHistory();
                }
            });
        }
        if (ragClose) {
            ragClose.addEventListener('click', () => this.closeAllDrawers());
        }

        // Report drawer
        const reportBtn = document.getElementById('toggle-report-btn');
        const reportDrawer = document.getElementById('report-drawer');
        const reportClose = document.getElementById('report-close-btn');

        if (reportBtn && reportDrawer) {
            reportBtn.addEventListener('click', () => {
                const isOpen = reportDrawer.classList.contains('show');
                this.closeAllDrawers();
                if (!isOpen) {
                    reportDrawer.classList.add('show');
                    reportBtn.classList.add('active');
                }
            });
        }
        if (reportClose) {
            reportClose.addEventListener('click', () => this.closeAllDrawers());
        }
    }

    closeAllDrawers() {
        document.querySelectorAll('.side-drawer').forEach(d => d.classList.remove('show'));
        document.getElementById('toggle-rag-btn')?.classList.remove('active');
        document.getElementById('toggle-report-btn')?.classList.remove('active');
    }

    /* ==================== Settings ==================== */
    bindSettingsEvents() {
        const promptSelect = document.getElementById('prompt-select');
        if (promptSelect) {
            promptSelect.addEventListener('change', () => {
                const choice = promptSelect.value;
                this.settings.prompt_choice = choice;
                if (choice !== '自定义' && this.presets[choice]) {
                    this.settings.system_prompt = this.presets[choice];
                    const pa = document.getElementById('system-prompt');
                    if (pa) pa.value = this.settings.system_prompt;
                }
                this.saveSettings();
            });
        }

        const systemPrompt = document.getElementById('system-prompt');
        if (systemPrompt) {
            systemPrompt.addEventListener('change', () => {
                this.settings.system_prompt = systemPrompt.value;
                this.saveSettings();
            });
        }

        const enableTts = document.getElementById('enable-tts');
        if (enableTts) {
            enableTts.addEventListener('change', () => {
                this.settings.enable_tts = enableTts.checked;
                this.saveSettings();
            });
        }

        const enableRag = document.getElementById('enable-rag');
        const ragSettings = document.getElementById('rag-settings');
        if (enableRag) {
            enableRag.addEventListener('change', () => {
                this.settings.enable_rag = enableRag.checked;
                if (ragSettings) ragSettings.style.display = enableRag.checked ? 'block' : 'none';
                this.saveSettings();
            });
        }

        const ragDomain = document.getElementById('rag-domain');
        if (ragDomain) {
            ragDomain.addEventListener('change', () => {
                this.settings.rag_domain = ragDomain.value;
                this.saveSettings();
            });
        }

        const ragTopk = document.getElementById('rag-topk');
        const topkValue = document.getElementById('topk-value');
        if (ragTopk) {
            ragTopk.addEventListener('input', () => {
                this.settings.rag_top_k = parseInt(ragTopk.value);
                if (topkValue) topkValue.textContent = ragTopk.value;
            });
            ragTopk.addEventListener('change', () => this.saveSettings());
        }

        // 精简模式开关
        const compactMode = document.getElementById('compact-mode');
        if (compactMode) {
            compactMode.addEventListener('change', () => {
                this.settings.compact_mode = compactMode.checked;
                this.saveSettings();
                // 通知聊天模块切换模式
                if (window.chat) {
                    window.chat.setCompactMode(compactMode.checked);
                }
            });
        }
    }

    /* ==================== Report ==================== */
    bindReportEvents() {
        document.getElementById('download-json')?.addEventListener('click', () => {
            window.location.href = '/api/report/download/json';
        });
        document.getElementById('download-txt')?.addEventListener('click', () => {
            window.location.href = '/api/report/download/txt';
        });
        document.getElementById('generate-report-btn')?.addEventListener('click', () => {
            this.generateReport();
        });
        document.getElementById('download-report-md')?.addEventListener('click', () => {
            this.downloadReportMarkdown();
        });
    }

    /* ==================== Phase Timeline ==================== */
    updatePhaseTimeline(phase) {
        const nodes = document.querySelectorAll('.phase-node');
        const lines = document.querySelectorAll('.phase-line');

        // Map visible phases to node indices
        const phaseMap = [0, 1, 3, 5, 6, 7, 8];

        nodes.forEach((node, idx) => {
            const nodePhase = phaseMap[idx];
            node.classList.remove('completed', 'active');

            if (nodePhase < phase) {
                node.classList.add('completed');
            } else if (nodePhase === phase || (nodePhase === phaseMap[idx] && phase >= nodePhase && phase < (phaseMap[idx + 1] || 999))) {
                // Mark active for current phase or phases in between
            }
        });

        // More precise: find the active node
        let activeIdx = 0;
        for (let i = 0; i < phaseMap.length; i++) {
            if (phase >= phaseMap[i]) {
                activeIdx = i;
            }
        }

        nodes.forEach((node, idx) => {
            node.classList.remove('completed', 'active');
            if (idx < activeIdx) {
                node.classList.add('completed');
            } else if (idx === activeIdx) {
                node.classList.add('active');
            }
        });

        // Highlight lines
        lines.forEach((line, idx) => {
            if (idx < activeIdx) {
                line.style.background = 'var(--neon-blue)';
                line.style.boxShadow = '0 0 6px rgba(0, 212, 255, 0.3)';
            } else {
                line.style.background = 'var(--text-muted)';
                line.style.boxShadow = 'none';
            }
        });
    }

    resetPhaseTimeline() {
        const nodes = document.querySelectorAll('.phase-node');
        const lines = document.querySelectorAll('.phase-line');
        nodes.forEach((node, idx) => {
            node.classList.remove('completed', 'active');
            if (idx === 0) node.classList.add('active');
        });
        lines.forEach(line => {
            line.style.background = 'var(--text-muted)';
            line.style.boxShadow = 'none';
        });
    }

    /* ==================== Data Loading ==================== */
    async loadPresets() {
        try {
            const response = await fetch('/api/presets');
            const data = await response.json();
            this.presets = data.prompts || {};
        } catch (error) {
            console.error('加载预设失败:', error);
        }
    }

    async loadSettings() {
        try {
            const response = await fetch('/api/settings');
            const data = await response.json();
            this.settings = { ...this.settings, ...data };
            this.updateSettingsUI();
        } catch (error) {
            console.error('加载设置失败:', error);
        }
    }

    async saveSettings() {
        try {
            await fetch('/api/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(this.settings)
            });
        } catch (error) {
            console.error('保存设置失败:', error);
        }
    }

    updateSettingsUI() {
        const promptSelect = document.getElementById('prompt-select');
        const systemPrompt = document.getElementById('system-prompt');
        const enableTts = document.getElementById('enable-tts');
        const enableRag = document.getElementById('enable-rag');
        const ragSettings = document.getElementById('rag-settings');
        const ragDomain = document.getElementById('rag-domain');
        const ragTopk = document.getElementById('rag-topk');
        const topkValue = document.getElementById('topk-value');

        if (promptSelect) promptSelect.value = this.settings.prompt_choice;
        if (systemPrompt) systemPrompt.value = this.settings.system_prompt || this.presets[this.settings.prompt_choice] || '';
        if (enableTts) enableTts.checked = this.settings.enable_tts;
        if (enableRag) enableRag.checked = this.settings.enable_rag;
        if (ragSettings) ragSettings.style.display = this.settings.enable_rag ? 'block' : 'none';
        if (ragDomain) ragDomain.value = this.settings.rag_domain;
        if (ragTopk) ragTopk.value = this.settings.rag_top_k;
        if (topkValue) topkValue.textContent = this.settings.rag_top_k;

        // 精简模式
        const compactMode = document.getElementById('compact-mode');
        if (compactMode) compactMode.checked = this.settings.compact_mode;
        // 同步到聊天模块
        if (window.chat) {
            window.chat.setCompactMode(this.settings.compact_mode);
        }
    }

    async loadRagDomains() {
        try {
            const response = await fetch('/api/rag/domains');
            const data = await response.json();
            const domains = data.domains || [];
            const ragDomain = document.getElementById('rag-domain');
            if (ragDomain && domains.length > 0) {
                ragDomain.innerHTML = domains.map(d =>
                    `<option value="${d}">${d}</option>`
                ).join('');
                ragDomain.value = this.settings.rag_domain;
            }
        } catch (error) {
            console.error('加载 RAG 领域失败:', error);
        }
    }

    async loadRagHistory() {
        try {
            const response = await fetch('/api/rag/history');
            const data = await response.json();
            const history = data.rag_history || [];
            const container = document.getElementById('rag-history');
            if (!container) return;

            if (history.length === 0) {
                container.innerHTML = '<div class="empty-state-mini"><i class="fas fa-search"></i><p>暂无检索记录</p></div>';
                return;
            }

            let html = `<p style="margin-bottom:12px;font-size:12px;color:var(--text-secondary);">共 <strong>${history.length}</strong> 条检索记录</p>`;
            for (let i = history.length - 1; i >= 0; i--) {
                const item = history[i];
                const snippets = item.retrieved.split('\n').filter(s => s.trim());
                const preview = snippets.slice(0, 3).map((s, idx) =>
                    `<div class="rag-snippet"><b>片段 ${idx + 1}:</b> ${this.escapeHtml(s.substring(0, 200))}${s.length > 200 ? '...' : ''}</div>`
                ).join('');
                html += `
                    <div class="rag-card">
                        <div class="rag-query">Q: ${this.escapeHtml(item.query)}</div>
                        <div class="rag-content">${preview}</div>
                        <div class="rag-meta">领域: ${item.domain} · Top-${item.top_k} · 共 ${snippets.length} 条片段</div>
                    </div>`;
            }
            container.innerHTML = html;
        } catch (error) {
            console.error('加载 RAG 历史失败:', error);
        }
    }

    /* ==================== Report Generation ==================== */
    async generateReport() {
        const reportContent = document.getElementById('report-content');
        const reportDownload = document.getElementById('report-download');
        const generateBtn = document.getElementById('generate-report-btn');
        if (!reportContent) return;

        if (generateBtn) generateBtn.disabled = true;
        reportContent.textContent = '正在生成报告，请稍候...';
        this.reportContent = '';

        try {
            const response = await fetch('/api/report/stream', { method: 'POST' });
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

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
                                this.reportContent = data.content;
                                if (window.mdRenderer) {
                                    window.mdRenderer.renderTo(reportContent, this.reportContent);
                                } else {
                                    reportContent.textContent = this.reportContent;
                                }
                            } else if (data.type === 'done') {
                                if (reportDownload) reportDownload.style.display = 'block';
                            } else if (data.type === 'error') {
                                reportContent.textContent = `生成失败: ${data.message}`;
                            }
                        } catch (e) {
                            console.error('解析报告数据失败:', e);
                        }
                    }
                }
            }
        } catch (error) {
            console.error('生成报告失败:', error);
            reportContent.textContent = `生成失败: ${error.message}`;
        } finally {
            if (generateBtn) generateBtn.disabled = false;
        }
    }

    downloadReportMarkdown() {
        if (!this.reportContent) {
            alert('没有报告内容可下载');
            return;
        }
        const blob = new Blob([this.reportContent], { type: 'text/markdown' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `interview_report_${new Date().toISOString().slice(0, 10)}.md`;
        a.click();
        URL.revokeObjectURL(url);
    }

    /* ==================== Resume ==================== */
    bindResumeEvents() {
        const resumeInput = document.getElementById('resume-input');
        const resumeUploadBtn = document.getElementById('resume-upload-btn');
        const resumeDeleteBtn = document.getElementById('resume-delete-btn');

        if (resumeUploadBtn && resumeInput) {
            resumeUploadBtn.addEventListener('click', () => resumeInput.click());
        }
        if (resumeInput) {
            resumeInput.addEventListener('change', async (e) => {
                const file = e.target.files[0];
                if (file) await this.uploadResume(file);
                resumeInput.value = '';
            });
        }
        if (resumeDeleteBtn) {
            resumeDeleteBtn.addEventListener('click', () => this.deleteResume());
        }
    }

    async loadResumeStatus() {
        try {
            const response = await fetch('/api/resume/status');
            const data = await response.json();
            this.resumeUploaded = data.uploaded;
            this.resumeFileName = data.file_name || '';
            this.updateResumeUI();
        } catch (error) {
            console.error('加载简历状态失败:', error);
        }
    }

    async uploadResume(file) {
        const uploadArea = document.getElementById('resume-upload-area');
        const progressArea = document.getElementById('resume-progress');
        const progressFill = document.getElementById('resume-progress-fill');
        const progressText = document.getElementById('resume-progress-text');

        if (uploadArea) uploadArea.style.display = 'none';
        if (progressArea) progressArea.style.display = 'block';
        if (progressFill) progressFill.style.width = '20%';
        if (progressText) progressText.textContent = '正在上传文件...';

        try {
            const formData = new FormData();
            formData.append('file', file);
            if (progressFill) progressFill.style.width = '40%';
            if (progressText) progressText.textContent = 'AI 正在分析简历（约 10-15 秒）...';

            const response = await fetch('/api/resume/upload', {
                method: 'POST',
                body: formData
            });
            const data = await response.json();

            if (data.status === 'ok') {
                if (progressFill) progressFill.style.width = '100%';
                if (progressText) progressText.textContent = '✅ 简历解析完成！';
                this.resumeUploaded = true;
                this.resumeFileName = data.file_name;
                setTimeout(() => this.updateResumeUI(), 1000);
            } else {
                throw new Error(data.message || '上传失败');
            }
        } catch (error) {
            console.error('简历上传失败:', error);
            if (progressText) progressText.textContent = `❌ 上传失败: ${error.message}`;
            setTimeout(() => this.updateResumeUI(), 3000);
        }
    }

    async deleteResume() {
        if (!confirm('确定要删除已上传的简历吗？')) return;
        try {
            const response = await fetch('/api/resume', { method: 'DELETE' });
            const data = await response.json();
            if (data.status === 'ok') {
                this.resumeUploaded = false;
                this.resumeFileName = '';
                this.updateResumeUI();
            }
        } catch (error) {
            console.error('删除简历失败:', error);
        }
    }

    updateResumeUI() {
        const uploadArea = document.getElementById('resume-upload-area');
        const uploadedArea = document.getElementById('resume-uploaded');
        const progressArea = document.getElementById('resume-progress');
        const fileNameEl = document.getElementById('resume-file-name');
        const statusEl = document.getElementById('resume-status');

        if (progressArea) progressArea.style.display = 'none';

        if (this.resumeUploaded) {
            if (uploadArea) uploadArea.style.display = 'none';
            if (uploadedArea) uploadedArea.style.display = 'flex';
            if (fileNameEl) fileNameEl.textContent = this.resumeFileName;
            if (statusEl) statusEl.innerHTML = '<p class="hint-text" style="color: var(--success);">✅ 简历已上传，面试将个性化进行</p>';
        } else {
            if (uploadArea) uploadArea.style.display = 'block';
            if (uploadedArea) uploadedArea.style.display = 'none';
            if (statusEl) statusEl.innerHTML = '<p class="hint-text">上传 PDF 简历，AI 将更了解你</p>';
        }
    }

    /* ==================== Utilities ==================== */
    getSettings() {
        return this.settings;
    }

    showLoading(text = '正在处理...') {
        if (this.loadingOverlay) this.loadingOverlay.classList.add('show');
        if (this.loadingText) this.loadingText.textContent = text;
    }

    hideLoading() {
        if (this.loadingOverlay) this.loadingOverlay.classList.remove('show');
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

document.addEventListener('DOMContentLoaded', () => {
    window.app = new App();
});

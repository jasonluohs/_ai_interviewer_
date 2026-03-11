/**
 * 主应用逻辑
 * 初始化、Tab 切换、设置管理、RAG 历史、报告生成
 */

class App {
    constructor() {
        // 设置
        this.settings = {
            prompt_choice: '正常型面试官（默认）',
            system_prompt: '',
            enable_tts: true,
            enable_rag: true,
            rag_domain: 'cs',
            rag_top_k: 6
        };
        
        // 预设提示词（从服务器加载）
        this.presets = {};
        
        // 报告内容
        this.reportContent = '';
        
        // 简历状态
        this.resumeUploaded = false;
        this.resumeFileName = '';
        
        // UI 元素
        this.loadingOverlay = document.getElementById('loading-overlay');
        this.loadingText = document.getElementById('loading-text');
        
        this.init();
    }
    
    /**
     * 初始化应用
     */
    async init() {
        console.log('🚀 初始化 AI 面试官...');
        
        // 绑定事件
        this.bindTabEvents();
        this.bindSidebarEvents();
        this.bindSettingsEvents();
        this.bindReportEvents();
        this.bindResumeEvents();
        
        // 加载数据
        await this.loadPresets();
        await this.loadSettings();
        await this.loadRagDomains();
        await this.loadRagHistory();
        await this.loadResumeStatus();
        
        console.log('✅ 初始化完成');
    }
    
    /**
     * Tab 切换
     */
    bindTabEvents() {
        const tabBtns = document.querySelectorAll('.tab-btn');
        const tabPanes = document.querySelectorAll('.tab-pane');
        
        tabBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                const tabId = btn.dataset.tab;
                
                // 更新按钮状态
                tabBtns.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                
                // 更新面板显示
                tabPanes.forEach(pane => {
                    pane.classList.toggle('active', pane.id === `tab-${tabId}`);
                });
                
                // 特殊处理
                if (tabId === 'rag') {
                    this.loadRagHistory();
                }
            });
        });
    }
    
    /**
     * 侧边栏事件
     */
    bindSidebarEvents() {
        const sidebarToggle = document.getElementById('sidebar-toggle');
        const sidebar = document.getElementById('sidebar');
        const mainContent = document.querySelector('.main-content');
        
        if (sidebarToggle && sidebar) {
            sidebarToggle.addEventListener('click', () => {
                sidebar.classList.toggle('show');
            });
            
            // 点击主内容区关闭侧边栏（移动端）
            if (mainContent) {
                mainContent.addEventListener('click', () => {
                    if (window.innerWidth <= 900) {
                        sidebar.classList.remove('show');
                    }
                });
            }
        }
        
        // 新对话按钮
        const newChatBtn = document.getElementById('new-chat-btn');
        if (newChatBtn) {
            newChatBtn.addEventListener('click', () => {
                if (confirm('确定要开始新对话吗？当前对话历史将被清空。')) {
                    window.chat?.clearHistory();
                    // 重置报告
                    this.reportContent = '';
                    const reportContentEl = document.getElementById('report-content');
                    if (reportContentEl) reportContentEl.textContent = '';
                    const reportDownload = document.getElementById('report-download');
                    if (reportDownload) reportDownload.style.display = 'none';
                }
            });
        }
        
        // 折叠面板
        const promptToggle = document.getElementById('prompt-toggle');
        const promptContent = document.getElementById('prompt-content');
        if (promptToggle && promptContent) {
            promptToggle.addEventListener('click', () => {
                promptToggle.classList.toggle('active');
                promptContent.classList.toggle('show');
            });
        }
    }
    
    /**
     * 设置事件
     */
    bindSettingsEvents() {
        // 面试官类型选择
        const promptSelect = document.getElementById('prompt-select');
        if (promptSelect) {
            promptSelect.addEventListener('change', () => {
                const choice = promptSelect.value;
                this.settings.prompt_choice = choice;
                
                // 更新提示词
                if (choice !== '自定义' && this.presets[choice]) {
                    this.settings.system_prompt = this.presets[choice];
                    const promptArea = document.getElementById('system-prompt');
                    if (promptArea) promptArea.value = this.settings.system_prompt;
                }
                
                this.saveSettings();
            });
        }
        
        // 系统提示词
        const systemPrompt = document.getElementById('system-prompt');
        if (systemPrompt) {
            systemPrompt.addEventListener('change', () => {
                this.settings.system_prompt = systemPrompt.value;
                this.saveSettings();
            });
        }
        
        // TTS 开关
        const enableTts = document.getElementById('enable-tts');
        if (enableTts) {
            enableTts.addEventListener('change', () => {
                this.settings.enable_tts = enableTts.checked;
                this.saveSettings();
            });
        }
        
        // RAG 开关
        const enableRag = document.getElementById('enable-rag');
        const ragSettings = document.getElementById('rag-settings');
        if (enableRag) {
            enableRag.addEventListener('change', () => {
                this.settings.enable_rag = enableRag.checked;
                if (ragSettings) {
                    ragSettings.style.display = enableRag.checked ? 'block' : 'none';
                }
                this.saveSettings();
            });
        }
        
        // RAG 领域
        const ragDomain = document.getElementById('rag-domain');
        if (ragDomain) {
            ragDomain.addEventListener('change', () => {
                this.settings.rag_domain = ragDomain.value;
                this.saveSettings();
            });
        }
        
        // RAG Top-K
        const ragTopk = document.getElementById('rag-topk');
        const topkValue = document.getElementById('topk-value');
        if (ragTopk) {
            ragTopk.addEventListener('input', () => {
                this.settings.rag_top_k = parseInt(ragTopk.value);
                if (topkValue) topkValue.textContent = ragTopk.value;
            });
            ragTopk.addEventListener('change', () => {
                this.saveSettings();
            });
        }
    }
    
    /**
     * 报告事件
     */
    bindReportEvents() {
        // 下载 JSON
        const downloadJson = document.getElementById('download-json');
        if (downloadJson) {
            downloadJson.addEventListener('click', () => {
                window.location.href = '/api/report/download/json';
            });
        }
        
        // 下载 TXT
        const downloadTxt = document.getElementById('download-txt');
        if (downloadTxt) {
            downloadTxt.addEventListener('click', () => {
                window.location.href = '/api/report/download/txt';
            });
        }
        
        // 生成报告
        const generateBtn = document.getElementById('generate-report-btn');
        if (generateBtn) {
            generateBtn.addEventListener('click', () => {
                this.generateReport();
            });
        }
        
        // 下载报告 Markdown
        const downloadReportMd = document.getElementById('download-report-md');
        if (downloadReportMd) {
            downloadReportMd.addEventListener('click', () => {
                this.downloadReportMarkdown();
            });
        }
    }
    
    /**
     * 加载预设提示词
     */
    async loadPresets() {
        try {
            const response = await fetch('/api/presets');
            const data = await response.json();
            this.presets = data.prompts || {};
            console.log('✅ 预设提示词已加载');
        } catch (error) {
            console.error('加载预设失败:', error);
        }
    }
    
    /**
     * 加载设置
     */
    async loadSettings() {
        try {
            const response = await fetch('/api/settings');
            const data = await response.json();
            this.settings = { ...this.settings, ...data };
            
            // 更新 UI
            this.updateSettingsUI();
            console.log('✅ 设置已加载');
        } catch (error) {
            console.error('加载设置失败:', error);
        }
    }
    
    /**
     * 保存设置
     */
    async saveSettings() {
        try {
            await fetch('/api/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(this.settings)
            });
            console.log('✅ 设置已保存');
        } catch (error) {
            console.error('保存设置失败:', error);
        }
    }
    
    /**
     * 更新设置 UI
     */
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
    }
    
    /**
     * 加载 RAG 领域
     */
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
    
    /**
     * 加载 RAG 历史
     */
    async loadRagHistory() {
        try {
            const response = await fetch('/api/rag/history');
            const data = await response.json();
            const history = data.rag_history || [];
            
            const container = document.getElementById('rag-history');
            if (!container) return;
            
            if (history.length === 0) {
                container.innerHTML = '<div class="empty-hint">暂无检索记录。开启 RAG 并发送消息后，检索到的知识片段会在此展示。</div>';
                return;
            }
            
            let html = `<p>共 <strong>${history.length}</strong> 条检索记录</p>`;
            
            // 倒序显示
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
                    </div>
                `;
            }
            
            container.innerHTML = html;
            
        } catch (error) {
            console.error('加载 RAG 历史失败:', error);
        }
    }
    
    /**
     * 生成面试报告
     */
    async generateReport() {
        const reportContent = document.getElementById('report-content');
        const reportDownload = document.getElementById('report-download');
        const generateBtn = document.getElementById('generate-report-btn');
        
        if (!reportContent) return;
        
        // 禁用按钮
        if (generateBtn) generateBtn.disabled = true;
        
        reportContent.textContent = '正在生成报告，请稍候...';
        this.reportContent = '';
        
        try {
            const response = await fetch('/api/report/stream', {
                method: 'POST'
            });
            
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
                                reportContent.textContent = this.reportContent;
                            } else if (data.type === 'done') {
                                console.log('✅ 报告生成完成');
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
    
    /**
     * 下载报告 Markdown
     */
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
    
    /**
     * 获取当前设置
     */
    getSettings() {
        return this.settings;
    }
    
    /**
     * 显示加载覆盖层
     * @param {string} text - 加载提示文本
     */
    showLoading(text = '正在处理...') {
        if (this.loadingOverlay) {
            this.loadingOverlay.classList.add('show');
        }
        if (this.loadingText) {
            this.loadingText.textContent = text;
        }
    }
    
    /**
     * 隐藏加载覆盖层
     */
    hideLoading() {
        if (this.loadingOverlay) {
            this.loadingOverlay.classList.remove('show');
        }
    }
    
    /**
     * HTML 转义
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    /**
     * 绑定简历上传事件
     */
    bindResumeEvents() {
        const resumeInput = document.getElementById('resume-input');
        const resumeUploadBtn = document.getElementById('resume-upload-btn');
        const resumeDeleteBtn = document.getElementById('resume-delete-btn');
        
        // 点击上传按钮触发文件选择
        if (resumeUploadBtn && resumeInput) {
            resumeUploadBtn.addEventListener('click', () => {
                resumeInput.click();
            });
        }
        
        // 文件选择后上传
        if (resumeInput) {
            resumeInput.addEventListener('change', async (e) => {
                const file = e.target.files[0];
                if (file) {
                    await this.uploadResume(file);
                }
                // 清空 input 以便重复选择同一文件
                resumeInput.value = '';
            });
        }
        
        // 删除简历
        if (resumeDeleteBtn) {
            resumeDeleteBtn.addEventListener('click', async () => {
                await this.deleteResume();
            });
        }
    }
    
    /**
     * 加载简历状态
     */
    async loadResumeStatus() {
        try {
            const response = await fetch('/api/resume/status');
            const data = await response.json();
            
            this.resumeUploaded = data.uploaded;
            this.resumeFileName = data.file_name || '';
            
            this.updateResumeUI();
            console.log('✅ 简历状态已加载');
        } catch (error) {
            console.error('加载简历状态失败:', error);
        }
    }
    
    /**
     * 上传简历
     */
    async uploadResume(file) {
        const uploadArea = document.getElementById('resume-upload-area');
        const progressArea = document.getElementById('resume-progress');
        const progressFill = document.getElementById('resume-progress-fill');
        const progressText = document.getElementById('resume-progress-text');
        
        // 显示进度条
        if (uploadArea) uploadArea.style.display = 'none';
        if (progressArea) progressArea.style.display = 'block';
        if (progressFill) progressFill.style.width = '20%';
        if (progressText) progressText.textContent = '正在上传文件...';
        
        try {
            // 创建 FormData
            const formData = new FormData();
            formData.append('file', file);
            
            // 更新进度
            if (progressFill) progressFill.style.width = '40%';
            if (progressText) progressText.textContent = 'AI 正在分析简历（约 10-15 秒）...';
            
            // 上传文件
            const response = await fetch('/api/resume/upload', {
                method: 'POST',
                body: formData
            });
            
            const data = await response.json();
            
            if (data.status === 'ok') {
                // 更新进度
                if (progressFill) progressFill.style.width = '100%';
                if (progressText) progressText.textContent = '✅ 简历解析完成！';
                
                // 更新状态
                this.resumeUploaded = true;
                this.resumeFileName = data.file_name;
                
                // 延迟后更新 UI
                setTimeout(() => {
                    this.updateResumeUI();
                }, 1000);
                
                console.log('✅ 简历上传成功:', data.file_name);
            } else {
                throw new Error(data.message || '上传失败');
            }
            
        } catch (error) {
            console.error('简历上传失败:', error);
            if (progressText) progressText.textContent = `❌ 上传失败: ${error.message}`;
            
            // 3 秒后恢复 UI
            setTimeout(() => {
                this.updateResumeUI();
            }, 3000);
        }
    }
    
    /**
     * 删除简历
     */
    async deleteResume() {
        if (!confirm('确定要删除已上传的简历吗？')) {
            return;
        }
        
        try {
            const response = await fetch('/api/resume', {
                method: 'DELETE'
            });
            
            const data = await response.json();
            
            if (data.status === 'ok') {
                this.resumeUploaded = false;
                this.resumeFileName = '';
                this.updateResumeUI();
                console.log('✅ 简历已删除');
            }
        } catch (error) {
            console.error('删除简历失败:', error);
        }
    }
    
    /**
     * 更新简历 UI
     */
    updateResumeUI() {
        const uploadArea = document.getElementById('resume-upload-area');
        const uploadedArea = document.getElementById('resume-uploaded');
        const progressArea = document.getElementById('resume-progress');
        const fileNameEl = document.getElementById('resume-file-name');
        const statusEl = document.getElementById('resume-status');
        
        // 隐藏进度条
        if (progressArea) progressArea.style.display = 'none';
        
        if (this.resumeUploaded) {
            // 显示已上传状态
            if (uploadArea) uploadArea.style.display = 'none';
            if (uploadedArea) uploadedArea.style.display = 'flex';
            if (fileNameEl) fileNameEl.textContent = this.resumeFileName;
            if (statusEl) statusEl.innerHTML = '<p class="resume-hint" style="color: #10b981;">✅ 简历已上传，面试将个性化进行</p>';
        } else {
            // 显示上传区域
            if (uploadArea) uploadArea.style.display = 'block';
            if (uploadedArea) uploadedArea.style.display = 'none';
            if (statusEl) statusEl.innerHTML = '<p class="resume-hint">上传 PDF 简历，让 AI 面试官更了解你</p>';
        }
    }
}

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
    window.app = new App();
});

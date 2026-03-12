/**
 * Markdown 渲染模块 — Cybernetic Command
 * 基于 marked.js + highlight.js，提供安全的 Markdown 渲染能力
 * 模块化设计，可独立于其他组件使用
 */

class MarkdownRenderer {
    constructor(options = {}) {
        this.ready = false;
        this.options = {
            enableHighlight: options.enableHighlight !== false,
            sanitize: options.sanitize !== false,
            breaks: options.breaks !== false,
            gfm: options.gfm !== false,
            ...options
        };
        this._init();
    }

    _init() {
        if (typeof marked === 'undefined') {
            console.warn('[MarkdownRenderer] marked.js 未加载，Markdown 渲染不可用');
            return;
        }

        try {
            // marked v12+ 不再支持 highlight 选项，使用后渲染方式应用高亮
            marked.setOptions({
                breaks: this.options.breaks,
                gfm: this.options.gfm
            });
        } catch (e) {
            console.warn('[MarkdownRenderer] setOptions 失败，使用默认配置:', e);
        }

        this.ready = true;
        console.log('[MarkdownRenderer] 初始化完成, marked.parse 可用:', typeof marked.parse === 'function');
    }

    /**
     * 将 Markdown 文本渲染为 HTML
     * @param {string} text - Markdown 原始文本
     * @returns {string} 渲染后的 HTML
     */
    render(text) {
        if (!text) return '';
        if (!this.ready) return this._escapeHtml(text);

        try {
            let html = marked.parse(text);
            if (this.options.sanitize) {
                html = this._sanitize(html);
            }
            return html;
        } catch (e) {
            console.error('[MarkdownRenderer] 渲染失败:', e);
            return this._escapeHtml(text);
        }
    }

    /**
     * 将渲染后的 HTML 注入到指定 DOM 元素
     * @param {HTMLElement} element - 目标元素
     * @param {string} text - Markdown 原始文本
     */
    renderTo(element, text) {
        if (!element) return;
        const html = this.render(text);
        element.innerHTML = html;

        // 后渲染代码高亮 (marked v12+ 不再内置 highlight 回调)
        this._highlightCode(element);
        // 对代码块添加复制按钮
        this._addCopyButtons(element);
    }

    /**
     * 对容器内所有代码块应用 highlight.js 高亮
     */
    _highlightCode(container) {
        if (!this.options.enableHighlight || typeof hljs === 'undefined') return;
        container.querySelectorAll('pre code').forEach(block => {
            try {
                hljs.highlightElement(block);
            } catch (_) { /* 忽略高亮失败 */ }
        });
    }

    /**
     * 基础 HTML 净化 — 移除危险标签和属性
     */
    _sanitize(html) {
        const dangerousTags = /<\/?(?:script|iframe|object|embed|form|input|button|select|textarea|link|meta|style)\b[^>]*>/gi;
        let sanitized = html.replace(dangerousTags, '');

        // 移除事件处理器属性
        sanitized = sanitized.replace(/\s+on\w+\s*=\s*["'][^"']*["']/gi, '');
        sanitized = sanitized.replace(/\s+on\w+\s*=\s*\S+/gi, '');

        // 移除 javascript: 协议
        sanitized = sanitized.replace(/href\s*=\s*["']javascript:[^"']*["']/gi, 'href="#"');

        return sanitized;
    }

    _escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * 为代码块添加复制按钮
     */
    _addCopyButtons(container) {
        container.querySelectorAll('pre').forEach(pre => {
            if (pre.querySelector('.code-copy-btn')) return;

            const btn = document.createElement('button');
            btn.className = 'code-copy-btn';
            btn.innerHTML = '<i class="fas fa-copy"></i>';
            btn.title = '复制代码';
            btn.addEventListener('click', () => {
                const code = pre.querySelector('code');
                const text = code ? code.textContent : pre.textContent;
                navigator.clipboard.writeText(text).then(() => {
                    btn.innerHTML = '<i class="fas fa-check"></i>';
                    btn.classList.add('copied');
                    setTimeout(() => {
                        btn.innerHTML = '<i class="fas fa-copy"></i>';
                        btn.classList.remove('copied');
                    }, 2000);
                });
            });

            pre.style.position = 'relative';
            pre.appendChild(btn);
        });
    }
}

// 全局单例
window.mdRenderer = new MarkdownRenderer();

/**
 * 公开内容生成平台 - 公共 JavaScript
 */

// =============================================================================
// 工具函数
// =============================================================================

const Utils = {
    /**
     * 格式化日期
     */
    formatDate: function(date) {
        if (!date) return '';
        const d = new Date(date);
        return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    },

    /**
     * 格式化日期时间
     */
    formatDateTime: function(date) {
        if (!date) return '';
        const d = new Date(date);
        return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
    },

    /**
     * 节流函数
     */
    throttle: function(func, limit) {
        let inThrottle;
        return function(...args) {
            if (!inThrottle) {
                func.apply(this, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        };
    },

    /**
     * 防抖函数
     */
    debounce: function(func, wait) {
        let timeout;
        return function(...args) {
            clearTimeout(timeout);
            timeout = setTimeout(() => func.apply(this, args), wait);
        };
    },

    /**
     * 深拷贝
     */
    deepClone: function(obj) {
        return JSON.parse(JSON.stringify(obj));
    },

    /**
     * 获取 URL 参数
     */
    getUrlParam: function(name) {
        const params = new URLSearchParams(window.location.search);
        return params.get(name);
    },

    /**
     * 复制文本到剪贴板
     */
    copyToClipboard: function(text) {
        return navigator.clipboard.writeText(text);
    },

    /**
     * 生成唯一 ID
     */
    generateId: function() {
        return Date.now().toString(36) + Math.random().toString(36).substr(2);
    }
};

// =============================================================================
// API 请求封装
// =============================================================================

const API = {
    baseUrl: '/public/api',

    /**
     * GET 请求
     */
    get: async function(url, params = {}) {
        const queryString = new URLSearchParams(params).toString();
        const fullUrl = queryString ? `${this.baseUrl}${url}?${queryString}` : `${this.baseUrl}${url}`;

        const response = await fetch(fullUrl, {
            method: 'GET',
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        return response.json();
    },

    /**
     * POST 请求
     */
    post: async function(url, data = {}) {
        const response = await fetch(`${this.baseUrl}${url}`, {
            method: 'POST',
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        });

        return response.json();
    },

    /**
     * PUT 请求
     */
    put: async function(url, data = {}) {
        const response = await fetch(`${this.baseUrl}${url}`, {
            method: 'PUT',
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        });

        return response.json();
    },

    /**
     * DELETE 请求
     */
    delete: async function(url) {
        const response = await fetch(`${this.baseUrl}${url}`, {
            method: 'DELETE',
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        return response.json();
    }
};

// =============================================================================
// UI 组件
// =============================================================================

const UI = {
    /**
     * 显示提示消息
     */
    toast: function(message, type = 'info', duration = 3000) {
        const toast = document.createElement('div');
        toast.className = `alert alert-${type}`;
        toast.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 9999;
            max-width: 300px;
            animation: slideIn 0.3s ease;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        `;
        toast.textContent = message;
        document.body.appendChild(toast);

        setTimeout(() => {
            toast.style.animation = 'slideOut 0.3s ease';
            setTimeout(() => toast.remove(), 300);
        }, duration);
    },

    /**
     * 显示加载中
     */
    showLoading: function(element) {
        if (!element) return;
        element.disabled = true;
        element.dataset.originalText = element.textContent;
        element.innerHTML = '<span class="spinner" style="width:16px;height:16px;border-width:2px;"></span> 加载中...';
    },

    /**
     * 隐藏加载中
     */
    hideLoading: function(element) {
        if (!element) return;
        element.disabled = false;
        element.textContent = element.dataset.originalText || element.textContent;
    },

    /**
     * 确认对话框
     */
    confirm: function(message, onConfirm, onCancel) {
        const overlay = document.createElement('div');
        overlay.className = 'modal-overlay active';
        overlay.innerHTML = `
            <div class="modal">
                <div class="modal-header">
                    <h3>确认操作</h3>
                    <button class="btn-close" onclick="UI.closeModal()">&times;</button>
                </div>
                <div class="modal-body">
                    <p>${message}</p>
                </div>
                <div class="modal-footer">
                    <button class="btn btn-outline-primary" onclick="UI.closeModal(${onCancel ? '() => { ' + onCancel.toString() + ' }' : ''})">取消</button>
                    <button class="btn btn-primary" id="confirm-btn">确认</button>
                </div>
            </div>
        `;
        document.body.appendChild(overlay);

        document.getElementById('confirm-btn').addEventListener('click', () => {
            UI.closeModal();
            if (onConfirm) onConfirm();
        });
    },

    /**
     * 关闭模态框
     */
    closeModal: function(callback) {
        const overlay = document.querySelector('.modal-overlay.active');
        if (overlay) {
            overlay.classList.remove('active');
            setTimeout(() => overlay.remove(), 200);
            if (callback) callback();
        }
    },

    /**
     * 渲染分页
     */
    renderPagination: function(container, currentPage, totalPages, onPageChange) {
        if (!container || totalPages <= 1) return;

        let html = '<div class="d-flex justify-content-center gap-2">';

        // 上一页
        if (currentPage > 1) {
            html += `<button class="btn btn-sm btn-outline-primary" onclick="${onPageChange}(${currentPage - 1})">上一页</button>`;
        }

        // 页码
        for (let i = 1; i <= totalPages; i++) {
            if (i === 1 || i === totalPages || (i >= currentPage - 2 && i <= currentPage + 2)) {
                html += `<button class="btn btn-sm ${i === currentPage ? 'btn-primary' : 'btn-outline-primary'}" onclick="${onPageChange}(${i})">${i}</button>`;
            } else if (i === currentPage - 3 || i === currentPage + 3) {
                html += '<span class="btn btn-sm btn-light">...</span>';
            }
        }

        // 下一页
        if (currentPage < totalPages) {
            html += `<button class="btn btn-sm btn-outline-primary" onclick="${onPageChange}(${currentPage + 1})">下一页</button>`;
        }

        html += '</div>';
        container.innerHTML = html;
    },

    /**
     * 渲染空状态
     */
    renderEmpty: function(container, message, icon = '📭') {
        if (!container) return;
        container.innerHTML = `
            <div class="text-center p-5">
                <div style="font-size: 4rem; opacity: 0.5;">${icon}</div>
                <p class="text-muted mt-3">${message}</p>
            </div>
        `;
    }
};

// =============================================================================
// 表单验证
// =============================================================================

const Validator = {
    rules: {
        required: (value) => value && value.trim().length > 0,
        email: (value) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value),
        phone: (value) => /^1[3-9]\d{9}$/.test(value),
        url: (value) => /^https?:\/\/.+/.test(value),
        minLength: (value, len) => value && value.length >= len,
        maxLength: (value, len) => !value || value.length <= len,
        number: (value) => !value || !isNaN(parseFloat(value)),
        integer: (value) => !value || Number.isInteger(parseFloat(value)),
        positive: (value) => !value || parseFloat(value) > 0,
    },

    messages: {
        required: '此字段不能为空',
        email: '请输入有效的邮箱地址',
        phone: '请输入有效的手机号码',
        url: '请输入有效的网址',
        minLength: '输入长度不足',
        maxLength: '输入长度超出限制',
        number: '请输入数字',
        integer: '请输入整数',
        positive: '请输入正数',
    },

    /**
     * 验证单个字段
     */
    validate: function(value, rules) {
        const errors = [];

        for (const rule of rules) {
            if (typeof rule === 'string') {
                if (!this.rules[rule](value)) {
                    errors.push(this.messages[rule]);
                }
            } else if (typeof rule === 'object') {
                const [ruleName, ruleParam] = Object.entries(rule)[0];
                if (!this.rules[ruleName](value, ruleParam)) {
                    if (ruleName === 'minLength') {
                        errors.push(`至少需要 ${ruleParam} 个字符`);
                    } else if (ruleName === 'maxLength') {
                        errors.push(`最多 ${ruleParam} 个字符`);
                    } else {
                        errors.push(this.messages[ruleName] || ruleName);
                    }
                }
            }
        }

        return errors;
    },

    /**
     * 验证表单
     */
    validateForm: function(formId, validators) {
        const form = document.getElementById(formId);
        if (!form) return true;

        let isValid = true;
        const errors = {};

        for (const [fieldName, rules] of Object.entries(validators)) {
            const input = form.querySelector(`[name="${fieldName}"]`);
            if (!input) continue;

            const fieldErrors = this.validate(input.value, rules);
            if (fieldErrors.length > 0) {
                isValid = false;
                errors[fieldName] = fieldErrors;

                // 显示错误
                const errorEl = form.querySelector(`[data-error-for="${fieldName}"]`);
                if (errorEl) {
                    errorEl.textContent = fieldErrors[0];
                    errorEl.style.display = 'block';
                }

                input.classList.add('is-invalid');
            } else {
                input.classList.remove('is-invalid');
                const errorEl = form.querySelector(`[data-error-for="${fieldName}"]`);
                if (errorEl) {
                    errorEl.style.display = 'none';
                }
            }
        }

        return { isValid, errors };
    }
};

// =============================================================================
// 添加 CSS 动画
// =============================================================================

const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from {
            transform: translateX(100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }

    @keyframes slideOut {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(100%);
            opacity: 0;
        }
    }

    .btn-close {
        background: none;
        border: none;
        font-size: 1.5rem;
        cursor: pointer;
        color: var(--text-muted);
        padding: 0;
        width: 30px;
        height: 30px;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 50%;
    }

    .btn-close:hover {
        background: var(--bg-light);
        color: var(--text-dark);
    }

    .is-invalid {
        border-color: var(--danger) !important;
    }

    .error-message {
        color: var(--danger);
        font-size: 0.75rem;
        margin-top: 0.25rem;
        display: none;
    }
`;
document.head.appendChild(style);

// =============================================================================
// 导出全局变量
// =============================================================================

window.Utils = Utils;
window.API = API;
window.UI = UI;
window.Validator = Validator;

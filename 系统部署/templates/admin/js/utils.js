/**
 * 工具函数模块
 * 提供通用的工具函数，避免全局污染
 */
const Utils = (function() {
    // 私有辅助函数
    function _createEscaper() {
        const div = document.createElement('div');
        return function escapeHtml(str) {
            if (!str) return '';
            div.textContent = str;
            return div.innerHTML;
        };
    }

    // 公共方法
    return {
        /**
         * HTML 转义 - 防止 XSS
         */
        escapeHtml: _createEscaper(),

        /**
         * 格式化字段值 - 支持对象和数组
         */
        formatFieldValue: function(fieldValue) {
            if (!fieldValue) return '-';
            if (typeof fieldValue === 'object') {
                if (Array.isArray(fieldValue)) {
                    return fieldValue.map(item => {
                        if (typeof item === 'object') {
                            return Object.entries(item).map(([k, v]) => `${k}: ${v}`).join('<br>');
                        }
                        return item;
                    }).join('<br>');
                } else {
                    return Object.entries(fieldValue).map(([k, v]) => `<strong>${k}:</strong> ${typeof v === 'object' ? JSON.stringify(v) : v}`).join('<br>');
                }
            }
            return fieldValue;
        },

        /**
         * 根据评分返回 Bootstrap 颜色类
         */
        getScoreColor: function(score) {
            if (score >= 8) return 'success';
            if (score >= 6) return 'primary';
            if (score >= 4) return 'warning';
            return 'danger';
        },

        /**
         * 根据进度获取进度条颜色
         */
        getProgressBarClass: function(progress) {
            if (progress >= 100) return 'bg-success';
            if (progress >= 50) return 'bg-info';
            return 'bg-primary';
        },

        /**
         * 获取任务类型名称
         */
        getTaskTypeNames: function(taskTypes) {
            if (!taskTypes) return '未知';
            const typeNames = {
                'profile': '画像',
                'design': '设计',
                'sub_category': '二级分类'
            };
            return taskTypes.map(t => typeNames[t] || t).join('+');
        }
    };
})();

// 兼容全局函数（供 onclick 等调用）
function escapeHtml(str) {
    return Utils.escapeHtml(str);
}

function formatFieldValue(fieldValue) {
    return Utils.formatFieldValue(fieldValue);
}

function getScoreColor(score) {
    return Utils.getScoreColor(score);
}

function getProgressBarClass(progress) {
    return Utils.getProgressBarClass(progress);
}

function getTaskTypeNames(taskTypes) {
    return Utils.getTaskTypeNames(taskTypes);
}

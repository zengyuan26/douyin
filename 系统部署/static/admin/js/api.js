/**
 * API 封装模块
 * 统一管理所有 API 请求
 */
const API = (function() {
    const BASE_URL = '/api/knowledge';

    // 通用请求方法
    async function request(endpoint, options = {}) {
        const url = endpoint.startsWith('http') ? endpoint : `${BASE_URL}${endpoint}`;
        const defaultOptions = {
            headers: {
                'Content-Type': 'application/json',
            },
        };
        const config = { ...defaultOptions, ...options };

        if (config.body && typeof config.body === 'object') {
            config.body = JSON.stringify(config.body);
        }

        try {
            const response = await fetch(url, config);
            const data = await response.json();
            return data;
        } catch (error) {
            console.error('[API Error]', endpoint, error);
            throw error;
        }
    }

    return {
        // ========== 账号相关 ==========
        accounts: {
            /**
             * 获取账号列表
             */
            list: async function(page = 1, pageSize = 20, keyword = '') {
                let url = `/accounts?page=${page}&page_size=${pageSize}`;
                if (keyword) url += `&keyword=${encodeURIComponent(keyword)}`;
                return await request(url);
            },

            /**
             * 获取单个账号详情
             */
            get: async function(accountId) {
                return await request(`/accounts/${accountId}`);
            },

            /**
             * 创建账号
             */
            create: async function(accountData) {
                return await request('/accounts', {
                    method: 'POST',
                    body: accountData
                });
            },

            /**
             * 更新账号
             */
            update: async function(accountId, accountData) {
                return await request(`/accounts/${accountId}`, {
                    method: 'PUT',
                    body: accountData
                });
            },

            /**
             * 删除账号
             */
            delete: async function(accountId) {
                return await request(`/accounts/${accountId}`, {
                    method: 'DELETE'
                });
            },

            /**
             * 分析账号画像
             */
            analyzeProfile: async function(accountId, data = {}) {
                return await request(`/accounts/${accountId}/analyze-profile`, {
                    method: 'POST',
                    body: data
                });
            },

            /**
             * 异步分析账号
             */
            analyzeAsync: async function(accountId) {
                return await request(`/accounts/${accountId}/analyze-async`, {
                    method: 'POST',
                    body: {}
                });
            },

            /**
             * 二次分类分析
             */
            analyzeSubCategories: async function(accountId, data = {}) {
                return await request(`/accounts/${accountId}/analyze-sub-categories`, {
                    method: 'POST',
                    body: data
                });
            },

            /**
             * 获取账号变更历史
             */
            getHistory: async function(accountId) {
                return await request(`/accounts/${accountId}/history`);
            }
        },

        // ========== 规则相关 ==========
        rules: {
            /**
             * 获取规则库列表
             */
            list: async function(params = {}) {
                const query = new URLSearchParams(params).toString();
                return await request(`/rules?${query}`);
            },

            /**
             * 获取规则详情
             */
            get: async function(ruleId) {
                return await request(`/rules/${ruleId}`);
            },

            /**
             * 创建规则
             */
            create: async function(ruleData) {
                return await request('/rules', {
                    method: 'POST',
                    body: ruleData
                });
            },

            /**
             * 更新规则
             */
            update: async function(ruleId, ruleData) {
                return await request(`/rules/${ruleId}`, {
                    method: 'PUT',
                    body: ruleData
                });
            },

            /**
             * 删除规则
             */
            delete: async function(ruleId) {
                return await request(`/rules/${ruleId}`, {
                    method: 'DELETE'
                });
            },

            /**
             * 导入规则
             */
            import: async function(formData) {
                return await request('/rules/import', {
                    method: 'POST',
                    body: formData
                });
            }
        },

        // ========== 素材相关 ==========
        materials: {
            /**
             * 获取素材配置
             */
            config: async function() {
                return await request('/materials/config');
            },

            /**
             * 保存素材
             */
            save: async function(materialData) {
                return await request('/materials', {
                    method: 'POST',
                    body: materialData
                });
            }
        }
    };
})();

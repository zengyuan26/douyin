/**
 * 账号管理模块
 * 封装账号相关的状态和操作
 */
const Accounts = (function() {
    // ========== 私有状态 ==========
    let currentAccount = null;
    let accountAnalysisResult = null;
    let currentAccountInfoForButton = null;
    let accountsPage = 1;
    let accountsTotalPages = 1;
    let accountsSearchKeyword = '';
    let historyData = [];
    let historyPage = 1;
    const HISTORY_PAGE_SIZE = 10;
    const ACCOUNTS_PAGE_SIZE = 20;

    // ========== 私有方法 ==========
    const platformNames = {
        'douyin': '抖音',
        'xhs': '小红书',
        'bilibili': 'B站',
        'kuaishou': '快手',
        'weibo': '微博',
        'other': '其他'
    };

    function renderAccountCard(acc) {
        const platform = platformNames[acc.platform] || acc.platform || '其他';
        const fansCount = acc.current_data?.followers || acc.current_data?.fans_count || '-';
        const statusBadge = acc.is_active
            ? '<span class="badge bg-success ms-1">活跃</span>'
            : '<span class="badge bg-secondary ms-1">非活跃</span>';

        return `
            <div class="col-md-6 col-lg-4 mb-3">
                <div class="card account-card h-100" onclick="Accounts.select(${acc.id})" style="cursor: pointer;">
                    <div class="card-body">
                        <h6 class="card-title mb-1">
                            ${Utils.escapeHtml(acc.name)}
                            ${statusBadge}
                        </h6>
                        <p class="text-muted small mb-1">
                            <i class="bi bi-link-45deg"></i> ${Utils.escapeHtml(acc.url || '-')}
                        </p>
                        <p class="text-muted small mb-0">
                            <span class="badge bg-info">${platform}</span>
                            <span class="ms-1">粉丝: ${fansCount}</span>
                        </p>
                    </div>
                </div>
            </div>
        `;
    }

    function updateAccountUI() {
        const listEl = document.getElementById('accounts-list');
        if (!listEl) return;

        // 更新分页信息
        const prevBtn = document.getElementById('accounts-prev-btn');
        const nextBtn = document.getElementById('accounts-next-btn');
        const pageInfo = document.getElementById('accounts-page-info');

        if (prevBtn) prevBtn.disabled = accountsPage <= 1;
        if (nextBtn) nextBtn.disabled = accountsPage >= accountsTotalPages;
        if (pageInfo) pageInfo.textContent = `${accountsPage} / ${accountsTotalPages}`;
    }

    // ========== 公共 API ==========
    return {
        /**
         * 获取当前账号
         */
        getCurrent: function() {
            return currentAccount;
        },

        /**
         * 获取分页信息
         */
        getPageInfo: function() {
            return {
                page: accountsPage,
                totalPages: accountsTotalPages,
                keyword: accountsSearchKeyword,
                pageSize: ACCOUNTS_PAGE_SIZE
            };
        },

        /**
         * 加载账号列表
         */
        loadList: async function() {
            const listEl = document.getElementById('accounts-list');
            if (listEl) listEl.innerHTML = '<div class="col-12 text-center text-muted py-4">加载中...</div>';

            try {
                let url = `/api/knowledge/accounts?page=${accountsPage}&page_size=${ACCOUNTS_PAGE_SIZE}`;
                if (accountsSearchKeyword) {
                    url += `&search=${encodeURIComponent(accountsSearchKeyword)}`;
                }
                const response = await fetch(url);
                const data = await response.json();

                if (data.code === 200) {
                    const accounts = data.data?.items || data.data || [];
                    accountsTotalPages = data.data?.total_pages || 1;

                    if (listEl) {
                        if (accounts.length > 0) {
                            listEl.innerHTML = accounts.map(renderAccountCard).join('');
                        } else {
                            listEl.innerHTML = '<div class="col-12 text-center text-muted py-4">暂无账号</div>';
                        }
                    }
                    updateAccountUI();
                } else {
                    if (listEl) listEl.innerHTML = `<div class="col-12 text-center text-danger py-4">加载失败: ${data.message || ''}</div>`;
                }
            } catch (e) {
                console.error('加载账号列表失败:', e);
                if (listEl) listEl.innerHTML = '<div class="col-12 text-center text-danger py-4">加载失败</div>';
            }
        },

        /**
         * 搜索账号
         */
        search: function(keyword) {
            accountsSearchKeyword = keyword;
            accountsPage = 1;
            this.loadList();
        },

        /**
         * 上一页
         */
        prevPage: function() {
            if (accountsPage > 1) {
                accountsPage--;
                this.loadList();
            }
        },

        /**
         * 下一页
         */
        nextPage: function() {
            if (accountsPage < accountsTotalPages) {
                accountsPage++;
                this.loadList();
            }
        },

        /**
         * 选择账号
         */
        select: async function(accountId) {
            console.log('Accounts.select called with id:', accountId);
            try {
                const response = await fetch(`/api/knowledge/accounts/${accountId}`);
                const data = await response.json();
                console.log('API response:', data);

                if (data.code === 200 && data.data) {
                    const acc = data.data;
                    currentAccount = {
                        id: acc.id,
                        name: acc.name,
                        url: acc.url || '',
                        bio: acc.current_data?.bio || '',
                        fans_count: acc.current_data?.followers || acc.current_data?.fans_count || '',
                        platform: acc.platform,
                        core_business: acc.core_business,
                        core_keywords: acc.core_keywords,
                        account_positioning: acc.account_positioning,
                        content_strategy: acc.content_strategy,
                        target_audience: acc.target_audience,
                        analysis_result: acc.analysis_result,
                        current_data: acc.current_data,
                        content_persona: acc.content_persona,
                        content_topic: acc.content_topic,
                        content_daily: acc.content_daily,
                        persona_type: acc.persona_type,
                        topic_content: acc.topic_content,
                        main_product: acc.main_product,
                        target_age_group: acc.target_age_group,
                        target_gender: acc.target_gender,
                        nickname_analysis: acc.nickname_analysis,
                        bio_analysis: acc.bio_analysis,
                        design_rules: acc.design_rules,
                        is_active: acc.is_active
                    };
                    return currentAccount;
                }
                return null;
            } catch (error) {
                console.error('选择账号失败:', error);
                return null;
            }
        },

        /**
         * 预览账号（点击卡片时）
         */
        preview: async function(accountId) {
            const account = await this.select(accountId);
            if (account) {
                this.displayAnalysisResult(account);
                this.addToHistory(account);
            }
        },

        /**
         * 切换到账号
         */
        switch: async function(accountId) {
            const account = await this.select(accountId);
            if (account) {
                this.enableContentTab();
                this.displayAnalysisResult(account);
                this.addToHistory(account);
            }
        },

        /**
         * 查看账号详情
         */
        detail: async function(accountId) {
            const account = await this.select(accountId);
            if (account) {
                this.showLinkedState(account);
                this.enableContentTab();
                this.displayAnalysisResult(account);
                this.addToHistory(account);
            }
        },

        /**
         * 显示账号关联状态
         */
        showLinkedState: function(account) {
            const linkedEl = document.getElementById('account-linked-state');
            if (linkedEl) {
                linkedEl.innerHTML = `
                    <div class="d-flex align-items-center">
                        <i class="bi bi-check-circle-fill text-success me-2"></i>
                        <span>当前账号: <strong>${Utils.escapeHtml(account.name)}</strong></span>
                    </div>
                `;
            }
        },

        /**
         * 启用内容 Tab
         */
        enableContentTab: function() {
            const contentTab = document.getElementById('content-tab');
            const accountTab = document.getElementById('account-tab');
            if (contentTab) contentTab.classList.remove('disabled');
            if (accountTab) {
                const bsTab = bootstrap.Tab.getOrCreateInstance(accountTab);
                bsTab.show();
            }
        },

        /**
         * 禁用内容 Tab
         */
        disableContentTab: function() {
            const contentTab = document.getElementById('content-tab');
            if (contentTab) contentTab.classList.add('disabled');
        },

        /**
         * 切换到内容 Tab
         */
        switchToContent: function() {
            const contentTab = document.getElementById('content-tab');
            if (contentTab && !contentTab.classList.contains('disabled')) {
                const bsTab = bootstrap.Tab.getOrCreateInstance(contentTab);
                bsTab.show();
            }
        },

        /**
         * 切换到账号 Tab
         */
        switchToAccount: function() {
            const accountTab = document.getElementById('account-tab');
            if (accountTab) {
                const bsTab = bootstrap.Tab.getOrCreateInstance(accountTab);
                bsTab.show();
            }
        },

        /**
         * 显示匹配规则
         */
        showMatchedRules: function(rules) {
            const container = document.getElementById('matched-rules-container');
            if (!container) return;

            if (!rules || rules.length === 0) {
                container.innerHTML = '<p class="text-muted">暂无匹配规则</p>';
                return;
            }

            container.innerHTML = rules.map(rule => `
                <div class="alert alert-info py-2 mb-2">
                    <strong>${Utils.escapeHtml(rule.dimension_name || rule.dimension_code)}</strong>
                    <span class="ms-2">${Utils.escapeHtml(rule.rule_name || '')}</span>
                </div>
            `).join('');
        },

        /**
         * 保存账号设计规则
         */
        saveDesignRule: async function(accountId, dimensionCode) {
            const response = await API.accounts.get(accountId);
            if (response.code !== 200 || !response.data) {
                alert('获取账号信息失败');
                return;
            }

            const account = response.data;
            const ruleData = account.design_rules?.[dimensionCode];
            if (!ruleData) {
                alert('暂无该维度的规则');
                return;
            }

            // 保存到后端
            const saveResponse = await fetch(`/api/knowledge/accounts/${accountId}/design-rules`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ dimension_code: dimensionCode, rules: ruleData })
            });

            const result = await saveResponse.json();
            if (result.code === 200) {
                alert('规则保存成功');
                this.loadList();
            } else {
                alert('保存失败: ' + result.message);
            }
        },

        /**
         * 保存昵称公式
         */
        saveNicknameFormula: async function(accountId, formula, score, scoreReason) {
            const response = await fetch(`/api/knowledge/accounts/${accountId}/nickname-formula`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ formula, score, score_reason: scoreReason })
            });
            const data = await response.json();
            if (data.code === 200) {
                alert('昵称公式保存成功');
            } else {
                alert('保存失败: ' + data.message);
            }
        },

        /**
         * 保存简介公式
         */
        saveBioFormula: async function(accountId, formula, score, scoreReason) {
            const response = await fetch(`/api/knowledge/accounts/${accountId}/bio-formula`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ formula, score, score_reason: scoreReason })
            });
            const data = await response.json();
            if (data.code === 200) {
                alert('简介公式保存成功');
            } else {
                alert('保存失败: ' + data.message);
            }
        },

        /**
         * 编辑账号
         */
        edit: async function(accountId) {
            const response = await API.accounts.get(accountId);
            if (response.code === 200 && response.data) {
                window.openAccountModal(response.data);
            }
        },

        /**
         * 删除账号
         */
        delete: async function(accountId) {
            if (!confirm('确定要删除这个账号吗？')) return;

            const response = await API.accounts.delete(accountId);
            if (response.code === 200) {
                alert('删除成功');
                this.loadList();
                this.clear();
            } else {
                alert('删除失败: ' + response.message);
            }
        },

        /**
         * 分析账号画像
         */
        analyzeProfile: async function(accountId, data = {}) {
            const response = await API.accounts.analyzeProfile(accountId, data);
            if (response.code === 200) {
                this.displayAnalysisResult(response.data);
                return response.data;
            } else {
                alert('分析失败: ' + response.message);
                return null;
            }
        },

        /**
         * 触发异步分析
         */
        triggerAnalysisAsync: async function(accountId) {
            const response = await API.accounts.analyzeAsync(accountId);
            if (response.code === 200) {
                this.startPolling(accountId);
            } else {
                alert('触发分析失败: ' + response.message);
            }
        },

        /**
         * 触发二次分类分析
         */
        triggerSubCategoryAnalysis: async function(accountId, event) {
            event.preventDefault();
            const response = await API.accounts.analyzeSubCategories(accountId, {});
            if (response.code === 200) {
                this.startPolling(accountId);
            } else {
                alert('触发分析失败: ' + response.message);
            }
        },

        /**
         * 启动轮询
         */
        startPolling: function(accountId) {
            if (window.queueStatusPollTimer) {
                clearInterval(window.queueStatusPollTimer);
            }

            window.queueStatusPollTimer = setInterval(async () => {
                try {
                    const response = await fetch(`/api/knowledge/accounts/${accountId}`);
                    const data = await response.json();
                    if (data.code === 200 && data.data) {
                        const status = data.data.analysis_status;
                        if (status === 'completed' || status === 'failed') {
                            clearInterval(window.queueStatusPollTimer);
                            window.queueStatusPollTimer = null;
                            this.displayAnalysisResult(data.data);
                        }
                    }
                } catch (e) {
                    console.error('轮询失败:', e);
                }
            }, 3000);
        },

        /**
         * 重新分析当前账号
         */
        reanalyze: async function() {
            if (!currentAccount || !currentAccount.id) {
                alert('请先选择账号');
                return;
            }
            await this.triggerAnalysisAsync(currentAccount.id);
        },

        /**
         * 清空当前账号
         */
        clear: function() {
            currentAccount = null;
            const linkedEl = document.getElementById('account-linked-state');
            if (linkedEl) linkedEl.innerHTML = '';
            this.disableContentTab();
        },

        /**
         * 显示分析结果
         */
        displayAnalysisResult: function(accountInfo) {
            // 设置全局变量供其他函数使用
            currentAccountInfoForButton = accountInfo;
            window.accountInfo = accountInfo;
            accountAnalysisResult = {
                account_name: accountInfo.account_name || accountInfo.nickname || accountInfo.name,
                account_url: accountInfo.url || accountInfo.account_url,
                bio: accountInfo.bio || accountInfo.current_data?.bio || '',
                fans_count: accountInfo.fans_count || accountInfo.current_data?.followers || accountInfo.current_data?.fans_count || '',
                avatar_description: accountInfo.avatar_description
            };

            // 显示结果区域
            document.getElementById('result-empty').classList.add('d-none');
            document.getElementById('result-content').classList.remove('d-none');

            // 获取分析维度分组
            fetch('/admin/api/analysis-dimensions/grouped', { cache: 'no-store' })
                .then(res => res.json())
                .then(result => {
                    const allGroups = (result.success && result.data && result.data.length > 0) ? result.data : window.getDefaultSubCategories();
                    const allSubCategories = allGroups.filter(g => (g.category || 'account') === 'account');
                    window.renderAccountAnalysisTabs(accountInfo, allSubCategories);
                })
                .catch(err => {
                    console.warn('获取分析维度分组失败，使用默认:', err);
                    const allSubCategories = window.getDefaultSubCategories().filter(g => g.category === 'account');
                    window.renderAccountAnalysisTabs(accountInfo, allSubCategories);
                });
        },

        // ========== 历史记录 ==========
        getHistory: function() {
            try {
                const stored = localStorage.getItem('account_history');
                historyData = stored ? JSON.parse(stored) : [];
            } catch (e) {
                historyData = [];
            }
            return historyData;
        },

        addToHistory: function(account) {
            const history = this.getHistory();
            // 移除重复项
            const filtered = history.filter(h => h.id !== account.id);
            // 添加到开头
            filtered.unshift({
                id: account.id,
                name: account.name,
                platform: account.platform,
                timestamp: Date.now()
            });
            // 限制数量
            historyData = filtered.slice(0, 50);
            localStorage.setItem('account_history', JSON.stringify(historyData));
        },

        deleteHistoryItem: function(index) {
            const history = this.getHistory();
            history.splice(index, 1);
            historyData = history;
            localStorage.setItem('account_history', JSON.stringify(historyData));
            this.renderHistory();
        },

        renderHistory: function() {
            const history = this.getHistory();
            const container = document.getElementById('account-history-list');
            if (!container) return;

            if (history.length === 0) {
                container.innerHTML = '<p class="text-muted small">暂无历史记录</p>';
                return;
            }

            const start = (historyPage - 1) * HISTORY_PAGE_SIZE;
            const end = start + HISTORY_PAGE_SIZE;
            const pageItems = history.slice(start, end);

            container.innerHTML = pageItems.map((item, idx) => `
                <div class="d-flex justify-content-between align-items-center py-1 border-bottom">
                    <span class="small">${Utils.escapeHtml(item.name)}</span>
                    <button class="btn btn-sm btn-link text-danger p-0" onclick="Accounts.deleteHistoryItem(${start + idx})">×</button>
                </div>
            `).join('');

            // 更新分页
            const totalPages = Math.ceil(history.length / HISTORY_PAGE_SIZE);
            const prevBtn = document.getElementById('history-prev-btn');
            const nextBtn = document.getElementById('history-next-btn');
            if (prevBtn) prevBtn.disabled = historyPage <= 1;
            if (nextBtn) nextBtn.disabled = historyPage >= totalPages;
        },

        historyPrevPage: function() {
            if (historyPage > 1) {
                historyPage--;
                this.renderHistory();
            }
        },

        historyNextPage: function() {
            const history = this.getHistory();
            const totalPages = Math.ceil(history.length / HISTORY_PAGE_SIZE);
            if (historyPage < totalPages) {
                historyPage++;
                this.renderHistory();
            }
        },

        selectFromHistory: function(item) {
            this.preview(item.id);
        },

        // ========== 账号选择下拉 ==========
        loadForSelect: async function() {
            const response = await API.accounts.list(1, 100);
            if (response.code === 200) {
                const accounts = response.data?.items || response.data || [];
                const selectEl = document.getElementById('account-select');
                if (selectEl) {
                    selectEl.innerHTML = accounts.map(acc =>
                        `<option value="${acc.id}">${Utils.escapeHtml(acc.name)}</option>`
                    ).join('');
                }
            }
        }
    };
})();

// ========== 兼容全局函数 ==========
function getAccountId() {
    return Accounts.getCurrent()?.id;
}

function accountsPrevPage() {
    Accounts.prevPage();
}

function accountsNextPage() {
    Accounts.nextPage();
}

function loadAccountsList() {
    return Accounts.loadList();
}

async function selectAccount(accountId) {
    return await Accounts.select(accountId);
}

async function selectAccountPreview(accountId) {
    return await Accounts.preview(accountId);
}

async function switchToAccount(accountId) {
    return await Accounts.switch(accountId);
}

async function viewAccountDetail(accountId) {
    return await Accounts.detail(accountId);
}

async function editAccount(accountId) {
    return await Accounts.edit(accountId);
}

async function deleteAccount(accountId) {
    return await Accounts.delete(accountId);
}

async function analyzeAccountProfile(accountId) {
    return await Accounts.analyzeProfile(accountId);
}

async function triggerAccountAnalysisAsync(accountId) {
    return await Accounts.triggerAnalysisAsync(accountId);
}

async function triggerSubCategoryAnalysis(event, accountId) {
    return await Accounts.triggerSubCategoryAnalysis(accountId, event);
}

function startAccountAnalysisPolling(accountId) {
    return Accounts.startPolling(accountId);
}

async function reanalyzeCurrentAccount() {
    return await Accounts.reanalyze();
}

function clearAccount() {
    return Accounts.clear();
}

function getAccountHistory() {
    return Accounts.getHistory();
}

function addToAccountHistory(account) {
    return Accounts.addToHistory(account);
}

function deleteHistoryItem(index) {
    return Accounts.deleteHistoryItem(index);
}

function renderAccountHistory() {
    return Accounts.renderHistory();
}

function historyPrevPage() {
    return Accounts.historyPrevPage();
}

function historyNextPage() {
    return Accounts.historyNextPage();
}

function selectAccountFromHistoryOnlyShow(item) {
    return Accounts.selectFromHistory(item);
}

function selectAccountFromHistory(item) {
    return Accounts.selectFromHistory(item);
}

function showAccountLinkedState(account) {
    return Accounts.showLinkedState(account);
}

function enableContentTab() {
    return Accounts.enableContentTab();
}

function disableContentTab() {
    return Accounts.disableContentTab();
}

function switchToContentTab() {
    return Accounts.switchToContent();
}

function switchToAccountTab() {
    return Accounts.switchToAccount();
}

function showMatchedRules(rules) {
    return Accounts.showMatchedRules(rules);
}

async function saveAccountDesignRule(accountId, dimensionCode) {
    return await Accounts.saveDesignRule(accountId, dimensionCode);
}

async function saveNicknameFormula(accountId, formula, score, scoreReason) {
    return await Accounts.saveNicknameFormula(accountId, formula, score, scoreReason);
}

async function saveBioFormula(accountId, formula, score, scoreReason) {
    return await Accounts.saveBioFormula(accountId, formula, score, scoreReason);
}

async function loadAccountsForSelect() {
    return await Accounts.loadForSelect();
}

function displayAccountAnalysisResult(accountInfo) {
    // 这个函数会被 render 模块使用，保留兼容性
    if (window.renderAccountAnalysisResult) {
        window.renderAccountAnalysisResult(accountInfo);
    }
}

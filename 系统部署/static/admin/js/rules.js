/**
 * 规则库模块
 * 封装规则的 API 和渲染函数
 */
const Rules = (function() {
    // 缓存
    let listCache = null;
    let detailCache = {};

    // ========== API 方法 ==========

    // 获取规则列表
    async function getList(params = {}) {
        const { page = 1, pageSize = 10, category = '', subCategory = '' } = params;
        try {
            let url = `/admin/api/rules?page=${page}&page_size=${pageSize}`;
            if (category) url += `&category=${encodeURIComponent(category)}`;
            if (subCategory) url += `&sub_category=${encodeURIComponent(subCategory)}`;

            const res = await fetch(url);
            const result = await res.json();
            if (result.success) {
                listCache = result.data;
                return result;
            }
        } catch (err) {
            console.warn('获取规则列表失败:', err);
        }
        return { success: false, data: [], page: 1, pages: 1, total: 0 };
    }

    // 获取规则详情
    async function get(id) {
        if (detailCache[id]) return detailCache[id];
        try {
            const res = await fetch(`/admin/api/rules/${id}`);
            const result = await res.json();
            if (result.success) {
                detailCache[id] = result.data;
                return result;
            }
        } catch (err) {
            console.warn('获取规则详情失败:', err);
        }
        return { success: false };
    }

    // 删除规则
    async function remove(id) {
        try {
            const res = await fetch(`/admin/api/rules/unified/${id}?source_type=rule`, {
                method: 'DELETE'
            });
            const result = await res.json();
            return result;
        } catch (err) {
            console.warn('删除规则失败:', err);
            return { success: false, message: err.message };
        }
    }

    // 清除缓存
    function invalidateCache() {
        listCache = null;
        detailCache = {};
    }

    // ========== 渲染方法 ==========

    // 渲染二级分类卡片
    function renderSubCategoryCards(categoryMap, currentCategory) {
        if (!currentCategory || !categoryMap[currentCategory]) {
            return '';
        }

        const subCats = categoryMap[currentCategory];
        const subCatList = Object.entries(subCats).map(([code, info]) => ({
            code,
            name: info.name,
            ruleCount: info.ruleCount || 0
        }));

        return subCatList.map(sc => `
            <div class="col-4 col-md-3 col-lg-2">
                <div class="card sub-category-card h-100 border shadow-sm" data-sub-category="${Utils.escapeHtml(sc.code)}" role="button">
                    <div class="card-body py-2 text-center">
                        <div class="fw-medium">${Utils.escapeHtml(sc.name)}</div>
                        <small class="text-muted">${sc.ruleCount} 条</small>
                    </div>
                </div>
            </div>
        `).join('');
    }

    // 渲染规则列表
    function renderRuleList(items, pagination = {}) {
        if (!items || items.length === 0) {
            return `
                <div class="text-center py-5">
                    <i class="bi bi-inbox fs-1 text-secondary d-block mb-2"></i>
                    <p class="text-muted mb-0">暂无规则数据</p>
                </div>
            `;
        }

        const cleanTitle = (title) => {
            if (!title) return '未命名公式';
            const idx = title.indexOf('：');
            return idx > 0 ? title.substring(idx + 1) : title;
        };

        // 生成分页HTML
        let paginationHtml = '';
        if (pagination && pagination.pages > 1) {
            const { page, pages, total } = pagination;
            let pageHtml = '';
            let startPage = Math.max(1, page - 3);
            let endPage = Math.min(pages, page + 3);
            if (endPage - startPage < 6) {
                if (startPage === 1) {
                    endPage = Math.min(pages, 7);
                } else {
                    startPage = Math.max(1, pages - 6);
                }
            }

            pageHtml += `<li class="page-item ${page <= 1 ? 'disabled' : ''}">
                <a class="page-link" href="javascript:void(0)" onclick="Rules.loadRules(${page - 1})">上一页</a>
            </li>`;

            for (let i = startPage; i <= endPage; i++) {
                pageHtml += `<li class="page-item ${i === page ? 'active' : ''}">
                    <a class="page-link" href="javascript:void(0)" onclick="Rules.loadRules(${i})">${i}</a>
                </li>`;
            }

            pageHtml += `<li class="page-item ${page >= pages ? 'disabled' : ''}">
                <a class="page-link" href="javascript:void(0)" onclick="Rules.loadRules(${page + 1})">下一页</a>
            </li>`;

            paginationHtml = `
                <div class="d-flex justify-content-between align-items-center mt-4 px-1">
                    <small class="text-muted">共 ${total} 条 · 第 ${page}/${pages} 页</small>
                    <nav><ul class="pagination pagination-sm mb-0">${pageHtml}</ul></nav>
                </div>
            `;
        }

        return `
            <div class="row g-2">
                ${items.map(item => `
                    <div class="col-6 col-md-4 col-lg-3">
                        <div class="border rounded shadow-sm rule-card h-100 p-2 d-flex justify-content-between align-items-center" onclick="Rules.viewRule(${item.id})">
                            <div class="text-truncate flex-grow-1 me-2" style="cursor: pointer;" title="${Utils.escapeHtml(cleanTitle(item.title))}">
                                <i class="bi bi-file-earmark-text text-secondary me-1"></i>
                                <span class="text-dark">${Utils.escapeHtml(cleanTitle(item.title))}</span>
                            </div>
                            <button class="btn btn-sm btn-outline-secondary flex-shrink-0" onclick="event.stopPropagation(); Rules.deleteRule(${item.id})" title="删除">
                                <i class="bi bi-trash"></i>
                            </button>
                        </div>
                    </div>
                `).join('')}
            </div>
            ${paginationHtml}
        `;
    }

    // 渲染规则详情弹窗
    function renderRuleDetail(rule) {
        const cleanTitle = (title) => {
            if (!title) return '(无标题)';
            const idx = title.indexOf('：');
            return idx > 0 ? title.substring(idx + 1) : title;
        };

        const toBadges = arr => arr && arr.length > 0
            ? arr.map(s => `<span class="badge bg-secondary me-1 mb-1">${Utils.escapeHtml(s)}</span>`).join('')
            : '-';

        document.getElementById('view-rule-title').textContent = cleanTitle(rule.title);
        document.getElementById('view-rule-content').textContent = rule.content || '';
        document.getElementById('view-rule-scenarios').innerHTML = toBadges(rule.applicable_scenarios);
        document.getElementById('view-rule-audiences').innerHTML = toBadges(rule.applicable_audiences);
        document.getElementById('view-rule-keywords').innerHTML = toBadges(rule.keywords);

        new bootstrap.Modal(document.getElementById('ruleViewModal')).show();
    }

    // ========== 公共 API ==========
    return {
        // API
        getList,
        get,
        remove,
        invalidateCache,

        // 渲染
        renderSubCategoryCards,
        renderRuleList,
        renderRuleDetail,

        // 兼容方法（供页面调用）
        loadRules: async function(page = 1) {
            const result = await this.getList({
                page,
                pageSize: 10,
                category: window.currentCategory || '',
                subCategory: window.currentSubCategory || ''
            });
            if (result.success) {
                document.getElementById('rules-container').innerHTML = this.renderRuleList(result.data, result);
            }
            return result;
        },
        viewRule: async function(id) {
            const result = await this.get(id);
            if (result.success) {
                this.renderRuleDetail(result.data);
            }
        },
        deleteRule: async function(id) {
            if (!confirm('确定要删除这条公式吗？')) return;
            const result = await this.remove(id);
            if (result.success) {
                alert('删除成功');
                this.loadRules(window.currentPage || 1);
            } else {
                alert(result.message || '删除失败');
            }
        }
    };
})();

// ========== 全局兼容函数 ==========
function loadRules(page = 1) {
    window.currentPage = page;
    const container = document.getElementById('rules-container');
    container.innerHTML = '<div class="text-center text-muted py-5"><div class="spinner-border text-secondary" role="status"></div><p class="mt-2">加载中...</p></div>';
    return Rules.loadRules(page);
}

function viewRule(id) {
    return Rules.viewRule(id);
}

function deleteRule(id) {
    return Rules.deleteRule(id);
}

function updateSubCategoryCards() {
    const container = document.getElementById('sub-category-cards');
    if (!window.currentCategory || !window.CATEGORY_MAP[window.currentCategory]) {
        container.innerHTML = '';
        return;
    }
    container.innerHTML = Rules.renderSubCategoryCards(window.CATEGORY_MAP, window.currentCategory);
}

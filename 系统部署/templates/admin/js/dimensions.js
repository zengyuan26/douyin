/**
 * 分析维度模块
 * 封装分析维度的 API 和渲染函数
 */
const Dimensions = (function() {
    // 缓存
    let groupedCache = null;
    let detailCache = {};

    // ========== API 方法 ==========

    // 获取分组维度
    async function getGrouped() {
        if (groupedCache) return groupedCache;
        try {
            const res = await fetch('/admin/api/analysis-dimensions/grouped');
            const result = await res.json();
            if (result.success) {
                groupedCache = result.data;
                return groupedCache;
            }
        } catch (err) {
            console.warn('获取分析维度分组失败:', err);
        }
        return [];
    }

    // 获取单个维度
    async function get(id) {
        if (detailCache[id]) return detailCache[id];
        try {
            const res = await fetch(`/admin/api/analysis-dimensions/${id}`);
            const result = await res.json();
            if (result.success) {
                detailCache[id] = result.data;
                return result.data;
            }
        } catch (err) {
            console.warn('获取维度失败:', err);
        }
        return null;
    }

    // 创建维度
    async function create(data) {
        const res = await fetch('/admin/api/analysis-dimensions', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        const result = await res.json();
        invalidateCache();
        return result;
    }

    // 更新维度
    async function update(id, data) {
        const res = await fetch(`/admin/api/analysis-dimensions/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        const result = await res.json();
        invalidateCache();
        return result;
    }

    // 删除维度
    async function remove(id) {
        const res = await fetch(`/admin/api/analysis-dimensions/${id}`, {
            method: 'DELETE'
        });
        const result = await res.json();
        invalidateCache();
        return result;
    }

    // 清除缓存
    function invalidateCache() {
        groupedCache = null;
        detailCache = {};
    }

    // ========== 渲染方法 ==========

    // 渲染维度徽章（知识拆解页面使用）
    function renderDimensionBadges(dimensions) {
        if (!dimensions || dimensions.length === 0) {
            return '<span class="text-muted small">暂无启用维度，请到分析维度管理配置</span>';
        }

        // 按分类分组
        const grouped = {};
        dimensions.forEach(d => {
            const cat = d.category || 'other';
            if (!grouped[cat]) grouped[cat] = [];
            grouped[cat].push(d);
        });

        const categoryNames = {
            'account': '账号分析',
            'content': '内容分析',
            'methodology': '方法论'
        };

        let html = '';
        for (const [cat, dims] of Object.entries(grouped)) {
            const catName = categoryNames[cat] || cat;
            html += `<div class="w-100 mb-1"><small class="text-muted">${catName}：</small></div>`;
            html += '<div class="d-flex flex-wrap gap-1">';
            dims.forEach(d => {
                html += `
                    <span class="badge bg-light text-dark border">
                        <i class="bi bi-check-circle text-success me-1"></i>${Utils.escapeHtml(d.name)}
                    </span>
                `;
            });
            html += '</div>';
        }

        return html;
    }

    // 渲染二级分类卡片（分析维度管理页面）
    function renderSubCategoryCard(group) {
        const subCat = group.sub_category;
        const subName = group.sub_category_name || subCat;
        const category = group.category;
        const meta = getCategoryMeta(category);
        const dimensions = group.dimensions || [];
        const activeDims = dimensions.filter(d => d.is_active);

        return `
            <div class="col-md-4 col-lg-3 mb-3">
                <div class="card h-100 sub-category-card" data-category="${category}" data-sub-category="${subCat}">
                    <div class="card-body">
                        <div class="d-flex align-items-center mb-2">
                            <span class="badge bg-${meta.color} me-2">
                                <i class="${meta.icon}"></i>
                            </span>
                            <h6 class="mb-0">${Utils.escapeHtml(subName)}</h6>
                        </div>
                        <p class="text-muted small mb-2">${dimensions.length} 个维度</p>
                        <div class="d-flex flex-wrap gap-1">
                            ${activeDims.slice(0, 5).map(d => `
                                <span class="badge bg-light text-dark">${Utils.escapeHtml(d.name)}</span>
                            `).join('')}
                            ${activeDims.length > 5 ? `<span class="badge bg-light">+${activeDims.length - 5}</span>` : ''}
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    // 渲染维度列表项（分析维度管理详情页）
    function renderDimensionItem(dimension, category) {
        const isActive = dimension.is_active !== false;
        const isLocked = dimension.is_system === true;

        return `
            <div class="card mb-2 dimension-card-wrapper" data-id="${dimension.id}" draggable="${!isLocked}">
                <div class="card-body py-2">
                    <div class="d-flex align-items-center justify-content-between">
                        <div class="d-flex align-items-center">
                            ${!isLocked ? '<i class="bi bi-grip-vertical text-muted me-2 cursor-move"></i>' : ''}
                            <div>
                                <strong>${Utils.escapeHtml(dimension.name)}</strong>
                                <span class="text-muted small ms-2">${Utils.escapeHtml(dimension.code)}</span>
                                ${isLocked ? '<span class="badge bg-secondary ms-1">系统</span>' : ''}
                            </div>
                        </div>
                        <div class="d-flex align-items-center">
                            <div class="form-check form-switch me-2">
                                <input class="form-check-input dimension-active-toggle" type="checkbox" 
                                    ${isActive ? 'checked' : ''} ${isLocked ? 'disabled' : ''}
                                    data-id="${dimension.id}">
                            </div>
                            ${!isLocked ? `
                                <button class="btn btn-sm btn-outline-primary me-1" onclick="Dimensions.edit(${dimension.id})">
                                    <i class="bi bi-pencil"></i>
                                </button>
                                <button class="btn btn-sm btn-outline-danger" onclick="Dimensions.delete(${dimension.id})">
                                    <i class="bi bi-trash"></i>
                                </button>
                            ` : ''}
                        </div>
                    </div>
                    ${dimension.description ? `<p class="mb-0 small text-muted mt-1">${Utils.escapeHtml(dimension.description)}</p>` : ''}
                </div>
            </div>
        `;
    }

    // 获取分类元信息
    function getCategoryMeta(category) {
        const meta = {
            'account': { icon: 'bi-person-badge', color: 'primary', name: '账号分析' },
            'content': { icon: 'bi-file-text', color: 'success', name: '内容分析' },
            'methodology': { icon: 'bi-book', color: 'warning', name: '方法论' }
        };
        return meta[category] || { icon: 'bi-circle', color: 'secondary', name: category };
    }

    // 获取分类对应的图标样式
    function getCategoryIcon(category) {
        return getCategoryMeta(category).icon;
    }

    // ========== 公共 API ==========
    return {
        // API
        getGrouped,
        get,
        create,
        update,
        remove,
        invalidateCache,

        // 渲染
        renderBadges: renderDimensionBadges,
        renderSubCategoryCard,
        renderDimensionItem,

        // 工具
        getCategoryMeta,
        getCategoryIcon
    };
})();

// ========== 全局兼容函数 ==========
function loadDefaultAnalysisDimensions() {
    return Dimensions.getGrouped().then(groups => {
        window.analysisDimensionGroups = groups || [];
        return groups;
    });
}

function renderAnalysisDimensions(dimensions) {
    const container = document.getElementById('analysis-dimensions-container');
    if (!container) return;
    container.innerHTML = Dimensions.renderBadges(dimensions);
}

function renderDefaultDimensions() {
    renderAnalysisDimensions([
        { code: 'title', name: '标题', category: 'content' },
        { code: 'cover', name: '封面', category: 'content' },
        { code: 'topic', name: '选题', category: 'content' },
        { code: 'content', name: '内容', category: 'content' },
        { code: 'psychology', name: '心理', category: 'content' },
        { code: 'commercial', name: '商业', category: 'content' },
        { code: 'why_popular', name: '爆款', category: 'content' },
        { code: 'ending', name: '结尾', category: 'content' },
        { code: 'tags', name: '标签', category: 'content' },
        { code: 'character', name: '人物', category: 'content' },
        { code: 'content_form', name: '形式', category: 'content' },
        { code: 'interaction', name: '互动', category: 'content' }
    ]);
}

// 分析维度管理页面专用
function loadGroupedDimensions(clearState = true) {
    return Dimensions.getGrouped().then(groups => {
        if (clearState) {
            window.groupedDataCache = groups || [];
        }
        return groups;
    });
}

function findGroupByCategory(category, subCategory) {
    return (window.groupedDataCache || []).find(g => g.category === category && g.sub_category === subCategory);
}

/**
 * 渲染模块
 * 封装基础渲染辅助函数
 */
const Render = (function() {
    // ========== 私有方法 ==========

    // 渲染维度卡片
    function renderDimCard(dimCode, dimData, dimName) {
        if (!dimData || Object.keys(dimData).length === 0) {
            return '';
        }

        const score = dimData.score;
        const scoreColor = Utils.getScoreColor(score);
        const scoreText = score !== undefined ? `${score}分` : '';
        const formula = dimData.formula || '';
        const analysis = dimData.analysis || '';
        const suggestions = dimData.suggestions || [];

        return `
            <div class="card mb-2">
                <div class="card-body py-2">
                    <div class="d-flex justify-content-between align-items-center mb-2">
                        <h6 class="mb-0">${Utils.escapeHtml(dimName)}</h6>
                        ${scoreText ? `<span class="badge bg-transparent border border-${scoreColor} text-${scoreColor}">${scoreText}</span>` : ''}
                    </div>
                    ${formula ? `<p class="mb-1 small"><strong>公式:</strong> ${Utils.escapeHtml(formula)}</p>` : ''}
                    ${analysis ? `<p class="mb-1 small text-muted">${Utils.escapeHtml(analysis)}</p>` : ''}
                    ${suggestions.length > 0 ? `
                        <div class="mt-2">
                            ${suggestions.map(s => `<span class="badge bg-transparent border text-dark me-1 mb-1">${Utils.escapeHtml(s)}</span>`).join('')}
                        </div>
                    ` : ''}
                </div>
            </div>
        `;
    }

    // 渲染通用分析
    function renderGenericAnalysis(data, dimensions) {
        if (!data || Object.keys(data).length === 0) {
            return '<p class="text-muted">暂无分析数据</p>';
        }

        let html = '';
        const dims = data.dimensions || dimensions || [];

        dims.forEach(dim => {
            const dimCode = dim.code || dim;
            const dimName = dim.name || dimCode;
            const dimData = data[dimCode] || {};
            html += renderDimCard(dimCode, dimData, dimName);
        });

        return html || '<p class="text-muted">暂无分析数据</p>';
    }

    // 渲染维度结果卡片
    function renderDimensionResult(dimension, data) {
        if (!data || !data.content) {
            return '<p class="text-muted">暂无内容</p>';
        }

        const content = data.content;
        const score = data.score;
        const scoreColor = Utils.getScoreColor(score);

        return `
            <div class="card">
                <div class="card-body">
                    ${score !== undefined ? `
                        <div class="d-flex justify-content-between align-items-center mb-2">
                            <span class="text-muted">评分</span>
                            <span class="badge bg-transparent border border-${scoreColor} text-${scoreColor}">${score}分</span>
                        </div>
                    ` : ''}
                    <div class="analysis-content">${Utils.formatFieldValue(content)}</div>
                </div>
            </div>
        `;
    }

    // 渲染内容策略
    function renderContentStrategy(strategy) {
        if (!strategy) return '<p class="text-muted">暂无内容策略</p>';

        return `
            <div class="card">
                <div class="card-body">
                    <h6 class="mb-3">内容策略</h6>
                    ${Object.entries(strategy).map(([key, value]) => `
                        <div class="mb-2">
                            <strong>${Utils.escapeHtml(key)}:</strong>
                            <span class="text-muted">${Utils.escapeHtml(String(value))}</span>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    }

    // 渲染市场分析
    function renderMarketAnalysis(data) {
        if (!data || !data.competitors) {
            return renderGenericAnalysis(data, []);
        }

        const competitors = data.competitors || [];
        const opportunities = data.opportunities || [];

        return `
            <div class="row">
                <div class="col-md-6">
                    <div class="card h-100">
                        <div class="card-header">竞争对手</div>
                        <div class="card-body">
                            ${competitors.length > 0 ? competitors.map(c => `
                                <div class="mb-2 p-2 bg-light rounded">
                                    <strong>${Utils.escapeHtml(c.name || '')}</strong>
                                    <p class="mb-0 small text-muted">${Utils.escapeHtml(c.description || '')}</p>
                                </div>
                            `).join('') : '<p class="text-muted">暂无数据</p>'}
                        </div>
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="card h-100">
                        <div class="card-header">机会点</div>
                        <div class="card-body">
                            ${opportunities.length > 0 ? opportunities.map(o => `
                                <div class="mb-2 p-2 bg-success bg-opacity-10 rounded">
                                    <strong>${Utils.escapeHtml(o.name || '')}</strong>
                                    <p class="mb-0 small text-muted">${Utils.escapeHtml(o.description || '')}</p>
                                </div>
                            `).join('') : '<p class="text-muted">暂无数据</p>'}
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    // 渲染运营规划
    function renderOperationPlanning(data) {
        if (!data || !data.content) {
            return renderGenericAnalysis(data, []);
        }

        const content = data.content;
        const schedule = content.schedule || [];
        const budget = content.budget || '';

        return `
            <div class="card">
                <div class="card-body">
                    ${budget ? `<p><strong>预算:</strong> ${Utils.escapeHtml(budget)}</p>` : ''}
                    ${schedule.length > 0 ? `
                        <div class="mt-3">
                            <h6>执行计划</h6>
                            ${schedule.map((item, idx) => `
                                <div class="d-flex align-items-start mb-2">
                                    <span class="badge bg-transparent border border-primary text-primary me-2">${idx + 1}</span>
                                    <div>
                                        <strong>${Utils.escapeHtml(item.phase || '')}</strong>
                                        <p class="mb-0 small text-muted">${Utils.escapeHtml(item.description || '')}</p>
                                    </div>
                                </div>
                            `).join('')}
                        </div>
                    ` : ''}
                </div>
            </div>
        `;
    }

    // 渲染标题分析
    function renderTitleAnalysis(data) {
        if (!data) return '<p class="text-muted">暂无数据</p>';

        const suggestions = data.suggestions || [];
        const keywords = data.keywords || [];
        const score = data.score;

        return `
            <div class="card">
                <div class="card-body">
                    ${score !== undefined ? `
                        <div class="mb-3">
                            <span class="text-muted">评分:</span>
                            <span class="badge bg-transparent border border-${Utils.getScoreColor(score)} text-${Utils.getScoreColor(score)} ms-1">${score}分</span>
                        </div>
                    ` : ''}
                    ${keywords.length > 0 ? `
                        <div class="mb-3">
                            <strong>关键词:</strong>
                            ${keywords.map(k => `<span class="badge bg-info me-1">${Utils.escapeHtml(k)}</span>`).join('')}
                        </div>
                    ` : ''}
                    ${suggestions.length > 0 ? `
                        <div>
                            <strong>优化建议:</strong>
                            <ul class="mb-0">
                                ${suggestions.map(s => `<li>${Utils.escapeHtml(s)}</li>`).join('')}
                            </ul>
                        </div>
                    ` : ''}
                </div>
            </div>
        `;
    }

    // 渲染钩子分析
    function renderHookAnalysis(data) {
        if (!data) return '<p class="text-muted">暂无数据</p>';

        const hooks = data.hooks || [];
        const patterns = data.patterns || [];
        const score = data.score;

        return `
            <div class="card">
                <div class="card-body">
                    ${score !== undefined ? `
                        <div class="mb-3">
                            <span class="text-muted">评分:</span>
                            <span class="badge bg-transparent border border-${Utils.getScoreColor(score)} text-${Utils.getScoreColor(score)} ms-1">${score}分</span>
                        </div>
                    ` : ''}
                    ${hooks.length > 0 ? `
                        <div class="mb-3">
                            <strong>热门钩子:</strong>
                            ${hooks.map(h => `
                                <div class="p-2 bg-light rounded mb-2">
                                    ${Utils.escapeHtml(h.content || '')}
                                    <span class="badge bg-transparent border border-success text-success ms-1">${h.score || ''}</span>
                                </div>
                            `).join('')}
                        </div>
                    ` : ''}
                    ${patterns.length > 0 ? `
                        <div>
                            <strong>常用模式:</strong>
                            ${patterns.map(p => `<span class="badge bg-transparent border border-secondary text-secondary me-1 mb-1">${Utils.escapeHtml(p)}</span>`).join('')}
                        </div>
                    ` : ''}
                </div>
            </div>
        `;
    }

    // 渲染内容体分析
    function renderContentBodyAnalysis(data) {
        if (!data) return '<p class="text-muted">暂无数据</p>';

        const structure = data.structure || [];
        const length = data.length || {};
        const score = data.score;

        return `
            <div class="card">
                <div class="card-body">
                    ${score !== undefined ? `
                        <div class="mb-3">
                            <span class="text-muted">评分:</span>
                            <span class="badge bg-transparent border border-${Utils.getScoreColor(score)} text-${Utils.getScoreColor(score)} ms-1">${score}分</span>
                        </div>
                    ` : ''}
                    ${Object.keys(length).length > 0 ? `
                        <div class="mb-3">
                            <strong>内容长度:</strong>
                            <span class="ms-1">${length.min || 0} - ${length.max || 0} 字</span>
                        </div>
                    ` : ''}
                    ${structure.length > 0 ? `
                        <div>
                            <strong>结构:</strong>
                            ${structure.map(s => `
                                <div class="d-flex align-items-center mb-1">
                                    <span class="badge bg-primary me-2">${s.order || ''}</span>
                                    <span>${Utils.escapeHtml(s.name || '')}</span>
                                </div>
                            `).join('')}
                        </div>
                    ` : ''}
                </div>
            </div>
        `;
    }

    // 渲染视觉设计分析
    function renderVisualDesignAnalysis(data) {
        if (!data) return '<p class="text-muted">暂无数据</p>';

        const styles = data.styles || [];
        const elements = data.elements || [];
        const score = data.score;

        return `
            <div class="card">
                <div class="card-body">
                    ${score !== undefined ? `
                        <div class="mb-3">
                            <span class="text-muted">评分:</span>
                            <span class="badge bg-transparent border border-${Utils.getScoreColor(score)} text-${Utils.getScoreColor(score)} ms-1">${score}分</span>
                        </div>
                    ` : ''}
                    ${styles.length > 0 ? `
                        <div class="mb-3">
                            <strong>风格:</strong>
                            ${styles.map(s => `<span class="badge bg-transparent border border-info text-info me-1 mb-1">${Utils.escapeHtml(s)}</span>`).join('')}
                        </div>
                    ` : ''}
                    ${elements.length > 0 ? `
                        <div>
                            <strong>元素:</strong>
                            ${elements.map(e => `<span class="badge bg-transparent border border-secondary text-secondary me-1 mb-1">${Utils.escapeHtml(e)}</span>`).join('')}
                        </div>
                    ` : ''}
                </div>
            </div>
        `;
    }

    // 渲染结尾分析
    function renderEndingAnalysis(data) {
        if (!data) return '<p class="text-muted">暂无数据</p>';

        const ctas = data.ctas || [];
        const suggestions = data.suggestions || [];
        const score = data.score;

        return `
            <div class="card">
                <div class="card-body">
                    ${score !== undefined ? `
                        <div class="mb-3">
                            <span class="text-muted">评分:</span>
                            <span class="badge bg-transparent border border-${Utils.getScoreColor(score)} text-${Utils.getScoreColor(score)} ms-1">${score}分</span>
                        </div>
                    ` : ''}
                    ${ctas.length > 0 ? `
                        <div class="mb-3">
                            <strong>行动号召:</strong>
                            ${ctas.map(c => `
                                <div class="p-2 bg-light rounded mb-1">
                                    ${Utils.escapeHtml(c.content || '')}
                                </div>
                            `).join('')}
                        </div>
                    ` : ''}
                    ${suggestions.length > 0 ? `
                        <div>
                            <strong>优化建议:</strong>
                            <ul class="mb-0">
                                ${suggestions.map(s => `<li>${Utils.escapeHtml(s)}</li>`).join('')}
                            </ul>
                        </div>
                    ` : ''}
                </div>
            </div>
        `;
    }

    // 渲染适用场景
    function renderApplicableScenario(data) {
        if (!data) return '<p class="text-muted">暂无数据</p>';

        const scenarios = data.scenarios || [];
        const score = data.score;

        return `
            <div class="card">
                <div class="card-body">
                    ${score !== undefined ? `
                        <div class="mb-3">
                            <span class="text-muted">评分:</span>
                            <span class="badge bg-transparent border border-${Utils.getScoreColor(score)} text-${Utils.getScoreColor(score)} ms-1">${score}分</span>
                        </div>
                    ` : ''}
                    ${scenarios.length > 0 ? `
                        <div class="d-flex flex-wrap gap-2">
                            ${scenarios.map(s => `
                                <span class="badge bg-transparent border border-primary text-primary">${Utils.escapeHtml(s.name || '')}</span>
                            `).join('')}
                        </div>
                    ` : '<p class="text-muted">暂无数据</p>'}
                </div>
            </div>
        `;
    }

    // 渲染适用人群
    function renderApplicableAudience(data) {
        if (!data) return '<p class="text-muted">暂无数据</p>';

        const audiences = data.audiences || [];
        const demographics = data.demographics || {};
        const score = data.score;

        return `
            <div class="card">
                <div class="card-body">
                    ${score !== undefined ? `
                        <div class="mb-3">
                            <span class="text-muted">评分:</span>
                            <span class="badge bg-transparent border border-${Utils.getScoreColor(score)} text-${Utils.getScoreColor(score)} ms-1">${score}分</span>
                        </div>
                    ` : ''}
                    ${audiences.length > 0 ? `
                        <div class="mb-3">
                            <strong>目标人群:</strong>
                            <div class="d-flex flex-wrap gap-2 mt-1">
                                ${audiences.map(a => `
                                    <span class="badge bg-transparent border border-success text-success">${Utils.escapeHtml(a.name || '')}</span>
                                `).join('')}
                            </div>
                        </div>
                    ` : ''}
                    ${Object.keys(demographics).length > 0 ? `
                        <div>
                            <strong>人口统计:</strong>
                            <ul class="mb-0 mt-1">
                                ${Object.entries(demographics).map(([k, v]) => `<li>${k}: ${v}</li>`).join('')}
                            </ul>
                        </div>
                    ` : ''}
                </div>
            </div>
        `;
    }

    // 渲染维度卡片集合
    function renderDimensionCards(data, prefix) {
        if (!data || Object.keys(data).length === 0) {
            return '<p class="text-muted">暂无数据</p>';
        }

        let html = '';
        Object.entries(data).forEach(([dimCode, dimData]) => {
            if (typeof dimData === 'object' && dimData !== null) {
                const dimName = dimData.name || dimCode;
                html += renderDimCard(dimCode, dimData, dimName);
            }
        });

        return html || '<p class="text-muted">暂无数据</p>';
    }

    // 渲染匹配规则
    function renderMatchedRules(rules) {
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
    }

    // ========== 公共 API ==========
    return {
        // 基础渲染
        dimCard: renderDimCard,
        genericAnalysis: renderGenericAnalysis,
        dimensionResult: renderDimensionResult,
        dimensionCards: renderDimensionCards,

        // 业务渲染
        contentStrategy: renderContentStrategy,
        marketAnalysis: renderMarketAnalysis,
        operationPlanning: renderOperationPlanning,
        titleAnalysis: renderTitleAnalysis,
        hookAnalysis: renderHookAnalysis,
        contentBodyAnalysis: renderContentBodyAnalysis,
        visualDesignAnalysis: renderVisualDesignAnalysis,
        endingAnalysis: renderEndingAnalysis,
        applicableScenario: renderApplicableScenario,
        applicableAudience: renderApplicableAudience,

        // 匹配规则
        matchedRules: renderMatchedRules
    };
})();

// ========== 全局兼容函数 ==========
function renderDimCard(dimCode, dimData, dimName) {
    return Render.dimCard(dimCode, dimData, dimName);
}

function renderGenericAnalysis(data, dimensions) {
    return Render.genericAnalysis(data, dimensions);
}

function renderDimensionResult(dimension, data) {
    return Render.dimensionResult(dimension, data);
}

function renderDimensionCards(data, prefix) {
    return Render.dimensionCards(data, prefix);
}

function renderContentStrategy(strategy) {
    return Render.contentStrategy(strategy);
}

function renderMarketAnalysis(data) {
    return Render.marketAnalysis(data);
}

function renderOperationPlanning(data) {
    return Render.operationPlanning(data);
}

function renderTitleAnalysis(data) {
    return Render.titleAnalysis(data);
}

function renderHookAnalysis(data) {
    return Render.hookAnalysis(data);
}

function renderContentBodyAnalysis(data) {
    return Render.contentBodyAnalysis(data);
}

function renderVisualDesignAnalysis(data) {
    return Render.visualDesignAnalysis(data);
}

function renderEndingAnalysis(data) {
    return Render.endingAnalysis(data);
}

function renderApplicableScenario(data) {
    return Render.applicableScenario(data);
}

function renderApplicableAudience(data) {
    return Render.applicableAudience(data);
}

function showMatchedRules(rules) {
    return Render.matchedRules(rules);
}

/**
 * 画像管理模块（含专属关键词库/选题库）
 *
 * 功能：
 * 1. 保存/加载/删除/切换画像
 * 2. 画像专属库管理（关键词库/选题库）
 * 3. 库更新配额检查
 * 4. 选题选择（专属库 + 实时混合）
 */

const PortraitManager = {
    _savedPortraits: [],
    _currentPortraitId: null,
    _quota: null,
    _libraryQuota: { keyword: null, topic: null },
    _currentLibraryPortraitId: null,

    // ========================================================================
    // 一、初始化
    // ========================================================================

    async init() {
        await this.loadQuota();
        await this.loadSavedPortraits();
        await this.loadLibraryQuota();
    },

    // ========================================================================
    // 二、配额管理
    // ========================================================================

    async loadQuota() {
        try {
            const resp = await fetch('/public/api/quota', { credentials: 'include' });
            const data = await resp.json();
            if (data.success) {
                this._quota = data.data;
                this.updateQuotaDisplay();
                // 付费用户显示画像专区
                if (this._quota && this._quota.can_save) {
                    document.getElementById('portrait-section').style.display = 'block';
                }
            }
        } catch (e) {
            console.error('[PortraitManager] 加载配额失败:', e);
        }
    },

    updateQuotaDisplay() {
        const el = document.getElementById('quota-info');
        if (!el || !this._quota) return;
        const planType = this._quota.plan_type || 'free';

        if (planType === 'free') {
            el.innerHTML = '<span>今日剩余次数：<strong id="quota-count">2</strong> 次</span><a href="/public/pricing" class="alert-link">升级获取更多次数 →</a>';
        } else {
            el.innerHTML = '';  // 付费用户不显示配额信息
        }
    },

    // ========================================================================
    // 三、画像加载 & 渲染
    // ========================================================================

    async loadSavedPortraits() {
        try {
            const resp = await fetch('/public/api/portraits/saved?include_data=true', { credentials: 'include' });
            const data = await resp.json();
            if (data.success) {
                this._savedPortraits = data.data || [];
                // 自动定位默认画像
                const defaultPortrait = this._savedPortraits.find(p => p.is_default);
                if (defaultPortrait) {
                    this._currentPortraitId = defaultPortrait.id;
                } else if (this._savedPortraits.length > 0 && !this._currentPortraitId) {
                    this._currentPortraitId = this._savedPortraits[0].id;
                }
                this.renderPortraitCards();
                // 有已保存画像时，隐藏超级定位步骤
                if (typeof updateSuperStepsVisibility === 'function') {
                    updateSuperStepsVisibility();
                }
            }
        } catch (e) {
            console.error('[PortraitManager] 加载画像失败:', e);
        }
    },

    renderPortraitCards() {
        const container = document.getElementById('portrait-cards-list');
        const loading = document.getElementById('portrait-cards-loading');
        if (!container) return;

        if (loading) loading.style.display = 'none';

        if (this._savedPortraits.length === 0) {
            container.innerHTML = `
                <div class="col-12 text-center py-4 text-muted">
                    <i class="bi bi-inbox" style="font-size:2rem;"></i>
                    <p class="mt-2 small">暂无保存的画像</p>
                    <p class="small text-muted">在下方「超级定位」流程中生成并保存画像后，可在此快速访问</p>
                </div>`;
            return;
        }

        // 只显示当前选中的或默认画像（每个客户只有一个画像）
        const currentPortrait = this._savedPortraits.find(p => p.id === this._currentPortraitId) 
            || this._savedPortraits.find(p => p.is_default)
            || this._savedPortraits[0];

        const p = currentPortrait;
        
        // 计算关键词库和选题库数量
        let kwCount = 0;
        if (p.keyword_library && p.keyword_library.categories) {
            p.keyword_library.categories.forEach(cat => {
                kwCount += (cat.keywords || []).length;
            });
            if (p.keyword_library.blue_ocean) {
                kwCount += p.keyword_library.blue_ocean.length;
            }
        }
        
        let topicCount = 0;
        if (p.topic_library && p.topic_library.topics) {
            topicCount = p.topic_library.topics.length;
        }

        container.innerHTML = `
            <div class="col-12">
                <div class="d-flex align-items-center justify-content-between p-3 border rounded bg-light">
                    <div class="d-flex align-items-center gap-3">
                        <div class="bg-primary rounded-circle d-flex align-items-center justify-content-center" style="width:48px;height:48px;">
                            <i class="bi bi-person text-white fs-4"></i>
                        </div>
                        <div>
                            <div class="fw-bold text-dark">${this.escapeHtml(p.portrait_name || '用户画像')}</div>
                            <div class="small text-muted">${this.escapeHtml(p.industry || '')} · ${this.formatDate(p.created_at)}</div>
                            <div class="d-flex gap-2 mt-1">
                                <span class="badge ${kwCount > 0 ? 'bg-info' : 'bg-secondary'}" style="font-size:11px;">
                                    <i class="bi bi-key me-1"></i>关键词${kwCount > 0 ? `(${kwCount})` : ''}
                                </span>
                                <span class="badge ${topicCount > 0 ? 'bg-success' : 'bg-secondary'}" style="font-size:11px;">
                                    <i class="bi bi-lightbulb me-1"></i>选题${topicCount > 0 ? `(${topicCount})` : ''}
                                </span>
                            </div>
                        </div>
                    </div>
                    <button class="btn btn-sm btn-outline-primary" onclick="PortraitManager.showPortraitDetail(${p.id})" title="查看画像详情">
                        <i class="bi bi-eye me-1"></i>查看详情
                    </button>
                </div>
            </div>`;
    },

    // 显示画像详情弹窗
    showPortraitDetail(portraitId) {
        const portrait = this._savedPortraits.find(p => p.id === portraitId);
        if (!portrait) return;

        const modalHtml = `
        <div class="modal fade" id="portraitDetailModal" tabindex="-1">
            <div class="modal-dialog modal-lg modal-dialog-scrollable">
                <div class="modal-content">
                    <div class="modal-header bg-primary text-white">
                        <h5 class="modal-title"><i class="bi bi-person-badge me-2"></i>${this.escapeHtml(portrait.portrait_name || '用户画像')}</h5>
                        <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        ${this._renderPortraitDetailContent(portrait)}
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-outline-danger btn-sm" onclick="PortraitManager.deletePortrait(${portrait.id})" data-bs-dismiss="modal">
                            <i class="bi bi-trash me-1"></i>删除此画像
                        </button>
                        <button type="button" class="btn btn-primary" onclick="PortraitManager.quickUsePortrait(${portrait.id})" data-bs-dismiss="modal">
                            <i class="bi bi-lightning-charge me-1"></i>直接生成内容
                        </button>
                    </div>
                </div>
            </div>
        </div>`;

        // 移除旧弹窗
        const oldModal = document.getElementById('portraitDetailModal');
        if (oldModal) oldModal.remove();

        // 添加新弹窗并显示
        document.body.insertAdjacentHTML('beforeend', modalHtml);
        const modal = new bootstrap.Modal(document.getElementById('portraitDetailModal'));
        modal.show();

        // 弹窗关闭后移除
        document.getElementById('portraitDetailModal').addEventListener('hidden.bs.modal', function () {
            this.remove();
        });
    },

    // 渲染画像详情内容
    _renderPortraitDetailContent(portrait) {
        const pd = portrait.portrait_data || {};
        let html = '';

        // 基本信息
        if (pd.name || portrait.portrait_name) {
            html += `
                <div class="mb-3">
                    <h6 class="text-primary mb-2"><i class="bi bi-tag me-1"></i>画像名称</h6>
                    <p class="mb-0">${this.escapeHtml(pd.name || portrait.portrait_name || '')}</p>
                </div>`;
        }

        // 目标用户描述
        if (pd.target_description || portrait.target_customer) {
            html += `
                <div class="mb-3">
                    <h6 class="text-primary mb-2"><i class="bi bi-people me-1"></i>目标用户</h6>
                    <p class="mb-0">${this.escapeHtml(pd.target_description || portrait.target_customer || '')}</p>
                </div>`;
        }

        // 人群画像列表
        if (pd.portraits && Array.isArray(pd.portraits) && pd.portraits.length > 0) {
            html += `<h6 class="text-primary mb-3"><i class="bi bi-person-badge me-1"></i>人群画像</h6>`;
            pd.portraits.forEach((p, idx) => {
                const colors = [
                    { bg: '#e0f2fe', border: '#0ea5e9', accent: '#0284c7' },
                    { bg: '#fce7f3', border: '#ec4899', accent: '#be185d' },
                    { bg: '#dcfce7', border: '#22c55e', accent: '#15803d' },
                    { bg: '#fef3c7', border: '#f59e0b', accent: '#d97706' },
                ];
                const c = colors[idx % colors.length];
                html += `
                    <div class="card mb-3 border" style="border-color: ${c.border} !important; background: ${c.bg}; border-radius: 12px;">
                        <div class="card-body p-3">
                            <div class="d-flex justify-content-between align-items-start mb-2">
                                <span class="badge" style="background: ${c.accent}; color: white;">${this.escapeHtml(p.name || '画像' + (idx+1))}</span>
                            </div>
                            <div class="small">
                                ${p.identity ? `<div class="mb-1"><strong>身份：</strong>${this.escapeHtml(p.identity)}</div>` : ''}
                                ${p.main_concerns ? `<div class="mb-1"><strong>主要诉求：</strong>${this.escapeHtml(p.main_concerns)}</div>` : ''}
                                ${p.behavior_patterns ? `<div class="mb-1"><strong>行为特征：</strong>${this.escapeHtml(p.behavior_patterns)}</div>` : ''}
                                ${p.content_preferences ? `<div class="mb-1"><strong>内容偏好：</strong>${this.escapeHtml(p.content_preferences)}</div>` : ''}
                                ${p.trigger_points ? `<div><strong>触发点：</strong>${this.escapeHtml(p.trigger_points)}</div>` : ''}
                            </div>
                            ${p.keywords && p.keywords.length ? `
                                <div class="mt-2">
                                    <span class="small text-muted">关键词：</span>
                                    ${p.keywords.slice(0, 8).map(k => `<span class="badge bg-light text-dark me-1 mb-1">${this.escapeHtml(k)}</span>`).join('')}
                                </div>` : ''}
                        </div>
                    </div>`;
            });
        }

        // 关键词库
        if (portrait.keyword_library) {
            html += `<h6 class="text-primary mb-3 mt-4"><i class="bi bi-key me-1"></i>关键词库</h6>`;
            const kl = portrait.keyword_library;
            if (kl.categories && kl.categories.length > 0) {
                kl.categories.forEach(cat => {
                    html += `
                        <div class="mb-2">
                            <span class="badge bg-secondary mb-1">${this.escapeHtml(cat.name || '未分类')}</span>
                            <div class="ms-2">
                                ${(cat.keywords || []).map(k => `<span class="badge bg-light text-dark me-1 mb-1">${this.escapeHtml(k)}</span>`).join('')}
                            </div>
                        </div>`;
                });
            }
            if (kl.blue_ocean && kl.blue_ocean.length > 0) {
                html += `
                    <div class="mb-2">
                        <span class="badge bg-success mb-1">蓝海关键词</span>
                        <div class="ms-2">
                            ${kl.blue_ocean.map(k => `<span class="badge bg-light text-dark me-1 mb-1">${this.escapeHtml(k)}</span>`).join('')}
                        </div>
                    </div>`;
            }
        }

        // 选题库
        if (portrait.topic_library && portrait.topic_library.topics && portrait.topic_library.topics.length > 0) {
            html += `<h6 class="text-primary mb-3 mt-4"><i class="bi bi-lightbulb me-1"></i>选题库</h6>`;
            portrait.topic_library.topics.slice(0, 10).forEach(t => {
                html += `
                    <div class="card mb-2 border">
                        <div class="card-body py-2 px-3">
                            <div class="d-flex justify-content-between align-items-start">
                                <div>
                                    <span class="badge bg-secondary me-1" style="font-size:10px;">${this.escapeHtml(t.type_name || t.type || '')}</span>
                                    ${t.priority ? `<span class="badge ${this._priorityBadgeClass(t.priority)} me-1" style="font-size:10px;">${t.priority}</span>` : ''}
                                    <strong class="small">${this.escapeHtml(t.title || '')}</strong>
                                </div>
                            </div>
                            ${t.reason ? `<div class="small text-muted mt-1">${this.escapeHtml(t.reason)}</div>` : ''}
                        </div>
                    </div>`;
            });
            if (portrait.topic_library.topics.length > 10) {
                html += `<div class="text-center text-muted small">还有 ${portrait.topic_library.topics.length - 10} 个选题...</div>`;
            }
        }

        return html || '<p class="text-muted text-center">暂无详情</p>';
    },

    // ========================================================================
    // 四、画像操作
    // ========================================================================

    async saveCurrentPortrait(portraitData, options = {}) {
        const result = this.canSavePortrait();
        if (!result.allowed) {
            showToast(result.reason, 'warning');
            return null;
        }
        try {
            const resp = await fetch('/public/api/portraits/save', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({
                    portrait_data: portraitData,
                    portrait_name: options.portraitName,
                    business_description: options.businessDescription,
                    industry: options.industry,
                    target_customer: options.targetCustomer,
                    set_as_default: options.setAsDefault || false
                })
            });
            const data = await resp.json();
            if (data.success) {
                this._currentPortraitId = data.data.id;
                await this.loadSavedPortraits();
                await this.loadQuota();
                showToast('画像保存成功', 'success');
                return data.data;
            } else {
                showToast(data.message || '保存失败', 'error');
                return null;
            }
        } catch (e) {
            console.error('[PortraitManager] 保存失败:', e);
            showToast('保存失败', 'error');
            return null;
        }
    },

    async deletePortrait(portraitId) {
        if (!confirm('确定删除该画像？')) return;
        try {
            const resp = await fetch(`/public/api/portraits/${portraitId}`, {
                method: 'DELETE', credentials: 'include'
            });
            const data = await resp.json();
            if (data.success) {
                if (this._currentPortraitId === portraitId) this._currentPortraitId = null;
                await this.loadSavedPortraits();
                await this.loadQuota();
                showToast('画像已删除', 'success');
            } else {
                showToast(data.message || '删除失败', 'error');
            }
        } catch (e) {
            showToast('删除失败', 'error');
        }
    },

    async setDefaultPortrait(portraitId) {
        try {
            const resp = await fetch(`/public/api/portraits/${portraitId}/set-default`, {
                method: 'POST', credentials: 'include'
            });
            const data = await resp.json();
            if (data.success) {
                await this.loadSavedPortraits();
                showToast('已设为默认', 'success');
            } else {
                showToast(data.message || '设置失败', 'error');
            }
        } catch (e) {
            showToast('设置失败', 'error');
        }
    },

    async quickUsePortrait(portraitId) {
        const portrait = this._savedPortraits.find(p => p.id === portraitId);
        if (!portrait) return;
        this._currentPortraitId = portraitId;
        // 触发全局选题选择
        if (window._onPortraitQuickUse) {
            window._onPortraitQuickUse(portrait);
        } else {
            // 兼容：打开选题选择弹窗
            await this.generateTopicsForPortrait(portraitId);
        }
    },

    // ========================================================================
    // 五、画像专属库
    // ========================================================================

    async openLibraryModal(portraitId) {
        const portrait = this._savedPortraits.find(p => p.id === portraitId);
        if (!portrait) return;
        this._currentLibraryPortraitId = portraitId;
        this._currentTopicLib = null; // 缓存完整选题数据

        // 填充头部信息
        document.getElementById('library-portrait-name').textContent = portrait.portrait_name || '未命名';
        document.getElementById('library-portrait-industry').textContent = portrait.industry || '';

        // 更新状态徽章（仅选题库）
        const hasTopic = portrait.topic_library && portrait.topic_library.topics && portrait.topic_library.topics.length > 0;
        const topicExpired = this._isExpired(portrait.topic_cache_expires_at);

        const topicStatus = document.getElementById('library-topic-status');
        if (hasTopic && !topicExpired) {
            topicStatus.className = 'badge bg-success';
            topicStatus.textContent = '选题库已就绪';
        } else if (hasTopic && topicExpired) {
            topicStatus.className = 'badge bg-warning';
            topicStatus.textContent = '选题库已过期';
        } else {
            topicStatus.className = 'badge bg-secondary';
            topicStatus.textContent = '无选题库';
        }

        // 重置滑条和筛选
        const slider = document.getElementById('topic-count-slider');
        if (slider) slider.value = 20;
        const label = document.getElementById('topic-count-label');
        if (label) label.textContent = '20';

        // 重置类型筛选到"全部"
        const allRadio = document.getElementById('topic-type-all');
        if (allRadio) allRadio.checked = true;

        // 绑定滑条和筛选事件
        this._bindTopicFilterEvents(portraitId);

        // 显示弹窗
        const modal = new bootstrap.Modal(document.getElementById('portraitLibraryModal'));
        modal.show();

        // 加载选题数据
        await this.loadLibraryData(portraitId, 'topic');
    },

    _bindTopicFilterEvents(portraitId) {
        const slider = document.getElementById('topic-count-slider');
        const label = document.getElementById('topic-count-label');
        if (slider && label) {
            slider.oninput = () => {
                label.textContent = slider.value;
                this._applyTopicFilter();
            };
        }

        // 类型筛选 radio
        document.querySelectorAll('input[name="topic-type"]').forEach(radio => {
            radio.onchange = () => this._applyTopicFilter();
        });

        // 更新按钮
        const regenBtn = document.getElementById('btn-regen-topic');
        if (regenBtn) {
            regenBtn.onclick = () => this.generateLibrary(portraitId);
        }

        // 使用画像生成内容按钮
        document.getElementById('btn-use-portrait-from-library').onclick = () => {
            bootstrap.Modal.getInstance(document.getElementById('portraitLibraryModal'))?.hide();
            this.quickUsePortrait(portraitId);
        };
    },

    _applyTopicFilter() {
        if (!this._currentTopicLib) return;
        const sliderVal = parseInt(document.getElementById('topic-count-slider')?.value || 20);
        const typeVal = document.querySelector('input[name="topic-type"]:checked')?.value || 'all';
        this._renderTopicList(this._currentTopicLib, sliderVal, typeVal);
    },

    async loadLibraryData(portraitId, tab = 'keyword') {
        portraitId = portraitId || this._currentLibraryPortraitId;
        if (!portraitId) return;
        try {
            const resp = await fetch(`/public/api/portraits/${portraitId}/library`, { credentials: 'include' });
            const data = await resp.json();
            if (!data.success) return;

            const lib = data.data || {};

            if (tab === 'topic') {
                this._currentTopicLib = lib;
                this._renderTopicLibrary(lib, portraitId);
            }
        } catch (e) {
            console.error('[PortraitManager] 加载库数据失败:', e);
        }
    },

    _renderKeywordLibrary(lib, portraitId) {
        // 关键词库仅后端存储，前端不再展示
    },

    _renderTopicLibrary(lib, portraitId) {
        const loading = document.getElementById('topic-loading');
        const empty = document.getElementById('topic-empty');
        const detail = document.getElementById('topic-detail');

        loading.style.display = 'none';

        if (!lib.topic_library || !lib.topic_library.topics || lib.topic_library.topics.length === 0) {
            empty.style.display = 'block';
            detail.style.display = 'none';
            // 无数据时绑定生成按钮
            const genBtn = document.getElementById('btn-gen-topic');
            if (genBtn) genBtn.onclick = () => this.generateLibrary(portraitId);
        } else {
            empty.style.display = 'none';
            detail.style.display = 'block';

            const updatedAt = lib.topic_updated_at ? new Date(lib.topic_updated_at).toLocaleString() : '未知';
            document.getElementById('topic-updated-at').textContent = `更新于：${updatedAt}`;
            const total = lib.topic_library.topics.length;
            document.getElementById('topic-total-hint').textContent = `共 ${total} 条`;

            // 滑条最大值为总数，最小5步长5
            const slider = document.getElementById('topic-count-slider');
            if (slider) {
                slider.max = Math.max(5, total);
                if (parseInt(slider.value) > total) slider.value = Math.min(20, total);
            }
            const label = document.getElementById('topic-count-label');
            if (label) label.textContent = Math.min(parseInt(slider?.value || 20), total);

            // 清空摘要区域
            document.getElementById('topic-summary').innerHTML = '';

            // 渲染选题列表（带筛选）
            const sliderVal = parseInt(document.getElementById('topic-count-slider')?.value || 20);
            const typeVal = document.querySelector('input[name="topic-type"]:checked')?.value || 'all';
            this._renderTopicList(lib, sliderVal, typeVal);

            // 有数据时绑定更新按钮
            const regenBtn = document.getElementById('btn-regen-topic');
            if (regenBtn) regenBtn.onclick = () => this.generateLibrary(portraitId);
        }
    },

    _renderTopicList(lib, count, typeFilter = 'all') {
        const list = document.getElementById('topic-list');
        const topics = lib.topic_library?.topics || [];

        let filtered = topics;
        if (typeFilter !== 'all') {
            filtered = topics.filter(t => (t.type_name || t.type || '') === typeFilter);
        }

        const shown = filtered.slice(0, count);

        list.innerHTML = shown.length === 0
            ? `<div class="col-12 text-center text-muted py-3 small">暂无此类选题</div>`
            : shown.map(t => `
                <div class="col-md-6 col-lg-4">
                    <div class="card border">
                        <div class="card-body py-2 px-2">
                            <div class="d-flex align-items-start gap-1 mb-1">
                                <span class="badge bg-secondary" style="font-size:10px;white-space:normal;">${this.escapeHtml(t.type_name || t.type || '')}</span>
                                ${t.priority ? `<span class="badge ${this._priorityBadgeClass(t.priority)}" style="font-size:10px;">${t.priority}</span>` : ''}
                            </div>
                            <div class="small fw-bold mb-1" style="line-height:1.3;">${this.escapeHtml(t.title || '')}</div>
                            ${t.reason ? `<div class="small text-muted" style="line-height:1.2;font-size:11px;">${this.escapeHtml(t.reason)}</div>` : ''}
                            ${t.keywords && t.keywords.length ? `
                                <div class="mt-1">
                                    ${t.keywords.slice(0,3).map(k => `<span class="badge bg-light text-muted" style="font-size:10px;">${this.escapeHtml(k)}</span>`).join('')}
                                </div>` : ''}
                        </div>
                    </div>
                </div>`).join('');
    },

    _priorityBadgeClass(p) {
        const map = { P0: 'bg-danger', P1: 'bg-warning text-dark', P2: 'bg-info', P3: 'bg-secondary' };
        return map[p] || 'bg-secondary';
    },

    async generateLibrary(portraitId) {
        // 检查选题库生成配额
        const quota = this._libraryQuota;
        if (quota && quota.keyword && quota.keyword.remaining <= 0) {
            showToast(`生成次数已用完（每天${quota.keyword.limit}次）`, 'warning');
            return;
        }

        const btn = document.getElementById('btn-regen-topic');
        if (btn) { btn.disabled = true; btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>生成中...'; }

        try {
            const resp = await fetch(`/public/api/portraits/${portraitId}/library/generate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ library_type: 'topic' })
            });
            const data = await resp.json();
            if (!data.success) {
                showToast(data.message || '生成失败', 'error');
                return;
            }

            showToast('专属库生成成功', 'success');
            await this.loadLibraryQuota();
            await this.loadLibraryData(portraitId, 'topic');
        } catch (e) {
            console.error('[PortraitManager] 生成库失败:', e);
            showToast('生成失败', 'error');
        } finally {
            if (btn) { btn.disabled = false; btn.innerHTML = '<i class="bi bi-arrow-clockwise me-1"></i>更新'; }
        }
    },

    async generateTopicsForPortrait(portraitId) {
        // 打开选题选择弹窗
        const modal = new bootstrap.Modal(document.getElementById('topicsSelectModal'));
        document.getElementById('topics-select-loading').style.display = 'block';
        document.getElementById('topics-select-list').innerHTML = '';
        document.getElementById('topics-select-footer').style.display = 'none';
        modal.show();

        const portrait = this._savedPortraits.find(p => p.id === portraitId);
        if (!portrait) {
            document.getElementById('topics-select-loading').style.display = 'none';
            showToast('画像不存在', 'error');
            return;
        }

        this._pendingPortraitForTopic = portrait;

        try {
            const resp = await fetch(`/public/api/portraits/${portraitId}/topics?count=10&source=mixed`, {
                credentials: 'include'
            });
            const data = await resp.json();
            document.getElementById('topics-select-loading').style.display = 'none';

            if (data.success && data.data && data.data.topics && data.data.topics.length > 0) {
                this._pendingTopics = data.data.topics;
                this.renderTopicsSelectList(data.data.topics, data.data.from_portrait_library);
                document.getElementById('topics-select-footer').style.display = 'flex';
            } else {
                document.getElementById('topics-select-empty').style.display = 'block';
                document.getElementById('topics-select-empty').textContent = '暂无选题，请先生成专属选题库';
            }
        } catch (e) {
            console.error('[PortraitManager] 获取选题失败:', e);
            document.getElementById('topics-select-loading').style.display = 'none';
            showToast('获取选题失败', 'error');
        }
    },

    renderTopicsSelectList(topics, fromLibrary = false) {
        const container = document.getElementById('topics-select-list');
        const fromLibBadge = fromLibrary ? '<span class="badge bg-success ms-1" style="font-size:10px;"><i class="bi bi-bookmark"></i>专属库</span>' : '';

        container.innerHTML = topics.map((t, i) => `
            <div class="form-check mb-2 p-3 border rounded topic-select-item" style="cursor:pointer;">
                <input class="form-check-input" type="radio" name="topic-select-radio" id="topic-select-${i}" value="${i}">
                <label class="form-check-label w-100" for="topic-select-${i}" style="cursor:pointer;">
                    <div class="d-flex justify-content-between align-items-start">
                        <div>
                            <span class="badge bg-secondary me-2" style="font-size:11px;">${t.type_name || t.type || ''}</span>
                            <span class="badge bg-warning text-dark me-2" style="font-size:11px;">${t.priority || 'P2'}</span>
                            ${fromLibBadge}
                            <strong>${this.escapeHtml(t.title || '')}</strong>
                        </div>
                    </div>
                    ${t.reason ? `<div class="small text-muted mt-1">${this.escapeHtml(t.reason)}</div>` : ''}
                    ${t.keywords && t.keywords.length ? `
                        <div class="mt-1">
                            ${t.keywords.slice(0,4).map(k => `<span class="badge bg-light text-muted" style="font-size:10px;">${this.escapeHtml(k)}</span>`).join('')}
                        </div>` : ''}
                </label>
            </div>`).join('');

        container.querySelectorAll('.topic-select-item').forEach(item => {
            item.addEventListener('click', e => {
                if (e.target.tagName !== 'INPUT') {
                    item.querySelector('input[type="radio"]').checked = true;
                }
            });
        });
    },

    async confirmTopicSelect() {
        const checked = document.querySelector('input[name="topic-select-radio"]:checked');
        if (!checked) { showToast('请选择一个选题', 'warning'); return; }

        const topicIndex = parseInt(checked.value);
        const topic = this._pendingTopics?.[topicIndex];
        const portrait = this._pendingPortraitForTopic;

        if (!topic || !portrait) { showToast('选题信息不完整', 'error'); return; }

        bootstrap.Modal.getInstance(document.getElementById('topicsSelectModal'))?.hide();

        if (window._generateContentForTopic) {
            await window._generateContentForTopic(topic, portrait.portrait_data || portrait);
        } else {
            showToast('生成功能暂不可用', 'error');
        }
    },

    // ========================================================================
    // 六、工具方法
    // ========================================================================

    canSavePortrait() {
        if (!this._quota) return { allowed: false, reason: '加载中...' };
        if (!this._quota.can_save) return { allowed: false, reason: '当前版本不支持保存画像，请升级' };
        const max = this._quota.max_saved || 0;
        if (max && this._savedPortraits.length >= max) return { allowed: false, reason: `已达保存上限（${max}个）` };
        return { allowed: true };
    },

    _isExpired(expiresAt) {
        if (!expiresAt) return true;
        const d = new Date(expiresAt);
        return d < new Date();
    },

    escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;')
            .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    },

    formatDate(dateStr) {
        if (!dateStr) return '';
        const d = new Date(dateStr);
        return `${d.getMonth() + 1}/${d.getDate()} ${d.getHours()}:${String(d.getMinutes()).padStart(2, '0')}`;
    },

    showLibraryModal() {
        if (this._savedPortraits.length === 0) {
            showToast('请先在下方生成并保存画像', 'info');
            return;
        }
        // 打开第一个画像的专属库弹窗
        this.openLibraryModal(this._savedPortraits[0].id);
    },

    // ========================================================================
    // 首次使用引导
    // ========================================================================
    showOnboardingTip() {
        const section = document.getElementById('portrait-section');
        if (!section || section.style.display === 'none') return;
        if (this._savedPortraits.length === 0) return;

        // 检查是否已看过引导（localStorage）
        const key = 'portrait_onboarding_shown_v1';
        if (localStorage.getItem(key)) return;

        // 3秒后显示引导提示
        setTimeout(() => {
            const tip = document.getElementById('portrait-onboarding-tip');
            if (tip) {
                tip.style.display = 'block';
                // 5秒后自动隐藏
                setTimeout(() => {
                    if (tip) tip.style.display = 'none';
                }, 5000);
            }
        }, 2000);

        // 标记已看过
        localStorage.setItem(key, '1');
    }
};

// 页面初始化
document.addEventListener('DOMContentLoaded', async () => {
    if (document.body.dataset.userId) {
        await PortraitManager.init();
        PortraitManager.showOnboardingTip();
    }
});
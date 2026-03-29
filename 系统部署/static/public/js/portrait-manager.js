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

    async loadLibraryQuota() {
        try {
            const resp = await fetch('/public/api/portraits/library/quota', { credentials: 'include' });
            const data = await resp.json();
            if (data.success) {
                this._libraryQuota = data.data || { keyword: null, topic: null };
                this.updateLibraryQuotaHint();
            }
        } catch (e) {
            console.error('[PortraitManager] 加载库配额失败:', e);
        }
    },

    updateLibraryQuotaHint() {
        const el = document.getElementById('library-quota-hint');
        if (!el) return;
        const kw = this._libraryQuota.keyword || {};
        const tp = this._libraryQuota.topic || {};
        if (!kw.limit && !tp.limit) {
            el.textContent = '';
            return;
        }
        el.textContent = `关键词库剩余:${kw.remaining || 0}/${kw.limit || 0} 选题库剩余:${tp.remaining || 0}/${tp.limit || 0}`;
    },

    updateQuotaDisplay() {
        const el = document.getElementById('quota-info');
        if (!el || !this._quota) return;
        const planType = this._quota.plan_type || 'free';
        const planNames = { free: '免费版', basic: '基础版', professional: '专业版', enterprise: '企业版' };

        if (planType === 'free') {
            el.innerHTML = '<span>今日剩余次数：<strong id="quota-count">2</strong> 次</span><a href="/public/pricing" class="alert-link">升级获取更多次数 →</a>';
        } else {
            el.innerHTML = `<span class="badge bg-primary">${planNames[planType] || planType}</span> 已保存画像：${this._savedPortraits.length}${this._quota.max_saved ? '/' + this._quota.max_saved : ''} 个`;
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

        container.innerHTML = this._savedPortraits.map(p => {
            const hasKw = p.keyword_library && Object.keys(p.keyword_library).length > 0;
            const hasTopic = p.topic_library && p.topic_library.topics && p.topic_library.topics.length > 0;
            const kwExpired = this._isExpired(p.keyword_cache_expires_at);
            const topicExpired = this._isExpired(p.topic_cache_expires_at);
            const isActive = p.id === this._currentPortraitId;
            return `
                <div class="col-md-4 col-lg-3">
                    <div class="card portrait-card ${isActive ? 'border-primary shadow' : ''}"
                         data-id="${p.id}" style="cursor:pointer;"
                         onclick="PortraitManager.openLibraryModal(${p.id})">
                        <div class="card-body py-2 px-3">
                            <div class="d-flex justify-content-between align-items-start mb-1">
                                <div class="portrait-card-name text-truncate" style="max-width: 140px;">
                                    ${this.escapeHtml(p.portrait_name || '未命名')}
                                    ${p.is_default ? '<span class="badge bg-primary ms-1" style="font-size:10px;">默认</span>' : ''}
                                </div>
                                <div class="dropdown">
                                    <button class="btn btn-sm btn-link text-muted p-0" onclick="event.stopPropagation();" data-bs-toggle="dropdown">
                                        <i class="bi bi-three-dots-vertical"></i>
                                    </button>
                                    <ul class="dropdown-menu dropdown-menu-end">
                                        <li><a class="dropdown-item small" href="#" onclick="event.stopPropagation(); PortraitManager.setDefaultPortrait(${p.id})">
                                            <i class="bi bi-star me-1"></i>设为默认</a></li>
                                        <li><a class="dropdown-item small" href="#" onclick="event.stopPropagation(); PortraitManager.quickUsePortrait(${p.id})">
                                            <i class="bi bi-lightning-charge me-1"></i>直接生成内容</a></li>
                                        <li><hr class="dropdown-divider"></li>
                                        <li><a class="dropdown-item small text-danger" href="#" onclick="event.stopPropagation(); PortraitManager.deletePortrait(${p.id})">
                                            <i class="bi bi-trash me-1"></i>删除</a></li>
                                    </ul>
                                </div>
                            </div>
                            <div class="small text-muted mb-1">
                                <span>${p.industry || '通用'}</span>
                                <span class="ms-1">使用 ${p.used_count || 0} 次</span>
                            </div>
                            <!-- 库状态徽章 -->
                            <div class="d-flex gap-1 flex-wrap">
                                ${hasKw && !kwExpired
                                    ? `<span class="badge bg-info" style="font-size:10px;"><i class="bi bi-key"></i> 关键词库</span>`
                                    : hasKw && kwExpired
                                    ? `<span class="badge bg-warning" style="font-size:10px;"><i class="bi bi-key"></i> 已过期</span>`
                                    : `<span class="badge bg-light text-muted" style="font-size:10px;"><i class="bi bi-key"></i> 无</span>`}
                                ${hasTopic && !topicExpired
                                    ? `<span class="badge bg-success" style="font-size:10px;"><i class="bi bi-lightbulb"></i> 选题库</span>`
                                    : hasTopic && topicExpired
                                    ? `<span class="badge bg-warning" style="font-size:10px;"><i class="bi bi-lightbulb"></i> 已过期</span>`
                                    : `<span class="badge bg-light text-muted" style="font-size:10px;"><i class="bi bi-lightbulb"></i> 无</span>`}
                            </div>
                        </div>
                    </div>
                </div>`;
        }).join('');
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

        // 填充头部信息
        document.getElementById('library-portrait-name').textContent = portrait.portrait_name || '未命名';
        document.getElementById('library-portrait-industry').textContent = portrait.industry || '';

        // 更新状态徽章
        const hasKw = portrait.keyword_library && Object.keys(portrait.keyword_library).length > 0;
        const hasTopic = portrait.topic_library && portrait.topic_library.topics && portrait.topic_library.topics.length > 0;
        const kwExpired = this._isExpired(portrait.keyword_cache_expires_at);
        const topicExpired = this._isExpired(portrait.topic_cache_expires_at);

        const kwStatus = document.getElementById('library-keyword-status');
        const topicStatus = document.getElementById('library-topic-status');

        if (hasKw && !kwExpired) {
            kwStatus.className = 'badge bg-info';
            kwStatus.textContent = '关键词库已就绪';
        } else if (hasKw && kwExpired) {
            kwStatus.className = 'badge bg-warning';
            kwStatus.textContent = '关键词库已过期';
        } else {
            kwStatus.className = 'badge bg-secondary';
            kwStatus.textContent = '无关键词库';
        }

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

        // 重置 Tab 到关键词库
        const tabKw = document.getElementById('tab-kw-btn');
        const tabTopic = document.getElementById('tab-topic-btn');
        const contentKw = document.getElementById('tab-kw');
        const contentTopic = document.getElementById('tab-topic');
        if (tabKw && tabTopic && contentKw && contentTopic) {
            tabKw.classList.add('active');
            tabTopic.classList.remove('active');
            contentKw.classList.add('show', 'active');
            contentTopic.classList.remove('show', 'active');
        }

        // 显示弹窗
        const modal = new bootstrap.Modal(document.getElementById('portraitLibraryModal'));
        modal.show();

        // 加载数据
        await this.loadLibraryData(portraitId, 'keyword');
    },

    async loadLibraryData(portraitId, tab = 'keyword') {
        portraitId = portraitId || this._currentLibraryPortraitId;
        if (!portraitId) return;
        try {
            const resp = await fetch(`/public/api/portraits/${portraitId}/library`, { credentials: 'include' });
            const data = await resp.json();
            if (!data.success) return;

            const lib = data.data || {};

            if (tab === 'keyword') {
                this._renderKeywordLibrary(lib, portraitId);
            } else {
                this._renderTopicLibrary(lib, portraitId);
            }
        } catch (e) {
            console.error('[PortraitManager] 加载库数据失败:', e);
        }
    },

    _renderKeywordLibrary(lib, portraitId) {
        const loading = document.getElementById('kw-loading');
        const empty = document.getElementById('kw-empty');
        const detail = document.getElementById('kw-detail');
        const categories = document.getElementById('kw-categories');

        loading.style.display = 'none';

        if (!lib.keyword_library || !lib.keyword_library.categories || lib.keyword_library.categories.length === 0) {
            empty.style.display = 'block';
            detail.style.display = 'none';
        } else {
            empty.style.display = 'none';
            detail.style.display = 'block';

            const updatedAt = lib.keyword_updated_at ? new Date(lib.keyword_updated_at).toLocaleString() : '未知';
            document.getElementById('kw-updated-at').textContent = `更新于：${updatedAt}`;
            document.getElementById('kw-update-count').textContent = `已更新 ${lib.keyword_update_count || 0} 次`;

            const cats = lib.keyword_library.categories || [];
            categories.innerHTML = cats.map(cat => `
                <div class="card mb-2">
                    <div class="card-header py-1 px-2 bg-light d-flex justify-content-between">
                        <strong style="font-size:13px;">${cat.name}</strong>
                        <span class="badge bg-secondary" style="font-size:10px;">${cat.count || 0}个</span>
                    </div>
                    <div class="card-body py-1 px-2">
                        <div class="d-flex flex-wrap gap-1">
                            ${(cat.keywords || []).map(kw => `<span class="badge bg-light text-dark" style="font-size:11px;">${this.escapeHtml(kw)}</span>`).join('')}
                        </div>
                    </div>
                </div>`).join('');

            // 蓝海词
            const blueOcean = lib.keyword_library.blue_ocean || [];
            if (blueOcean.length > 0) {
                categories.innerHTML += `
                    <div class="card mb-2 border-warning">
                        <div class="card-header py-1 px-2 bg-warning bg-opacity-10">
                            <strong style="font-size:13px;color:#856404;">蓝海长尾词</strong>
                        </div>
                        <div class="card-body py-1 px-2">
                            <div class="d-flex flex-wrap gap-1">
                                ${blueOcean.map(b => `<span class="badge bg-warning text-dark" style="font-size:11px;" title="${b.modifier}">${this.escapeHtml(b.full_keyword || b.core_word)}</span>`).join('')}
                            </div>
                        </div>
                    </div>`;
            }
        }

        // 绑定更新按钮
        this._bindLibraryUpdateBtns(portraitId, 'keyword');
    },

    _renderTopicLibrary(lib, portraitId) {
        const loading = document.getElementById('topic-loading');
        const empty = document.getElementById('topic-empty');
        const detail = document.getElementById('topic-detail');
        const summary = document.getElementById('topic-summary');
        const list = document.getElementById('topic-list');

        loading.style.display = 'none';

        if (!lib.topic_library || !lib.topic_library.topics || lib.topic_library.topics.length === 0) {
            empty.style.display = 'block';
            detail.style.display = 'none';
        } else {
            empty.style.display = 'none';
            detail.style.display = 'block';

            const updatedAt = lib.topic_updated_at ? new Date(lib.topic_updated_at).toLocaleString() : '未知';
            document.getElementById('topic-updated-at').textContent = `更新于：${updatedAt}`;
            document.getElementById('topic-update-count').textContent = `已更新 ${lib.topic_update_count || 0} 次`;

            const topics = lib.topic_library.topics || [];
            const priorities = lib.topic_library.priorities || {};

            // 统计摘要
            summary.innerHTML = `
                <div class="d-flex gap-2 flex-wrap">
                    ${Object.entries(priorities).map(([p, n]) => {
                        const colors = { P0: 'bg-danger', P1: 'bg-warning', P2: 'bg-info', P3: 'bg-secondary' };
                        return `<span class="badge ${colors[p] || 'bg-secondary'}" style="font-size:11px;">${p}: ${n}条</span>`;
                    }).join('')}
                    <span class="badge bg-light text-dark" style="font-size:11px;">共 ${topics.length} 条</span>
                </div>`;

            // 选题列表
            list.innerHTML = topics.slice(0, 20).map(t => `
                <div class="col-md-6">
                    <div class="card border">
                        <div class="card-body py-2 px-2">
                            <div class="d-flex justify-content-between align-items-start mb-1">
                                <span class="badge ${this._priorityBadgeClass(t.priority)}" style="font-size:10px;">${t.priority || 'P2'}</span>
                                <span class="badge bg-light text-muted" style="font-size:10px;">${t.type_name || t.source || ''}</span>
                            </div>
                            <div class="small fw-bold mb-1" style="line-height:1.3;">${this.escapeHtml(t.title || '')}</div>
                            ${t.reason ? `<div class="small text-muted" style="line-height:1.2;">${this.escapeHtml(t.reason)}</div>` : ''}
                            ${t.keywords && t.keywords.length ? `
                                <div class="mt-1">
                                    ${t.keywords.slice(0,3).map(k => `<span class="badge bg-light text-muted" style="font-size:10px;">${this.escapeHtml(k)}</span>`).join('')}
                                </div>` : ''}
                        </div>
                    </div>
                </div>`).join('');
        }

        // 绑定更新按钮
        this._bindLibraryUpdateBtns(portraitId, 'topic');
    },

    _priorityBadgeClass(p) {
        const map = { P0: 'bg-danger', P1: 'bg-warning text-dark', P2: 'bg-info', P3: 'bg-secondary' };
        return map[p] || 'bg-secondary';
    },

    _bindLibraryUpdateBtns(portraitId, type) {
        const genBtn = document.getElementById(type === 'keyword' ? 'btn-gen-kw' : 'btn-gen-topic');
        const regenBtn = document.getElementById(type === 'keyword' ? 'btn-regen-kw' : 'btn-regen-topic');

        if (genBtn) {
            genBtn.onclick = () => this.generateLibrary(portraitId, type);
        }
        if (regenBtn) {
            regenBtn.onclick = () => this.generateLibrary(portraitId, type);
        }

        // 使用画像生成内容按钮
        document.getElementById('btn-use-portrait-from-library').onclick = () => {
            bootstrap.Modal.getInstance(document.getElementById('portraitLibraryModal'))?.hide();
            this.quickUsePortrait(portraitId);
        };

        // Tab 切换时加载
        document.getElementById(type === 'keyword' ? 'tab-topic-btn' : 'tab-kw-btn').onclick = () => {
            setTimeout(() => this.loadLibraryData(portraitId, type === 'keyword' ? 'topic' : 'keyword'), 50);
        };
    },

    async generateLibrary(portraitId, type = 'all') {
        // 检查配额（关键词库+选题库合并，一次配额）
        const quota = this._libraryQuota;
        if (quota && quota.keyword && quota.keyword.remaining <= 0) {
            showToast(`生成次数已用完（每天${quota.keyword.limit}次）`, 'warning');
            return;
        }

        const btnId = type === 'keyword' ? 'btn-regen-kw' : type === 'topic' ? 'btn-regen-topic' : 'btn-create-library';
        const btn = document.getElementById(btnId);
        if (btn) { btn.disabled = true; btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>生成中...'; }

        try {
            const resp = await fetch(`/public/api/portraits/${portraitId}/library/generate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ library_type: type })
            });
            const data = await resp.json();
            if (!data.success) {
                showToast(data.message || '生成失败', 'error');
                return;
            }

            showToast('专属库生成成功', 'success');
            await this.loadLibraryQuota();
            await this.loadLibraryData(portraitId, type === 'all' ? 'keyword' : type);
            await this.loadSavedPortraits(); // 刷新卡片状态
        } catch (e) {
            console.error('[PortraitManager] 生成库失败:', e);
            showToast('生成失败', 'error');
        } finally {
            if (btn) { btn.disabled = false; btn.innerHTML = type === 'keyword' ? '<i class="bi bi-arrow-clockwise me-1"></i>更新' : '<i class="bi bi-arrow-clockwise me-1"></i>更新'; }
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
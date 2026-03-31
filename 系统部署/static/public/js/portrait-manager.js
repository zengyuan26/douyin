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

    async loadLibraryQuota() {
        try {
            const resp = await fetch('/public/api/portraits/library/quota', { credentials: 'include' });
            const data = await resp.json();
            if (data.success) {
                this._libraryQuota = data.data || {};
            }
        } catch (e) {
            console.error('[PortraitManager] 加载库配额失败:', e);
        }
    },

    // ========================================================================
    // 三、画像加载 & 渲染
    // ========================================================================

    async loadSavedPortraits(savedPortraitId = null) {
        try {
            const resp = await fetch('/public/api/portraits/saved?include_data=true', { credentials: 'include' });
            if (!resp.ok) {
                console.error('[PortraitManager] 加载画像失败，HTTP状态:', resp.status);
                showToast('加载画像列表失败，请刷新页面重试', 'error');
                return;
            }
            const data = await resp.json();
            if (data.success) {
                this._savedPortraits = data.data || [];
                console.log('[PortraitManager] 已加载画像数量:', this._savedPortraits.length);

                // 优先使用传入的画像ID（保存成功后）
                if (savedPortraitId) {
                    this._currentPortraitId = savedPortraitId;
                    console.log('[PortraitManager] 使用保存的画像ID:', savedPortraitId);
                } else if (this._currentPortraitId) {
                    // 保持当前选中的画像ID（如果仍然存在）
                    const exists = this._savedPortraits.some(p => p.id === this._currentPortraitId);
                    if (!exists) {
                        this._currentPortraitId = null;
                    }
                }

                // 如果没有选中的画像，选择默认的或第一个
                if (!this._currentPortraitId) {
                    const defaultPortrait = this._savedPortraits.find(p => p.is_default);
                    if (defaultPortrait) {
                        this._currentPortraitId = defaultPortrait.id;
                    } else if (this._savedPortraits.length > 0) {
                        this._currentPortraitId = this._savedPortraits[0].id;
                    }
                }

                this.renderPortraitCards();
                // 有已保存画像时，隐藏超级定位步骤
                if (typeof updateSuperStepsVisibility === 'function') {
                    updateSuperStepsVisibility();
                }
            } else {
                console.error('[PortraitManager] 加载画像失败:', data.message);
                showToast('加载画像列表失败: ' + (data.message || '未知错误'), 'error');
            }
        } catch (e) {
            console.error('[PortraitManager] 加载画像失败:', e);
            showToast('加载画像列表失败，请检查网络连接', 'error');
        }
    },

    renderPortraitCards() {
        const container = document.getElementById('portrait-cards-list');
        const loading = document.getElementById('portrait-cards-loading');
        if (!container) {
            console.error('[PortraitManager] 未找到画像卡片容器 #portrait-cards-list');
            return;
        }

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

        try {
            // 只显示当前选中的或默认画像（每个客户只有一个画像）
            const currentPortrait = this._savedPortraits.find(p => p.id === this._currentPortraitId) 
                || this._savedPortraits.find(p => p.is_default)
                || this._savedPortraits[0];

            if (!currentPortrait) {
                console.error('[PortraitManager] 未找到有效的画像数据');
                container.innerHTML = '<div class="col-12 text-center py-4 text-danger">画像数据异常</div>';
                return;
            }

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
            
            // 选题库状态提示
            let topicBadge = '';
            if (topicCount > 0) {
                topicBadge = `<span class="badge bg-success me-1" style="cursor:pointer;" onclick="event.stopPropagation(); PortraitManager.showTopicListModal(${p.id})" title="点击查看选题列表">📋 选题库 ${topicCount} 个</span>`;
            } else {
                topicBadge = `<span class="badge bg-secondary me-1">📋 选题库 生成中...</span>`;
            }

            container.innerHTML = `
            <div class="col-12">
                <div class="d-flex align-items-center justify-content-between flex-wrap gap-2 p-3 border rounded bg-light" style="cursor:default;">
                    <div class="d-flex align-items-center gap-3 flex-grow-1 min-w-0">
                        <div class="bg-primary rounded-circle d-flex align-items-center justify-content-center flex-shrink-0" style="width:48px;height:48px;">
                            <i class="bi bi-person text-white fs-4"></i>
                        </div>
                        <div class="min-w-0">
                            <div class="fw-bold text-dark">${this.escapeHtml(p.portrait_name || '用户画像')}</div>
                            <div class="small text-muted">${this.escapeHtml(p.industry || '')}</div>
                            <div class="mt-1">${topicBadge}</div>
                        </div>
                    </div>
                    <div class="d-flex align-items-center gap-2 flex-shrink-0 flex-wrap justify-content-end ms-auto">
                        <button class="btn btn-success btn-sm" onclick="PortraitManager.showRecommendedTopicsModal(${p.id})" title="推荐选题">
                            <i class="bi bi-lightbulb me-1"></i>推荐选题
                        </button>
                        <button class="btn btn-primary btn-sm" onclick="PortraitManager.showTopicSelectAndGenerate(${p.id})" title="生成内容">
                            <i class="bi bi-lightning-charge me-1"></i>生成内容
                        </button>
                        <button class="btn btn-sm btn-outline-primary" onclick="PortraitManager.showPortraitDetail(${p.id})" title="查看详情">
                            <i class="bi bi-eye me-1"></i>查看详情
                        </button>
                    </div>
                </div>
            </div>`;
            console.log('[PortraitManager] 画像卡片渲染成功，当前画像ID:', p.id);
        } catch (e) {
            console.error('[PortraitManager] 渲染画像卡片失败:', e);
            container.innerHTML = '<div class="col-12 text-center py-4 text-danger">渲染画像卡片失败</div>';
        }
    },

    // 直接显示选题选择弹窗（选择后生成内容）
    showTopicSelectAndGenerate(portraitId) {
        const portrait = this._savedPortraits.find(p => p.id === portraitId);
        if (!portrait) return;

        const topics = portrait.topic_library?.topics || [];
        if (topics.length === 0) {
            alert('暂无选题库，请重新生成画像');
            return;
        }

        // 随机推荐5个选题
        const shuffled = [...topics].sort(() => Math.random() - 0.5);
        const recommended = shuffled.slice(0, 5);

        const modalHtml = `
        <div class="modal fade" id="topicSelectModal" tabindex="-1">
            <div class="modal-dialog modal-dialog-scrollable">
                <div class="modal-content">
                    <div class="modal-header bg-primary text-white">
                        <h5 class="modal-title"><i class="bi bi-lightning-charge me-2"></i>选择选题生成内容</h5>
                        <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <p class="text-muted small mb-3">从选题库中随机推荐5个，选择一个后点击生成内容</p>
                        <div class="list-group" id="topic-list">
                            ${recommended.map((t, idx) => `
                                <label class="list-group-item list-group-item-action d-flex gap-3 py-3" style="cursor:pointer;">
                                    <input class="form-check-input flex-shrink-0 mt-1" type="radio" name="topicSelect" value="${idx}" id="topic-${idx}">
                                    <div class="flex-grow-1">
                                        <div class="d-flex align-items-center gap-2 mb-1">
                                            <span class="badge bg-secondary" style="font-size:10px;">${this.escapeHtml(t.type_name || t.type || '选题')}</span>
                                            ${t.priority ? `<span class="badge ${this._priorityBadgeClass(t.priority)}" style="font-size:10px;">${t.priority}</span>` : ''}
                                        </div>
                                        <div class="fw-medium">${this.escapeHtml(t.title || '')}</div>
                                        ${t.reason ? `<div class="small text-muted mt-1">${this.escapeHtml(t.reason)}</div>` : ''}
                                    </div>
                                </label>
                            `).join('')}
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">取消</button>
                        <button type="button" class="btn btn-primary" onclick="PortraitManager.generateWithSelectedTopic(${portraitId})">
                            <i class="bi bi-lightning-charge me-1"></i>生成内容
                        </button>
                    </div>
                </div>
            </div>
        </div>`;

        this._recommendedTopics = recommended;

        const oldModal = document.getElementById('topicSelectModal');
        if (oldModal) oldModal.remove();

        document.body.insertAdjacentHTML('beforeend', modalHtml);
        const modal = new bootstrap.Modal(document.getElementById('topicSelectModal'));
        modal.show();

        document.getElementById('topicSelectModal').addEventListener('hidden.bs.modal', function () {
            this.remove();
        });
    },

    // 显示推荐选题弹窗（只查看，不直接生成）
    showRecommendedTopicsModal(portraitId) {
        const portrait = this._savedPortraits.find(p => p.id === portraitId);
        if (!portrait) return;

        const topics = portrait.topic_library?.topics || [];
        if (topics.length === 0) {
            alert('暂无选题库，请重新生成画像');
            return;
        }

        const shuffled = [...topics].sort(() => Math.random() - 0.5);
        const recommended = shuffled.slice(0, 5);

        const modalHtml = `
        <div class="modal fade" id="topicRecommendModal" tabindex="-1">
            <div class="modal-dialog modal-dialog-scrollable">
                <div class="modal-content">
                    <div class="modal-header bg-success text-white">
                        <h5 class="modal-title"><i class="bi bi-lightbulb me-2"></i>推荐选题</h5>
                        <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <p class="text-muted small mb-3">从选题库中随机推荐5个，可选择一个后生成内容</p>
                        <div class="list-group">
                            ${recommended.map((t, idx) => `
                                <label class="list-group-item list-group-item-action d-flex gap-3 py-3" style="cursor:pointer;">
                                    <input class="form-check-input flex-shrink-0 mt-1" type="radio" name="topicSelect" value="${idx}" id="topic-${idx}">
                                    <div class="flex-grow-1">
                                        <div class="d-flex align-items-center gap-2 mb-1">
                                            <span class="badge bg-secondary" style="font-size:10px;">${this.escapeHtml(t.type_name || t.type || '选题')}</span>
                                            ${t.priority ? `<span class="badge ${this._priorityBadgeClass(t.priority)}" style="font-size:10px;">${t.priority}</span>` : ''}
                                        </div>
                                        <div class="fw-medium">${this.escapeHtml(t.title || '')}</div>
                                        ${t.reason ? `<div class="small text-muted mt-1">${this.escapeHtml(t.reason)}</div>` : ''}
                                    </div>
                                </label>
                            `).join('')}
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">关闭</button>
                        <button type="button" class="btn btn-success" onclick="PortraitManager.generateWithSelectedTopic(${portraitId})">
                            <i class="bi bi-lightning-charge me-1"></i>生成内容
                        </button>
                    </div>
                </div>
            </div>
        </div>`;

        this._recommendedTopics = recommended;

        const oldModal = document.getElementById('topicRecommendModal');
        if (oldModal) oldModal.remove();

        document.body.insertAdjacentHTML('beforeend', modalHtml);
        const modal = new bootstrap.Modal(document.getElementById('topicRecommendModal'));
        modal.show();

        document.getElementById('topicRecommendModal').addEventListener('hidden.bs.modal', function () {
            this.remove();
        });
    },

    // 使用选中的选题生成内容
    generateWithSelectedTopic(portraitId) {
        const selected = document.querySelector('input[name="topicSelect"]:checked');
        if (!selected) {
            alert('请先选择一个选题');
            return;
        }

        const topicIdx = parseInt(selected.value);
        const topic = this._recommendedTopics[topicIdx];
        if (!topic) return;

        // 关闭弹窗
        const modal = bootstrap.Modal.getInstance(document.getElementById('topicSelectModal'));
        if (modal) modal.hide();

        // 调用内容生成（传入选题信息）
        if (typeof this.generateContentWithTopic === 'function') {
            this.generateContentWithTopic(portraitId, topic);
        } else {
            // 备用方案：显示到控制台
            console.log('生成内容:', { portraitId, topic });
            alert(`将使用选题「${topic.title}」生成内容`);
        }
    },

    // 显示画像详情弹窗（直接展示超级定位保存的画像信息）
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
                        <button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">关闭</button>
                        <button type="button" class="btn btn-outline-danger btn-sm" onclick="PortraitManager.deletePortrait(${portrait.id})">
                            <i class="bi bi-trash me-1"></i>删除此画像
                        </button>
                    </div>
                </div>
            </div>
        </div>`;

        const oldModal = document.getElementById('portraitDetailModal');
        if (oldModal) oldModal.remove();

        document.body.insertAdjacentHTML('beforeend', modalHtml);
        const modal = new bootstrap.Modal(document.getElementById('portraitDetailModal'));
        modal.show();

        document.getElementById('portraitDetailModal').addEventListener('hidden.bs.modal', function () {
            this.remove();
        });
    },

    // 渲染画像详情内容（展示超级定位保存的完整画像信息）
    _renderPortraitDetailContent(portrait) {
        // portrait_data 可能是单一画像对象（旧格式），也可能是包含 portraits 数组的对象（新格式）
        const pd = portrait.portrait_data || {};
        let html = '';

        // 判断是单一画像还是多画像格式
        const isSinglePortrait = pd.name && (pd.user_perspective || pd.buyer_perspective || pd.portrait_summary);
        const portraits = pd.portraits || (isSinglePortrait ? [pd] : []);

        // 基本信息
        if (portrait.target_customer) {
            html += `
                <div class="mb-2">
                    <span class="badge bg-info"><i class="bi bi-people me-1"></i>${this.escapeHtml(portrait.target_customer)}</span>
                    ${portrait.industry ? `<span class="badge bg-secondary ms-1"><i class="bi bi-briefcase me-1"></i>${this.escapeHtml(portrait.industry)}</span>` : ''}
                </div>`;
        }

        // 人群画像列表
        if (portraits.length > 0) {
            html += `<h6 class="text-primary mb-3 mt-3"><i class="bi bi-person-badge me-1"></i>人群画像</h6>`;
            portraits.forEach((p, idx) => {
                const colors = [
                    { bg: '#f8f7ff', border: '#667eea', accent: '#667eea' },
                    { bg: '#fff5f7', border: '#f5576c', accent: '#f5576c' },
                    { bg: '#f0fbff', border: '#4facfe', accent: '#4facfe' },
                    { bg: '#f0fff4', border: '#43e97b', accent: '#43e97b' },
                ];
                const c = colors[idx % colors.length];

                // 身份标签
                const identityTags = p.identity_tags || {};
                const buyerTag = identityTags.buyer || '';
                const userTag = identityTags.user || '';

                // 使用者视角
                const userPersp = p.user_perspective || {};
                const userProblem = userPersp.problem || '';
                const userState = userPersp.current_state || '';
                const userImpact = userPersp.impact || '';

                // 付费者视角
                const buyerPersp = p.buyer_perspective || {};
                const buyerGoal = buyerPersp.goal || '';
                const buyerObstacles = buyerPersp.obstacles || '';
                const buyerPsych = buyerPersp.psychology || '';

                // 自然语言摘要
                let summaryNatural = (p.portrait_summary || '').trim();
                if (!summaryNatural) {
                    const obs = (buyerObstacles || '').replace(/；/g, '，').replace(/;/g, '，').trim();
                    if (userProblem && buyerTag) {
                        if (obs) {
                            summaryNatural = `${userProblem}，${buyerTag}自个儿扛着，想解决可又${obs}。`;
                        } else if (buyerGoal) {
                            summaryNatural = `${userProblem}，${buyerTag}自个儿扛着，${buyerGoal}。`;
                        }
                    } else if (userProblem) {
                        summaryNatural = userProblem + (obs ? `，可又${obs}。` : '。');
                    } else if (buyerGoal) {
                        summaryNatural = buyerGoal + (obs ? `，可又${obs}。` : '。');
                    }
                }

                html += `
                    <div class="card mb-3 border" style="border: 2px solid ${c.border}; background: ${c.bg}; border-radius: 12px;">
                        <div class="card-body p-3">
                            <div class="d-flex justify-content-between align-items-start mb-2">
                                <div>
                                    <span class="badge" style="background: ${c.accent}; color: white; font-size: 13px;">${this.escapeHtml(p.name || '用户画像' + (idx+1))}</span>
                                    ${buyerTag ? `<span class="badge bg-warning text-dark ms-1" style="font-size:11px;">💰 ${this.escapeHtml(buyerTag)}</span>` : ''}
                                    ${userTag ? `<span class="badge bg-secondary ms-1" style="font-size:11px;">👤 ${this.escapeHtml(userTag)}</span>` : ''}
                                </div>
                            </div>`;

                // 自然语言摘要
                if (summaryNatural) {
                    html += `<div class="mb-3 p-2 rounded" style="background: white; font-size: 14px; line-height: 1.6;">${this.escapeHtml(summaryNatural)}</div>`;
                }

                // 使用者视角
                if (userProblem || userState || userImpact) {
                    html += `
                        <div style="background: white; border-radius: 8px; padding: 0.75rem; margin-bottom: 0.75rem; border-left: 3px solid #4facfe;">
                            <div class="small text-muted mb-1"><i class="bi bi-person me-1"></i>使用者视角</div>
                            ${userProblem ? `<div class="mb-1"><strong>问题：</strong>${this.escapeHtml(userProblem)}</div>` : ''}
                            ${userState ? `<div class="mb-1"><strong>现状：</strong>${this.escapeHtml(userState)}</div>` : ''}
                            ${userImpact ? `<div><strong>影响：</strong>${this.escapeHtml(userImpact)}</div>` : ''}
                        </div>`;
                }

                // 付费者视角
                if (buyerGoal || buyerObstacles || buyerPsych) {
                    html += `
                        <div style="background: white; border-radius: 8px; padding: 0.75rem; margin-bottom: 0.75rem; border-left: 3px solid #fbbf24;">
                            <div class="small text-muted mb-1"><i class="bi bi-currency-dollar me-1"></i>付费者视角</div>
                            ${buyerGoal ? `<div class="mb-1"><strong>目标：</strong>${this.escapeHtml(buyerGoal)}</div>` : ''}
                            ${buyerObstacles ? `<div class="mb-1"><strong>顾虑：</strong>${this.escapeHtml(buyerObstacles)}</div>` : ''}
                            ${buyerPsych ? `<div><strong>心理：</strong>${this.escapeHtml(buyerPsych)}</div>` : ''}
                        </div>`;
                }

                html += `</div></div>`;
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
        // 确保配额已加载
        if (!this._quota) {
            showToast('正在加载用户信息，请稍候...', 'info');
            await this.loadQuota();
        }
        const result = this.canSavePortrait();
        if (!result.allowed) {
            showToast(result.reason, 'warning');
            return null;
        }
        try {
            console.log('[PortraitManager.saveCurrentPortrait] 开始保存画像...');
            console.log('[PortraitManager.saveCurrentPortrait] portraitData:', portraitData);
            console.log('[PortraitManager.saveCurrentPortrait] options:', options);
            
            // 创建 AbortController 用于超时控制
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 120000); // 2分钟超时
            
            const resp = await fetch('/public/api/portraits/save', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                signal: controller.signal,
                body: JSON.stringify({
                    portrait_data: portraitData,
                    portrait_name: options.portraitName,
                    business_description: options.businessDescription,
                    industry: options.industry,
                    target_customer: options.targetCustomer,
                    set_as_default: options.setAsDefault || false
                })
            });
            
            clearTimeout(timeoutId);
            
            console.log('[PortraitManager.saveCurrentPortrait] 响应状态:', resp.status);
            const data = await resp.json();
            console.log('[PortraitManager.saveCurrentPortrait] 响应数据:', JSON.stringify(data));
            
            if (data.success) {
                const savedPortraitId = data.data?.id;
                console.log('[PortraitManager] 画像保存成功，ID:', savedPortraitId);

                // 重新加载画像列表，并指定当前画像ID
                await this.loadSavedPortraits(savedPortraitId);
                await this.loadQuota();

                // 启动轮询检查选题库生成状态（付费用户）
                if (this._quota && this._quota.can_save) {
                    this._startTopicPolling(savedPortraitId);
                }

                console.log('[PortraitManager.saveCurrentPortrait] 返回 savedPortraitId:', savedPortraitId);
                // 返回保存结果，由调用方统一显示提示和刷新
                return data.data;
            } else {
                console.error('[PortraitManager] 保存失败:', data.message);
                showToast(data.message || '保存失败', 'error');
                return null;
            }
        } catch (e) {
            console.error('[PortraitManager] 保存失败异常:', e);
            if (e.name === 'AbortError') {
                showToast('保存超时，请重试', 'error');
            } else {
                showToast('保存失败', 'error');
            }
            return null;
        }
    },

    async deletePortrait(portraitId) {
        if (!confirm('确定删除该画像？')) return;
        try {
            console.log('[PortraitManager] 开始删除画像 ID:', portraitId);
            const resp = await fetch(`/public/api/portraits/${portraitId}`, {
                method: 'DELETE', credentials: 'include'
            });
            console.log('[PortraitManager] 删除响应状态:', resp.status);
            const data = await resp.json();
            console.log('[PortraitManager] 删除响应数据:', data);
            if (data.success) {
                if (this._currentPortraitId === portraitId) this._currentPortraitId = null;
                await this.loadSavedPortraits();
                await this.loadQuota();
                // 手动关闭详情弹窗
                const modal = bootstrap.Modal.getInstance(document.getElementById('portraitDetailModal'));
                if (modal) modal.hide();
                showToast('画像已删除', 'success');
            } else {
                showToast(data.message || '删除失败', 'error');
            }
        } catch (e) {
            console.error('[PortraitManager] 删除画像失败:', e);
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

    async generateLibrary(portraitId, type = 'topic') {
        // 检查配额
        const quota = this._libraryQuota;
        if (quota && quota[type] && quota[type].remaining <= 0) {
            console.log(`[generateLibrary] ${type} 库生成次数已用完，跳过`);
            return;
        }

        const typeLabel = type === 'keyword' ? '关键词库' : '选题库';

        try {
            const resp = await fetch(`/public/api/portraits/${portraitId}/library/generate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ library_type: type })
            });
            const data = await resp.json();
            if (!data.success) {
                console.error(`[generateLibrary] ${typeLabel}生成失败:`, data.message);
                return;
            }

            console.log(`[generateLibrary] ${typeLabel}生成成功`);
            await this.loadLibraryQuota();
            // 如果当前正在查看这个画像的库数据，刷新显示
            if (this._currentLibraryPortraitId === portraitId) {
                await this.loadLibraryData(portraitId, type);
            }
        } catch (e) {
            console.error(`[generateLibrary] ${typeLabel}生成异常:`, e);
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
    
    // 轮询检查选题库生成状态
    _startTopicPolling(portraitId) {
        let attempts = 0;
        const maxAttempts = 30; // 最多30次，每次3秒 = 90秒
        
        const poll = async () => {
            if (attempts >= maxAttempts) {
                console.log('[PortraitManager] 选题库轮询超时');
                return;
            }
            
            attempts++;
            console.log(`[PortraitManager] 检查选题库生成状态... (${attempts}/${maxAttempts})`);
            
            // 重新加载画像数据
            try {
                const resp = await fetch('/public/api/portraits/saved?include_data=true', { credentials: 'include' });
                const data = await resp.json();
                
                if (data.success) {
                    const portraits = data.data || [];
                    const portrait = portraits.find(p => p.id === portraitId);
                    
                    if (portrait && portrait.topic_library && portrait.topic_library.topics && portrait.topic_library.topics.length > 0) {
                        console.log('[PortraitManager] 选题库已生成:', portrait.topic_library.topics.length, '个');
                        
                        // 更新本地缓存
                        const localPortrait = this._savedPortraits.find(p => p.id === portraitId);
                        if (localPortrait) {
                            localPortrait.topic_library = portrait.topic_library;
                        }
                        
                        // 重新渲染卡片
                        this.renderPortraitCards();
                        showToast('选题库生成完成', 'success');
                        return;
                    }
                }
            } catch (e) {
                console.error('[PortraitManager] 轮询失败:', e);
            }
            
            // 继续轮询
            setTimeout(poll, 3000);
        };
        
        // 延迟3秒开始第一次检查
        setTimeout(poll, 3000);
    },

    // 使用选题生成内容
    async generateContentWithTopic(portraitId, topic) {
        const portrait = this._savedPortraits.find(p => p.id === portraitId);
        if (!portrait) {
            showToast('画像信息不存在', 'error');
            return;
        }

        // 调用全局生成函数
        if (window._generateContentForTopic) {
            await window._generateContentForTopic(topic, portrait.portrait_data || portrait);
        } else {
            showToast('生成功能暂不可用，请刷新页面重试', 'error');
        }
    },

    escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;')
            .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    },
    
    // 显示选题库列表弹窗
    showTopicListModal(portraitId) {
        const portrait = this._savedPortraits.find(p => p.id === portraitId);
        if (!portrait) return;
        
        const topics = portrait.topic_library?.topics || [];
        if (topics.length === 0) {
            showToast('选题库为空，请稍后刷新页面', 'info');
            return;
        }
        
        const modalHtml = `
        <div class="modal fade" id="topicListModal" tabindex="-1">
            <div class="modal-dialog modal-lg modal-dialog-scrollable">
                <div class="modal-content">
                    <div class="modal-header bg-success text-white">
                        <h5 class="modal-title"><i class="bi bi-list-ul me-2"></i>选题库（共 ${topics.length} 个）</h5>
                        <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <div class="row g-2" id="topic-list-content">
                            ${topics.map(t => `
                                <div class="col-md-6 col-lg-4">
                                    <div class="card border h-100">
                                        <div class="card-body py-2 px-3">
                                            <div class="d-flex align-items-start gap-1 mb-1 flex-wrap">
                                                <span class="badge bg-secondary" style="font-size:10px;">${this.escapeHtml(t.type_name || t.type || '')}</span>
                                                ${t.priority ? `<span class="badge ${this._priorityBadgeClass(t.priority)}" style="font-size:10px;">${t.priority}</span>` : ''}
                                            </div>
                                            <div class="small fw-bold mb-1" style="line-height:1.3;">${this.escapeHtml(t.title || '')}</div>
                                            ${t.reason ? `<div class="small text-muted" style="line-height:1.2;font-size:11px;">${this.escapeHtml(t.reason)}</div>` : ''}
                                        </div>
                                    </div>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">关闭</button>
                        <button type="button" class="btn btn-success" onclick="PortraitManager.generateWithRandomTopic(${portraitId})">
                            <i class="bi bi-shuffle me-1"></i>随机选一个生成
                        </button>
                    </div>
                </div>
            </div>
        </div>`;
        
        const oldModal = document.getElementById('topicListModal');
        if (oldModal) oldModal.remove();
        
        document.body.insertAdjacentHTML('beforeend', modalHtml);
        const modal = new bootstrap.Modal(document.getElementById('topicListModal'));
        modal.show();
        
        this._topicListModalPortrait = portrait;
        
        document.getElementById('topicListModal').addEventListener('hidden.bs.modal', function () {
            this.remove();
        });
    },
    
    // 随机选一个选题生成
    generateWithRandomTopic(portraitId) {
        const portrait = this._topicListModalPortrait || this._savedPortraits.find(p => p.id === portraitId);
        if (!portrait) return;
        
        const topics = portrait.topic_library?.topics || [];
        if (topics.length === 0) {
            showToast('选题库为空', 'error');
            return;
        }
        
        const randomTopic = topics[Math.floor(Math.random() * topics.length)];
        
        // 关闭弹窗
        const modal = bootstrap.Modal.getInstance(document.getElementById('topicListModal'));
        if (modal) modal.hide();
        
        // 生成内容
        if (window._generateContentForTopic) {
            window._generateContentForTopic(randomTopic, portrait.portrait_data || portrait);
        } else {
            showToast(`将使用选题「${randomTopic.title}」生成内容`, 'info');
        }
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
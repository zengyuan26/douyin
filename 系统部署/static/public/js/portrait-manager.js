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

    // 推荐选题相关状态
    _recommendedTopics: [],           // 当前显示的5个选题
    _recommendedHistory: [],          // 已浏览过的选题ID列表
    _currentRecommendPortraitId: null, // 当前推荐弹窗对应的画像ID
    _totalTopicCount: 0,              // 选题库总数
    _selectedTopicIdx: null,          // 当前选中的选题索引

    // 精选区卡片悬停选题缓存（每个画像随机抽3条，进页面只抽一次）
    _quickTopicsCache: {},            // { portraitId: { topics: [], status: 'loading'|'done'|'empty' } }

    // ========================================================================
    // 一、初始化
    // ========================================================================

    async init() {
        console.log('[PortraitManager.init] 开始');
        await this.loadQuota();
        console.log('[PortraitManager.init] loadQuota 完成');
        await this.loadSavedPortraits();
        console.log('[PortraitManager.init] loadSavedPortraits 完成');
        await this.loadLibraryQuota();
        console.log('[PortraitManager.init] loadLibraryQuota 完成');
    },

    // 重置当前画像索引
    resetPortraitIndex() {
        this._currentPortraitIndex = 0;
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
                // 付费用户显示画像专区（横铺）- portrait-section 已移至客户画像页面
                if (this._quota && this._quota.can_save) {
                    document.getElementById('portraits-row-section').style.display = 'block';
                    // document.getElementById('portrait-section').style.display = 'block';
                }
            }
        } catch (e) {
            console.error('[PortraitManager] 加载配额失败:', e);
        }
    },

    updateQuotaDisplay() {
        // 配额展示已移除
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
                // 重置当前索引
                this._currentPortraitIndex = 0;
                console.log('[PortraitManager] 已加载画像数量:', this._savedPortraits.length);
                
                // 调试：打印每个画像的状态
                this._savedPortraits.forEach(p => {
                    const kwCount = (p.keyword_library?.categories || []).reduce((sum, cat) => sum + (cat.keywords || []).length, 0);
                    console.log(`[PortraitManager] 画像 ${p.id} ${p.portrait_name}: status=${p.generation_status}, kwCount=${kwCount}, topicCount=${p.topic_library?.topics?.length || 0}`);
                });

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

                this.renderPortraitsRow();
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
        // 先移除 loading，防止元素缺失时 loading 一直存在
        if (loading) loading.style.display = 'none';
        if (!container) {
            console.error('[PortraitManager] 未找到画像卡片容器 #portrait-cards-list');
            return;
        }

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
            // 保存当前显示的索引
            if (!this._currentPortraitIndex) {
                this._currentPortraitIndex = 0;
            }

            const total = this._savedPortraits.length;

            // 只显示当前索引的画像
            const p = this._savedPortraits[this._currentPortraitIndex];

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

            // 生成状态
            const genStatus = p.generation_status || 'pending';
            // 关键词库状态 - iPod Classic 风格
            let kwBadge = '';
            if (kwCount > 0) {
                kwBadge = `<span class="badge me-1" style="cursor:pointer; background: linear-gradient(135deg, #e8f5e9 0%, #c8e6c9 100%); color: #2e7d32; border: 1px solid #a5d6a7; box-shadow: 0 2px 6px rgba(46,125,50,0.15); font-size: 11px; padding: 4px 10px; border-radius: 12px; font-weight: 600;" onclick="event.stopPropagation(); PortraitManager.showKeywordLibraryMd(${p.id})" title="点击查看关键词库">📚 关键词库 ${kwCount} 个</span>`;
            } else if (genStatus === 'generating') {
                kwBadge = `<span class="badge me-1" style="background: linear-gradient(135deg, #fff8e1 0%, #ffecb3 100%); color: #f57f17; border: 1px solid #ffe082; font-size: 11px; padding: 4px 10px; border-radius: 12px; font-weight: 600;" id="kw-status-badge-${p.id}">📚 关键词库 <span class="spinner-border spinner-border-sm" style="width:10px;height:10px;"></span> 生成中</span>`;
            } else if (genStatus === 'failed') {
                kwBadge = `<span class="badge me-1" style="cursor:pointer; background: linear-gradient(135deg, #ffebee 0%, #ffcdd2 100%); color: #c62828; border: 1px solid #ef9a9a; font-size: 11px; padding: 4px 10px; border-radius: 12px; font-weight: 600;" id="kw-status-badge-${p.id}" onclick="event.stopPropagation(); PortraitManager.retryGenerateLibrary(${p.id})" title="点击重试">📚 关键词库 生成失败（点击重试）</span>`;
            } else {
                kwBadge = `<span class="badge me-1" style="background: #f5f5f5; color: #8e8e93; font-size: 11px; padding: 4px 10px; border-radius: 12px; font-weight: 600;" id="kw-status-badge-${p.id}">📚 关键词库 待生成</span>`;
            }
            // 选题库状态 - iPod Classic 风格
            let topicBadge = '';
            if (topicCount > 0) {
                topicBadge = `<span class="badge me-1" style="cursor:pointer; background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%); color: #1565c0; border: 1px solid #90caf9; box-shadow: 0 2px 6px rgba(21,101,192,0.15); font-size: 11px; padding: 4px 10px; border-radius: 12px; font-weight: 600;" onclick="event.stopPropagation(); PortraitManager.showTopicLibraryMd(${p.id})" title="点击查看选题库 Markdown">📋 选题库 ${topicCount} 个</span>`;
            } else if (genStatus === 'generating') {
                topicBadge = `<span class="badge me-1" style="background: linear-gradient(135deg, #fff8e1 0%, #ffecb3 100%); color: #f57f17; border: 1px solid #ffe082; font-size: 11px; padding: 4px 10px; border-radius: 12px; font-weight: 600;" id="topic-status-badge-${p.id}">📋 选题库 <span class="spinner-border spinner-border-sm" style="width:10px;height:10px;"></span> 生成中</span>`;
            } else if (genStatus === 'failed') {
                topicBadge = `<span class="badge me-1" style="cursor:pointer; background: linear-gradient(135deg, #ffebee 0%, #ffcdd2 100%); color: #c62828; border: 1px solid #ef9a9a; font-size: 11px; padding: 4px 10px; border-radius: 12px; font-weight: 600;" id="topic-status-badge-${p.id}" onclick="event.stopPropagation(); PortraitManager.retryGenerateLibrary(${p.id})" title="点击重试">📋 选题库 生成失败（点击重试）</span>`;
            } else {
                topicBadge = `<span class="badge me-1" style="background: #f5f5f5; color: #8e8e93; font-size: 11px; padding: 4px 10px; border-radius: 12px; font-weight: 600;" id="topic-status-badge-${p.id}">📋 选题库 待生成</span>`;
            }

            // 左右导航 HTML
            const navHtml = total > 1 ? `
                <div class="portrait-card-nav d-flex align-items-center justify-content-between">
                    <button class="btn-nav" onclick="PortraitManager.prevPortrait(${this._currentPortraitIndex})"
                            ${this._currentPortraitIndex === 0 ? 'disabled' : ''}
                            style="width: 40px; height: 40px; border-radius: 50%; border: 1px solid #e5e7eb; background: white; display: flex; align-items: center; justify-content: center; cursor: pointer; transition: all 0.2s; ${this._currentPortraitIndex === 0 ? 'opacity: 0.3; cursor: not-allowed;' : ''}">
                        <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor" style="color: #3c3c43;">
                            <path d="M10 12L6 8L10 4" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round"/>
                        </svg>
                    </button>
                    <div class="d-flex align-items-center gap-2">
                        <span class="badge" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; font-size: 12px; padding: 6px 12px; border-radius: 20px;">
                            ${this._currentPortraitIndex + 1} / ${total}
                        </span>
                    </div>
                    <button class="btn-nav" onclick="PortraitManager.nextPortrait(${this._currentPortraitIndex})"
                            ${this._currentPortraitIndex === total - 1 ? 'disabled' : ''}
                            style="width: 40px; height: 40px; border-radius: 50%; border: 1px solid #e5e7eb; background: white; display: flex; align-items: center; justify-content: center; cursor: pointer; transition: all 0.2s; ${this._currentPortraitIndex === total - 1 ? 'opacity: 0.3; cursor: not-allowed;' : ''}">
                        <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor" style="color: #3c3c43;">
                            <path d="M6 4L10 8L6 12" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round"/>
                        </svg>
                    </button>
                </div>
            ` : '';

            container.innerHTML = `
                ${navHtml}
                <div class="col-12">
                    <div class="portrait-card" style="cursor:default;">
                        <div class="card-body" style="position: relative; z-index: 2;">
                            <div class="d-flex align-items-center justify-content-between flex-wrap gap-3">
                                <div class="d-flex align-items-center gap-3 flex-grow-1 min-w-0">
                                    <div class="rounded-circle d-flex align-items-center justify-content-center flex-shrink-0" style="width:56px;height:56px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); box-shadow: 0 4px 12px rgba(102,126,234,0.3);">
                                        <i class="bi bi-person text-white fs-4"></i>
                                    </div>
                                    <div class="min-w-0">
                                        <div class="fw-bold" style="color: #1a1a1a; text-shadow: 0 1px 0 rgba(255,255,255,0.5); font-size: 1.1rem;" id="pm-badge-name-${p.id}">${this.escapeHtml(p.portrait_name || '用户画像')}</div>
                                        <div class="small" style="color: #8e8e93;" id="pm-badge-industry-${p.id}">${this.escapeHtml(p.industry || '')}</div>
                                        <div class="mt-2 d-flex flex-wrap gap-2" id="pm-badge-container-${p.id}">
                                            ${kwBadge}
                                            ${topicBadge}
                                        </div>
                                    </div>
                                </div>
                                <div class="d-flex align-items-center gap-2 flex-shrink-0 flex-wrap justify-content-end">
                                    <button class="btn btn-sm" style="background: linear-gradient(135deg, #34c759 0%, #28a745 100%); border: none; color: white; border-radius: 10px; font-weight: 600; box-shadow: 0 2px 8px rgba(52,199,89,0.25); padding: 0.4rem 1rem;" onclick="PortraitManager.showRecommendedTopicsModal(${p.id})" title="推荐选题">
                                        <i class="bi bi-lightbulb me-1"></i>推荐选题
                                    </button>
                                    <button class="btn btn-sm" style="background: linear-gradient(135deg, #007AFF 0%, #0056cc 100%); border: none; color: white; border-radius: 10px; font-weight: 600; box-shadow: 0 2px 8px rgba(0,122,255,0.25); padding: 0.4rem 1rem;" onclick="PortraitManager.showTopicSelectAndGenerate(${p.id})" title="生成内容">
                                        <i class="bi bi-lightning-charge me-1"></i>生成内容
                                    </button>
                                    <button class="btn btn-sm" style="background: white; border: 1px solid #e5e7eb; color: #3c3c43; border-radius: 10px; font-weight: 600; box-shadow: 0 2px 6px rgba(0,0,0,0.06); padding: 0.4rem 1rem;" onclick="PortraitManager.showPortraitDetail(${p.id})" title="查看详情">
                                        <i class="bi bi-eye me-1"></i>查看详情
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            `;

            console.log('[PortraitManager] 画像卡片渲染成功，共', total, '个画像，当前显示第', this._currentPortraitIndex + 1, '个');

            // 为所有正在生成中的画像启动轮询
            if (genStatus === 'generating') {
                this._startLibraryPolling(p.id);
            }
        } catch (e) {
            console.error('[PortraitManager] 渲染画像卡片失败:', e);
            container.innerHTML = '<div class="col-12 text-center py-4 text-danger">渲染画像卡片失败</div>';
        }
    },

    // 切换到上一张画像
    prevPortrait(currentIndex) {
        if (currentIndex > 0) {
            this._currentPortraitIndex = currentIndex - 1;
            this.renderPortraitCards();
            this.renderPortraitsRow();
        }
    },

    // 切换到下一张画像
    nextPortrait(currentIndex) {
        if (currentIndex < this._savedPortraits.length - 1) {
            this._currentPortraitIndex = currentIndex + 1;
            this.renderPortraitCards();
            this.renderPortraitsRow();
        }
    },

    // 轮询词库生成状态（最多轮询5分钟）
    _startLibraryPolling(portraitId) {
        // 防止重复轮询
        if (this._pollingTimers && this._pollingTimers[portraitId]) {
            return;
        }
        if (!this._pollingTimers) this._pollingTimers = {};

        let pollCount = 0;
        const maxPolls = 60; // 最多60次，每次5秒 = 5分钟
        const interval = 5000; // 5秒

        const poll = async () => {
            if (pollCount >= maxPolls) {
                console.warn('[PortraitManager] 词库生成轮询超时 portraitId:', portraitId);
                delete this._pollingTimers[portraitId];
                return;
            }
            pollCount++;

            try {
                const resp = await fetch(`/public/api/portraits/${portraitId}/status`, {
                    credentials: 'include'
                });
                const data = await resp.json();
                if (!data.success) {
                    delete this._pollingTimers[portraitId];
                    return;
                }

                const status = data.data.generation_status;

                if (status === 'completed' || status === 'failed') {
                    // 生成完成或失败，停止轮询
                    delete this._pollingTimers[portraitId];
                    
                    // 重新加载完整画像列表，确保包含最新生成的词库数据
                    await this.loadSavedPortraits(portraitId);

                    if (status === 'failed') {
                        const errMsg = data.data.generation_error || '未知错误';
                        showToast('词库生成失败：' + errMsg, 'error');
                    } else {
                        showToast('词库生成完成！', 'success');
                    }
                    return;
                }

                // 仍在生成中，继续轮询
                this._pollingTimers[portraitId] = setTimeout(poll, interval);

            } catch (e) {
                console.error('[PortraitManager] 轮询状态失败:', e);
                delete this._pollingTimers[portraitId];
            }
        };

        this._pollingTimers[portraitId] = setTimeout(poll, interval);
    },

    // 重新触发词库生成（手动重试）
    async retryGenerateLibrary(portraitId) {
        if (!confirm('确定要重新生成词库吗？')) return;

        try {
            const resp = await fetch(`/public/api/portraits/${portraitId}/library/generate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ library_type: 'all' })
            });
            const data = await resp.json();

            if (data.success) {
                showToast('词库重新生成已启动...', 'info');
                // 更新本地状态为 generating
                const idx = this._savedPortraits.findIndex(p => p.id === portraitId);
                if (idx >= 0) {
                    this._savedPortraits[idx].generation_status = 'generating';
                    this.renderPortraitCards();
                    this.renderPortraitsRow();
                    this._startLibraryPolling(portraitId);
                }
            } else {
                showToast(data.message || '启动生成失败', 'error');
            }
        } catch (e) {
            console.error('[PortraitManager] retryGenerateLibrary 失败:', e);
            showToast('重试失败，请稍后重试', 'error');
        }
    },

    // 直接显示选题选择弹窗（选择后生成内容）- 兼容旧版
    showTopicSelectAndGenerate(portraitId) {
        const portrait = this._savedPortraits.find(p => p.id === portraitId);
        if (!portrait) return;

        // 检查词库生成状态
        const genStatus = portrait.generation_status || 'pending';
        const topics = portrait.topic_library?.topics || [];

        if (genStatus === 'generating') {
            showToast('词库正在生成中，请稍候...', 'info');
            return;
        }
        if (genStatus === 'failed') {
            showToast('词库生成失败，请点击重试后使用', 'error');
            return;
        }
        if (topics.length === 0) {
            showToast('暂无选题库，请等待生成完成', 'warning');
            return;
        }

        // 初始化状态（与推荐选题共用）
        this._currentRecommendPortraitId = portraitId;
        this._recommendedHistory = [];
        this._selectedTopicIdx = null;
        this._totalTopicCount = topics.length;

        // 随机推荐5个选题
        const shuffled = [...topics].sort(() => Math.random() - 0.5);
        this._recommendedTopics = shuffled.slice(0, 5);

        // 更新已浏览历史（存储索引）
        shuffled.forEach((t, idx) => {
            this._recommendedHistory.push(idx);
        });

        const modalHtml = `
        <div class="modal fade" id="topicSelectModal" tabindex="-1">
            <div class="modal-dialog modal-dialog-scrollable">
                <div class="modal-content">
                    <div class="modal-header" style="background: linear-gradient(135deg, #007AFF 0%, #0056cc 100%); color: white;">
                        <h5 class="modal-title"><i class="bi bi-lightning-charge me-2"></i>选择选题生成内容</h5>
                        <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <p class="small mb-3" style="color: #8e8e93;">从选题库中随机推荐5个，选择一个后点击生成内容</p>
                        <div id="topic-select-list">
                            ${this._renderTopicSelectList()}
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn" style="background: white; border: 1px solid #e5e7eb; color: #3c3c43; border-radius: 10px; font-weight: 600;" data-bs-dismiss="modal">取消</button>
                        <button type="button" class="btn" id="btn-generate-from-select"
                                style="background: linear-gradient(135deg, #007AFF 0%, #0056cc 100%); border: none; color: white; border-radius: 10px; font-weight: 600;"
                                onclick="PortraitManager.generateFromSelectModal()"
                                disabled>
                            <i class="bi bi-lightning-charge me-1"></i>生成内容
                        </button>
                    </div>
                </div>
            </div>
        </div>`;

        const oldModal = document.getElementById('topicSelectModal');
        if (oldModal) oldModal.remove();

        document.body.insertAdjacentHTML('beforeend', modalHtml);
        const modal = new bootstrap.Modal(document.getElementById('topicSelectModal'));
        modal.show();

        document.getElementById('topicSelectModal').addEventListener('hidden.bs.modal', function () {
            this.remove();
        });
    },

    // 渲染选题选择列表（用于 showTopicSelectAndGenerate）
    _renderTopicSelectList() {
        return this._recommendedTopics.map((t, idx) => `
            <div class="topic-item ${this._selectedTopicIdx === idx ? 'selected' : ''}"
                 onclick="PortraitManager.onSelectTopicForGenerate(${idx}, 'topicSelectModal', 'btn-generate-from-select')">
                <div class="topic-radio">
                    <div class="topic-radio-inner"></div>
                </div>
                <div class="topic-content">
                    <div class="d-flex align-items-center gap-2 mb-1 flex-wrap">
                        <span class="topic-type-badge">${this.escapeHtml(t.type_name || t.type || '选题')}</span>
                        ${t.priority ? `<span class="topic-priority-badge">${t.priority}</span>` : ''}
                    </div>
                    <div class="topic-title-text">${this.escapeHtml(t.title || '')}</div>
                    ${t.reason ? `<div class="topic-reason-text">📝 ${this.escapeHtml(t.reason)}</div>` : ''}
                </div>
            </div>
        `).join('');
    },

    // 选择选题（用于生成内容弹窗）
    onSelectTopicForGenerate(idx, modalId, btnId) {
        this._selectedTopicIdx = idx;

        // 更新 UI
        document.querySelectorAll('#' + modalId + ' .topic-item').forEach((el, i) => {
            el.classList.toggle('selected', i === idx);
        });

        const generateBtn = document.getElementById(btnId);
        if (generateBtn) {
            generateBtn.disabled = false;
        }
    },

    // 从选题选择弹窗生成内容
    generateFromSelectModal() {
        if (this._selectedTopicIdx === null || this._selectedTopicIdx === undefined) {
            showToast('请先选择一个选题', 'warning');
            return;
        }

        const topic = this._recommendedTopics[this._selectedTopicIdx];
        if (!topic) return;

        // 关闭弹窗
        const modal = bootstrap.Modal.getInstance(document.getElementById('topicSelectModal'));
        if (modal) modal.hide();

        // 调用内容��成
        if (typeof this.generateContentWithTopic === 'function') {
            this.generateContentWithTopic(this._currentRecommendPortraitId, topic);
        } else {
            console.log('生成内容:', { portraitId: this._currentRecommendPortraitId, topic });
            showToast(`将使用选题「${topic.title}」生成内容`, 'info');
        }
    },

    // 显示推荐选题弹窗（重构版）
    async showRecommendedTopicsModal(portraitId) {
        console.log('[推荐选题] 打开弹窗, portraitId:', portraitId);

        const portrait = this._savedPortraits.find(p => p.id === portraitId);
        if (!portrait) {
            console.error('[推荐选题] 未找到画像:', portraitId);
            return;
        }

        // 检查词库生成状态
        const genStatus = portrait.generation_status || 'pending';
        const topics = portrait.topic_library?.topics || [];

        console.log('[推荐选题] 画像状态:', genStatus, '选题数量:', topics.length);

        if (genStatus === 'generating') {
            showToast('词库正在生成中，请稍候...', 'info');
            return;
        }
        if (genStatus === 'failed') {
            showToast('词库生成失败，请点击重试后查看', 'error');
            return;
        }
        if (topics.length === 0) {
            showToast('暂无选题库，请等待生成完成', 'warning');
            return;
        }

        // 初始化状态 - 强制重置
        this._currentRecommendPortraitId = portraitId;
        this._recommendedHistory = [];  // 重置历史
        this._viewedHashes = new Set();  // 重置哈希集合
        this._selectedTopicIdx = null;
        this._totalTopicCount = topics.length;

        console.log('[推荐选题] 总选题数:', this._totalTopicCount);

        // 加载第一批选题
        await this._loadMoreTopics();

        console.log('[推荐选题] 已加载选题:', this._recommendedTopics.length, '已浏览历史:', this._recommendedHistory);

        // 渲染弹窗
        this._renderRecommendModal();
    },

    // 从选题库加载更多选题（排除已浏览的）
    async _loadMoreTopics() {
        const portrait = this._savedPortraits.find(p => p.id === this._currentRecommendPortraitId);
        if (!portrait) {
            console.error('[加载选题] 未找到画像');
            return;
        }

        const allTopics = portrait.topic_library?.topics || [];
        console.log('[加载选题] 总选题:', allTopics.length, '已浏览:', this._recommendedHistory);

        // 初始化 _viewedHashes 如果不存在
        if (!this._viewedHashes) this._viewedHashes = new Set();

        // 过滤掉已浏览过的（用内容哈希比对）
        const available = allTopics.filter(t => {
            const hash = this._hashTopic(t);
            return !this._viewedHashes.has(hash);
        });

        console.log('[加载选题] 可用选题:', available.length);

        if (available.length === 0) {
            console.log('[加载选题] 已全部浏览，触发刷新');
            await this._refreshTopicLibrary();
            return;
        }

        const shuffled = available.sort(() => Math.random() - 0.5);
        this._recommendedTopics = shuffled.slice(0, 5);

        console.log('[加载选题] 本次加载:', this._recommendedTopics.length);

        // 用内容哈希记录已浏览
        shuffled.forEach(t => {
            this._viewedHashes.add(this._hashTopic(t));
        });

        console.log('[加载选题] 完成后已浏览总数:', this._viewedHashes.size);
    },

    // 生成选题内容哈希（用于去重）
    _hashTopic(t) {
        return `${t.content_direction || ''}|${t.content_hints || ''}|${(t.keywords || []).join(',')}|${t.priority || ''}|${t.publish_timing || ''}`;
    },

    // 刷新选题库
    async _refreshTopicLibrary() {
        showToast('选题库已全部浏览，正在刷新...', 'info');

        // 显示刷新状态
        const statusEl = document.getElementById('topic-refresh-status');
        const progressText = document.getElementById('topic-progress-text');
        const progressBar = document.getElementById('topic-progress-bar');
        if (statusEl) statusEl.style.display = 'inline';
        if (progressText) progressText.textContent = '正在刷新选题库...';
        if (progressBar) progressBar.style.width = '100%';

        const refreshBtn = document.getElementById('btn-refresh-topics');
        const generateBtn = document.getElementById('btn-generate-with-topic');
        if (refreshBtn) refreshBtn.disabled = true;
        if (generateBtn) generateBtn.disabled = true;

        try {
            // 触发词库重新生成
            const resp = await fetch(`/public/api/portraits/${this._currentRecommendPortraitId}/library/generate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ library_type: 'topic' })
            });
            const data = await resp.json();

            if (data.success) {
                // 重新加载画像数据
                await this.loadSavedPortraits(this._currentRecommendPortraitId);

                // 重置状态
                this._recommendedHistory = [];
                this._viewedHashes = new Set();
                this._selectedTopicIdx = null;

                // 重新加载选题
                const portrait = this._savedPortraits.find(p => p.id === this._currentRecommendPortraitId);
                this._totalTopicCount = portrait?.topic_library?.topics?.length || 0;

                await this._loadMoreTopics();

                // 更新弹窗内容
                this._updateRecommendModalContent();

                if (statusEl) statusEl.style.display = 'none';
                showToast('选题库已更新，共 ' + this._totalTopicCount + ' 个选题', 'success');
            } else {
                showToast(data.message || '刷新失败，请稍后重试', 'error');
                if (refreshBtn) refreshBtn.disabled = false;
                if (generateBtn) generateBtn.disabled = false;
            }
        } catch (e) {
            showToast('刷新失败，请稍后重试', 'error');
            if (refreshBtn) refreshBtn.disabled = false;
            if (generateBtn) generateBtn.disabled = false;
        }
    },

    // 渲染推荐选题弹窗
    _renderRecommendModal() {
        const viewedCount = this._viewedHashes ? this._viewedHashes.size : 0;
        const progress = this._totalTopicCount > 0
            ? (viewedCount / this._totalTopicCount) * 100
            : 0;
        const remaining = this._totalTopicCount - viewedCount;
        const isAllViewed = remaining <= 0;

        console.log('[渲染弹窗] 进度:', viewedCount + '/' + this._totalTopicCount, '选题数据:', this._recommendedTopics);

        const modalHtml = `
        <div class="modal fade" id="topicRecommendModal" tabindex="-1">
            <div class="modal-dialog modal-dialog-scrollable">
                <div class="modal-content">
                    <div class="modal-header" style="background: linear-gradient(135deg, #34c759 0%, #28a745 100%); color: white;">
                        <h5 class="modal-title"><i class="bi bi-lightbulb me-2"></i>推荐选题</h5>
                        <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <!-- 进度指示 -->
                        <div class="mb-3">
                            <div class="d-flex justify-content-between align-items-center mb-2">
                                <span id="topic-progress-text" class="small" style="color: #8e8e93;">从选题库中随机推荐，已浏览 ${viewedCount}/${this._totalTopicCount} 个</span>
                                <span id="topic-refresh-status" class="small" style="color: #34c759; display: none;">
                                    <span class="spinner-border spinner-border-sm me-1"></span>刷新中
                                </span>
                            </div>
                            <div class="topic-progress">
                                <div id="topic-progress-bar" class="topic-progress-bar" style="width: ${progress}%"></div>
                            </div>
                        </div>

                        <!-- 选题列表 -->
                        <div id="recommend-topic-list">
                            ${this._renderRecommendTopicList()}
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn" id="btn-refresh-topics"
                                style="background: white; border: 1px solid #e5e7eb; color: #3c3c43; border-radius: 10px; font-weight: 600;"
                                onclick="PortraitManager.onRefreshRecommended()"
                                ${isAllViewed ? 'disabled' : ''}>
                            <i class="bi bi-arrow-repeat me-1"></i>换一批
                            ${isAllViewed ? '<span class="small ms-1">(已全部浏览)</span>' : ''}
                        </button>
                        <button type="button" class="btn" id="btn-generate-with-topic"
                                style="background: linear-gradient(135deg, #34c759 0%, #28a745 100%); border: none; color: white; border-radius: 10px; font-weight: 600;"
                                onclick="PortraitManager.generateWithSelectedTopic()"
                                disabled>
                            <i class="bi bi-lightning-charge me-1"></i>生成内容
                        </button>
                    </div>
                </div>
            </div>
        </div>`;

        const oldModal = document.getElementById('topicRecommendModal');
        if (oldModal) oldModal.remove();

        document.body.insertAdjacentHTML('beforeend', modalHtml);
        const modal = new bootstrap.Modal(document.getElementById('topicRecommendModal'));
        modal.show();

        document.getElementById('topicRecommendModal').addEventListener('hidden.bs.modal', function () {
            this.remove();
        });
    },

    // 渲染推荐选题列表
    _renderRecommendTopicList() {
        if (this._recommendedTopics.length === 0) {
            return '<div class="text-center py-4 text-muted">暂无更多选题</div>';
        }

        return this._recommendedTopics.map((t, idx) => `
            <div class="topic-item ${this._selectedTopicIdx === idx ? 'selected' : ''}"
                 onclick="PortraitManager.onSelectTopic(${idx})">
                <div class="topic-radio">
                    <div class="topic-radio-inner"></div>
                </div>
                <div class="topic-content">
                    <div class="d-flex align-items-center gap-2 mb-1 flex-wrap">
                        <span class="topic-type-badge">${this.escapeHtml(t.type_name || t.type || '选题')}</span>
                        ${t.priority ? `<span class="topic-priority-badge">${t.priority}</span>` : ''}
                    </div>
                    <div class="topic-title-text">${this.escapeHtml(t.title || '')}</div>
                    ${t.reason ? `<div class="topic-reason-text">📝 ${this.escapeHtml(t.reason)}</div>` : ''}
                </div>
            </div>
        `).join('');
    },

    // 更新弹窗内容（不重新渲染整个弹窗）
    _updateRecommendModalContent() {
        const listContainer = document.getElementById('recommend-topic-list');
        if (listContainer) {
            listContainer.innerHTML = this._renderRecommendTopicList();
        }

        const viewedCount = this._viewedHashes ? this._viewedHashes.size : this._recommendedHistory.length;
        const progress = this._totalTopicCount > 0
            ? (viewedCount / this._totalTopicCount) * 100
            : 0;
        const remaining = this._totalTopicCount - viewedCount;

        const progressBar = document.getElementById('topic-progress-bar');
        const progressText = document.getElementById('topic-progress-text');
        if (progressBar) progressBar.style.width = `${progress}%`;
        if (progressText) {
            progressText.textContent = `从选题库中随机推荐，已浏览 ${viewedCount}/${this._totalTopicCount} 个`;
        }

        // 更新按钮状态
        const refreshBtn = document.getElementById('btn-refresh-topics');
        const generateBtn = document.getElementById('btn-generate-with-topic');

        if (refreshBtn) {
            refreshBtn.disabled = remaining <= 0;
            refreshBtn.innerHTML = remaining <= 0
                ? '<i class="bi bi-arrow-repeat me-1"></i>换一批<span class="small ms-1">(已全部浏览)</span>'
                : '<i class="bi bi-arrow-repeat me-1"></i>换一批';
        }
        if (generateBtn) {
            generateBtn.disabled = this._selectedTopicIdx === null;
        }
    },

    // 选择选题
    onSelectTopic(idx) {
        this._selectedTopicIdx = idx;

        // 更新 UI
        document.querySelectorAll('.topic-item').forEach((el, i) => {
            el.classList.toggle('selected', i === idx);
        });

        const generateBtn = document.getElementById('btn-generate-with-topic');
        if (generateBtn) {
            generateBtn.disabled = false;
        }
    },

    // 点击"换一批"
    async onRefreshRecommended() {
        const viewedCount = this._viewedHashes ? this._viewedHashes.size : this._recommendedHistory.length;
        const remaining = this._totalTopicCount - viewedCount;

        console.log('[换一批] 当前已浏览:', viewedCount, '剩余:', remaining);

        if (remaining <= 0) {
            await this._refreshTopicLibrary();
            return;
        }

        const refreshBtn = document.getElementById('btn-refresh-topics');
        if (refreshBtn) {
            refreshBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>加载中...';
            refreshBtn.disabled = true;
        }

        await this._loadMoreTopics();
        console.log('[换一批] 刷新后已浏览:', this._viewedHashes.size);
        this._updateRecommendModalContent();
    },

    // 使用选中的选题生成内容
    generateWithSelectedTopic() {
        if (this._selectedTopicIdx === null || this._selectedTopicIdx === undefined) {
            showToast('请先选择一个选题', 'warning');
            return;
        }

        const topic = this._recommendedTopics[this._selectedTopicIdx];
        if (!topic) return;

        // 关闭弹窗
        const modal = bootstrap.Modal.getInstance(document.getElementById('topicRecommendModal'));
        if (modal) modal.hide();

        // 调用内容生成（传入选题信息）
        if (typeof this.generateContentWithTopic === 'function') {
            this.generateContentWithTopic(this._currentRecommendPortraitId, topic);
        } else {
            // 备用方案：显示到控制台
            console.log('生成内容:', { portraitId: this._currentRecommendPortraitId, topic });
            showToast(`将使用选题「${topic.title}」生成内容`, 'info');
        }
    },

    // 显示画像详情弹窗（直接展示超级定位保存的画像信息）
    showPortraitDetail(portraitId) {
        const portrait = this._savedPortraits.find(p => p.id === portraitId);
        if (!portrait) return;

        const modalHtml = `
        <div class="modal fade" id="portraitDetailModal" tabindex="-1">
            <div class="modal-dialog modal-lg modal-dialog-scrollable">
                <div class="modal-content" style="border-radius: 16px; overflow: hidden; box-shadow: 0 20px 60px rgba(0,0,0,0.2);">
                    <div class="modal-header" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border: none;">
                        <h5 class="modal-title"><i class="bi bi-person-badge me-2"></i>${this.escapeHtml(portrait.portrait_name || '用户画像')}</h5>
                        <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body" style="background: #f8f9fa;">
                        ${this._renderPortraitDetailContent(portrait)}
                    </div>
                    <div class="modal-footer" style="background: white; border-top: 1px solid rgba(0,0,0,0.06);">
                        <button type="button" class="btn" style="background: white; border: 1px solid #e5e7eb; color: #3c3c43; border-radius: 10px; font-weight: 600;" data-bs-dismiss="modal">关闭</button>
                        <button type="button" class="btn btn-delete-portrait" data-portrait-id="${portrait.id}" style="background: linear-gradient(135deg, #ff3b30 0%, #d32f2f 100%); border: none; color: white; border-radius: 10px; font-weight: 600;">
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

        // 事件委托处理删除按钮，避免闭包和动态元素问题
        const deleteBtn = document.getElementById('portraitDetailModal').querySelector('.btn-delete-portrait');
        if (deleteBtn) {
            deleteBtn.addEventListener('click', () => {
                this.deletePortrait(portrait.id);
            });
        }

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
                <div class="mb-3">
                    <span class="badge" style="background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%); color: #1565c0; border: 1px solid #90caf9; font-size: 12px; padding: 6px 14px; border-radius: 14px; font-weight: 600; box-shadow: 0 2px 6px rgba(21,101,192,0.15);"><i class="bi bi-people me-1"></i>${this.escapeHtml(portrait.target_customer)}</span>
                    ${portrait.industry ? `<span class="badge" style="background: #f5f5f5; color: #8e8e93; border: 1px solid #e5e7eb; font-size: 12px; padding: 6px 14px; border-radius: 14px; font-weight: 600; margin-left: 8px;"><i class="bi bi-briefcase me-1"></i>${this.escapeHtml(portrait.industry)}</span>` : ''}
                </div>`;
        }

        // 画像名称和简介（顶层信息兜底）
        if (portrait.portrait_name) {
            html += `
                <div class="mb-3">
                    <h6 style="color: #1a1a1a; font-weight: 700; margin-bottom: 4px;">${this.escapeHtml(portrait.portrait_name)}</h6>
                    ${portrait.business_description ? `<p class="small mb-0" style="color: #8e8e93;">${this.escapeHtml(portrait.business_description)}</p>` : ''}
                </div>`;
        }

        // 人群画像列表
        if (portraits.length > 0) {
            html += `<h6 class="mb-3 mt-4" style="color: #007AFF; font-weight: 700; display: flex; align-items: center; gap: 8px;"><i class="bi bi-person-badge me-1"></i>人群画像</h6>`;
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

                // 兼容旧格式字段
                const name = p.name || p.portrait_name || '画像' + (idx + 1);
                const summary = p.portrait_summary || p.summary || '';
                const goals = p.goals || p.goal || '';
                const obstacles = p.obstacles || p.fears || '';
                const psychology = p.psychology || '';
                const contentTopics = p.content_topics || '';
                const searchKeywords = p.search_keywords || '';

                html += `
                    <div class="card mb-3 border" style="border: 2px solid ${c.border} !important; background: ${c.bg}; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.08);">
                        <div class="card-body p-3">
                            <div class="d-flex justify-content-between align-items-start mb-3">
                                <div class="d-flex flex-wrap gap-2">
                                    <span class="badge" style="background: linear-gradient(135deg, ${c.accent} 0%, ${c.border} 100%); color: white; font-size: 13px; padding: 6px 14px; border-radius: 14px; font-weight: 700; box-shadow: 0 2px 8px ${c.accent}40;">${this.escapeHtml(name)}</span>
                                    ${buyerTag ? `<span class="badge" style="background: linear-gradient(135deg, #fff8e1 0%, #ffecb3 100%); color: #f57f17; border: 1px solid #ffe082; font-size: 11px; padding: 4px 10px; border-radius: 12px; font-weight: 600; box-shadow: 0 2px 6px rgba(245,127,23,0.15);">💰 ${this.escapeHtml(buyerTag)}</span>` : ''}
                                    ${userTag ? `<span class="badge" style="background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%); color: #1565c0; border: 1px solid #90caf9; font-size: 11px; padding: 4px 10px; border-radius: 12px; font-weight: 600; box-shadow: 0 2px 6px rgba(21,101,192,0.15);">👤 ${this.escapeHtml(userTag)}</span>` : ''}
                                </div>
                            </div>`;

                // 使用者视角
                if (userProblem || userState || userImpact) {
                    html += `
                        <div style="background: white; border-radius: 12px; padding: 0.85rem; margin-bottom: 0.85rem; border-left: 4px solid #4facfe; box-shadow: 0 2px 8px rgba(0,0,0,0.05);">
                            <div class="small mb-2" style="color: #8e8e93; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em;"><i class="bi bi-person me-1"></i>使用者视角</div>
                            ${userProblem ? `<div class="mb-2"><strong>问题：</strong><span style="color: #3c3c43;">${this.escapeHtml(userProblem)}</span></div>` : ''}
                            ${userState ? `<div class="mb-2"><strong>现状：</strong><span style="color: #3c3c43;">${this.escapeHtml(userState)}</span></div>` : ''}
                            ${userImpact ? `<div><strong>影响：</strong><span style="color: #3c3c43;">${this.escapeHtml(userImpact)}</span></div>` : ''}
                        </div>`;
                }

                // 付费者视角
                if (buyerGoal || buyerObstacles || buyerPsych) {
                    html += `
                        <div style="background: white; border-radius: 12px; padding: 0.85rem; margin-bottom: 0.85rem; border-left: 4px solid #fbbf24; box-shadow: 0 2px 8px rgba(0,0,0,0.05);">
                            <div class="small mb-2" style="color: #8e8e93; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em;"><i class="bi bi-currency-dollar me-1"></i>付费者视角</div>
                            ${buyerGoal ? `<div class="mb-2"><strong>目标：</strong><span style="color: #3c3c43;">${this.escapeHtml(buyerGoal)}</span></div>` : ''}
                            ${buyerObstacles ? `<div class="mb-2"><strong>顾虑：</strong><span style="color: #3c3c43;">${this.escapeHtml(buyerObstacles)}</span></div>` : ''}
                            ${buyerPsych ? `<div><strong>心理：</strong><span style="color: #3c3c43;">${this.escapeHtml(buyerPsych)}</span></div>` : ''}
                        </div>`;
                }

                // 兼容旧格式的展示
                if (summary) {
                    html += `
                        <div style="background: white; border-radius: 12px; padding: 0.85rem; margin-bottom: 0.85rem; border-left: 4px solid #667eea; box-shadow: 0 2px 8px rgba(0,0,0,0.05);">
                            <div class="small mb-2" style="color: #8e8e93; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em;"><i class="bi bi-card-text me-1"></i>画像摘要</div>
                            <div style="color: #3c3c43;">${this.escapeHtml(summary)}</div>
                        </div>`;
                }
                if (goals) {
                    html += `
                        <div style="background: white; border-radius: 12px; padding: 0.85rem; margin-bottom: 0.85rem; border-left: 4px solid #34c759; box-shadow: 0 2px 8px rgba(0,0,0,0.05);">
                            <div class="small mb-2" style="color: #8e8e93; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em;"><i class="bi bi-bullseye me-1"></i>核心目标</div>
                            <div style="color: #3c3c43;">${this.escapeHtml(goals)}</div>
                        </div>`;
                }
                if (obstacles) {
                    html += `
                        <div style="background: white; border-radius: 12px; padding: 0.85rem; margin-bottom: 0.85rem; border-left: 4px solid #ff3b30; box-shadow: 0 2px 8px rgba(0,0,0,0.05);">
                            <div class="small mb-2" style="color: #8e8e93; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em;"><i class="bi bi-shield-exclamation me-1"></i>核心障碍</div>
                            <div style="color: #3c3c43;">${this.escapeHtml(obstacles)}</div>
                        </div>`;
                }
                if (contentTopics) {
                    html += `
                        <div style="background: white; border-radius: 12px; padding: 0.85rem; margin-bottom: 0.85rem; border-left: 4px solid #af52de; box-shadow: 0 2px 8px rgba(0,0,0,0.05);">
                            <div class="small mb-2" style="color: #8e8e93; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em;"><i class="bi bi-chat-quote me-1"></i>内容选题</div>
                            <div style="color: #3c3c43;">${this.escapeHtml(contentTopics)}</div>
                        </div>`;
                }
                if (searchKeywords) {
                    html += `
                        <div style="background: white; border-radius: 12px; padding: 0.85rem; margin-bottom: 0.85rem; border-left: 4px solid #ff9500; box-shadow: 0 2px 8px rgba(0,0,0,0.05);">
                            <div class="small mb-2" style="color: #8e8e93; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em;"><i class="bi bi-search me-1"></i>搜索关键词</div>
                            <div style="color: #3c3c43;">${this.escapeHtml(searchKeywords)}</div>
                        </div>`;
                }

                html += `</div></div>`;
            });
        } else if (!portrait.portrait_name && !portrait.target_customer && !portrait.business_description) {
            // 完全没有画像数据时给出提示
            html += `
                <div class="text-center py-4" style="color: #8e8e93;">
                    <i class="bi bi-info-circle" style="font-size: 2rem;"></i>
                    <p class="mt-2 mb-0">该画像暂无详细的画像信息</p>
                    <p class="small">画像的核心信息（人群、痛点、目标）将在下次重新生成时保存</p>
                </div>`;
        }

        // 关键词库
        if (portrait.keyword_library) {
            html += `<h6 class="mb-3 mt-4" style="color: #007AFF; font-weight: 700; display: flex; align-items: center; gap: 8px;"><i class="bi bi-key me-1"></i>关键词库</h6>`;
            const kl = portrait.keyword_library;
            if (kl.categories && kl.categories.length > 0) {
                kl.categories.forEach(cat => {
                    html += `
                        <div class="mb-3">
                            <span class="badge" style="background: linear-gradient(135deg, #f5f5f5 0%, #e8e8e8 100%); color: #3c3c43; border: 1px solid #e5e7eb; font-size: 12px; padding: 5px 12px; border-radius: 12px; font-weight: 600; box-shadow: 0 1px 4px rgba(0,0,0,0.06);">${this.escapeHtml(cat.name || '未分类')}</span>
                            <div class="mt-2 ms-2 d-flex flex-wrap gap-2">
                                ${(cat.keywords || []).map(k => `<span class="badge" style="background: linear-gradient(135deg, #f3e5f5 0%, #e1bee7 100%); color: #7b1fa2; border: 1px solid #ce93d8; font-size: 11px; padding: 4px 10px; border-radius: 10px; font-weight: 500; box-shadow: 0 1px 4px rgba(123,31,162,0.1);">${this.escapeHtml(k)}</span>`).join('')}
                            </div>
                        </div>`;
                });
            }
            if (kl.blue_ocean && kl.blue_ocean.length > 0) {
                html += `
                    <div class="mb-3">
                        <span class="badge" style="background: linear-gradient(135deg, #e8f5e9 0%, #c8e6c9 100%); color: #2e7d32; border: 1px solid #a5d6a7; font-size: 12px; padding: 5px 12px; border-radius: 12px; font-weight: 600; box-shadow: 0 1px 4px rgba(46,125,50,0.1);">蓝海关键词</span>
                        <div class="mt-2 ms-2 d-flex flex-wrap gap-2">
                            ${kl.blue_ocean.map(k => `<span class="badge" style="background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%); color: #1565c0; border: 1px solid #90caf9; font-size: 11px; padding: 4px 10px; border-radius: 10px; font-weight: 500; box-shadow: 0 1px 4px rgba(21,101,192,0.1);">${this.escapeHtml(k)}</span>`).join('')}
                        </div>
                    </div>`;
            }
        }

        // 选题库
        if (portrait.topic_library && portrait.topic_library.topics && portrait.topic_library.topics.length > 0) {
            html += `<h6 class="mb-3 mt-4" style="color: #007AFF; font-weight: 700; display: flex; align-items: center; gap: 8px;"><i class="bi bi-lightbulb me-1"></i>选题库</h6>`;
            portrait.topic_library.topics.slice(0, 10).forEach(t => {
                html += `
                    <div class="card mb-2 border" style="border-radius: 12px !important; box-shadow: 0 2px 8px rgba(0,0,0,0.06);">
                        <div class="card-body py-2 px-3">
                            <div class="d-flex justify-content-between align-items-start flex-wrap gap-2">
                                <div class="d-flex flex-wrap gap-2 align-items-center">
                                    <span class="badge" style="background: linear-gradient(135deg, #f5f5f5 0%, #e8e8e8 100%); color: #3c3c43; border: 1px solid #e5e7eb; font-size: 10px; padding: 3px 8px; border-radius: 8px; font-weight: 600;">${this.escapeHtml(t.type_name || t.type || '')}</span>
                                    ${t.priority ? `<span class="badge" style="background: linear-gradient(135deg, #ffebee 0%, #ffcdd2 100%); color: #c62828; border: 1px solid #ef9a9a; font-size: 10px; padding: 3px 8px; border-radius: 8px; font-weight: 600;">${t.priority}</span>` : ''}
                                    <strong class="small" style="color: #1a1a1a;">${this.escapeHtml(t.title || '')}</strong>
                                </div>
                            </div>
                            ${t.reason ? `<div class="small mt-1" style="color: #8e8e93;">${this.escapeHtml(t.reason)}</div>` : ''}
                        </div>
                    </div>`;
            });
            if (portrait.topic_library.topics.length > 10) {
                html += `<div class="text-center small mt-2" style="color: #8e8e93;">还有 ${portrait.topic_library.topics.length - 10} 个选题...</div>`;
            }
        }

        return html || '<p class="text-center" style="color: #8e8e93;">暂无详情</p>';
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
                this.renderPortraitCards();  // 刷新侧边栏列表
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

        // 内容方向筛选 radio
        document.querySelectorAll('input[name="topic-dir"]').forEach(radio => {
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
        const dirVal = document.querySelector('input[name="topic-dir"]:checked')?.value || 'all';
        this._renderTopicList(this._currentTopicLib, sliderVal, typeVal, dirVal);
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
            const dirVal = document.querySelector('input[name="topic-dir"]:checked')?.value || 'all';
            this._renderTopicList(lib, sliderVal, typeVal, dirVal);

            // 有数据时绑定更新按钮
            const regenBtn = document.getElementById('btn-regen-topic');
            if (regenBtn) regenBtn.onclick = () => this.generateLibrary(portraitId);
        }
    },

    _renderTopicList(lib, count, typeFilter = 'all', dirFilter = 'all') {
        const list = document.getElementById('topic-list');
        const topics = lib.topic_library?.topics || [];

        let filtered = topics;
        if (typeFilter !== 'all') {
            filtered = filtered.filter(t => (t.type_name || t.type || '') === typeFilter);
        }
        if (dirFilter !== 'all') {
            filtered = filtered.filter(t => (t.content_direction || '') === dirFilter);
        }

        const shown = filtered.slice(0, count);

        list.innerHTML = shown.length === 0
            ? `<div class="col-12 text-center py-3" style="color: #8e8e93;">暂无此类选题</div>`
            : shown.map(t => {
                const contentDir = t.content_direction || '';
                const dirClass = contentDir === '转化型' ? 'dir-convert' : contentDir === '种草型' ? 'dir-sow' : '';
                const dirIcon = contentDir === '转化型' ? '🔴' : contentDir === '种草型' ? '🟡' : '';
                const dirBadge = contentDir ? `<span class="badge" style="font-size:10px; border:1px solid; background: ${contentDir==='转化型'?'linear-gradient(135deg, #ffebee 0%, #ffcdd2 100%)':'linear-gradient(135deg, #fff8e1 0%, #ffecb3 100%)'}; color: ${contentDir==='转化型'?'#c62828':'#f57f17'}; padding: 3px 8px; border-radius: 8px; font-weight: 600; margin-left: 4px;">${dirIcon}${contentDir}</span>` : '';
                return `
                <div class="col-md-6 col-lg-4">
                    <div class="card border" style="border-radius: 12px !important; box-shadow: 0 2px 8px rgba(0,0,0,0.06);">
                        <div class="card-body py-2 px-3">
                            <div class="d-flex align-items-start gap-1 mb-2 flex-wrap">
                                <span class="badge" style="background: linear-gradient(135deg, #f5f5f5 0%, #e8e8e8 100%); color: #3c3c43; border: 1px solid #e5e7eb; font-size: 10px; padding: 3px 8px; border-radius: 8px; font-weight: 600; white-space: normal;">${this.escapeHtml(t.type_name || t.type || '')}</span>
                                ${dirBadge}
                                ${t.priority ? `<span class="badge" style="background: linear-gradient(135deg, #ffebee 0%, #ffcdd2 100%); color: #c62828; border: 1px solid #ef9a9a; font-size: 10px; padding: 3px 8px; border-radius: 8px; font-weight: 600;">${t.priority}</span>` : ''}
                            </div>
                            <div class="small fw-bold mb-2" style="line-height:1.3; color: #1a1a1a;">${this.escapeHtml(t.title || '')}</div>
                            ${t.reason ? `<div class="small" style="line-height:1.2;font-size:11px; color: #8e8e93;">${this.escapeHtml(t.reason)}</div>` : ''}
                            ${t.keywords && t.keywords.length ? `
                                <div class="mt-2 d-flex flex-wrap gap-1">
                                    ${t.keywords.slice(0,3).map(k => `<span class="badge" style="background: linear-gradient(135deg, #f3e5f5 0%, #e1bee7 100%); color: #7b1fa2; border: 1px solid #ce93d8; font-size: 10px; padding: 2px 6px; border-radius: 6px;">${this.escapeHtml(k)}</span>`).join('')}
                                </div>` : ''}
                        </div>
                    </div>
                </div>`;
            }).join('');
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
        const fromLibBadge = fromLibrary ? '<span class="badge me-1" style="background: linear-gradient(135deg, #e8f5e9 0%, #c8e6c9 100%); color: #2e7d32; border: 1px solid #a5d6a7; font-size: 10px; padding: 3px 8px; border-radius: 8px; font-weight: 600;">📚 专属库</span>' : '';

        container.innerHTML = topics.map((t, i) => `
            <div class="form-check mb-2 p-3 topic-select-item" style="cursor:pointer; border-radius: 12px; border: 2px solid #e5e7eb; background: white; transition: all 0.3s;">
                <input class="form-check-input" type="radio" name="topic-select-radio" id="topic-select-${i}" value="${i}">
                <label class="form-check-label w-100" for="topic-select-${i}" style="cursor:pointer;">
                    <div class="d-flex justify-content-between align-items-start flex-wrap gap-2">
                        <div class="d-flex flex-wrap gap-2 align-items-center">
                            <span class="badge" style="background: linear-gradient(135deg, #f5f5f5 0%, #e8e8e8 100%); color: #3c3c43; border: 1px solid #e5e7eb; font-size: 11px; padding: 4px 10px; border-radius: 10px; font-weight: 600;">${t.type_name || t.type || ''}</span>
                            <span class="badge" style="background: linear-gradient(135deg, #ffebee 0%, #ffcdd2 100%); color: #c62828; border: 1px solid #ef9a9a; font-size: 11px; padding: 4px 10px; border-radius: 10px; font-weight: 600;">${t.priority || 'P2'}</span>
                            ${fromLibBadge}
                            <strong style="color: #1a1a1a;">${this.escapeHtml(t.title || '')}</strong>
                        </div>
                    </div>
                    ${t.reason ? `<div class="small mt-2" style="color: #8e8e93;">${this.escapeHtml(t.reason)}</div>` : ''}
                    ${t.keywords && t.keywords.length ? `
                        <div class="mt-2 d-flex flex-wrap gap-1">
                            ${t.keywords.slice(0,4).map(k => `<span class="badge" style="background: linear-gradient(135deg, #f3e5f5 0%, #e1bee7 100%); color: #7b1fa2; border: 1px solid #ce93d8; font-size: 10px; padding: 3px 8px; border-radius: 8px;">${this.escapeHtml(k)}</span>`).join('')}
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

    // 增量更新单个画像的 badge（避免整页重新渲染）
    _updatePortraitBadges(portraitId) {
        const p = this._savedPortraits.find(x => x.id === portraitId);
        if (!p) return;

        const container = document.getElementById(`pm-badge-container-${portraitId}`);
        if (!container) return;

        let kwCount = 0;
        if (p.keyword_library && p.keyword_library.categories) {
            p.keyword_library.categories.forEach(cat => { kwCount += (cat.keywords || []).length; });
            if (p.keyword_library.blue_ocean) kwCount += p.keyword_library.blue_ocean.length;
        }

        let topicCount = 0;
        if (p.topic_library && p.topic_library.topics) {
            topicCount = p.topic_library.topics.length;
        }

        const genStatus = p.generation_status || 'pending';
        let kwBadge = '';
        if (kwCount > 0) {
            kwBadge = `<span class="badge me-1" style="cursor:pointer; background: linear-gradient(135deg, #e8f5e9 0%, #c8e6c9 100%); color: #2e7d32; border: 1px solid #a5d6a7; box-shadow: 0 2px 6px rgba(46,125,50,0.15); font-size: 11px; padding: 4px 10px; border-radius: 12px; font-weight: 600;" onclick="event.stopPropagation(); PortraitManager.showKeywordLibraryMd(${p.id})" title="点击查看关键词库">📚 关键词库 ${kwCount} 个</span>`;
        } else if (genStatus === 'generating') {
            kwBadge = `<span class="badge me-1" style="background: linear-gradient(135deg, #fff8e1 0%, #ffecb3 100%); color: #f57f17; border: 1px solid #ffe082; font-size: 11px; padding: 4px 10px; border-radius: 12px; font-weight: 600;" data-kw-status="generating">📚 关键词库 生成中...</span>`;
        } else if (genStatus === 'failed') {
            kwBadge = `<span class="badge me-1" style="cursor:pointer; background: linear-gradient(135deg, #ffebee 0%, #ffcdd2 100%); color: #c62828; border: 1px solid #ef9a9a; font-size: 11px; padding: 4px 10px; border-radius: 12px; font-weight: 600;" data-kw-status="failed" onclick="event.stopPropagation(); PortraitManager.retryGenerateLibrary(${p.id})">📚 关键词库 生成失败（点击重试）</span>`;
        } else {
            kwBadge = `<span class="badge me-1" style="background: #f5f5f5; color: #8e8e93; font-size: 11px; padding: 4px 10px; border-radius: 12px; font-weight: 600;" data-kw-status="pending">📚 关键词库 待生成</span>`;
        }

        let topicBadge = '';
        if (topicCount > 0) {
            topicBadge = `<span class="badge me-1" style="cursor:pointer; background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%); color: #1565c0; border: 1px solid #90caf9; box-shadow: 0 2px 6px rgba(21,101,192,0.15); font-size: 11px; padding: 4px 10px; border-radius: 12px; font-weight: 600;" onclick="event.stopPropagation(); PortraitManager.showTopicLibraryMd(${p.id})" title="点击查看选题库 Markdown">📋 选题库 ${topicCount} 个</span>`;
        } else if (genStatus === 'generating') {
            topicBadge = `<span class="badge me-1" style="background: linear-gradient(135deg, #fff8e1 0%, #ffecb3 100%); color: #f57f17; border: 1px solid #ffe082; font-size: 11px; padding: 4px 10px; border-radius: 12px; font-weight: 600;" data-topic-status="generating">📋 选题库 生成中...</span>`;
        } else if (genStatus === 'failed') {
            topicBadge = `<span class="badge me-1" style="cursor:pointer; background: linear-gradient(135deg, #ffebee 0%, #ffcdd2 100%); color: #c62828; border: 1px solid #ef9a9a; font-size: 11px; padding: 4px 10px; border-radius: 12px; font-weight: 600;" data-topic-status="failed" onclick="event.stopPropagation(); PortraitManager.retryGenerateLibrary(${p.id})">📋 选题库 生成失败（点击重试）</span>`;
        } else {
            topicBadge = `<span class="badge me-1" style="background: #f5f5f5; color: #8e8e93; font-size: 11px; padding: 4px 10px; border-radius: 12px; font-weight: 600;" data-topic-status="pending">📋 选题库 待生成</span>`;
        }

        container.innerHTML = kwBadge + ' ' + topicBadge;
    },
    
    // 轮询检查选题库生成状态（使用轻量化状态端点）
    _startTopicPolling(portraitId) {
        let attempts = 0;
        const maxAttempts = 120; // 最多120次，每次3秒 = 6分钟
        let kwReady = false;
        let topicReady = false;

        const updateStatus = () => {
            const remaining = Math.max(0, maxAttempts - attempts);
            const secondsLeft = remaining * 3;
            const minSec = secondsLeft >= 60
                ? `约${Math.ceil(secondsLeft / 60)}分钟`
                : `约${secondsLeft}秒`;
            // 更新 badge 显示进度
            const container = document.getElementById(`pm-badge-container-${portraitId}`);
            if (container) {
                const kwBadge = container.querySelector('[data-kw-status]');
                const topicBadge = container.querySelector('[data-topic-status]');
                if (kwBadge && !kwReady) {
                    kwBadge.innerHTML = `📚 关键词库 生成中(${minSec})...`;
                }
                if (topicBadge && !topicReady) {
                    topicBadge.innerHTML = `📋 选题库 生成中(${minSec})...`;
                }
            }
        };

        const poll = async () => {
            if (attempts >= maxAttempts) {
                console.log('[PortraitManager] 选题库轮询超时（6分钟）');
                const container = document.getElementById(`pm-badge-container-${portraitId}`);
                if (container) {
                    container.innerHTML = `<span class="badge bg-warning me-1">📚 关键词库 生成超时</span>` +
                        `<span class="badge bg-warning me-1">📋 选题库 生成超时</span>`;
                }
                showToast('关键词库/选题库生成超时，请在画像卡片上点击「查看详情」刷新状态', 'warning', 6000);
                return;
            }

            attempts++;
            updateStatus();

            try {
                const resp = await fetch(`/public/api/portraits/${portraitId}/status`, { credentials: 'include' });
                const result = await resp.json();

                if (result.success) {
                    const status = result.data;
                    const genStatus = status.generation_status;

                    // 如果已完成或失败，停止轮询并更新 UI
                    if (genStatus === 'completed' || genStatus === 'failed') {
                        // 更新本地数据
                        const localPortrait = this._savedPortraits.find(p => p.id === portraitId);
                        if (localPortrait) {
                            Object.assign(localPortrait, status);
                        }
                        this.renderPortraitCards();
                        this.renderPortraitsRow();

                        if (genStatus === 'failed') {
                            const errMsg = status.generation_error || '未知错误';
                            showToast('词库生成失败：' + errMsg, 'error');
                        } else {
                            showToast('关键词库和选题库生成完成！', 'success');
                        }
                        return;
                    }

                    // 关键词库
                    if (status.keyword_library && !kwReady) {
                        kwReady = true;
                        const localPortrait = this._savedPortraits.find(p => p.id === portraitId);
                        if (localPortrait) {
                            localPortrait.keyword_library = status.keyword_library;
                            localPortrait.keyword_updated_at = status.keyword_updated_at;
                        }
                    }

                    // 选题库
                    if (status.topic_library && status.topic_library.topics && status.topic_library.topics.length > 0 && !topicReady) {
                        topicReady = true;
                        const localPortrait = this._savedPortraits.find(p => p.id === portraitId);
                        if (localPortrait) {
                            localPortrait.topic_library = status.topic_library;
                            localPortrait.topic_updated_at = status.topic_updated_at;
                        }
                        // 增量更新 badge
                        this._updatePortraitBadges(portraitId);
                        showToast('关键词库和选题库生成完成！', 'success');
                        return;
                    }
                }
            } catch (e) {
                console.error('[PortraitManager] 轮询失败:', e);
            }

            // 继续轮询
            setTimeout(poll, 3000);
        };

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

    // 显示关键词库 Markdown 弹窗
    async showKeywordLibraryMd(portraitId) {
        // 显示弹窗
        const modal = new bootstrap.Modal(document.getElementById('keywordLibraryMdModal'));
        modal.show();

        // 重置状态
        document.getElementById('kw-md-loading').style.display = 'block';
        document.getElementById('kw-md-error').style.display = 'none';
        document.getElementById('kw-md-content').style.display = 'none';
        document.getElementById('kw-md-text').textContent = '';

        try {
            const resp = await fetch(`/public/api/portraits/${portraitId}/keyword-library/markdown`, {
                credentials: 'include'
            });
            const data = await resp.json();

            document.getElementById('kw-md-loading').style.display = 'none';

            if (data.success && data.data && data.data.markdown) {
                document.getElementById('kw-md-content').style.display = 'block';
                document.getElementById('kw-md-text').textContent = data.data.markdown;

                // 绑定复制按钮
                document.getElementById('btn-copy-kw-md').onclick = async () => {
                    await this._copyToClipboard(data.data.markdown, '关键词库');
                };
            } else {
                document.getElementById('kw-md-error').style.display = 'block';
                document.getElementById('kw-md-error-msg').textContent = data.message || '关键词库为空，请先生成';
            }
        } catch (e) {
            document.getElementById('kw-md-loading').style.display = 'none';
            document.getElementById('kw-md-error').style.display = 'block';
            document.getElementById('kw-md-error-msg').textContent = '加载失败：' + e.message;
        }
    },

    // 显示选题库 Markdown 弹窗
    async showTopicLibraryMd(portraitId) {
        // 显示弹窗
        const modal = new bootstrap.Modal(document.getElementById('topicLibraryMdModal'));
        modal.show();

        // 重置状态
        document.getElementById('topic-md-loading').style.display = 'block';
        document.getElementById('topic-md-error').style.display = 'none';
        document.getElementById('topic-md-content').style.display = 'none';
        document.getElementById('topic-md-text').textContent = '';

        try {
            const resp = await fetch(`/public/api/portraits/${portraitId}/topic-library/markdown`, {
                credentials: 'include'
            });
            const data = await resp.json();

            document.getElementById('topic-md-loading').style.display = 'none';

            if (data.success && data.data && data.data.markdown) {
                document.getElementById('topic-md-content').style.display = 'block';
                document.getElementById('topic-md-text').textContent = data.data.markdown;

                // 绑定复制按钮
                document.getElementById('btn-copy-topic-md').onclick = async () => {
                    await this._copyToClipboard(data.data.markdown, '选题库');
                };
            } else {
                document.getElementById('topic-md-error').style.display = 'block';
                document.getElementById('topic-md-error-msg').textContent = data.message || '选题库为空，请先生成';
            }
        } catch (e) {
            document.getElementById('topic-md-loading').style.display = 'none';
            document.getElementById('topic-md-error').style.display = 'block';
            document.getElementById('topic-md-error-msg').textContent = '加载失败：' + e.message;
        }
    },

    // 复制文本到剪贴板
    async _copyToClipboard(text, label = '') {
        try {
            await navigator.clipboard.writeText(text);
            showToast((label || '') + ' Markdown 已复制到剪贴板', 'success');
        } catch (e) {
            // 降级方案
            const textarea = document.createElement('textarea');
            textarea.value = text;
            textarea.style.position = 'fixed';
            textarea.style.opacity = '0';
            document.body.appendChild(textarea);
            textarea.select();
            try {
                document.execCommand('copy');
                showToast((label || '') + ' Markdown 已复制到剪贴板', 'success');
            } catch (e2) {
                showToast('复制失败，请手动选择文本复制', 'error');
            }
            document.body.removeChild(textarea);
        }
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
                    <div class="modal-header" style="background: linear-gradient(135deg, #34c759 0%, #28a745 100%); color: white;">
                        <h5 class="modal-title"><i class="bi bi-list-ul me-2"></i>选题库（共 ${topics.length} 个）</h5>
                        <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <div class="row g-3" id="topic-list-content">
                            ${topics.map(t => `
                                <div class="col-md-6 col-lg-4">
                                    <div class="card border h-100" style="border-radius: 12px !important; box-shadow: 0 2px 8px rgba(0,0,0,0.06);">
                                        <div class="card-body py-2 px-3">
                                            <div class="d-flex align-items-start gap-1 mb-2 flex-wrap">
                                                <span class="badge" style="background: linear-gradient(135deg, #f5f5f5 0%, #e8e8e8 100%); color: #3c3c43; border: 1px solid #e5e7eb; font-size: 10px; padding: 3px 8px; border-radius: 8px; font-weight: 600;">${this.escapeHtml(t.type_name || t.type || '')}</span>
                                                ${t.priority ? `<span class="badge" style="background: linear-gradient(135deg, #ffebee 0%, #ffcdd2 100%); color: #c62828; border: 1px solid #ef9a9a; font-size: 10px; padding: 3px 8px; border-radius: 8px; font-weight: 600;">${t.priority}</span>` : ''}
                                            </div>
                                            <div class="small fw-bold mb-1" style="line-height:1.3; color: #1a1a1a;">${this.escapeHtml(t.title || '')}</div>
                                            ${t.reason ? `<div class="small" style="line-height:1.2;font-size:11px; color: #8e8e93;">${this.escapeHtml(t.reason)}</div>` : ''}
                                        </div>
                                    </div>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">关闭</button>
                        <button type="button" class="btn" style="background: linear-gradient(135deg, #34c759 0%, #28a745 100%); border: none; color: white; border-radius: 10px; font-weight: 600;" onclick="PortraitManager.generateWithRandomTopic(${portraitId})">
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
    },

    // 画像摘要（用于横铺卡片）
    _getPortraitBrief(p) {
        const bd = p.business_description || '';
        const industry = p.industry || '';
        const parts = [];
        if (industry) parts.push(industry);
        if (bd) {
            const short = bd.length > 30 ? bd.substring(0, 30) + '…' : bd;
            parts.push(short);
        }
        return parts.join(' · ') || '暂无描述';
    },

    // ========================================================================
    // 画像横铺区（横向滚动卡片行）- 精选区风格
    // ========================================================================
    renderPortraitsRow() {
        const section = document.getElementById('portraits-row-section');
        const scroll = document.getElementById('portraits-row-scroll');
        const loading = document.getElementById('portraits-row-loading');
        // 先移除 loading，防止元素缺失时 loading 一直存在
        if (loading) loading.remove();
        if (!section || !scroll) return;

        section.style.display = this._savedPortraits.length > 0 ? 'block' : 'none';

        if (this._savedPortraits.length === 0) {
            scroll.innerHTML = '<div class="pr-empty">暂无保存的画像</div>';
            return;
        }

        const html = this._savedPortraits.map((p, i) => {
            const name = this.escapeHtml(p.portrait_name || '画像' + (i + 1));
            const brief = this._getPortraitBrief(p);
            const date = p.created_at ? new Date(p.created_at).toLocaleDateString('zh-CN') : '';
            const isActive = p.id === this._currentPortraitId;
            let topicCount = 0;
            if (p.topic_library && p.topic_library.topics) topicCount = p.topic_library.topics.length;
            const statText = topicCount > 0 ? `🎧 ${topicCount} 个选题` : '🎧 选题待生成';

            // 直接从业务描述字段获取核心业务词
            const coreBusinessText = p.business_description || '暂无核心业务词';

            return `
                <div class="pr-card${isActive ? ' selected' : ''}" data-portrait-id="${p.id}"
                     onmouseenter="PortraitManager._onCardHover(${p.id})"
                     onclick="PortraitManager.selectPortraitById(${p.id})">
                    <div class="pr-card-surface">
                        <div class="pr-card-cover">
                            <span class="pr-card-stat">${this.escapeHtml(statText)}</span>
                            <i class="bi bi-person-fill" aria-hidden="true"></i>
                        </div>
                        <div class="pr-card-footer">
                            <div class="pr-card-name">${name}</div>
                            <div class="pr-card-meta">${this.escapeHtml(brief)}</div>
                            ${date ? `<div class="pr-card-date">${this.escapeHtml(date)}</div>` : ''}
                        </div>
                    </div>
                    <div class="pr-hover-overlay">
                        <div class="pr-hover-content" id="pr-overlay-${p.id}">
                            <div class="pr-hover-core-business">${this.escapeHtml(coreBusinessText)}</div>
                        </div>
                        <button type="button" class="pr-hover-play" aria-label="进入生成" title="进入生成"
                                onclick="event.stopPropagation(); PortraitManager._onPlayClick(${p.id})">
                            <i class="bi bi-play-fill" aria-hidden="true"></i>
                        </button>
                    </div>
                </div>`;
        }).join('');

        scroll.innerHTML = html;

        // 渲染已缓存的选题（防止 hover 再次触发时闪烁）
        Object.keys(this._quickTopicsCache).forEach(pid => {
            const c = this._quickTopicsCache[pid];
            if (c.status === 'done' || c.status === 'empty') {
                this._renderHoverOverlay(parseInt(pid), c.topics, c.core_business || '');
            }
        });
    },

    _onCardHover(portraitId) {
        if (!this._quickTopicsCache[portraitId]) {
            this._quickTopicsCache[portraitId] = { topics: [], status: 'loading' };
            this._fetchQuickTopics(portraitId);
        }
    },

    _fetchQuickTopics(portraitId) {
        fetch('/public/api/portraits/' + portraitId + '/topics/quick?count=3', {
            credentials: 'include'
        })
        .then(r => r.json())
        .then(data => {
            if (data.success && data.data) {
                const topics = data.data.topics || [];
                const hasTopics = data.data.has_topics;
                const coreBusiness = data.data.core_business || '';
                this._quickTopicsCache[portraitId] = { topics, status: hasTopics ? 'done' : 'empty', core_business: coreBusiness };
                this._renderHoverOverlay(portraitId, topics, coreBusiness);
            } else {
                this._quickTopicsCache[portraitId] = { topics: [], status: 'empty', core_business: '' };
                this._renderHoverOverlay(portraitId, [], '');
            }
        })
        .catch(() => {
            this._quickTopicsCache[portraitId] = { topics: [], status: 'empty', core_business: '' };
            this._renderHoverOverlay(portraitId, [], '');
        });
    },

    _renderHoverOverlay(portraitId, topics, coreBusiness) {
        // 只更新选题列表区域，不覆盖核心业务词
        // 核心业务词在卡片渲染时已从 business_description 字段获取
        const el = document.getElementById('pr-overlay-' + portraitId);
        if (!el) return;

        // 查找或创建选题列表容器
        let topicsContainer = el.querySelector('.pr-hover-topics-container');
        if (!topicsContainer) {
            topicsContainer = document.createElement('div');
            topicsContainer.className = 'pr-hover-topics-container';
            el.appendChild(topicsContainer);
        }

        // 构建选题列表
        if (!topics || topics.length === 0) {
            topicsContainer.innerHTML = '';
        } else {
            topicsContainer.innerHTML = '<ul class="pr-hover-topics">' +
                topics.map(t => '<li class="pr-hover-topic" title="' + this.escapeHtml(t.title || '') + '">' +
                    this.escapeHtml(t.title || '') + '</li>').join('') +
                '</ul>';
        }
    },

    _onPlayClick(portraitId) {
        window.location.href = '/public/produce?portraitId=' + portraitId;
    },

    selectPortraitById(portraitId) {
        this._currentPortraitId = portraitId;
        this.renderPortraitsRow();
        // 同时更新原 accordion 区（如果存在）
        if (typeof this.renderPortraitCards === 'function') {
            this.renderPortraitCards();
        }
        // 滚动到当前卡片
        const idx = this._savedPortraits.findIndex(p => p.id === portraitId);
        if (idx >= 0) {
            const row = document.getElementById('portraits-row-scroll');
            const card = row?.querySelectorAll('.pr-card')[idx];
            card?.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
        }
    },

    confirmDeletePortrait(portraitId) {
        if (!confirm('确定要删除这个画像吗？')) return;
        this.deletePortrait(portraitId);
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
                <div class="cf-empty text-center py-5">
                    <i class="bi bi-inbox" style="font-size:3rem;color:#d1d1d6;"></i>
                    <p class="mt-3 text-muted">暂无已保存的画像</p>
                    <p class="small text-secondary">在下方超级定位流程中生成并保存画像后，可在此快速访问</p>
                </div>`;
            return;
        }

        // Cover Flow 模式：有多张画像时启用
        this._cfContainer = container;
        container.innerHTML = this._buildCoverFlowHTML();
        this._initCoverFlow();
    },

    _buildCoverFlowHTML() {
        const cards = this._savedPortraits.map((p, i) => {
            const isActive = (p.id === this._currentPortraitId) || (!this._currentPortraitId && i === 0);
            const name = this.escapeHtml(p.portrait_name || '画像' + (i + 1));
            const industry = this.escapeHtml(p.industry || '');
            const bodyHtml = this._getCoverFlowCardBody(p);
            return `
                <div class="cf-card${isActive ? ' active' : ''}" data-index="${i}" data-id="${p.id}">
                    <div class="cf-card-inner">
                        <div class="cf-header">
                            <div class="cf-icon">
                                <i class="bi bi-person-fill"></i>
                            </div>
                            <div class="cf-title-area">
                                <span class="cf-name">${name}</span>
                                ${industry ? `<span class="cf-industry">${industry}</span>` : ''}
                            </div>
                        </div>
                        <div class="cf-body">${bodyHtml}</div>
                        <div class="cf-footer">
                            <button class="cf-btn" onclick="event.stopPropagation(); PortraitManager.showRecommendedTopicsModal(${p.id})">
                                <i class="bi bi-lightbulb me-1"></i>推荐选题
                            </button>
                            <button class="cf-btn primary" onclick="event.stopPropagation(); PortraitManager.showTopicSelectAndGenerate(${p.id})">
                                <i class="bi bi-lightning-charge me-1"></i>生成内容
                            </button>
                            <button class="cf-btn" onclick="event.stopPropagation(); PortraitManager.showPortraitDetail(${p.id})">
                                <i class="bi bi-eye me-1"></i>查看详情
                            </button>
                        </div>
                    </div>
                </div>`;
        }).join('');

        return `
            <div class="cf-stage">
                <div class="cf-track">${cards}</div>
            </div>
            <div class="cf-nav">
                <button class="cf-arrow" id="cf-prev-btn" title="上一张">
                    <i class="bi bi-chevron-left"></i>
                </button>
                <span class="cf-counter" id="cf-counter">${this._cfIndex + 1} / ${this._savedPortraits.length}</span>
                <button class="cf-arrow" id="cf-next-btn" title="下一张">
                    <i class="bi bi-chevron-right"></i>
                </button>
            </div>`;
    },

    _getCoverFlowCardBody(p) {
        const genStatus = p.generation_status || 'pending';
        let kwCount = 0;
        if (p.keyword_library?.categories) {
            p.keyword_library.categories.forEach(cat => { kwCount += (cat.keywords || []).length; });
            if (p.keyword_library.blue_ocean) kwCount += p.keyword_library.blue_ocean.length;
        }
        let topicCount = 0;
        if (p.topic_library?.topics) topicCount = p.topic_library.topics.length;

        let kwBadge = '', topicBadge = '';
        if (kwCount > 0) {
            kwBadge = `<span class="cf-badge kw" onclick="event.stopPropagation(); PortraitManager.showKeywordLibraryMd(${p.id})">📚 关键词库 ${kwCount} 个</span>`;
        } else if (genStatus === 'generating') {
            kwBadge = `<span class="cf-badge generating">📚 关键词库 <span class="spinner-border spinner-border-sm" style="width:10px;height:10px;"></span> 生成中</span>`;
        } else if (genStatus === 'failed') {
            kwBadge = `<span class="cf-badge failed" onclick="event.stopPropagation(); PortraitManager.retryGenerateLibrary(${p.id})">📚 生成失败（点击重试）</span>`;
        } else {
            kwBadge = `<span class="cf-badge pending">📚 关键词库 待生成</span>`;
        }

        if (topicCount > 0) {
            topicBadge = `<span class="cf-badge topic" onclick="event.stopPropagation(); PortraitManager.showTopicLibraryMd(${p.id})">📋 选题库 ${topicCount} 个</span>`;
        } else if (genStatus === 'generating') {
            topicBadge = `<span class="cf-badge generating">📋 选题库 <span class="spinner-border spinner-border-sm" style="width:10px;height:10px;"></span> 生成中</span>`;
        } else if (genStatus === 'failed') {
            topicBadge = `<span class="cf-badge failed" onclick="event.stopPropagation(); PortraitManager.retryGenerateLibrary(${p.id})">📋 生成失败（点击重试）</span>`;
        } else {
            topicBadge = `<span class="cf-badge pending">📋 选题库 待生成</span>`;
        }

        return `<div class="cf-badges">${kwBadge}${topicBadge}</div>`;
    },

    _initCoverFlow() {
        const ci = this._savedPortraits.findIndex(p => p.id === this._currentPortraitId);
        this._cfIndex = ci >= 0 ? ci : 0;
        this._cfCardWidth = typeof window !== 'undefined' && window.matchMedia && window.matchMedia('(max-width: 768px)').matches ? 280 : 340;
        this._cfDragging = false;
        this._cfStartX = 0;
        this._cfCurrentX = 0;
        this._cfThreshold = 80;

        const stage = this._cfContainer?.querySelector('.cf-stage');
        const track = this._cfContainer?.querySelector('.cf-track');
        if (!stage || !track) return;

        // 移除旧事件监听
        if (this._cfBoundHandlers) {
            document.removeEventListener('mousemove', this._cfBoundHandlers.onMove);
            document.removeEventListener('mouseup', this._cfBoundHandlers.onEnd);
            document.removeEventListener('touchmove', this._cfBoundHandlers.onMove);
            document.removeEventListener('touchend', this._cfBoundHandlers.onEnd);
        }

        const self = this;
        const onStart = function(e) {
            self._cfDragging = true;
            self._cfStartX = e.type.includes('mouse') ? e.clientX : e.touches[0].clientX;
            self._cfCurrentX = 0;
            track.style.transition = 'none';
        };
        const onMove = function(e) {
            if (!self._cfDragging) return;
            if (e.type === 'touchmove') e.preventDefault();
            const clientX = e.type.includes('mouse') ? e.clientX : (e.touches && e.touches[0] ? e.touches[0].clientX : 0);
            self._cfCurrentX = clientX - self._cfStartX;
            self._updateCoverFlowTransform(self._cfIndex, self._cfCurrentX);
        };
        const onEnd = function() {
            if (!self._cfDragging) return;
            self._cfDragging = false;
            track.style.transition = '';
            const delta = self._cfCurrentX;
            if (delta < -self._cfThreshold && self._cfIndex < self._savedPortraits.length - 1) {
                self._cfIndex++;
            } else if (delta > self._cfThreshold && self._cfIndex > 0) {
                self._cfIndex--;
            }
            self._updateCoverFlowTransform(self._cfIndex, 0);
            self._updateCounter();
        };

        this._cfBoundHandlers = { onMove, onEnd };

        stage.addEventListener('mousedown', onStart);
        stage.addEventListener('touchstart', onStart, { passive: true });
        document.addEventListener('mousemove', onMove);
        document.addEventListener('touchmove', onMove, { passive: false });
        document.addEventListener('mouseup', onEnd);
        document.addEventListener('touchend', onEnd);

        // 左右箭头按钮
        const prevBtn = this._cfContainer?.querySelector('#cf-prev-btn');
        const nextBtn = this._cfContainer?.querySelector('#cf-next-btn');
        if (prevBtn) {
            prevBtn.addEventListener('click', () => this.cfPrev());
        }
        if (nextBtn) {
            nextBtn.addEventListener('click', () => this.cfNext());
        }

        this._updateCoverFlowTransform(this._cfIndex, 0);
    },

    _updateCoverFlowTransform(index, offset) {
        const track = this._cfContainer?.querySelector('.cf-track');
        if (!track) return;
        const cards = track.querySelectorAll('.cf-card');
        const w = this._cfCardWidth;
        cards.forEach((card, i) => {
            const pos = i - index;
            const x = pos * w + offset;
            const rotateY = pos * -25;
            const scale = i === index ? 1.08 : 0.88;
            const zIndex = 100 - Math.abs(pos);
            const opacity = Math.abs(pos) > 2 ? 0 : 1;
            /* left:50% + translateX(calc(-50%+x))：卡片以自身中心为锚点平移；勿再写 margin-left:-半宽，否则会双重左移 */
            card.style.transform = `translateX(calc(-50% + ${x}px)) rotateY(${rotateY}deg) scale(${scale})`;
            card.style.zIndex = zIndex;
            card.style.opacity = opacity;
            card.classList.toggle('active', i === index);
        });
    },

    cfPrev() {
        if (this._cfIndex > 0) {
            this._cfIndex--;
            this._updateCoverFlowTransform(this._cfIndex, 0);
            this._updateCounter();
        }
    },

    cfNext() {
        if (this._cfIndex < this._savedPortraits.length - 1) {
            this._cfIndex++;
            this._updateCoverFlowTransform(this._cfIndex, 0);
            this._updateCounter();
        }
    },

    _updateCounter() {
        const counter = this._cfContainer?.querySelector('#cf-counter');
        if (counter) {
            counter.textContent = `${this._cfIndex + 1} / ${this._savedPortraits.length}`;
        }
    },
};

// 页面初始化
document.addEventListener('DOMContentLoaded', async () => {
    if (document.body.dataset.userId) {
        await PortraitManager.init();
        PortraitManager.showOnboardingTip();
    }
});
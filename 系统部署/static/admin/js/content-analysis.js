/**
 * 内容分析 JS 模块
 *
 * 职责：
 * 1. 内容列表加载、分页、搜索
 * 2. 内容 CRUD 操作
 * 3. 内容分析触发（含队列控制）
 * 4. 批量操作
 * 5. 分析结果展示（Tab 模式）
 */

const ContentAnalysis = (function() {
    // ========== 状态管理 ==========
    let state = {
        currentAccountId: null,
        currentContentId: null,
        page: 1,
        totalPages: 1,
        searchKeyword: '',
        pageSize: 4,
        selectedIds: new Set(),
        queuePollingTimer: null
    };

    // ========== DOM 元素 ==========
    const elements = {
        list: 'contents-list',
        searchInput: 'content-search-input',
        searchBtn: 'content-search-btn',
        prevBtn: 'contents-prev-btn',
        nextBtn: 'contents-next-btn',
        pageInfo: 'contents-page-info',
        addBtn: 'add-content-btn',
        form: 'content-manual-form',
        modal: 'contentEditModal',
        modalTitle: 'content-edit-modal-title',
        titleInput: 'manual-content-title',
        typeSelect: 'manual-content-type',
        descInput: 'manual-content-desc',
        loading: 'content-loading',
        progress: 'analysis-progress',
        resultEmpty: 'result-empty',
        resultContent: 'result-content',
        batchToolbar: 'content-batch-toolbar',
        batchAnalyzeBtn: 'batch-analyze-btn',
        batchDeleteBtn: 'batch-delete-btn',
        queueStatus: 'content-queue-status'
    };

    // ========== API 接口 ==========
    const API = {
        base: '/api/knowledge',

        list(accountId, page, pageSize, search) {
            let url = `${this.base}/contents?account_id=${accountId}&page=${page}&page_size=${pageSize}`;
            if (search) url += `&search=${encodeURIComponent(search)}`;
            return fetch(url).then(r => r.json());
        },

        get(contentId) {
            return fetch(`${this.base}/contents/${contentId}`).then(r => r.json());
        },

        create(data) {
            return fetch(`${this.base}/contents`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            }).then(r => r.json());
        },

        update(contentId, data) {
            return fetch(`${this.base}/contents/${contentId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            }).then(r => r.json());
        },

        delete(contentId) {
            return fetch(`${this.base}/contents/${contentId}`, { method: 'DELETE' }).then(r => r.json());
        },

        analyze(contentId) {
            return fetch(`${this.base}/contents/${contentId}/analyze`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({})
            }).then(r => r.json());
        },

        analyzeDimension(contentId, dimension) {
            return fetch(`${this.base}/contents/${contentId}/analyze-dimension`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ dimension })
            }).then(r => r.json());
        },

        getQueueStatus() {
            return fetch(`${this.base}/contents/queue-status`).then(r => r.json());
        },

        batchAnalyze(contentIds) {
            return fetch(`${this.base}/contents/batch-analyze`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ content_ids: contentIds })
            }).then(r => r.json());
        },

        batchDelete(contentIds) {
            return fetch(`${this.base}/contents/batch-delete`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ content_ids: contentIds })
            }).then(r => r.json());
        }
    };

    // ========== 工具函数 ==========
    function escapeHtml(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    function showLoading(message = '处理中...') {
        const el = document.getElementById(elements.loading);
        const progress = document.getElementById(elements.progress);
        if (el) el.classList.remove('d-none');
        if (progress) progress.textContent = message;
    }

    function hideLoading() {
        const el = document.getElementById(elements.loading);
        if (el) el.classList.add('d-none');
    }

    function syncGlobalContentId() {
        if (typeof window.__syncDismantleContentId === 'function') {
            window.__syncDismantleContentId(state.currentContentId);
        }
    }

    function getContentModalEl() {
        return document.getElementById(elements.modal);
    }

    function showContentModal() {
        const modalEl = getContentModalEl();
        if (!modalEl || typeof bootstrap === 'undefined') return;
        bootstrap.Modal.getOrCreateInstance(modalEl).show();
    }

    function hideContentModal() {
        const modalEl = getContentModalEl();
        if (!modalEl || typeof bootstrap === 'undefined') return;
        bootstrap.Modal.getInstance(modalEl)?.hide();
    }

    function setModalTitle(text) {
        const el = document.getElementById(elements.modalTitle);
        if (el) el.textContent = text;
    }

    function fillFormFromContent(c) {
        document.getElementById(elements.titleInput).value = c.title || '';
        document.getElementById(elements.typeSelect).value = c.content_type || 'video';
        document.getElementById(elements.descInput).value = c.content_data?.description || '';
    }

    // ========== 维度元信息 ==========
    const DIM_META = {
        'title':        { name: '标题',   icon: 'bi-card-heading' },
        'cover':        { name: '封面',   icon: 'bi-image' },
        'topic':        { name: '选题',   icon: 'bi-lightbulb' },
        'content':      { name: '内容',   icon: 'bi-text-paragraph' },
        'ending':       { name: '结尾',   icon: 'bi-flag' },
        'tags':         { name: '标签',   icon: 'bi-tags' },
        'psychology':   { name: '心理',   icon: 'bi-brain' },
        'commercial':   { name: '商业',   icon: 'bi-currency-dollar' },
        'why_popular':  { name: '爆款',   icon: 'bi-fire' },
        'character':    { name: '人物',   icon: 'bi-person' },
        'content_form': { name: '形式',   icon: 'bi-layout-text-window-reverse' },
        'interaction':  { name: '互动',   icon: 'bi-hand-thumbs-up' },
        'hook':         { name: '开头',   icon: 'bi-play-circle' },
        'emotion':      { name: '情绪',   icon: 'bi-emoji-smile' },
        'rhythm':       { name: '节奏',   icon: 'bi-graph-up' },
    };

    function getDimMeta(code) {
        if (window.analysisDimensionsCache) {
            const d = window.analysisDimensionsCache.find(x => x.code === code);
            if (d) return { name: d.name || code, icon: d.icon || 'bi-check-circle' };
        }
        return DIM_META[code] || { name: code, icon: 'bi-check-circle' };
    }

    // ========== 列表渲染 ==========
    function renderList(contents) {
        const listEl = document.getElementById(elements.list);
        if (!listEl) return;

        const typeNames = { 'video': '视频', 'image_text': '图文', 'plain_text': '长文' };
        const typeColors = { 'video': 'text-danger', 'image_text': 'text-primary', 'plain_text': 'text-success' };

        if (contents.length === 0) {
            listEl.innerHTML = '<div class="text-center text-muted py-4">暂无内容，点击上方「+」新增</div>';
            return;
        }

        listEl.innerHTML = contents.map(c => {
        const typeColor = typeColors[c.content_type] || 'text-secondary';
        const typeName = typeNames[c.content_type] || c.content_type || '未知';
        const hasAnalysis = c.analysis_result && Object.keys(c.analysis_result).length > 0;
        const isSelected = state.currentContentId === c.id;
        const isChecked = state.selectedIds.has(c.id);

            return `
                <div class="card mb-2 ${isSelected ? 'border-primary' : ''}"
                     onclick="ContentAnalysis.selectContent(${c.id})" style="cursor:pointer;">
                    <div class="card-body py-2 px-2">
                        <div class="d-flex justify-content-between align-items-start">
                            <div class="d-flex align-items-center overflow-hidden">
                                <input type="checkbox" class="form-check-input me-2" style="cursor:pointer"
                                    ${isChecked ? 'checked' : ''}
                                    onclick="event.stopPropagation(); ContentAnalysis.toggleSelect(${c.id})">
                                <div class="overflow-hidden">
                                    <div class="small fw-medium text-truncate" style="max-width:320px">
                                        <span class="${typeColor} fw-bold">${typeName}</span>
                                        <span class="text-dark">${escapeHtml(c.title || '无标题')}</span>
                                        ${hasAnalysis ? '<i class="bi bi-check-circle-fill text-success ms-1" title="已分析"></i>' : ''}
                                    </div>
                                </div>
                            </div>
                            <div onclick="event.stopPropagation()" class="d-flex gap-1">
                                <button class="btn btn-sm btn-outline-success" onclick="ContentAnalysis.analyzeContent(${c.id})" title="分析">
                                    <i class="bi bi-lightning-charge"></i>
                                </button>
                                <button class="btn btn-sm btn-outline-primary" onclick="ContentAnalysis.editContent(${c.id})" title="编辑">
                                    <i class="bi bi-pencil"></i>
                                </button>
                                <button class="btn btn-sm btn-outline-danger" onclick="ContentAnalysis.deleteContent(${c.id})" title="删除">
                                    <i class="bi bi-trash"></i>
                                </button>
                            </div>
                        </div>
                    </div>
                </div>`;
        }).join('');

        updateBatchToolbar();
    }

    function updatePagination() {
        const prevBtn = document.getElementById(elements.prevBtn);
        const nextBtn = document.getElementById(elements.nextBtn);
        const pageInfo = document.getElementById(elements.pageInfo);
        if (prevBtn) prevBtn.disabled = state.page <= 1;
        if (nextBtn) nextBtn.disabled = state.page >= state.totalPages;
        if (pageInfo) pageInfo.textContent = `${state.page}/${state.totalPages}`;
    }

    // ========== 核心功能 ==========
    async function loadList() {
        if (!state.currentAccountId) {
            const listEl = document.getElementById(elements.list);
            if (listEl) listEl.innerHTML = '<div class="text-center text-muted py-4">请先选择账号</div>';
            return;
        }

        const listEl = document.getElementById(elements.list);
        if (listEl) listEl.innerHTML = '<div class="text-center text-muted py-4">加载中...</div>';

        try {
            const data = await API.list(state.currentAccountId, state.page, state.pageSize, state.searchKeyword);
            if (data.code === 200) {
                const contents = data.data?.items || [];
                state.totalPages = data.data?.total_pages || 1;
                renderList(contents);
                updatePagination();
            } else {
                if (listEl) listEl.innerHTML = `<div class="text-center text-danger py-4">加载失败</div>`;
            }
        } catch (e) {
            console.error('加载内容列表失败:', e);
        }
    }

    async function selectContent(contentId) {
        state.currentContentId = contentId;
        syncGlobalContentId();
        loadList();

        try {
            const data = await API.get(contentId);
            if (data.code === 200 && data.data) {
                if (data.data.analysis_result && Object.keys(data.data.analysis_result).length > 0) {
                    displayAnalysisResult(data.data.analysis_result);
                } else {
                    clearAnalysisResult();
                }
            }
        } catch (e) {
            console.error('获取内容详情失败:', e);
        }
    }

    async function editContent(contentId) {
        try {
            const data = await API.get(contentId);
            if (data.code !== 200 || !data.data) {
                alert(data.message || '获取内容失败');
                return;
            }
            const c = data.data;
            state.currentContentId = contentId;
            syncGlobalContentId();
            fillFormFromContent(c);
            setModalTitle('编辑内容');
            showContentModal();
            loadList();

            if (c.analysis_result && Object.keys(c.analysis_result).length > 0) {
                displayAnalysisResult(c.analysis_result);
            } else {
                clearAnalysisResult();
            }
        } catch (e) {
            console.error('获取内容详情失败:', e);
            alert('获取内容失败');
        }
    }

    async function deleteContent(contentId) {
        if (!confirm('确定删除该内容吗？')) return;
        try {
            const data = await API.delete(contentId);
            if (data.code === 200) {
                if (state.currentContentId === contentId) {
                    state.currentContentId = null;
                    syncGlobalContentId();
                    clearForm();
                    clearAnalysisResult();
                }
                loadList();
            } else {
                alert(data.message || '删除失败');
            }
        } catch (e) {
            alert('删除失败: ' + e.message);
        }
    }

    async function analyzeContent(contentId) {
        const targetId = contentId || state.currentContentId;
        if (!targetId) {
            alert('请先选择要分析的内容');
            return;
        }

        showLoading('正在分析内容...');
        try {
            const data = await API.analyze(targetId);
            if (data.code === 200) {
                state.currentContentId = targetId;
                syncGlobalContentId();
                loadList();
                await selectContent(targetId);
            } else {
                alert(data.message || '分析失败');
            }
        } catch (e) {
            alert('分析失败: ' + e.message);
        } finally {
            hideLoading();
        }
    }

    // ========== 分析结果展示（Tab 模式） ==========
    let _currentContentResult = null;
    let _activeDimTab = null;

    function displayAnalysisResult(result) {
        _currentContentResult = result;

        document.getElementById(elements.resultEmpty)?.classList.add('d-none');
        document.getElementById('result-content')?.classList.remove('d-none');
        document.getElementById('account-reanalyze-container')?.classList.add('d-none');
        document.getElementById('content-dim-tabs')?.classList.remove('d-none');

        // 收集有结果的维度
        const dims = [];
        const srcs = [result?.analyses, result?.modules_results].filter(Boolean);
        for (const src of srcs) {
            for (const [k, v] of Object.entries(src)) {
                if (!dims.includes(k) && v && typeof v === 'object') dims.push(k);
            }
        }
        if (dims.length === 0 && result && typeof result === 'object') {
            for (const [k, v] of Object.entries(result)) {
                if (!dims.includes(k) && v && (v.content || typeof v === 'string')) dims.push(k);
            }
        }

        renderContentDimTabs(dims);

        if (dims[0]) {
            _activeDimTab = dims[0];
            renderDimContent(dims[0]);
        } else {
            const scrollEl = document.getElementById('analysis-results-scroll');
            if (scrollEl) {
                scrollEl.innerHTML = `
                    <div class="text-center text-muted py-5">
                        <i class="bi bi-hourglass fs-2 d-block mb-2"></i>
                        <div>内容已保存，正在自动分析中...</div>
                        <div class="small mt-1">完成后将自动展示分析结果</div>
                    </div>`;
            }
        }
    }

    function renderContentDimTabs(dims) {
        const tabsEl = document.getElementById('content-dim-tabs');
        if (!tabsEl) return;

        if (dims.length === 0) {
            tabsEl.innerHTML = '<ul class="nav nav-underline small"><li class="nav-item"><span class="nav-link text-muted">暂无分析结果</span></li></ul>';
            return;
        }

        tabsEl.innerHTML = '<ul class="nav nav-underline small" role="tablist"></ul>';
        const ul = tabsEl.querySelector('ul');

        dims.forEach(dim => {
            const { name, icon } = getDimMeta(dim);
            const active = dim === _activeDimTab ? ' active' : '';
            ul.innerHTML += `
                <li class="nav-item" role="presentation">
                    <button class="nav-link${active}" role="tab"
                        data-bs-toggle="tab"
                        data-bs-target="#dim-tab-${dim}"
                        aria-controls="dim-tab-${dim}"
                        onclick="ContentAnalysis.switchDimTab('${dim}')">
                        <i class="${icon} me-1"></i>${name}
                    </button>
                </li>`;
        });
    }

    function renderDimContent(dim) {
        const scrollEl = document.getElementById('analysis-results-scroll');
        if (!scrollEl) return;

        const data = (_currentContentResult?.analyses?.[dim])
                  || (_currentContentResult?.modules_results?.[dim])
                  || null;
        const { name, icon } = getDimMeta(dim);
        const content = data?.content || (data && typeof data === 'string' ? data : null);
        const hasResult = !!content;

        scrollEl.innerHTML = `
            <div class="tab-content" id="dim-tab-${dim}">
                <div class="d-flex justify-content-between align-items-center mb-3">
                    <h6 class="mb-0"><i class="${icon} me-2 text-success"></i>${name}</h6>
                    <button class="btn btn-sm btn-outline-success"
                        onclick="ContentAnalysis.analyzeDimension('${dim}')">
                        <i class="bi bi-lightning-charge me-1"></i>重新分析
                    </button>
                </div>
                ${hasResult
                    ? `<div class="p-3 bg-light rounded">
                         <pre class="mb-0" style="white-space:pre-wrap;word-break:break-all;">${escapeHtml(content)}</pre>
                       </div>`
                    : `<div class="text-center text-muted py-4">
                         <div>该维度暂无分析结果</div>
                         <button class="btn btn-sm btn-success mt-2"
                             onclick="ContentAnalysis.analyzeDimension('${dim}')">
                             <i class="bi bi-lightning-charge me-1"></i>立即分析
                         </button>
                       </div>`
                }
            </div>`;
    }

    function clearAnalysisResult() {
        _currentContentResult = null;
        _activeDimTab = null;

        document.getElementById(elements.resultEmpty)?.classList.remove('d-none');
        document.getElementById('result-content')?.classList.add('d-none');
        document.getElementById('account-reanalyze-container')?.classList.remove('d-none');
        document.getElementById('content-dim-tabs')?.classList.add('d-none');
        document.getElementById('analysis-results-scroll').innerHTML = '';
    }

    async function analyzeDimension(dim) {
        if (!state.currentContentId) {
            alert('请先选择要分析的内容');
            return;
        }

        const btn = event?.target?.closest('button');
        const orig = btn?.innerHTML;
        if (btn) { btn.disabled = true; btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>分析中...'; }

        try {
            const data = await API.analyzeDimension(state.currentContentId, dim);
            if (data.code === 200) {
                if (!_currentContentResult) _currentContentResult = {};
                if (!_currentContentResult.analyses) _currentContentResult.analyses = {};
                _currentContentResult.analyses[dim] = data.data?.[dim];

                const existingDims = Object.keys(_currentContentResult.analyses || {});
                renderContentDimTabs(existingDims);
                renderDimContent(dim);
                loadList();
            } else {
                alert(data.message || '分析失败');
            }
        } catch (e) {
            alert('分析失败: ' + e.message);
        } finally {
            if (btn) { btn.disabled = false; btn.innerHTML = orig; }
        }
    }

    function switchDimTab(dim) {
        _activeDimTab = dim;
        renderDimContent(dim);
    }

    // ========== 表单操作 ==========
    function clearForm() {
        const form = document.getElementById(elements.form);
        if (form) form.reset();
        state.currentContentId = null;
        syncGlobalContentId();
    }

    async function persistContentFromForm() {
        const title = document.getElementById(elements.titleInput)?.value.trim();
        const contentType = document.getElementById(elements.typeSelect)?.value;
        const description = document.getElementById(elements.descInput)?.value.trim();

        if (!title) { alert('请输入内容标题'); return { ok: false }; }
        if (!state.currentAccountId) { alert('请先选择账号'); return { ok: false }; }

        const contentData = { description };
        const wasUpdate = !!state.currentContentId;

        try {
            let data;
            if (state.currentContentId) {
                data = await API.update(state.currentContentId, {
                    title, account_id: state.currentAccountId,
                    content_type: contentType, content_data: contentData
                });
            } else {
                data = await API.create({
                    title, account_id: state.currentAccountId,
                    content_url: '', content_type: contentType,
                    source_type: 'manual', content_data: contentData
                });
            }

            if (data.code === 200) {
                if (!state.currentContentId && data.data?.id) {
                    state.currentContentId = data.data.id;
                }
                syncGlobalContentId();
                return { ok: true, wasUpdate };
            }
            alert(data.message || '保存失败');
            return { ok: false };
        } catch (e) {
            alert('保存失败: ' + e.message);
            return { ok: false };
        }
    }

    async function saveContent(e) {
        e.preventDefault();

        const r = await persistContentFromForm();
        if (!r.ok) return;

        hideContentModal();
        loadList();
        await selectContent(state.currentContentId);
        // 保存成功后自动触发内容分析（异步）
        await analyzeContent(state.currentContentId);
    }

    // ========== 批量操作 ==========
    function toggleSelect(contentId) {
        if (state.selectedIds.has(contentId)) {
            state.selectedIds.delete(contentId);
        } else {
            state.selectedIds.add(contentId);
        }
        updateBatchToolbar();
    }

    function updateBatchToolbar() {
        const toolbar = document.getElementById(elements.batchToolbar);
        const count = state.selectedIds.size;
        if (toolbar) {
            if (count > 0) {
                toolbar.classList.remove('d-none');
                toolbar.querySelector('.selected-count').textContent = count;
            } else {
                toolbar.classList.add('d-none');
            }
        }
    }

    async function batchAnalyze() {
        const ids = Array.from(state.selectedIds);
        if (ids.length === 0) { alert('请先选择要分析的内容'); return; }
        if (!confirm(`确定要分析选中的 ${ids.length} 条内容吗？`)) return;

        try {
            showLoading('正在加入分析队列...');
            const data = await API.batchAnalyze(ids);
            if (data.code === 200) {
                state.selectedIds.clear();
                loadList();
                updateBatchToolbar();
                const msg = [];
                if (data.data.queued.length > 0) msg.push(`已加入 ${data.data.queued.length} 条`);
                if (data.data.skipped.length > 0) msg.push(`跳过 ${data.data.skipped.length} 条`);
                alert(msg.join('，'));
            } else {
                alert(data.message || '批量分析失败');
            }
        } catch (e) {
            alert('批量分析失败: ' + e.message);
        } finally {
            hideLoading();
        }
        startQueuePolling();
    }

    async function batchDelete() {
        const ids = Array.from(state.selectedIds);
        if (ids.length === 0) { alert('请先选择要删除的内容'); return; }
        if (!confirm(`确定要删除选中的 ${ids.length} 条内容吗？此操作不可恢复！`)) return;

        try {
            const data = await API.batchDelete(ids);
            if (data.code === 200) {
                if (state.currentContentId != null && ids.some(i => Number(i) === Number(state.currentContentId))) {
                    state.currentContentId = null;
                    syncGlobalContentId();
                    clearAnalysisResult();
                }
                state.selectedIds.clear();
                loadList();
                updateBatchToolbar();
                const msg = [];
                if (data.data.deleted.length > 0) msg.push(`已删除 ${data.data.deleted.length} 条`);
                if (data.data.skipped.length > 0) msg.push(`跳过 ${data.data.skipped.length} 条`);
                alert(msg.join('，'));
            } else {
                alert(data.message || '批量删除失败');
            }
        } catch (e) {
            alert('批量删除失败: ' + e.message);
        }
    }

    // ========== 队列状态 ==========
    function startQueuePolling() {
        if (state.queuePollingTimer) clearInterval(state.queuePollingTimer);

        updateQueueStatus();
        state.queuePollingTimer = setInterval(async () => {
            await updateQueueStatus();
            const data = await API.getQueueStatus();
            if (data.code === 200) {
                const { running_count, queued_count } = data.data.content_queue;
                if (running_count === 0 && queued_count === 0) {
                    clearInterval(state.queuePollingTimer);
                    state.queuePollingTimer = null;
                    setTimeout(() => {
                        loadList();
                        alert('所有内容分析完成！');
                    }, 1000);
                }
            }
        }, 3000);
    }

    async function updateQueueStatus() {
        const statusEl = document.getElementById(elements.queueStatus);
        if (!statusEl) return;
        try {
            const data = await API.getQueueStatus();
            if (data.code === 200) {
                const { running_count, queued_count } = data.data.content_queue;
                if (running_count > 0 || queued_count > 0) {
                    statusEl.innerHTML = `<div class="d-flex align-items-center gap-2"><span class="spinner-border spinner-border-sm text-success" role="status"></span><span class="small">分析中: ${running_count} | 排队: ${queued_count}</span></div>`;
                    statusEl.classList.remove('d-none');
                } else {
                    statusEl.classList.add('d-none');
                }
            }
        } catch (e) { console.error('获取队列状态失败:', e); }
    }

    // ========== 事件绑定 ==========
    function bindEvents() {
        document.getElementById(elements.prevBtn)?.addEventListener('click', () => {
            if (state.page > 1) { state.page--; loadList(); }
        });
        document.getElementById(elements.nextBtn)?.addEventListener('click', () => {
            if (state.page < state.totalPages) { state.page++; loadList(); }
        });
        document.getElementById(elements.searchBtn)?.addEventListener('click', () => {
            state.searchKeyword = document.getElementById(elements.searchInput)?.value.trim() || '';
            state.page = 1; loadList();
        });
        document.getElementById(elements.searchInput)?.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                state.searchKeyword = e.target.value.trim();
                state.page = 1; loadList();
            }
        });
        document.getElementById(elements.addBtn)?.addEventListener('click', () => {
            clearForm();
            clearAnalysisResult();
            setModalTitle('新增内容');
            showContentModal();
        });
        document.getElementById(elements.form)?.addEventListener('submit', saveContent);
        document.getElementById(elements.batchAnalyzeBtn)?.addEventListener('click', batchAnalyze);
        document.getElementById(elements.batchDeleteBtn)?.addEventListener('click', batchDelete);
    }

    // ========== 公开接口 ==========
    return {
        init() { bindEvents(); },

        setAccount(accountId) {
            state.currentAccountId = accountId;
            state.currentContentId = null;
            syncGlobalContentId();
            state.page = 1;
            state.searchKeyword = '';
            state.selectedIds.clear();
            loadList();
        },

        loadList,
        selectContent,
        editContent,
        deleteContent,
        analyzeContent,
        analyzeDimension,
        switchDimTab,
        clearForm,
        clearAnalysisResult,
        toggleSelect,
        batchAnalyze,
        batchDelete,
        saveContent,
        displayAnalysisResult,

        getState() { return { ...state }; }
    };
})();

document.addEventListener('DOMContentLoaded', function() {
    ContentAnalysis.init();
});

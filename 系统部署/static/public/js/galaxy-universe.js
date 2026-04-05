/**
 * 内容星球 - 星系内容宇宙
 * 星系可视化模块
 *
 * 数据模型映射：
 * - 星系 = 当前登录用户（按 user_id 完全隔离）
 * - 恒星 = 用户画像（saved_portraits）
 * - 行星 = 核心问题（persona_user_problems）
 * - 卫星 = 历史生成的选题/内容（public_generations）
 *
 * 交互：
 * - 点击恒星 → 弹出画像详情面板（portrait_summary 五要素）
 * - 点击行星 → 弹出问题详情面板（症状/场景/严重程度）
 * - 点击卫星 → 弹出历史记录面板（累计次数 + 历史列表）
 * - 支持拖拽/缩放/高亮
 */

const GalaxyUniverse = {
    chart: null,
    nodes: [],
    links: [],
    stats: {},

    // 颜色配置
    colors: {
        star: {
            border: '#FFD700',
            bg: 'rgba(255, 215, 0, 0.15)',
            glow: 'rgba(255, 215, 0, 0.5)',
            text: '#FFD700',
            symbol: 'circle',
        },
        planet: {
            border: '#007AFF',
            bg: 'rgba(0, 122, 255, 0.12)',
            glow: 'rgba(0, 122, 255, 0.4)',
            text: '#007AFF',
            symbol: 'diamond',
        },
        satellite: {
            border: '#8E8E93',
            bg: 'rgba(142, 142, 147, 0.08)',
            glow: 'rgba(142, 142, 147, 0.2)',
            text: '#8E8E93',
            symbol: 'roundRect',
        },
        linkWeak: '#3A3A3C',
        linkStrong: '#FFD700',
    },

    // 当前激活的节点
    activeNodeId: null,

    // ========================================================================
    // 一、初始化
    // ========================================================================

    async init() {
        this.bindEvents();
        await this.loadGalaxyData();
    },

    // ========================================================================
    // 二、事件绑定
    // ========================================================================

    bindEvents() {
        // 刷新
        document.getElementById('btn-refresh')?.addEventListener('click', () => this.loadGalaxyData());

        // 回填按钮
        document.getElementById('btn-backfill')?.addEventListener('click', () => this.runBackfill());

        // 缩放控制
        document.getElementById('btn-zoom-in')?.addEventListener('click', () => this.zoomChart(1.2));
        document.getElementById('btn-zoom-out')?.addEventListener('click', () => this.zoomChart(0.8));
        document.getElementById('btn-zoom-reset')?.addEventListener('click', () => this.resetZoom());

        // 面板关闭
        document.getElementById('panel-close')?.addEventListener('click', () => this.closePanel());
        document.getElementById('panel-overlay')?.addEventListener('click', () => this.closePanel());

        // 内容详情弹窗
        document.getElementById('btn-close-modal')?.addEventListener('click', () => this.closeContentModal());
        document.getElementById('btn-copy-content')?.addEventListener('click', () => this.copyContent());

        // ESC 关闭
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.closePanel();
                this.closeContentModal();
            }
        });
    },

    // ========================================================================
    // 三、数据加载
    // ========================================================================

    async loadGalaxyData() {
        const loading = document.getElementById('loading-state');
        const empty = document.getElementById('empty-state');
        const chartDom = document.getElementById('galaxy-chart');
        const legend = document.getElementById('chart-legend');
        const zoomControls = document.getElementById('zoom-controls');

        if (loading) loading.style.display = 'flex';
        if (empty) empty.style.display = 'none';
        if (chartDom) chartDom.style.display = 'none';
        if (legend) legend.style.display = 'none';
        if (zoomControls) zoomControls.style.display = 'none';

        try {
            const resp = await fetch('/public/api/galaxy/graph', {
                credentials: 'same-origin',
            });
            const data = await resp.json();

            if (!data.success) {
                this.showError(data.message || '加载失败');
                return;
            }

            this.nodes = data.data.nodes || [];
            this.links = data.data.links || [];
            this.stats = data.data.stats || {};

            // 更新统计
            this.updateStats();

            if (loading) loading.style.display = 'none';

            if (this.nodes.length === 0) {
                if (empty) empty.style.display = 'block';
                return;
            }

            if (chartDom) chartDom.style.display = 'block';
            if (legend) legend.style.display = 'flex';
            if (zoomControls) zoomControls.style.display = 'flex';

            this.renderChart();
        } catch (err) {
            console.error('[Galaxy] 加载失败:', err);
            this.showError('网络错误，请刷新重试');
            if (loading) loading.style.display = 'none';
        }
    },

    showError(msg) {
        console.error('[Galaxy]', msg);
    },

    updateStats() {
        const s = this.stats;
        const el = (id, val) => {
            const el = document.getElementById(id);
            if (el) el.textContent = val ?? 0;
        };
        el('stat-stars', s.total_portraits);
        el('stat-planets', s.total_problems);
        el('stat-satellites', s.total_satellites);
        el('stat-generations', s.total_generations);
    },

    // ========================================================================
    // 四、图表渲染（ECharts Graph GL 力导向图）
    // ========================================================================

    renderChart() {
        const chartDom = document.getElementById('galaxy-chart');
        if (!chartDom) return;

        if (this.chart) {
            this.chart.dispose();
        }

        this.chart = echarts.init(chartDom, null, { renderer: 'canvas' });

        // 节点映射
        const nodeMap = {};
        this.nodes.forEach(n => { nodeMap[n.id] = n; });

        // 预处理节点
        const echartsNodes = this.nodes.map(node => this.buildNode(node));

        // 预处理连线
        const echartsLinks = this.links.map(link => this.buildLink(link, nodeMap));

        const option = {
            backgroundColor: 'transparent',
            animation: true,
            animationDuration: 1500,
            animationEasing: 'cubicOut',

            // 坐标系
            xAxis: { show: false, type: 'value', min: 0, max: 100 },
            yAxis: { show: false, type: 'value', min: 0, max: 100 },

            series: [{
                type: 'graph',
                layout: 'force',
                draggable: true,
                roam: true,          // 开启鼠标缩放和平移
                focusNodeAdjacency: true,  // 高亮相邻节点

                // 力导向配置
                force: {
                    repulsion: {
                        // 根据节点类型设置斥力
                        恒星: 800,
                        行星: 400,
                        卫星: 200,
                    }[node => node.data?.type] || 300,
                    edgeLength: [60, 200],
                    gravity: 0.1,
                    layoutAnimation: true,
                },

                // 节点
                data: echartsNodes,

                // 连线
                edges: echartsLinks,

                // 标签
                label: {
                    show: true,
                    position: 'bottom',
                    distance: 6,
                    formatter: '{b}',
                    fontSize: 11,
                    color: 'rgba(255,255,255,0.75)',
                    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
                    lineHeight: 14,
                    backgroundColor: 'rgba(0,0,0,0.4)',
                    borderRadius: 4,
                    padding: [3, 6, 3, 6],
                },

                // 连线样式
                lineStyle: {
                    width: 'scale',
                    curveness: 0.2,
                    opacity: 0.6,
                },

                // 节点大小
                symbolSize: (val, params) => {
                    return this.calcNodeSize(params.data);
                },

                // 节点样式
                itemStyle: {
                    borderWidth: 2,
                    borderRadius: 8,
                    shadowBlur: 20,
                    shadowColor: 'transparent',
                },

                emphasis: {
                    focus: 'adjacency',
                    scale: true,
                    itemStyle: {
                        shadowBlur: 30,
                        borderWidth: 3,
                    },
                    label: {
                        show: true,
                        fontSize: 12,
                        fontWeight: 600,
                    },
                },

                cursor: 'pointer',
            }],
        };

        // 动态设置斥力（根据恒星数量调整）
        const starCount = this.nodes.filter(n => n.type === 'star').length;
        const repulsionBase = starCount > 3 ? 600 : 900;
        option.series[0].force.repulsion = repulsionBase;

        this.chart.setOption(option);

        // 节点点击事件
        this.chart.on('click', (params) => {
            if (params.dataType === 'node') {
                this.handleNodeClick(params.data);
            }
        });

        // 鼠标悬停事件
        this.chart.on('mouseover', (params) => {
            if (params.dataType === 'node') {
                this.showTooltip(params.event.event);
            } else {
                this.hideTooltip();
            }
        });

        this.chart.on('mouseout', () => {
            this.hideTooltip();
        });

        // 窗口大小变化时重绘
        window.addEventListener('resize', () => {
            this.chart?.resize();
        });
    },

    /**
     * 构建 ECharts 节点配置
     */
    buildNode(node) {
        const type = node.type;
        let symbol = 'circle';
        let size = 30;
        let color = this.colors.satellite;
        let borderColor = '#8E8E93';
        let itemStyle = {};

        if (type === 'star') {
            symbol = 'circle';
            size = Math.max(50, 70 - Math.min(50, 30)); // 画像数量少则恒星大
            color = this.colors.star;
            borderColor = '#FFD700';
            itemStyle = {
                color: {
                    type: 'radial',
                    x: 0.3, y: 0.3, r: 0.7,
                    colorStops: [
                        { offset: 0, color: '#FFF8DC' },
                        { offset: 0.5, color: '#FFD700' },
                        { offset: 1, color: '#DAA520' },
                    ],
                },
                borderColor: '#FFD700',
                borderWidth: 3,
                shadowBlur: 25,
                shadowColor: 'rgba(255, 215, 0, 0.7)',
            };
        } else if (type === 'planet') {
            symbol = 'diamond';
            size = 35;
            color = this.colors.planet;
            borderColor = '#007AFF';
            const genCount = node.generation_count || 1;
            const planetOpacity = Math.min(1, 0.5 + genCount * 0.05);
            itemStyle = {
                color: `rgba(0, 122, 255, ${planetOpacity * 0.3})`,
                borderColor: '#007AFF',
                borderWidth: 2,
                shadowBlur: 15,
                shadowColor: `rgba(0, 122, 255, ${planetOpacity * 0.5})`,
            };
        } else {
            symbol = 'roundRect';
            size = 18;
            color = this.colors.satellite;
            borderColor = '#636366';
            itemStyle = {
                color: 'rgba(142, 142, 147, 0.1)',
                borderColor: '#636366',
                borderWidth: 1,
            };
        }

        return {
            id: node.id,
            name: this.truncateName(node.name || node.title || '未命名', 12),
            value: [10 + Math.random() * 80, 10 + Math.random() * 80], // 初始随机位置
            nodeData: node,
            symbol,
            symbolSize: size,
            itemStyle,
            label: {
                show: true,
                position: 'bottom',
                distance: 4,
                formatter: '{b}',
                fontSize: 10,
                color: type === 'star' ? '#FFD700' : (type === 'planet' ? 'rgba(255,255,255,0.8)' : 'rgba(255,255,255,0.5)'),
                backgroundColor: type === 'planet' ? 'rgba(0,0,0,0.5)' : 'transparent',
                borderRadius: 3,
                padding: type === 'planet' ? [2, 5, 2, 5] : 0,
            },
        };
    },

    /**
     * 构建 ECharts 连线配置
     */
    buildLink(link, nodeMap) {
        const weight = link.weight || 1;
        // 连线粗细：1-5px
        const lineWidth = Math.min(5, Math.max(0.5, Math.log2(weight + 1) * 1.5));

        // 连线颜色：生成次数越多越亮
        const intensity = Math.min(1, 0.2 + weight * 0.08);
        const isStarLink = nodeMap[link.source]?.type === 'star' || nodeMap[link.target]?.type === 'star';
        const color = isStarLink
            ? `rgba(255, 215, 0, ${intensity})`
            : `rgba(100, 149, 237, ${intensity})`;

        return {
            source: link.source,
            target: link.target,
            lineStyle: {
                width: lineWidth,
                color,
                curveness: 0.1 + Math.random() * 0.15,
                opacity: Math.min(0.9, 0.3 + intensity * 0.4),
                type: 'solid',
            },
            linkData: link,
        };
    },

    /**
     * 计算节点大小
     */
    calcNodeSize(params) {
        const node = params.data?.nodeData;
        if (!node) return 30;

        if (node.type === 'star') {
            return 55;
        } else if (node.type === 'planet') {
            const gen = node.generation_count || 1;
            return Math.min(50, 30 + gen * 2);
        } else {
            return 22;
        }
    },

    /**
     * 截断名称
     */
    truncateName(name, maxLen) {
        if (!name) return '未命名';
        if (name.length <= maxLen) return name;
        return name.slice(0, maxLen - 1) + '...';
    },

    // ========================================================================
    // 五、节点点击交互
    // ========================================================================

    async handleNodeClick(nodeData) {
        const node = nodeData.nodeData || nodeData;
        const type = node.type;

        this.activeNodeId = node.id;

        // 高亮当前节点
        this.chart.dispatchAction({
            type: 'focusNodeAdjacency',
            dataIndex: this.nodes.findIndex(n => n.id === node.id),
        });

        if (type === 'star') {
            await this.showStarPanel(node.portrait_id);
        } else if (type === 'planet') {
            if (node.is_inferred) {
                // 推断行星：用 industry 统计信息显示
                this.showInferredPlanetPanel(node);
            } else {
                await this.showPlanetPanel(node.problem_id);
            }
        } else if (type === 'satellite') {
            await this.showSatellitePanel(node.generation_id);
        }

        this.openPanel();
    },

    // ========================================================================
    // 六、恒星（画像）详情面板
    // ========================================================================

    async showStarPanel(portraitId) {
        try {
            const resp = await fetch(`/public/api/galaxy/node/star/${portraitId}`, {
                credentials: 'same-origin',
            });
            const data = await resp.json();
            if (!data.success) return;

            const d = data.data;

            // 提取 portrait_summary 五要素
            const summary = d.portrait_summary || '';
            const buyerPersp = d.buyer_perspective || {};
            const userPersp = d.user_perspective || {};
            const psychology = d.psychology || '';

            // 五要素字段
            const identityTags = d.identity_tags || {};
            const buyerTag = identityTags.buyer || '';
            const userTag = identityTags.user || '';
            const scenes = Array.isArray(d.scenes) ? d.scenes : [];
            const painPoints = Array.isArray(d.pain_points) ? d.pain_points : [];

            let bodyHTML = '';

            // 画像摘要
            if (summary) {
                bodyHTML += `
                    <div class="panel-section">
                        <div class="panel-section-title">&#30011;&#20687;&#25688;&#35201;</div>
                        <div class="panel-summary-text">${this.escapeHtml(summary)}</div>
                    </div>`;
            }

            // 五要素卡片
            bodyHTML += `<div class="panel-section"><div class="panel-section-title">&#20116;&#35201;&#32032;&#35299;&#26512;</div>`;

            if (buyerTag) {
                bodyHTML += `
                    <div class="element-card">
                        <div class="element-card-label">&#36523;&#20221;&#26631;&#31614;</div>
                        <div class="element-card-value">${this.escapeHtml(buyerTag)}</div>
                    </div>`;
            }
            if (userTag) {
                bodyHTML += `
                    <div class="element-card">
                        <div class="element-card-label">&#29992;&#25143;&#36523;&#20221;</div>
                        <div class="element-card-value">${this.escapeHtml(userTag)}</div>
                    </div>`;
            }
            if (summary) {
                // 从 summary 解析五要素
                bodyHTML += `
                    <div class="element-card">
                        <div class="element-card-label">&#26684;&#24335;&#35299;&#26512;</div>
                        <div class="element-card-value" style="font-size:0.78rem;color:var(--apple-gray);">
                            &#36523;&#20221; + &#38382;&#39064;/&#30151;&#29366; + &#24819;&#36716;&#21464; + &#21463;&#38480;&#20110;&#22256;&#22659; + &#28145;&#23618;&#38656;&#27714;
                        </div>
                    </div>`;
            }

            // 深层心理
            if (psychology) {
                bodyHTML += `
                    <div class="element-card" style="background:linear-gradient(135deg,rgba(255,215,0,0.08),rgba(255,165,0,0.04));border:1px solid rgba(255,215,0,0.2);">
                        <div class="element-card-label" style="color:#B8860B;">&#28145;&#23618;&#24515;&#29702;</div>
                        <div class="element-card-value">${this.escapeHtml(psychology)}</div>
                    </div>`;
            }

            // 使用场景
            if (scenes.length > 0) {
                bodyHTML += `
                    <div class="element-card">
                        <div class="element-card-label">&#20351;&#29992;&#22330;&#26223;</div>
                        <div class="panel-tags">${scenes.map(s => `<span class="panel-tag star">${this.escapeHtml(s)}</span>`).join('')}</div>
                    </div>`;
            }

            // 核心痛点
            if (painPoints.length > 0) {
                bodyHTML += `
                    <div class="element-card">
                        <div class="element-card-label">&#26680;&#24515;&#30131;&#28857;</div>
                        <div class="panel-tags">${painPoints.slice(0, 5).map(p => `<span class="panel-tag planet">${this.escapeHtml(p)}</span>`).join('')}</div>
                    </div>`;
            }

            bodyHTML += `</div>`;

            // 基本信息
            bodyHTML += `
                <div class="panel-section">
                    <div class="panel-section-title">&#22522;&#26412;&#20449;&#24687;</div>
                    <div class="panel-field">
                        <span class="panel-field-label">&#34892;&#19994;</span>
                        <span class="panel-field-value">${this.escapeHtml(d.industry || '&#26410;&#22635;&#20889;')}</span>
                    </div>
                    <div class="panel-field">
                        <span class="panel-field-label">&#30446;&#26631;&#23458;&#25143;</span>
                        <span class="panel-field-value">${this.escapeHtml(d.target_customer || '&#26410;&#22635;&#20889;')}</span>
                    </div>
                    <div class="panel-field">
                        <span class="panel-field-label">&#29983;&#25104;&#29305;&#25968;</span>
                        <span class="panel-field-value" style="color:var(--apple-blue);font-weight:600;">${d.generation_count || 0} &#27425;</span>
                    </div>
                    <div class="panel-field">
                        <span class="panel-field-label">&#21019;&#24314;&#26102;&#38388;</span>
                        <span class="panel-field-value">${d.created_at || '&#26410;&#30693;'}</span>
                    </div>
                </div>`;

            this.setPanel({
                type: 'star',
                iconText: '&#11088;',
                iconClass: 'star',
                title: d.name || '未命名画像',
                subtitle: `<span class="badge" style="background:rgba(255,215,0,0.15);color:#B8860B;">&#26085;&#26143;</span> ${this.escapeHtml(d.industry || '')}`,
                body: bodyHTML,
            });

        } catch (err) {
            console.error('[Galaxy] 加载画像详情失败:', err);
        }
    },

    // ========================================================================
    // 七、行星（核心问题）详情面板
    // ========================================================================

    async showPlanetPanel(problemId) {
        try {
            const resp = await fetch(`/public/api/galaxy/node/planet/${problemId}`, {
                credentials: 'same-origin',
            });
            const data = await resp.json();
            if (!data.success) return;

            const d = data.data;

            // 严重程度样式
            const severityMap = { '高': 'severity-h', '中': 'severity-m', '低': 'severity-l' };
            const sevClass = severityMap[d.severity] || 'severity-m';

            let bodyHTML = '';

            // 核心描述
            if (d.description) {
                bodyHTML += `
                    <div class="panel-section">
                        <div class="panel-section-title">&#38382;&#39064;&#25551;&#36848;</div>
                        <div class="panel-summary-text">${this.escapeHtml(d.description)}</div>
                    </div>`;
            }

            // 详细信息
            bodyHTML += `
                <div class="panel-section">
                    <div class="panel-section-title">&#38382;&#39064;&#20869;&#23481;</div>`;

            if (d.specific_symptoms) {
                bodyHTML += `
                    <div class="element-card">
                        <div class="element-card-label">&#20855;&#20307;&#30151;&#29366;</div>
                        <div class="element-card-value">${this.escapeHtml(d.specific_symptoms)}</div>
                    </div>`;
            }
            if (d.trigger_scenario) {
                bodyHTML += `
                    <div class="element-card">
                        <div class="element-card-label">&#35373;&#21457;&#22330;&#26223;</div>
                        <div class="element-card-value">${this.escapeHtml(d.trigger_scenario)}</div>
                    </div>`;
            }
            if (d.user_awareness) {
                bodyHTML += `
                    <div class="panel-field">
                        <span class="panel-field-label">&#29992;&#25143;&#24863;&#30693;</span>
                        <span class="panel-field-value">${this.escapeHtml(d.user_awareness)}</span>
                    </div>`;
            }

            bodyHTML += `</div>`;

            // 归属画像
            if (d.related_portraits && d.related_portraits.length > 0) {
                bodyHTML += `
                    <div class="panel-section">
                        <div class="panel-section-title">&#24402;&#23646;&#30011;&#20687;</div>
                        <div style="display:flex;flex-wrap:wrap;gap:6px;">
                            ${d.related_portraits.map(p => `
                                <span class="related-portrait-chip">
                                    <i class="bi bi-person-fill" style="font-size:0.7rem;"></i>
                                    ${this.escapeHtml(p.name)}
                                </span>
                            `).join('')}
                        </div>
                    </div>`;
            }

            // 生成统计
            bodyHTML += `
                <div class="panel-section">
                    <div class="panel-section-title">&#32467;&#26500;&#29305;&#25968;</div>
                    <div class="panel-count-highlight">
                        <div class="panel-count-num">${d.generation_count || 0}</div>
                        <div class="panel-count-label">
                            &#28145;&#20851;&#20869;&#23481;&#29983;&#25104;<br>
                            <span style="font-size:0.7rem;color:var(--apple-gray);">&#21333;&#27425;&#28857;&#20987;&#26597;&#30475;&#20855;&#20307;</span>
                        </div>
                    </div>
                </div>`;

            // 标签
            const tags = [];
            if (d.severity) tags.push(`<span class="panel-tag ${sevClass}">${d.severity}&#20005;&#37325;&#24230;</span>`);
            if (d.user_awareness) tags.push(`<span class="panel-tag">${this.escapeHtml(d.user_awareness)}</span>`);

            this.setPanel({
                type: 'planet',
                iconText: '&#9679;',
                iconClass: 'planet',
                title: d.name || '未命名问题',
                subtitle: tags.join(' ') + ` <span style="color:var(--apple-gray);font-size:0.7rem;">${d.created_at || ''}</span>`,
                body: bodyHTML,
            });

        } catch (err) {
            console.error('[Galaxy] 加载问题详情失败:', err);
        }
    },

    /**
     * 显示推断行星面板（无真实 problem_id）
     */
    showInferredPlanetPanel(node) {
        const genCount = node.generation_count || 0;

        const bodyHTML = `
            <div class="panel-section">
                <div class="panel-section-title">&#25551;&#35848;</div>
                <div class="panel-summary-text">
                    &#36825;&#26159;&#30001;&#21382;&#21490;&#29983;&#25104;&#35760;&#24405;&#25551;&#25509;&#30340;&#8220;&#34394;&#25311;&#34892;&#26143;&#8221;&#65292;&#20027;&#35201;&#26469;&#28304;&#20110;&#24744;&#30340;&#34892;&#19994;&#21644;&#30446;&#26631;&#23458;&#25143;&#26631;&#31614;&#12290;
                </div>
            </div>
            <div class="panel-section">
                <div class="panel-section-title">&#28145;&#20851;&#20869;&#23481;</div>
                <div class="panel-field">
                    <span class="panel-field-label">&#34892;&#19994;</span>
                    <span class="panel-field-value">${this.escapeHtml(node.name.split('·')[0] || '&#36890;&#29992;')}</span>
                </div>
                <div class="panel-field">
                    <span class="panel-field-label">&#30446;&#26631;&#23458;&#25143;</span>
                    <span class="panel-field-value">${this.escapeHtml(node.name.split('·')[1] || '&#36890;&#29992;&#29992;&#25143;')}</span>
                </div>
                <div class="panel-field">
                    <span class="panel-field-label">&#25551;&#25509;&#26426;&#25484;</span>
                    <span class="panel-field-value" style="font-size:0.78rem;color:var(--apple-gray);">&#30001;&#35813;&#34892;&#19994;+&#30446;&#26631;&#23458;&#25143;&#27169;&#31946;&#21305;&#37197;&#25512;&#26041;</span>
                </div>
            </div>
            <div class="panel-section">
                <div class="panel-section-title">&#28145;&#20851;&#32467;&#26500;</div>
                <div class="panel-count-highlight">
                    <div class="panel-count-num" style="color:var(--apple-green);">${genCount}</div>
                    <div class="panel-count-label">
                        &#35813;&#32452;&#21512;&#30340;&#20869;&#23481;&#29983;&#25104;&#27425;&#25968;<br>
                        <span style="font-size:0.7rem;color:var(--apple-gray);">&#36816;&#34892;&#22238;&#22635;&#21518;&#23558;&#33258;&#21160;&#20851;&#32852;</span>
                    </div>
                </div>
            </div>
            <div class="panel-section">
                <div class="panel-section-title" style="color:var(--apple-orange);">&#25551;&#25509;&#25551;&#21521;</div>
                <div style="font-size:0.8rem;color:var(--apple-gray);line-height:1.6;padding:10px;background:var(--apple-gray6);border-radius:8px;">
                    &#36816;&#34892;&#8220;&#22238;&#22635;&#20851;&#32852;&#8221;&#21151;&#33021;&#21518;&#65292;&#31995;&#32479;&#23558;&#33258;&#21160;&#23558;&#36825;&#20123;&#35760;&#24405;&#20851;&#32852;&#21040;&#30456;&#24212;&#30340;&#30011;&#20687;&#65292;&#24182;&#23558;&#28145;&#23618;&#20869;&#23481;&#24314;&#31435;&#29305;&#23450;&#30340;&#34892;&#26144;&#20851;&#31995;&#12290;
                </div>
            </div>
        `;

        this.setPanel({
            type: 'planet',
            iconText: '&#9679;',
            iconClass: 'planet',
            title: node.name || '推断行星',
            subtitle: `<span class="panel-tag severity-m">&#31995;&#32479;&#25551;&#25509;</span>`,
            body: bodyHTML,
        });
    },

    // ========================================================================
    // 八、卫星（选题/内容）详情面板
    // ========================================================================

    async showSatellitePanel(generationId) {
        try {
            const resp = await fetch(`/public/api/galaxy/node/satellite/${generationId}`, {
                credentials: 'same-origin',
            });
            const data = await resp.json();
            if (!data.success) return;

            const d = data.data;
            const titles = d.titles || [];
            const history = d.history || [];
            const totalCount = d.total_count || 0;

            let bodyHTML = '';

            // 标题列表
            if (titles.length > 0) {
                bodyHTML += `
                    <div class="panel-section">
                        <div class="panel-section-title">&#26631;&#39064;&#26041;&#26696;</div>
                        <div class="panel-history-list">
                            ${titles.slice(0, 5).map((t, i) => `
                                <div class="panel-history-item ${i === 0 ? 'is-current' : ''}">
                                    <div class="panel-history-title">${this.escapeHtml(t)}</div>
                                    ${i === 0 ? '<span style="font-size:0.65rem;color:var(--apple-blue);">&#24402;&#23646;&#24403;&#21069;</span>' : ''}
                                </div>
                            `).join('')}
                        </div>
                    </div>`;
            }

            // 累计次数（高亮）
            bodyHTML += `
                <div class="panel-section">
                    <div class="panel-section-title">&#28145;&#20851;&#32467;&#26500;</div>
                    <div class="panel-count-highlight">
                        <div class="panel-count-num" style="color:var(--apple-green);">${totalCount}</div>
                        <div class="panel-count-label">
                            &#35813;&#38382;&#39064;&#19979;&#30340;&#32034;&#26377;&#20869;&#23481;&#25968;<br>
                            <span style="font-size:0.7rem;color:var(--apple-gray);">&#28857;&#20987;&#26597;&#30475;&#20855;&#20307;</span>
                        </div>
                    </div>
                </div>`;

            // 历史记录列表
            if (history.length > 0) {
                bodyHTML += `
                    <div class="panel-section">
                        <div class="panel-section-title">&#21382;&#21490;&#35760;&#24405; &#65288;&#20849;${history.length}&#26465;&#65289;</div>
                        <div class="panel-history-list">
                            ${history.slice(0, 20).map((rec, i) => `
                                <div class="panel-history-item" onclick="GalaxyUniverse.showContentDetail(${rec.generation_id}, '${this.escapeHtmlAttr(rec.title)}', '${this.escapeHtmlAttr(rec.content_snippet)}', \`${this.escapeHtmlAttr(rec.content || '')}\`, '${this.escapeHtmlAttr(rec.created_at)}')">
                                    <div class="panel-history-title">${this.escapeHtml(rec.title || `&#20869;&#23481; #${rec.generation_id}`)}</div>
                                    <div class="panel-history-time">
                                        <i class="bi bi-clock" style="font-size:0.65rem;"></i>
                                        ${rec.created_at || ''}
                                    </div>
                                </div>
                            `).join('')}
                        </div>
                    </div>`;
            }

            // 基本信息
            bodyHTML += `
                <div class="panel-section">
                    <div class="panel-section-title">&#20869;&#23481;&#20449;&#24687;</div>
                    <div class="panel-field">
                        <span class="panel-field-label">&#34892;&#19994;</span>
                        <span class="panel-field-value">${this.escapeHtml(d.industry || '&#26410;&#22635;&#20889;')}</span>
                    </div>
                    <div class="panel-field">
                        <span class="panel-field-label">&#30446;&#26631;&#23458;&#25143;</span>
                        <span class="panel-field-value">${this.escapeHtml(d.target_customer || '&#26410;&#22635;&#20889;')}</span>
                    </div>
                    <div class="panel-field">
                        <span class="panel-field-label">&#29983;&#25104;&#26102;&#38388;</span>
                        <span class="panel-field-value">${d.created_at || '&#26410;&#30693;'}</span>
                    </div>
                    <div class="panel-field">
                        <span class="panel-field-label">&#28040;&#32791;Tokens</span>
                        <span class="panel-field-value">${d.used_tokens || 0}</span>
                    </div>
                </div>`;

            this.setPanel({
                type: 'satellite',
                iconText: '&#9711;',
                iconClass: 'satellite',
                title: titles[0] || `内容 #${generationId}`,
                subtitle: `<span class="badge" style="background:var(--apple-gray6);color:var(--apple-gray);font-size:0.65rem;">&#20986;&#29616;&#26102;&#38388;: ${d.created_at || ''}</span>`,
                body: bodyHTML,
            });

        } catch (err) {
            console.error('[Galaxy] 加载内容详情失败:', err);
        }
    },

    // ========================================================================
    // 九、内容详情弹窗
    // ========================================================================

    showContentDetail(genId, title, snippet, fullContent, createdAt) {
        const overlay = document.getElementById('content-modal-overlay');
        const titleEl = document.getElementById('modal-title');
        const metaEl = document.getElementById('modal-meta');
        const bodyEl = document.getElementById('modal-body');

        if (!overlay) return;

        if (titleEl) titleEl.textContent = title || `内容 #${genId}`;
        if (metaEl) metaEl.textContent = createdAt || '';
        if (bodyEl) bodyEl.textContent = fullContent || snippet || '暂无内容';

        // 存储当前内容供复制使用
        this._currentContent = fullContent || snippet || '';

        overlay.classList.add('is-visible');
    },

    closeContentModal() {
        const overlay = document.getElementById('content-modal-overlay');
        if (overlay) overlay.classList.remove('is-visible');
    },

    async copyContent() {
        const content = this._currentContent;
        if (!content) return;
        try {
            await navigator.clipboard.writeText(content);
            const btn = document.getElementById('btn-copy-content');
            if (btn) {
                const orig = btn.innerHTML;
                btn.innerHTML = '<i class="bi bi-check"></i> 已复制';
                setTimeout(() => { btn.innerHTML = orig; }, 2000);
            }
        } catch (err) {
            console.error('[Galaxy] 复制失败:', err);
        }
    },

    // ========================================================================
    // 十、面板控制
    // ========================================================================

    setPanel({ type, iconText, iconClass, title, subtitle, body }) {
        const panel = document.getElementById('galaxy-panel');
        const iconEl = document.getElementById('panel-icon');
        const iconTextEl = document.getElementById('panel-icon-text');
        const titleEl = document.getElementById('panel-title');
        const subtitleEl = document.getElementById('panel-subtitle');
        const bodyEl = document.getElementById('panel-body');

        if (panel) panel.className = `galaxy-panel ${type === 'star' ? 'star-theme' : ''}`;
        if (iconEl) {
            iconEl.className = `panel-header-icon ${iconClass}`;
            if (iconTextEl) iconTextEl.innerHTML = iconText;
        }
        if (titleEl) titleEl.textContent = title;
        if (subtitleEl) subtitleEl.innerHTML = subtitle;
        if (bodyEl) bodyEl.innerHTML = body;
    },

    openPanel() {
        document.getElementById('panel-overlay')?.classList.add('is-visible');
        document.getElementById('galaxy-panel')?.classList.add('is-visible');
    },

    closePanel() {
        document.getElementById('panel-overlay')?.classList.remove('is-visible');
        document.getElementById('galaxy-panel')?.classList.remove('is-visible');

        // 取消节点高亮
        if (this.chart) {
            this.chart.dispatchAction({ type: 'downplay' });
        }
        this.activeNodeId = null;
    },

    // ========================================================================
    // 十一、缩放控制
    // ========================================================================

    zoomChart(ratio) {
        if (!this.chart) return;
        const option = this.chart.getOption();
        const currentZoom = option.series[0].zoom || 1;
        const newZoom = Math.min(3, Math.max(0.2, currentZoom * ratio));
        this.chart.setOption({
            series: [{ zoom: newZoom }],
        });
    },

    resetZoom() {
        if (!this.chart) return;
        this.chart.setOption({
            series: [{ zoom: 1 }],
        });
        this.chart.dispatchAction({ type: 'restore' });
    },

    // ========================================================================
    // 十二、工具提示
    // ========================================================================

    showTooltip(event) {
        const tooltip = document.getElementById('galaxy-tooltip');
        if (!tooltip) return;

        const node = event.target?.data?.nodeData;
        if (!node) {
            this.hideTooltip();
            return;
        }

        const typeLabel = { star: '恒星', planet: '行星', satellite: '卫星' };
        const label = typeLabel[node.type] || '节点';
        const name = node.name || node.title || '未命名';
        const count = node.same_problem_count || node.generation_count || 0;

        let text = `<strong>${label}</strong>: ${name}`;
        if (count > 1) {
            text += `<br><span style="font-size:0.7rem;opacity:0.7;">&#28145;&#20851; ${count} &#27425;&#20869;&#23481;</span>`;
        }

        tooltip.innerHTML = text;
        tooltip.classList.add('is-visible');

        // 定位
        const container = document.querySelector('.galaxy-chart-container');
        if (container) {
            const rect = container.getBoundingClientRect();
            tooltip.style.left = (event.clientX - rect.left + 10) + 'px';
            tooltip.style.top = (event.clientY - rect.top - 30) + 'px';
        }
    },

    hideTooltip() {
        const tooltip = document.getElementById('galaxy-tooltip');
        if (tooltip) tooltip.classList.remove('is-visible');
    },

    // ========================================================================
    // 十三、回填数据
    // ========================================================================

    async runBackfill() {
        const btn = document.getElementById('btn-backfill');
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = '<i class="bi bi-arrow-repeat spin"></i> 回填中...';
        }

        try {
            const resp = await fetch('/public/api/galaxy/backfill', {
                method: 'POST',
                credentials: 'same-origin',
                headers: { 'Content-Type': 'application/json' },
            });
            const data = await resp.json();

            if (data.success) {
                // 刷新图表
                await this.loadGalaxyData();
                alert(`回填完成，共更新 ${data.data.updated_count} 条记录`);
            } else {
                alert('回填失败: ' + (data.message || '未知错误'));
            }
        } catch (err) {
            console.error('[Galaxy] 回填失败:', err);
            alert('回填失败，请检查网络');
        } finally {
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = '<i class="bi bi-arrow-repeat"></i> 回填关联';
            }
        }
    },

    // ========================================================================
    // 十四、工具函数
    // ========================================================================

    escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    },

    escapeHtmlAttr(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;')
            .replace(/`/g, '&#96;')
            .replace(/\$/g, '&#36;');
    },
};

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
    GalaxyUniverse.init();
});

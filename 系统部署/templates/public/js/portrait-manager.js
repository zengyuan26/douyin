/**
 * 画像管理模块
 * 
 * 功能：
 * 1. 保存画像到服务器
 * 2. 加载已保存的画像
 * 3. 切换画像（含频率控制检查）
 * 4. 画像使用统计
 */

const PortraitManager = {
    // 当前保存的画像列表
    _savedPortraits: [],
    
    // 当前选中的画像ID
    _currentPortraitId: null,
    
    // 用户配额信息
    _quota: null,
    
    /**
     * 初始化画像管理模块
     */
    async init() {
        await this.loadQuota();
        await this.loadSavedPortraits();
    },
    
    /**
     * 获取用户配额信息
     */
    async loadQuota() {
        try {
            const resp = await fetch('/public/api/portraits/quota', {
                credentials: 'include'
            });
            const data = await resp.json();
            if (data.success) {
                this._quota = data.data;
                this.updateQuotaDisplay();
            }
        } catch (e) {
            console.error('[PortraitManager] 加载配额失败:', e);
        }
    },
    
    /**
     * 更新配额显示
     */
    updateQuotaDisplay() {
        if (!this._quota) return;
        
        const quotaDisplay = document.getElementById('portrait-quota-display');
        if (!quotaDisplay) return;
        
        const planType = this._quota.plan_type || 'free';
        const planNames = {
            'free': '免费版',
            'basic': '基础版',
            'professional': '专业版',
            'enterprise': '企业版'
        };
        
        let quotaText = '';
        if (planType === 'free') {
            quotaText = '<span class="badge bg-secondary">免费用户：每次生成新画像</span>';
        } else {
            const weeklyLimit = this._quota.weekly_change_limit;
            const weeklyUsed = this._quota.weekly_changes_used;
            if (weeklyLimit) {
                const remaining = weeklyLimit - weeklyUsed;
                quotaText = `<span class="badge bg-primary">本周剩余更换次数：${remaining}/${weeklyLimit}</span>`;
            } else {
                quotaText = '<span class="badge bg-success">无更换限制</span>';
            }
        }
        
        quotaDisplay.innerHTML = `
            <div class="d-flex align-items-center gap-2 flex-wrap">
                <span class="badge bg-info">${planNames[planType] || planType}</span>
                ${quotaText}
                <span class="badge bg-light text-dark">已保存：${this._savedPortraits.length}${this._quota.max_saved ? '/' + this._quota.max_saved : ''}</span>
            </div>
        `;
    },
    
    /**
     * 加载已保存的画像列表
     */
    async loadSavedPortraits() {
        try {
            const resp = await fetch('/public/api/portraits/saved?include_data=true', {
                credentials: 'include'
            });
            const data = await resp.json();
            if (data.success) {
                this._savedPortraits = data.data || [];
                this.renderSavedPortraits();
            }
        } catch (e) {
            console.error('[PortraitManager] 加载已保存画像失败:', e);
        }
    },
    
    /**
     * 渲染已保存的画像列表
     */
    renderSavedPortraits() {
        const container = document.getElementById('saved-portraits-list');
        if (!container) return;
        
        if (this._savedPortraits.length === 0) {
            container.innerHTML = '<div class="text-muted small">暂无保存的画像</div>';
            return;
        }
        
        container.innerHTML = this._savedPortraits.map(p => `
            <div class="saved-portrait-item ${p.id === this._currentPortraitId ? 'active' : ''}" 
                 data-id="${p.id}" onclick="PortraitManager.selectPortrait(${p.id})">
                <div class="d-flex justify-content-between align-items-center">
                    <div>
                        <span class="portrait-name">${this.escapeHtml(p.portrait_name || '未命名')}</span>
                        ${p.is_default ? '<span class="badge bg-primary ms-1">默认</span>' : ''}
                    </div>
                    <div class="btn-group btn-group-sm">
                        <button class="btn btn-outline-primary" onclick="event.stopPropagation(); PortraitManager.usePortrait(${p.id})" title="使用">
                            <i class="bi bi-check-circle"></i>
                        </button>
                        <button class="btn btn-outline-danger" onclick="event.stopPropagation(); PortraitManager.deletePortrait(${p.id})" title="删除">
                            <i class="bi bi-trash"></i>
                        </button>
                    </div>
                </div>
            </div>
        `).join('');
    },
    
    /**
     * 选择画像（用于切换）
     */
    async selectPortrait(portraitId) {
        // 检查更换权限
        const checkResp = await fetch('/public/api/portraits/check-change', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ change_type: 'switch_saved' })
        });
        const checkData = await checkResp.json();
        
        if (!checkData.data || !checkData.data.allowed) {
            alert(checkData.data?.reason || '无法更换画像');
            return;
        }
        
        await this.usePortrait(portraitId);
    },
    
    /**
     * 使用画像
     */
    async usePortrait(portraitId) {
        try {
            const resp = await fetch('/public/api/portraits/change', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({
                    new_portrait_id: portraitId,
                    change_type: 'switch_saved'
                })
            });
            const data = await resp.json();
            
            if (data.success) {
                this._currentPortraitId = portraitId;
                await this.loadSavedPortraits();
                await this.loadQuota();
                
                // 触发事件：画像切换
                if (window.onPortraitChanged) {
                    window.onPortraitChanged(data.data);
                }
                
                showToast('已切换到画像：' + data.data.portrait_name, 'success');
            } else {
                showToast(data.message || '切换画像失败', 'error');
            }
        } catch (e) {
            console.error('[PortraitManager] 使用画像失败:', e);
            showToast('切换画像失败', 'error');
        }
    },
    
    /**
     * 保存当前画像
     */
    async saveCurrentPortrait(portraitData, options = {}) {
        const {
            portraitName,
            businessDescription,
            industry,
            targetCustomer,
            sourceSessionId,
            setAsDefault = false
        } = options;
        
        try {
            const resp = await fetch('/public/api/portraits/save', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({
                    portrait_data: portraitData,
                    portrait_name: portraitName,
                    business_description: businessDescription,
                    industry: industry,
                    target_customer: targetCustomer,
                    source_session_id: sourceSessionId,
                    set_as_default: setAsDefault
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
                showToast(data.message || '保存画像失败', 'error');
                return null;
            }
        } catch (e) {
            console.error('[PortraitManager] 保存画像失败:', e);
            showToast('保存画像失败', 'error');
            return null;
        }
    },
    
    /**
     * 删除画像
     */
    async deletePortrait(portraitId) {
        if (!confirm('确定要删除这个画像吗？')) return;
        
        try {
            const resp = await fetch(`/public/api/portraits/${portraitId}`, {
                method: 'DELETE',
                credentials: 'include'
            });
            const data = await resp.json();
            
            if (data.success) {
                if (this._currentPortraitId === portraitId) {
                    this._currentPortraitId = null;
                }
                await this.loadSavedPortraits();
                await this.loadQuota();
                showToast('画像已删除', 'success');
            } else {
                showToast(data.message || '删除失败', 'error');
            }
        } catch (e) {
            console.error('[PortraitManager] 删除画像失败:', e);
            showToast('删除失败', 'error');
        }
    },
    
    /**
     * 设为默认画像
     */
    async setDefaultPortrait(portraitId) {
        try {
            const resp = await fetch(`/public/api/portraits/${portraitId}/set-default`, {
                method: 'POST',
                credentials: 'include'
            });
            const data = await resp.json();
            
            if (data.success) {
                await this.loadSavedPortraits();
                showToast('已设为默认画像', 'success');
            } else {
                showToast(data.message || '设置失败', 'error');
            }
        } catch (e) {
            console.error('[PortraitManager] 设置默认画像失败:', e);
            showToast('设置失败', 'error');
        }
    },
    
    /**
     * 获取画像统计
     */
    async getStats() {
        try {
            const resp = await fetch('/public/api/portraits/stats', {
                credentials: 'include'
            });
            const data = await resp.json();
            if (data.success) {
                return data.data;
            }
        } catch (e) {
            console.error('[PortraitManager] 获取统计失败:', e);
        }
        return null;
    },
    
    /**
     * 获取默认画像
     */
    async getDefaultPortrait() {
        try {
            const resp = await fetch('/public/api/portraits/default', {
                credentials: 'include'
            });
            const data = await resp.json();
            if (data.success && data.data) {
                return data.data;
            }
        } catch (e) {
            console.error('[PortraitManager] 获取默认画像失败:', e);
        }
        return null;
    },
    
    /**
     * 检查是否可以保存画像
     */
    canSavePortrait() {
        if (!this._quota) return { allowed: false, reason: '加载中...' };
        if (!this._quota.can_save) {
            return { 
                allowed: false, 
                reason: '当前版本不支持保存画像，请升级到基础版或更高版本' 
            };
        }
        if (this._quota.max_saved && this._savedPortraits.length >= this._quota.max_saved) {
            return { 
                allowed: false, 
                reason: `已达保存上限（${this._quota.max_saved}个），请删除后再保存` 
            };
        }
        return { allowed: true };
    },
    
    /**
     * 检查是否可以更换画像
     */
    canChangePortrait() {
        if (!this._quota) return { allowed: false, reason: '加载中...' };
        if (this._quota.plan_type === 'free') {
            return { allowed: true, reason: '免费用户可随时更换' };
        }
        if (this._quota.weekly_change_limit) {
            const remaining = this._quota.weekly_change_limit - this._quota.weekly_changes_used;
            if (remaining <= 0) {
                return { 
                    allowed: false, 
                    reason: `本周更换次数已用完（${this._quota.weekly_change_limit}次）` 
                };
            }
        }
        return { allowed: true };
    },
    
    /**
     * 工具方法：HTML转义
     */
    escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    },
    
    /**
     * 工具方法：格式化日期
     */
    formatDate(dateStr) {
        if (!dateStr) return '';
        const d = new Date(dateStr);
        return `${d.getMonth() + 1}/${d.getDate()} ${d.getHours()}:${String(d.getMinutes()).padStart(2, '0')}`;
    }
};

// 内容类型推荐模块
const ContentTypeRecommender = {
    /**
     * 推荐内容类型
     */
    async recommend(topic, portrait, businessInfo) {
        try {
            const resp = await fetch('/public/api/topics/recommend-type', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({
                    topic: topic,
                    portrait: portrait,
                    business_info: businessInfo
                })
            });
            const data = await resp.json();
            if (data.success) {
                return data.recommendation;
            }
        } catch (e) {
            console.error('[ContentTypeRecommender] 推荐失败:', e);
        }
        return null;
    },
    
    /**
     * 获取内容类型推荐（前端计算版本）
     */
    getRecommendation(topic, portrait, businessInfo) {
        // 基础分数
        const scores = {
            'graphic': 0.5,
            'long_text': 0.5,
            'short_video': 0.5
        };
        
        const topicType = topic.type || '问题诊断';
        
        // 选题类型评分
        const typeScores = {
            'graphic': { '问题诊断': 0.9, '解决方案': 0.8, '避坑指南': 0.95, '知识科普': 0.85, '经验分享': 0.7 },
            'long_text': { '知识科普': 0.9, '解决方案': 0.7, '经验分享': 0.6 },
            'short_video': { '问题诊断': 0.7, '解决方案': 0.9, '经验分享': 0.95, '避坑指南': 0.6, '知识科普': 0.75 }
        };
        
        // 应用选题类型分数
        if (typeScores.graphic[topicType]) scores.graphic = typeScores.graphic[topicType];
        if (typeScores.long_text[topicType]) scores.long_text = typeScores.long_text[topicType];
        if (typeScores.short_video[topicType]) scores.short_video = typeScores.short_video[topicType];
        
        // 业务信息调整
        if (businessInfo) {
            if (businessInfo.is_hot_topic) {
                scores.short_video += 0.2;
                scores.graphic -= 0.1;
            }
            if (businessInfo.is_professional) {
                scores.long_text += 0.15;
            }
            if (businessInfo.is_comparison) {
                scores.graphic += 0.2;
            }
            if (businessInfo.is_local_service) {
                scores.graphic += 0.15;
            }
        }
        
        // 画像调整
        if (portrait) {
            const ageRange = portrait.age_range || '';
            if (ageRange.includes('25') || ageRange.includes('30') || ageRange.includes('35')) {
                scores.short_video += 0.1;
            }
        }
        
        // 排序
        const sorted = Object.entries(scores).sort((a, b) => b[1] - a[1]);
        
        const typeNames = {
            'graphic': '图文',
            'long_text': '长文',
            'short_video': '短视频'
        };
        
        const typeDescriptions = {
            'graphic': '适合对比、步骤、清单类内容',
            'long_text': '适合深度分析、专业知识讲解',
            'short_video': '适合故事讲述、场景演示'
        };
        
        return {
            primary: {
                type: sorted[0][0],
                name: typeNames[sorted[0][0]],
                score: Math.round(sorted[0][1] * 100),
                description: typeDescriptions[sorted[0][0]]
            },
            secondary: {
                type: sorted[1][0],
                name: typeNames[sorted[1][0]],
                score: Math.round(sorted[1][1] * 100)
            },
            all_scores: {
                'graphic': Math.round(scores.graphic * 100),
                'long_text': Math.round(scores.long_text * 100),
                'short_video': Math.round(scores.short_video * 100)
            }
        };
    },
    
    /**
     * 渲染内容类型推荐
     */
    renderRecommendation(recommendation, containerId) {
        const container = document.getElementById(containerId);
        if (!container || !recommendation) return;
        
        container.innerHTML = `
            <div class="content-type-recommendation">
                <div class="mb-2">
                    <span class="badge bg-primary fs-6 me-2">
                        <i class="bi bi-lightbulb"></i> 推荐：${recommendation.primary.name}
                    </span>
                    <span class="badge bg-outline-primary">匹配度 ${recommendation.primary.score}%</span>
                </div>
                <p class="small text-muted mb-2">${recommendation.primary.description}</p>
                <div class="small">
                    <span class="text-muted">其他选项：</span>
                    ${recommendation.secondary ? `
                        <span class="badge bg-light text-dark me-1">${recommendation.secondary.name} (${recommendation.secondary.score}%)</span>
                    ` : ''}
                </div>
                <div class="mt-2">
                    <small class="text-muted">各类型得分：</small>
                    <div class="progress" style="height: 6px;">
                        ${Object.entries(recommendation.all_scores).map(([type, score], i) => `
                            <div class="progress-bar ${type === 'graphic' ? 'bg-success' : type === 'long_text' ? 'bg-info' : 'bg-warning'}" 
                                 style="width: ${score}%" 
                                 title="${type === 'graphic' ? '图文' : type === 'long_text' ? '长文' : '短视频'}: ${score}%">
                            </div>
                        `).join('')}
                    </div>
                    <div class="d-flex justify-content-between small text-muted mt-1">
                        <span>图文 ${recommendation.all_scores.graphic}%</span>
                        <span>长文 ${recommendation.all_scores.long_text}%</span>
                        <span>短视频 ${recommendation.all_scores.short_video}%</span>
                    </div>
                </div>
            </div>
        `;
    }
};

// 页面初始化
document.addEventListener('DOMContentLoaded', async () => {
    // 检查是否已登录
    const isLoggedIn = document.body.dataset.userId;
    if (isLoggedIn) {
        await PortraitManager.init();
    }
});

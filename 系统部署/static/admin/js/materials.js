/**
 * 素材库模块
 * 管理素材入库相关功能
 */
const Materials = (function() {
    // 缓存配置
    let _config = null;

    // 素材类型 -> 规则分类 映射
    const CATEGORY_MAP = {
        'title': 'template',
        'hook': 'template',
        'cover': 'template',
        'topic': 'topic',
        'structure': 'template',
        'ending': 'template',
        'psychology': 'keywords',
        'commercial': 'operation',
        'why_popular': 'template',
        'tags': 'keywords',
        'character': 'template',
        'content_form': 'template',
        'interaction': 'template'
    };

    /**
     * 加载素材库配置
     */
    async function loadConfig() {
        if (_config) return _config;
        try {
            const response = await fetch('/api/content-materials/config');
            const data = await response.json();
            if (data.code === 200) {
                _config = data.data;
                return _config;
            }
        } catch (e) {
            console.error('加载素材库配置失败:', e);
        }
        return null;
    }

    /**
     * 获取素材类型对应的规则分类
     */
    function getRuleCategory(materialType) {
        return CATEGORY_MAP[materialType] || 'template';
    }

    /**
     * 比对规则库（检查重复）
     */
    async function checkRules(ruleContent, category, sourceDimension) {
        const response = await fetch('/admin/api/knowledge/rules/check', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                rules: [{
                    rule_content: ruleContent,
                    category: category,
                    source_dimension: sourceDimension
                }]
            })
        });
        return await response.json();
    }

    /**
     * 保存素材到素材库
     */
    async function save(materialData) {
        const response = await fetch('/api/content-materials/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(materialData)
        });
        return await response.json();
    }

    /**
     * 获取 DOM 元素（带检查）
     */
    function getElement(id) {
        return document.getElementById(id);
    }

    /**
     * 显示入库弹窗
     */
    async function showSaveModal(dimension, materialType, content) {
        const config = await loadConfig();
        if (!config) {
            alert('加载素材库配置失败');
            return;
        }

        // 设置维度
        const dimInput = getElement('material-dimension');
        if (dimInput) dimInput.value = dimension;

        // 填充素材类型下拉框
        const typeSelect = getElement('material-type-select');
        if (typeSelect) {
            typeSelect.innerHTML = '<option value="">请选择素材库类型</option>';
            const materialConfigForType = config.material_types[materialType];
            if (materialConfigForType) {
                typeSelect.innerHTML += `<option value="${materialType}" selected>${materialConfigForType.name}</option>`;
            }
        }

        // 填充内容（截取前500字符避免过长）
        const shortContent = content.length > 500 ? content.substring(0, 500) + '...' : content;
        const contentInput = getElement('material-content');
        if (contentInput) contentInput.value = shortContent;

        // 填充行业下拉框
        const industrySelect = getElement('material-industry');
        if (industrySelect) {
            industrySelect.innerHTML = '<option value="">请选择行业</option>';
            config.industry_options.forEach(ind => {
                industrySelect.innerHTML += `<option value="${ind}">${ind}</option>`;
            });
        }

        // 更新类型下拉框
        updateTypeOptions(materialType);

        // 显示弹窗
        const modalEl = getElement('saveToMaterialModal');
        if (modalEl) {
            const modal = new bootstrap.Modal(modalEl);
            modal.show();
        }
    }

    /**
     * 更新类型下拉框
     */
    function updateTypeOptions(materialType) {
        const typeSelect = getElement('material-type');
        if (!typeSelect || !_config) return;

        typeSelect.innerHTML = '<option value="">请选择类型</option>';

        if (_config.material_types[materialType]) {
            const options = _config.material_types[materialType].type_options || [];
            options.forEach(opt => {
                typeSelect.innerHTML += `<option value="${opt}">${opt}</option>`;
            });
        }
    }

    /**
     * 确认入库
     */
    async function confirmSave() {
        const materialType = getElement('material-type-select')?.value;
        const content = getElement('material-content')?.value.trim();
        const industry = getElement('material-industry')?.value;
        const type = getElement('material-type')?.value;
        const dimension = getElement('material-dimension')?.value;

        const contentTypes = [];
        if (getElement('material-content-type-video')?.checked) contentTypes.push('video');
        if (getElement('material-content-type-image_text')?.checked) contentTypes.push('image_text');
        if (getElement('material-content-type-long_text')?.checked) contentTypes.push('long_text');

        if (!materialType) {
            alert('请选择素材库类型');
            return;
        }

        if (!content) {
            alert('请输入入库内容');
            return;
        }

        try {
            // 第一步：比对规则库
            const category = getRuleCategory(materialType);
            const checkData = await checkRules(content, category, dimension);

            if (!checkData.success) {
                alert('比对失败: ' + checkData.message);
                return;
            }

            const checkResult = checkData.results?.[0];

            if (checkResult?.is_duplicate) {
                let message = '⚠️ 系统已有相似规则：\n\n';
                checkResult.similar_rules.forEach(r => {
                    message += `• ${r.rule_title || r.rule_content}\n  相似度: ${r.similarity}\n\n`;
                });
                message += '是否仍然入库？';
                if (!confirm(message)) return;
            }

            // 第二步：执行入库
            const data = await save({
                material_type: materialType,
                content: content,
                industry: industry,
                type: type,
                content_types: contentTypes,
                dimension: dimension
            });

            if (data.code === 200) {
                alert('✅ 入库成功！');
                const modalEl = getElement('saveToMaterialModal');
                if (modalEl) {
                    bootstrap.Modal.getInstance(modalEl)?.hide();
                }
            } else {
                alert(data.message || '入库失败');
            }
        } catch (error) {
            console.error('入库失败:', error);
            alert('入库失败，请稍后重试');
        }
    }

    /**
     * 绑定事件
     */
    function bindEvents() {
        const confirmBtn = getElement('confirm-save-btn');
        if (confirmBtn) {
            confirmBtn.addEventListener('click', confirmSave);
        }
    }

    // 初始化
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', bindEvents);
    } else {
        bindEvents();
    }

    return {
        loadConfig,
        showSaveModal,
        updateTypeOptions,
        confirmSave,
        getRuleCategory,
        checkRules,
        save
    };
})();

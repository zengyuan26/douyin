<template>
  <div class="result-page">
    <div class="container">
      <!-- 加载状态 -->
      <div v-if="isLoading" class="loading-state">
        <div class="loading-spinner"></div>
        <p>正在分析你的答案...</p>
      </div>

      <!-- 结果内容 -->
      <div v-else-if="result" class="result-content animate-fade-in-up">
        <!-- 顶部标题 -->
        <div class="header">
          <h1 class="title">🎉 诊断完成！</h1>
          <p class="subtitle">这是你的赚钱能力报告</p>
        </div>

        <!-- 分数卡片 -->
        <div class="score-card">
          <div class="score-circle">
            <svg class="score-ring" viewBox="0 0 100 100">
              <circle class="ring-bg" cx="50" cy="50" r="45" />
              <circle
                class="ring-progress"
                cx="50" cy="50" r="45"
                :stroke-dasharray="circumference"
                :stroke-dashoffset="strokeOffset"
              />
            </svg>
            <div class="score-content">
              <span class="score-value">{{ result.percentage }}</span>
              <span class="score-unit">分</span>
            </div>
          </div>
          <div class="score-label">你的赚钱能力</div>
        </div>

        <!-- 阶段标签 -->
        <div class="stage-card">
          <span class="stage-emoji">{{ stageEmoji }}</span>
          <div class="stage-info">
            <span class="stage-name">{{ result.stage }}</span>
            <span class="stage-desc">{{ result.stage_label }}</span>
          </div>
        </div>

        <!-- 类型标签 -->
        <div class="type-tags">
          <div class="type-tag">
            <span class="tag-icon">💰</span>
            <span class="tag-label">{{ result.value_type_label }}</span>
          </div>
          <div class="type-tag">
            <span class="tag-icon">🎯</span>
            <span class="tag-label">{{ result.asset_type_label }}</span>
          </div>
        </div>

        <!-- 优势部分 -->
        <div class="section" v-if="result.strengths?.length">
          <h3 class="section-title">✨ 你的优势</h3>
          <div class="strengths-list">
            <div v-for="(item, idx) in result.strengths" :key="idx" class="strength-item">
              <span class="item-icon">✅</span>
              <span class="item-text">{{ item }}</span>
            </div>
          </div>
        </div>

        <!-- 不足部分 -->
        <div class="section" v-if="result.weaknesses?.length">
          <h3 class="section-title">⚠️ 需要提升</h3>
          <div class="weaknesses-list">
            <div v-for="(item, idx) in result.weaknesses" :key="idx" class="weakness-item">
              <span class="item-icon">{{ weaknessIcons[idx] }}</span>
              <span class="item-text">{{ item }}</span>
            </div>
          </div>
        </div>

        <!-- 洞察部分 -->
        <div class="section insights-section" v-if="result.insights?.length">
          <h3 class="section-title">💡 核心洞察</h3>
          <div class="insights-list">
            <div v-for="(insight, idx) in result.insights" :key="idx" class="insight-item">
              {{ insight }}
            </div>
          </div>
        </div>

        <!-- 建议部分 -->
        <div class="section" v-if="result.recommendations?.length">
          <h3 class="section-title">🎯 下一步建议</h3>
          <div class="recommendations-list">
            <div
              v-for="(rec, idx) in result.recommendations"
              :key="idx"
              class="recommendation-item"
            >
              <div class="rec-header">
                <span class="rec-icon">{{ rec.icon || (idx + 1 + '️⃣') }}</span>
                <span class="rec-title">{{ rec.title }}</span>
              </div>
              <p class="rec-action">{{ rec.action || rec.description }}</p>
              <p class="rec-result" v-if="rec.result">→ {{ rec.result }}</p>
            </div>
          </div>
        </div>

        <!-- 操作按钮 -->
        <div class="action-buttons">
          <button class="btn-secondary" @click="handleRetry">
            再测一次
          </button>
          <button class="btn-primary" @click="handleShare">
            分享给朋友
          </button>
        </div>
      </div>

      <!-- 错误状态 -->
      <div v-else class="error-state">
        <p>加载失败，请重试</p>
        <button class="btn-primary" @click="loadResult">重新加载</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useDiagnosisStore } from '../stores/diagnosis'

const route = useRoute()
const router = useRouter()
const store = useDiagnosisStore()

const isLoading = ref(true)
const result = ref(null)

const circumference = 2 * Math.PI * 45
const strokeOffset = computed(() => {
  if (!result.value) return circumference
  return circumference - (result.value.percentage / 100) * circumference
})

const stageEmoji = computed(() => {
  const stage = result.value?.stage || ''
  if (stage.includes('第一') || stage.includes('起步')) return '🌱'
  if (stage.includes('第二') || stage.includes('发展')) return '🚀'
  if (stage.includes('第三') || stage.includes('成熟')) return '⭐'
  if (stage.includes('第四') || stage.includes('突破')) return '👑'
  return '📊'
})

const weaknessIcons = ['🚧', '📈', '💪']

onMounted(async () => {
  await loadResult()
})

async function loadResult() {
  isLoading.value = true
  const sessionId = route.params.sessionId
  if (sessionId) {
    result.value = await store.loadResult(sessionId)
  }
  isLoading.value = false
}

function handleRetry() {
  store.reset()
  localStorage.removeItem('naval_diagnosis_progress')
  router.push('/')
}

function handleShare() {
  if (result.value?.id) {
    navigator.clipboard.writeText(`${window.location.origin}/share/${result.value.id}`)
    alert('链接已复制到剪贴板！')
  }
}
</script>

<style scoped>
.result-page {
  min-height: 100vh;
  padding: 20px;
  padding-top: 40px;
  padding-bottom: 120px;
}

.container {
  max-width: 480px;
  margin: 0 auto;
}

.loading-state {
  text-align: center;
  color: white;
  padding: 60px 0;
}

.loading-spinner {
  width: 48px;
  height: 48px;
  border: 4px solid rgba(255, 255, 255, 0.3);
  border-top-color: white;
  border-radius: 50%;
  margin: 0 auto 16px;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.result-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.header {
  text-align: center;
  color: white;
}

.title {
  font-size: 28px;
  font-weight: 800;
  margin-bottom: 8px;
}

.subtitle {
  font-size: 16px;
  opacity: 0.9;
}

.score-card {
  background: white;
  border-radius: 24px;
  padding: 32px;
  text-align: center;
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
}

.score-circle {
  position: relative;
  width: 150px;
  height: 150px;
  margin: 0 auto 16px;
}

.score-ring {
  width: 100%;
  height: 100%;
  transform: rotate(-90deg);
}

.ring-bg {
  fill: none;
  stroke: #e5e7eb;
  stroke-width: 8;
}

.ring-progress {
  fill: none;
  stroke: url(#gradient);
  stroke-width: 8;
  stroke-linecap: round;
  transition: stroke-dashoffset 1s ease;
  stroke: #3b82f6;
}

.score-content {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
}

.score-value {
  font-size: 48px;
  font-weight: 800;
  color: #1f2937;
}

.score-unit {
  font-size: 20px;
  color: #6b7280;
  align-self: flex-end;
  margin-bottom: 8px;
}

.score-label {
  font-size: 16px;
  color: #6b7280;
}

.stage-card {
  background: white;
  border-radius: 16px;
  padding: 20px;
  display: flex;
  align-items: center;
  gap: 16px;
  box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.1);
}

.stage-emoji {
  font-size: 40px;
}

.stage-info {
  display: flex;
  flex-direction: column;
}

.stage-name {
  font-size: 20px;
  font-weight: 700;
  color: #1f2937;
}

.stage-desc {
  font-size: 14px;
  color: #6b7280;
}

.type-tags {
  display: flex;
  gap: 12px;
}

.type-tag {
  flex: 1;
  background: white;
  border-radius: 12px;
  padding: 16px;
  display: flex;
  align-items: center;
  gap: 10px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}

.tag-icon {
  font-size: 24px;
}

.tag-label {
  font-size: 14px;
  font-weight: 600;
  color: #1f2937;
}

.section {
  background: white;
  border-radius: 16px;
  padding: 20px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}

.section-title {
  font-size: 16px;
  font-weight: 700;
  color: #1f2937;
  margin-bottom: 16px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.strengths-list,
.weaknesses-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.strength-item,
.weakness-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  font-size: 14px;
  color: #374151;
  line-height: 1.5;
}

.item-icon {
  font-size: 18px;
  flex-shrink: 0;
}

.insights-section {
  background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
}

.insights-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.insight-item {
  font-size: 15px;
  color: #92400e;
  line-height: 1.6;
  padding: 12px;
  background: rgba(255, 255, 255, 0.6);
  border-radius: 8px;
}

.recommendations-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.recommendation-item {
  padding: 16px;
  background: #f9fafb;
  border-radius: 12px;
  border-left: 4px solid #3b82f6;
}

.rec-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}

.rec-icon {
  font-size: 20px;
}

.rec-title {
  font-size: 15px;
  font-weight: 700;
  color: #1f2937;
}

.rec-action {
  font-size: 14px;
  color: #4b5563;
  margin-bottom: 4px;
}

.rec-result {
  font-size: 13px;
  color: #3b82f6;
  font-weight: 500;
}

.action-buttons {
  display: flex;
  gap: 12px;
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 20px;
  padding-bottom: env(safe-area-inset-bottom, 20px);
  background: linear-gradient(to top, rgba(102, 126, 234, 1) 0%, rgba(118, 75, 162, 1) 100%);
  z-index: 100;
}

.action-buttons button {
  flex: 1;
}
</style>

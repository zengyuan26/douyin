<template>
  <div class="share-page">
    <div class="container">
      <!-- 加载状态 -->
      <div v-if="isLoading" class="loading-state">
        <div class="loading-spinner"></div>
        <p>正在加载...</p>
      </div>

      <!-- 结果内容 -->
      <div v-else-if="shareData" class="share-content animate-fade-in-up">
        <!-- 分享者信息 -->
        <div class="share-header">
          <p class="share-hint">朋友分享的诊断报告</p>
          <h1 class="title">你的赚钱能力诊断</h1>
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
              <span class="score-value">{{ shareData.percentage }}</span>
              <span class="score-unit">分</span>
            </div>
          </div>
          <div class="score-label">他的赚钱能力</div>
        </div>

        <!-- 阶段 -->
        <div class="stage-card">
          <span class="stage-emoji">{{ stageEmoji }}</span>
          <div class="stage-info">
            <span class="stage-name">{{ shareData.stage }}</span>
            <span class="stage-desc">{{ shareData.stage_label }}</span>
          </div>
        </div>

        <!-- 洞察 -->
        <div class="section insights-section" v-if="shareData.insights?.length">
          <h3 class="section-title">💡 他的洞察</h3>
          <div class="insights-list">
            <div v-for="(insight, idx) in shareData.insights" :key="idx" class="insight-item">
              {{ insight }}
            </div>
          </div>
        </div>

        <!-- CTA -->
        <div class="cta-section">
          <p class="cta-text">想知道你的赚钱能力是多少？</p>
          <button class="btn-primary" @click="handleStartTest">
            开始我的诊断 →
          </button>
        </div>
      </div>

      <!-- 错误状态 -->
      <div v-else class="error-state">
        <p>报告不存在或已过期</p>
        <button class="btn-primary" @click="handleStartTest">
          开始我的诊断
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'

const router = useRouter()
const isLoading = ref(true)
const shareData = ref(null)

const circumference = 2 * Math.PI * 45
const strokeOffset = computed(() => {
  if (!shareData.value) return circumference
  return circumference - (shareData.value.percentage / 100) * circumference
})

const stageEmoji = computed(() => {
  const stage = shareData.value?.stage || ''
  if (stage.includes('第一') || stage.includes('起步')) return '🌱'
  if (stage.includes('第二') || stage.includes('发展')) return '🚀'
  if (stage.includes('第三') || stage.includes('成熟')) return '⭐'
  if (stage.includes('第四') || stage.includes('突破')) return '👑'
  return '📊'
})

onMounted(async () => {
  const shareCode = window.location.pathname.split('/').pop()
  if (shareCode) {
    try {
      const response = await axios.get(`/api/v1/share/${shareCode}`)
      shareData.value = response.data
    } catch (e) {
      console.error('加载失败:', e)
    }
  }
  isLoading.value = false
})

function handleStartTest() {
  router.push('/')
}
</script>

<style scoped>
.share-page {
  min-height: 100vh;
  padding: 20px;
  padding-top: 40px;
  padding-bottom: 100px;
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

.share-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.share-header {
  text-align: center;
  color: white;
}

.share-hint {
  font-size: 14px;
  opacity: 0.8;
  margin-bottom: 8px;
}

.title {
  font-size: 24px;
  font-weight: 800;
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
  stroke: #3b82f6;
  stroke-width: 8;
  stroke-linecap: round;
  transition: stroke-dashoffset 1s ease;
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

.cta-section {
  background: white;
  border-radius: 24px;
  padding: 32px;
  text-align: center;
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
}

.cta-text {
  font-size: 16px;
  color: #6b7280;
  margin-bottom: 16px;
}

.cta-section .btn-primary {
  width: 100%;
}

.error-state {
  text-align: center;
  color: white;
  padding: 60px 0;
}

.error-state p {
  margin-bottom: 20px;
  font-size: 18px;
}
</style>

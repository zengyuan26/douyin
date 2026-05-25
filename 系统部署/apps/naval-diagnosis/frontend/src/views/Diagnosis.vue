<template>
  <div class="diagnosis-page">
    <div class="container">
      <!-- 进度条 -->
      <div class="progress-bar">
        <div class="progress-fill" :style="{ width: progressPercent + '%' }"></div>
      </div>
      <div class="progress-text">{{ currentIndex + 1 }} / {{ totalQuestions }}</div>

      <!-- 问题卡片 -->
      <div class="question-card animate-fade-in-up" :key="currentQuestion?.key">
        <!-- 问题配图 -->
        <div class="question-image">
          <div class="image-placeholder">{{ questionEmoji }}</div>
        </div>

        <!-- 问题标题 -->
        <h2 class="question-title">{{ currentQuestion?.title }}</h2>
        <p class="question-subtitle">{{ currentQuestion?.subtitle }}</p>

        <!-- 选项列表 -->
        <div class="options-list">
          <button
            v-for="option in currentQuestion?.options"
            :key="option.value"
            class="option-card"
            :class="{ selected: answers[currentQuestion?.key] === option.value }"
            @click="handleSelect(option.value)"
          >
            <span class="option-icon">{{ option.icon }}</span>
            <div class="option-content">
              <span class="option-label">{{ option.label }}</span>
              <span class="option-desc">{{ option.description }}</span>
            </div>
          </button>
        </div>

        <!-- 预估分数 -->
        <div class="preview-score" v-if="previewScore > 0">
          <span class="score-label">预估得分</span>
          <span class="score-value">{{ previewScore }}</span>
        </div>
      </div>

      <!-- 导航按钮 -->
      <div class="nav-buttons">
        <button
          v-if="currentIndex > 0"
          class="btn-secondary"
          @click="handleBack"
        >
          ← 上一步
        </button>
        <button
          v-if="currentIndex === totalQuestions - 1"
          class="btn-primary complete-btn"
          :disabled="!isComplete || isSubmitting"
          @click="handleComplete"
        >
          {{ isSubmitting ? '分析中...' : '查看结果' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useDiagnosisStore } from '../stores/diagnosis'

const router = useRouter()
const store = useDiagnosisStore()

// 问题对应的emoji（备用显示）
const questionEmojis = {
  earn: '💰',
  unique: '🦸',
  pause: '⏸️',
  team: '👥',
  content: '📱',
  clients: '🤝',
  passive: '💤',
  ceiling: '🏔️',
  model: '📋',
  ambition: '🚀'
}

const currentQuestion = computed(() => store.currentQuestion)
const currentIndex = computed(() => store.currentIndex)
const totalQuestions = computed(() => store.totalQuestions)
const answers = computed(() => store.answers)
const isComplete = computed(() => store.isComplete)
const previewScore = computed(() => store.previewScore)
const isSubmitting = computed(() => store.isSubmitting)

const progressPercent = computed(() => {
  return Math.round(((currentIndex.value + 1) / totalQuestions.value) * 100)
})

const questionEmoji = computed(() => {
  const image = currentQuestion.value?.image
  return questionEmojis[image] || '❓'
})

onMounted(() => {
  // 如果没有题目，跳转回首页
  if (store.questions.length === 0) {
    router.push('/')
  }
})

async function handleSelect(value) {
  await store.selectAnswer(currentQuestion.value.key, value)

  // 如果是最后一题且有完整答案，自动提交
  if (currentIndex.value === totalQuestions.value - 1) {
    // 等待一小段时间让用户看到选择效果
    setTimeout(() => {
      if (store.isComplete) {
        handleComplete()
      }
    }, 300)
  }
}

function handleBack() {
  store.goBack()
}

async function handleComplete() {
  if (!store.isComplete || store.isSubmitting) return

  const data = await store.completeDiagnosis()
  if (data && store.sessionId) {
    router.push(`/result/${store.sessionId}`)
  }
}
</script>

<style scoped>
.diagnosis-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  padding-top: 40px;
}

.container {
  width: 100%;
  max-width: 480px;
}

.progress-bar {
  height: 6px;
  background: rgba(255, 255, 255, 0.3);
  border-radius: 3px;
  overflow: hidden;
  margin-bottom: 8px;
}

.progress-fill {
  height: 100%;
  background: white;
  border-radius: 3px;
  transition: width 0.3s ease;
}

.progress-text {
  text-align: center;
  color: white;
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 24px;
}

.question-card {
  background: white;
  border-radius: 24px;
  padding: 32px 24px;
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
  margin-bottom: 24px;
}

.question-image {
  text-align: center;
  margin-bottom: 20px;
}

.image-placeholder {
  width: 80px;
  height: 80px;
  margin: 0 auto;
  background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
  border-radius: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 40px;
}

.question-title {
  font-size: 22px;
  font-weight: 700;
  color: #1f2937;
  text-align: center;
  margin-bottom: 8px;
}

.question-subtitle {
  font-size: 14px;
  color: #6b7280;
  text-align: center;
  margin-bottom: 24px;
}

.options-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.option-card {
  background: #f9fafb;
  border: 2px solid transparent;
  border-radius: 16px;
  padding: 16px;
  cursor: pointer;
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  gap: 16px;
  text-align: left;
  width: 100%;
}

.option-card:hover {
  background: #f3f4f6;
  border-color: #d1d5db;
}

.option-card.selected {
  background: #eff6ff;
  border-color: #3b82f6;
  transform: scale(1.02);
}

.option-icon {
  font-size: 32px;
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: white;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}

.option-content {
  flex: 1;
}

.option-label {
  display: block;
  font-size: 16px;
  font-weight: 600;
  color: #1f2937;
  margin-bottom: 4px;
}

.option-desc {
  display: block;
  font-size: 13px;
  color: #6b7280;
}

.preview-score {
  margin-top: 20px;
  padding: 16px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: white;
}

.score-label {
  font-size: 14px;
  opacity: 0.9;
}

.score-value {
  font-size: 24px;
  font-weight: 700;
}

.nav-buttons {
  display: flex;
  gap: 12px;
}

.btn-secondary {
  flex: 1;
}

.complete-btn {
  flex: 2;
}
</style>

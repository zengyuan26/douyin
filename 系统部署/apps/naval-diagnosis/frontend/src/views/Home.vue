<template>
  <div class="home-page">
    <div class="container">
      <!-- 装饰图形 -->
      <div class="decorations">
        <div class="circle circle-1"></div>
        <div class="circle circle-2"></div>
        <div class="circle circle-3"></div>
      </div>

      <!-- 主内容 -->
      <div class="content animate-fade-in-up">
        <!-- 图标 -->
        <div class="icon-container">
          <div class="icon-circle">
            <span class="icon-text">💰</span>
          </div>
        </div>

        <!-- 标题 -->
        <h1 class="title">你的赚钱能力诊断</h1>
        <p class="subtitle">3分钟测一测，发现你的优势</p>

        <!-- 开始按钮 -->
        <button
          class="btn-primary start-btn"
          @click="handleStart"
          :disabled="isLoading"
        >
          <span v-if="isLoading">加载中...</span>
          <span v-else>开始诊断 →</span>
        </button>

        <!-- 底部提示 -->
        <p class="hint">基于纳瓦尔财富理念 · 10道题测出你的商业模式</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useDiagnosisStore } from '../stores/diagnosis'

const router = useRouter()
const store = useDiagnosisStore()
const isLoading = ref(false)

async function handleStart() {
  isLoading.value = true
  const success = await store.startDiagnosis()
  if (success) {
    router.push('/diagnosis')
  }
  isLoading.value = false
}
</script>

<style scoped>
.home-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}

.container {
  position: relative;
  width: 100%;
  max-width: 480px;
}

.decorations {
  position: absolute;
  inset: 0;
  overflow: hidden;
  pointer-events: none;
}

.circle {
  position: absolute;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.1);
}

.circle-1 {
  width: 200px;
  height: 200px;
  top: -100px;
  right: -50px;
}

.circle-2 {
  width: 150px;
  height: 150px;
  bottom: 50px;
  left: -80px;
}

.circle-3 {
  width: 80px;
  height: 80px;
  top: 20%;
  left: -40px;
}

.content {
  background: white;
  border-radius: 32px;
  padding: 48px 32px;
  text-align: center;
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
}

.icon-container {
  margin-bottom: 24px;
}

.icon-circle {
  width: 100px;
  height: 100px;
  margin: 0 auto;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 10px 30px rgba(102, 126, 234, 0.4);
}

.icon-text {
  font-size: 48px;
}

.title {
  font-size: 28px;
  font-weight: 800;
  color: #1f2937;
  margin-bottom: 12px;
}

.subtitle {
  font-size: 16px;
  color: #6b7280;
  margin-bottom: 32px;
}

.start-btn {
  width: 100%;
  margin-bottom: 16px;
}

.hint {
  font-size: 12px;
  color: #9ca3af;
}
</style>

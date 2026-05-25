import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import axios from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 30000
})

export const useDiagnosisStore = defineStore('diagnosis', () => {
  // 状态
  const sessionId = ref(null)
  const questions = ref([])
  const currentIndex = ref(0)
  const answers = ref({})
  const isLoading = ref(false)
  const isSubmitting = ref(false)
  const result = ref(null)
  const error = ref(null)

  // 计算属性
  const currentQuestion = computed(() => questions.value[currentIndex.value])
  const totalQuestions = computed(() => questions.value.length)
  const progress = computed(() => Math.round(((currentIndex.value + 1) / totalQuestions.value) * 100))
  const isComplete = computed(() => Object.keys(answers.value).length === totalQuestions.value)
  const previewScore = computed(() => {
    const scores = {
      q1_earn_type: { product: 80, skill: 60, knowledge: 70, labor: 40 },
      q2_replicable: { only_me: 30, need_train: 60, anyone: 90 },
      q3_pause_week: { stop: 40, some_impact: 60, no_impact: 90 },
      q4_team: { alone: 30, small_team: 60, big_team: 90 },
      q5_content: { yes_active: 80, yes_sometimes: 50, no: 20 },
      q6_client_source: { referral: 60, active: 40, passive: 80 },
      q7_passive_income: { yes: 90, some: 60, no: 30 },
      q8_income_limit: { very_high: 90, some_limit: 60, very_limited: 30 },
      q9_model: { yes_standard: 90, some_formal: 60, chaos: 30 },
      q10_ambition: { very_much: 80, somewhat: 50, no_need: 20 }
    }
    let total = 0
    for (const [qKey, answer] of Object.entries(answers.value)) {
      if (scores[qKey] && scores[qKey][answer]) {
        total += scores[qKey][answer]
      }
    }
    return total
  })

  // 方法
  async function startDiagnosis() {
    isLoading.value = true
    error.value = null
    try {
      const response = await api.post('/diagnosis/start', {})
      sessionId.value = response.data.session_id
      await loadQuestions()
      return true
    } catch (e) {
      error.value = e.message
      return false
    } finally {
      isLoading.value = false
    }
  }

  async function loadQuestions() {
    try {
      const response = await api.get('/diagnosis/questions')
      questions.value = response.data
      return true
    } catch (e) {
      error.value = e.message
      return false
    }
  }

  async function selectAnswer(questionKey, value) {
    answers.value[questionKey] = value

    // 提交答案到服务器
    if (sessionId.value) {
      try {
        await api.post('/diagnosis/answer', {
          session_id: sessionId.value,
          question_key: questionKey,
          answer_value: { value }
        })
      } catch (e) {
        console.error('保存答案失败:', e)
      }
    }

    // 自动进入下一步
    if (currentIndex.value < totalQuestions.value - 1) {
      currentIndex.value++
    }
  }

  function goBack() {
    if (currentIndex.value > 0) {
      currentIndex.value--
    }
  }

  function goNext() {
    if (currentIndex.value < totalQuestions.value - 1) {
      currentIndex.value++
    }
  }

  async function completeDiagnosis() {
    isSubmitting.value = true
    error.value = null
    try {
      const response = await api.post('/diagnosis/complete', {
        session_id: sessionId.value,
        user_description: ''
      })
      return response.data
    } catch (e) {
      error.value = e.message
      return null
    } finally {
      isSubmitting.value = false
    }
  }

  async function loadResult(sessionIdParam) {
    isLoading.value = true
    try {
      const response = await api.get(`/result/${sessionIdParam}`)
      result.value = response.data
      return response.data
    } catch (e) {
      error.value = e.message
      return null
    } finally {
      isLoading.value = false
    }
  }

  function reset() {
    sessionId.value = null
    questions.value = []
    currentIndex.value = 0
    answers.value = {}
    result.value = null
    error.value = null
  }

  // 从localStorage恢复进度
  function restoreProgress() {
    const saved = localStorage.getItem('naval_diagnosis_progress')
    if (saved) {
      try {
        const data = JSON.parse(saved)
        sessionId.value = data.sessionId
        answers.value = data.answers || {}
        currentIndex.value = data.currentIndex || 0
        return true
      } catch {
        return false
      }
    }
    return false
  }

  // 保存进度到localStorage
  function saveProgress() {
    if (sessionId.value) {
      localStorage.setItem('naval_diagnosis_progress', JSON.stringify({
        sessionId: sessionId.value,
        answers: answers.value,
        currentIndex: currentIndex.value
      }))
    }
  }

  return {
    // 状态
    sessionId,
    questions,
    currentIndex,
    answers,
    isLoading,
    isSubmitting,
    result,
    error,
    // 计算属性
    currentQuestion,
    totalQuestions,
    progress,
    isComplete,
    previewScore,
    // 方法
    startDiagnosis,
    loadQuestions,
    selectAnswer,
    goBack,
    goNext,
    completeDiagnosis,
    loadResult,
    reset,
    restoreProgress,
    saveProgress
  }
})

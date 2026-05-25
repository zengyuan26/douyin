import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'Home',
    component: () => import('./views/Home.vue')
  },
  {
    path: '/diagnosis',
    name: 'Diagnosis',
    component: () => import('./views/Diagnosis.vue')
  },
  {
    path: '/result/:sessionId',
    name: 'Result',
    component: () => import('./views/Result.vue')
  },
  {
    path: '/share/:code',
    name: 'Share',
    component: () => import('./views/Share.vue')
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router

import { createRouter, createWebHistory } from 'vue-router'
import { useGoogleAuth } from '@slate/composables'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
      meta: { public: true },
    },
    {
      path: '/',
      name: 'dashboard',
      component: () => import('@/views/DashboardView.vue'),
    },
  ],
})

router.beforeEach((to) => {
  if (to.meta.public) return true
  const { isAuthenticated } = useGoogleAuth()
  if (!isAuthenticated()) return { name: 'login' }
})

export default router

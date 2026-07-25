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
      path: '/report',
      name: 'report',
      component: () => import('@/views/ReportView.vue'),
    },
    {
      path: '/track/:id',
      name: 'track',
      component: () => import('@/views/TrackView.vue'),
    },
    {
      path: '/:pathMatch(.*)*',
      redirect: '/report',
    },
  ],
})

router.beforeEach((to) => {
  if (to.meta.public) return true
  const { isAuthenticated } = useGoogleAuth()
  if (!isAuthenticated()) return { name: 'login' }
  return true
})

export default router

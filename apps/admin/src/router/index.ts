import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'dashboard',
      component: () => import('../views/DashboardView.vue'),
    },
    {
      path: '/incidents',
      name: 'incidents',
      component: () => import('../views/IncidentsView.vue'),
    },
    {
      path: '/incidents/:id',
      name: 'incident-detail',
      component: () => import('../views/IncidentDetailView.vue'),
    },
    {
      path: '/adjusters',
      name: 'adjusters',
      component: () => import('../views/AdjustersView.vue'),
    },
    {
      path: '/adjusters/:id',
      name: 'adjuster-detail',
      component: () => import('../views/AdjusterDetailView.vue'),
    },
    {
      path: '/assignments',
      name: 'assignments',
      component: () => import('../views/AssignmentsView.vue'),
    },
    {
      path: '/optimization',
      name: 'optimization',
      component: () => import('../views/OptimizationView.vue'),
    },
    {
      path: '/demand',
      name: 'demand',
      component: () => import('../views/DemandView.vue'),
    },
    {
      path: '/positioning',
      name: 'positioning',
      component: () => import('../views/PositioningView.vue'),
    },
    {
      path: '/settings',
      name: 'settings',
      component: () => import('../views/SettingsView.vue'),
    },
    {
      path: '/users',
      name: 'users',
      component: () => import('../views/UsersView.vue'),
    },
  ],
})

export default router

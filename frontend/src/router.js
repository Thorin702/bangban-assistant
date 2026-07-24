import { createRouter, createWebHashHistory } from 'vue-router'
import { store } from './store'

const routes = [
  { path: '/login', component: () => import('./views/LoginView.vue'), meta: { public: true } },
  { path: '/', component: () => import('./views/HomeView.vue') },
  { path: '/consult', component: () => import('./views/ConsultView.vue') },
  { path: '/history', component: () => import('./views/HistoryView.vue') },
  { path: '/history/:id', component: () => import('./views/HistoryDetailView.vue') },
  { path: '/admin', component: () => import('./views/AdminView.vue'), meta: { admin: true } },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

export const router = createRouter({ history: createWebHashHistory(), routes })

router.beforeEach((to) => {
  if (!to.meta.public && !store.token) return '/login'
  if (to.meta.admin && store.user?.role !== 'admin') return '/'
  if (to.meta.public && store.token && to.path === '/login') return '/'
})

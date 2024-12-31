import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import App from '../App.vue'
import Login from '../views/Login.vue'

const routes = [
  {
    path: '/',
    name: 'home',
    component: App,
    meta: { requiresAuth: true }
  },
  {
    path: '/login',
    name: 'login',
    component: Login,
    meta: { guest: true }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// Auth guard
router.beforeEach(async (to, from, next) => {
  const authStore = useAuthStore()
  const isAuthenticated = authStore.isAuthenticated

  // Auth gerektiren route'lar için kontrol
  if (to.matched.some(record => record.meta.requiresAuth)) {
    if (!isAuthenticated) {
      // Giriş yapılmamışsa login sayfasına yönlendir
      next({
        path: '/login',
        query: { redirect: to.fullPath }
      })
    } else {
      next()
    }
  } 
  // Sadece misafirler için olan route'lar (örn: login)
  else if (to.matched.some(record => record.meta.guest)) {
    if (isAuthenticated) {
      // Zaten giriş yapılmışsa ana sayfaya yönlendir
      next({ path: '/' })
    } else {
      next()
    }
  } else {
    next()
  }
})

export default router 
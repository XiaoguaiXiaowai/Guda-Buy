import type { RouteRecordRaw } from 'vue-router'
import { createRouter, createWebHistory } from 'vue-router'

import { useAuthStore } from '@/stores/auth'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'home',
    component: () => import('@/views/front/HomeView.vue'),
    meta: { title: '首页' },
  },
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/auth/LoginView.vue'),
    meta: { title: '登录', guestOnly: true },
  },
  {
    path: '/register',
    name: 'register',
    component: () => import('@/views/auth/RegisterView.vue'),
    meta: { title: '注册', guestOnly: true },
  },
  {
    path: '/forgot-password',
    name: 'forgot-password',
    component: () => import('@/views/auth/ForgotPasswordView.vue'),
    meta: { title: '找回密码', guestOnly: true },
  },
  {
    path: '/reset-password',
    name: 'reset-password',
    component: () => import('@/views/auth/ResetPasswordView.vue'),
    meta: { title: '重置密码' },
  },
  {
    path: '/user',
    redirect: '/user/profile',
  },
  {
    path: '/user/profile',
    name: 'user-profile',
    component: () => import('@/views/user/ProfileView.vue'),
    meta: { title: '个人资料', requiresAuth: true },
  },
  {
    path: '/user/addresses',
    name: 'user-addresses',
    component: () => import('@/views/user/AddressListView.vue'),
    meta: { title: '收货地址', requiresAuth: true },
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    component: () => import('@/views/front/NotFoundView.vue'),
    meta: { title: '页面不存在' },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior: () => ({ top: 0 }),
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()

  if (to.meta.requiresAuth) {
    const ready = await auth.ensureSession()
    if (!ready) {
      return { name: 'login', query: { redirect: to.fullPath } }
    }
  }

  if (to.meta.guestOnly && auth.isAuthenticated) {
    return { name: 'user-profile' }
  }

  return true
})

router.afterEach((to) => {
  const title = to.meta.title
  document.title = title ? `${String(title)} · GUDA 商城` : 'GUDA 商城'
})

export default router

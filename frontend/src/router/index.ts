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
    path: '/products',
    name: 'product-list',
    component: () => import('@/views/front/ProductListView.vue'),
    meta: { title: '商品' },
  },
  {
    path: '/category/:publicId',
    name: 'category-products',
    component: () => import('@/views/front/ProductListView.vue'),
    meta: { title: '分类商品' },
  },
  {
    path: '/product/:publicId',
    name: 'product-detail',
    component: () => import('@/views/front/ProductDetailView.vue'),
    meta: { title: '商品详情' },
  },
  {
    path: '/page/:slug',
    name: 'cms-page',
    component: () => import('@/views/front/CmsPageView.vue'),
    meta: { title: '内容页' },
  },
  {
    path: '/cart',
    name: 'cart',
    component: () => import('@/views/front/CartView.vue'),
    meta: { title: '购物车', requiresAuth: true },
  },
  {
    path: '/checkout',
    name: 'checkout',
    component: () => import('@/views/front/CheckoutView.vue'),
    meta: { title: '确认订单', requiresAuth: true },
  },
  {
    path: '/user/orders',
    name: 'user-orders',
    component: () => import('@/views/front/OrderListView.vue'),
    meta: { title: '我的订单', requiresAuth: true },
  },
  {
    path: '/user/orders/:orderNo',
    name: 'user-order-detail',
    component: () => import('@/views/front/OrderDetailView.vue'),
    meta: { title: '订单详情', requiresAuth: true },
  },
  {
    path: '/user/orders/:orderNo/review',
    name: 'user-order-review',
    component: () => import('@/views/front/ReviewFormView.vue'),
    meta: { title: '评价订单', requiresAuth: true },
  },
  {
    path: '/pay/:orderNo/result',
    name: 'payment-result',
    component: () => import('@/views/front/PaymentResultView.vue'),
    meta: { title: '支付结果', requiresAuth: true },
  },
  {
    path: '/pay/:orderNo',
    name: 'payment',
    component: () => import('@/views/front/PaymentView.vue'),
    meta: { title: '收银台', requiresAuth: true },
  },
  {
    path: '/support',
    name: 'support',
    component: () => import('@/views/front/SupportView.vue'),
    meta: { title: '在线客服', requiresAuth: true },
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
    path: '/user/coupons',
    name: 'user-coupons',
    component: () => import('@/views/user/CouponListView.vue'),
    meta: { title: '我的优惠券', requiresAuth: true },
  },
  {
    path: '/user/transactions',
    name: 'user-transactions',
    component: () => import('@/views/user/TransactionView.vue'),
    meta: { title: '交易记录', requiresAuth: true },
  },
  {
    path: '/user/notifications',
    name: 'user-notifications',
    component: () => import('@/views/user/NotificationListView.vue'),
    meta: { title: '消息中心', requiresAuth: true },
  },
  {
    path: '/admin',
    redirect: '/admin/products',
  },
  {
    path: '/admin/categories',
    name: 'admin-categories',
    component: () => import('@/views/admin/AdminCategoryView.vue'),
    meta: { title: '分类管理', requiresAuth: true, requiresCatalogAdmin: true },
  },
  {
    path: '/admin/products',
    name: 'admin-products',
    component: () => import('@/views/admin/AdminProductListView.vue'),
    meta: { title: '商品管理', requiresAuth: true, requiresCatalogAdmin: true },
  },
  {
    path: '/admin/products/new',
    name: 'admin-product-create',
    component: () => import('@/views/admin/AdminProductEditView.vue'),
    meta: { title: '新建商品', requiresAuth: true, requiresCatalogAdmin: true },
  },
  {
    path: '/admin/products/:publicId/edit',
    name: 'admin-product-edit',
    component: () => import('@/views/admin/AdminProductEditView.vue'),
    meta: { title: '编辑商品', requiresAuth: true, requiresCatalogAdmin: true },
  },
  {
    path: '/admin/cms',
    name: 'admin-cms',
    component: () => import('@/views/admin/AdminCmsView.vue'),
    meta: { title: '内容运营', requiresAuth: true, requiresCmsAdmin: true },
  },
  {
    path: '/admin/coupons',
    name: 'admin-coupons',
    component: () => import('@/views/admin/AdminCouponView.vue'),
    meta: { title: '优惠券管理', requiresAuth: true, requiresCatalogAdmin: true },
  },
  {
    path: '/admin/reviews',
    name: 'admin-reviews',
    component: () => import('@/views/admin/AdminReviewView.vue'),
    meta: { title: '评价审核', requiresAuth: true, requiresCatalogAdmin: true },
  },
  {
    path: '/admin/support',
    name: 'admin-support',
    component: () => import('@/views/admin/AdminSupportView.vue'),
    meta: { title: '客服工作台', requiresAuth: true, requiresSupportStaff: true },
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

  if ((to.meta.requiresCatalogAdmin || to.meta.requiresCmsAdmin) && !auth.isCatalogStaff) {
    return { name: 'home' }
  }

  if (to.meta.requiresSupportStaff && !auth.isSupportStaff) {
    return { name: 'home' }
  }

  return true
})

router.afterEach((to) => {
  const title = to.meta.title
  document.title = title ? `${String(title)} · GUDA 商城` : 'GUDA 商城'
})

export default router

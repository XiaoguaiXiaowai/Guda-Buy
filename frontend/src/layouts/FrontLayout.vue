<script setup lang="ts">
import { onBeforeUnmount, onMounted, watch } from 'vue'
import { RouterLink, RouterView, useRouter } from 'vue-router'

import { useAuthStore } from '@/stores/auth'
import { useCartStore } from '@/stores/cart'
import { useNotificationStore } from '@/stores/notification'

const router = useRouter()
const auth = useAuthStore()
const cart = useCartStore()
const notifications = useNotificationStore()

async function handleAccountCommand(command: string) {
  if (command === 'logout') {
    await auth.logout()
    cart.reset()
    notifications.reset()
    notifications.stopPolling()
    await router.push('/')
    return
  }
  await router.push(command)
}

onMounted(() => {
  if (auth.isAuthenticated) {
    void cart.refreshCount()
    notifications.startPolling()
  }
})

onBeforeUnmount(() => {
  notifications.stopPolling()
})

watch(
  () => auth.isAuthenticated,
  (authenticated) => {
    if (authenticated) {
      void cart.refreshCount()
      notifications.startPolling()
    } else {
      cart.reset()
      notifications.reset()
      notifications.stopPolling()
    }
  },
)
</script>

<template>
  <div class="front-layout">
    <header class="front-layout__header">
      <div class="front-layout__inner">
        <RouterLink class="front-layout__brand" to="/">GUDA</RouterLink>
        <nav class="front-layout__nav" aria-label="主导航">
          <RouterLink to="/">首页</RouterLink>
          <RouterLink to="/products">商品</RouterLink>
          <RouterLink to="/cart" class="front-layout__cart">
            购物车
            <el-badge
              v-if="cart.totalQuantity"
              class="front-layout__badge"
              :value="cart.totalQuantity"
              :max="99"
            />
          </RouterLink>
          <RouterLink to="/user/notifications" class="front-layout__messages">
            消息
            <el-badge
              v-if="notifications.unreadCount"
              class="front-layout__badge"
              :value="notifications.unreadCount"
              :max="99"
            />
          </RouterLink>
          <RouterLink to="/user/profile">我的</RouterLink>
        </nav>

        <el-dropdown
          v-if="auth.isAuthenticated"
          class="front-layout__account"
          @command="handleAccountCommand"
        >
          <span class="front-layout__user">
            <el-avatar :size="28" :src="auth.user?.avatar ?? undefined">
              {{ auth.user?.nickname?.slice(0, 1) ?? 'G' }}
            </el-avatar>
            <span class="front-layout__nickname">{{ auth.user?.nickname }}</span>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="/user/profile">个人资料</el-dropdown-item>
              <el-dropdown-item command="/user/orders">我的订单</el-dropdown-item>
              <el-dropdown-item command="/user/transactions">交易记录</el-dropdown-item>
              <el-dropdown-item command="/user/coupons">我的优惠券</el-dropdown-item>
              <el-dropdown-item command="/user/addresses">收货地址</el-dropdown-item>
              <el-dropdown-item command="/user/notifications">消息中心</el-dropdown-item>
              <el-dropdown-item v-if="auth.isCatalogStaff" command="/admin/products" divided>
                商品后台
              </el-dropdown-item>
              <el-dropdown-item v-if="auth.isCatalogStaff" command="/admin/cms">
                内容后台
              </el-dropdown-item>
              <el-dropdown-item v-if="auth.isCatalogStaff" command="/admin/coupons">
                优惠券后台
              </el-dropdown-item>
              <el-dropdown-item v-if="auth.isCatalogStaff" command="/admin/reviews">
                评价审核后台
              </el-dropdown-item>
              <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>

        <div v-else class="front-layout__guest">
          <RouterLink class="front-layout__login" to="/login">登录</RouterLink>
          <RouterLink class="front-layout__register" to="/register">注册</RouterLink>
        </div>
      </div>
    </header>

    <main class="front-layout__main">
      <RouterView />
    </main>

    <footer class="front-layout__footer">
      <div class="front-layout__inner">
        <span>GUDA 在线电商网站 · 演示项目</span>
        <span>Vue 3 + Vite + Django 5.2 + DRF</span>
      </div>
    </footer>
  </div>
</template>

<style scoped lang="scss">
.front-layout {
  min-height: 100vh;
  display: flex;
  flex-direction: column;

  &__header {
    border-bottom: 1px solid var(--guda-border);
    background: var(--guda-surface);
    position: sticky;
    top: 0;
    z-index: 10;
  }

  &__inner {
    width: min(1200px, calc(100% - 48px));
    margin: 0 auto;
    display: flex;
    align-items: center;
    gap: 32px;
    min-height: 64px;
  }

  &__brand {
    font-size: 20px;
    font-weight: 700;
    letter-spacing: 2px;
    color: var(--guda-primary);
    text-decoration: none;
  }

  &__nav {
    display: flex;
    gap: 24px;
    font-size: 14px;

    a {
      color: var(--guda-text);
      text-decoration: none;

      &:hover,
      &.router-link-active {
        color: var(--guda-primary);
      }
    }
  }

  &__cart {
    display: inline-flex;
    align-items: center;
    gap: 8px;
  }

  &__messages {
    display: inline-flex;
    align-items: center;
    gap: 8px;
  }

  &__badge {
    line-height: 1;

    :deep(.el-badge__content) {
      border: none;
    }
  }

  &__account {
    margin-left: auto;
    cursor: pointer;
  }

  &__user {
    display: flex;
    align-items: center;
    gap: 8px;
    outline: none;
  }

  &__nickname {
    font-size: 14px;
    max-width: 120px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  &__guest {
    margin-left: auto;
    display: flex;
    align-items: center;
    gap: 12px;
    font-size: 14px;
  }

  &__login {
    color: var(--guda-text);
    text-decoration: none;
  }

  &__register {
    color: #fff;
    background: var(--guda-primary);
    padding: 6px 14px;
    border-radius: 999px;
    text-decoration: none;

    &:hover {
      opacity: 0.9;
    }
  }

  &__main {
    flex: 1;
    width: min(1200px, calc(100% - 48px));
    margin: 0 auto;
    padding: 40px 0 64px;
  }

  &__footer {
    border-top: 1px solid var(--guda-border);
    color: var(--guda-text-muted);
    font-size: 13px;

    .front-layout__inner {
      min-height: 64px;
      justify-content: space-between;
      gap: 16px;
      flex-wrap: wrap;
    }
  }
}

@media (max-width: 767px) {
  .front-layout {
    &__inner {
      width: calc(100% - 32px);
      gap: 16px;
    }

    &__nav {
      gap: 12px;
    }

    &__main {
      width: calc(100% - 32px);
      padding: 24px 0 40px;
    }
  }
}
</style>

<script setup lang="ts">
import { RouterLink, RouterView, useRouter } from 'vue-router'

import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()

async function handleAccountCommand(command: string) {
  if (command === 'logout') {
    await auth.logout()
    await router.push('/')
    return
  }
  await router.push(command)
}
</script>

<template>
  <div class="front-layout">
    <header class="front-layout__header">
      <div class="front-layout__inner">
        <RouterLink class="front-layout__brand" to="/">GUDA</RouterLink>
        <nav class="front-layout__nav" aria-label="主导航">
          <RouterLink to="/">首页</RouterLink>
          <span class="front-layout__nav-disabled">商品</span>
          <span class="front-layout__nav-disabled">购物车</span>
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
              <el-dropdown-item command="/user/addresses">收货地址</el-dropdown-item>
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

  &__nav-disabled {
    color: var(--guda-text-muted);
    cursor: not-allowed;
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

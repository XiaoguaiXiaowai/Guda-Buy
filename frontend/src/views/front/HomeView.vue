<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { fetchHealth, type HealthStatus } from '@/api/health'

const health = ref<HealthStatus | null>(null)
const healthLoading = ref(true)
const healthFailed = ref(false)

const baselineItems = [
  '邮箱验证码注册与登录锁定保护',
  'JWT 访问令牌 + HttpOnly Refresh 轮换',
  '个人信息、头像上传与资料修改',
  '收货地址增删改查与默认地址',
  '未登录拦截与页面刷新后静默恢复登录',
]

onMounted(async () => {
  try {
    health.value = await fetchHealth()
  } catch {
    healthFailed.value = true
  } finally {
    healthLoading.value = false
  }
})
</script>

<template>
  <section class="home">
    <div class="home__hero">
      <p class="home__eyebrow">GUDA 在线电商网站</p>
      <h1 class="home__title">会员账号体系就绪</h1>
      <p class="home__desc">
        迭代 I1 已交付注册登录、JWT 静默刷新、个人资料与收货地址管理，后续商品、购物车与订单能力将在此之上叠加。
      </p>
    </div>

    <div class="home__grid">
      <div class="home__card">
        <h2 class="home__card-title">后端健康检查</h2>
        <div v-if="healthLoading" class="home__status">检测中…</div>
        <div v-else-if="health" class="home__checks">
          <span class="home__check home__check--ok">数据库 {{ health.db }}</span>
          <span class="home__check home__check--ok">Redis {{ health.redis }}</span>
        </div>
        <div v-else-if="healthFailed" class="home__checks">
          <span class="home__check home__check--fail">后端未启动或依赖不可用</span>
        </div>
        <p class="home__hint">GET /healthz/ · 依赖异常时返回 503 COMMON_SERVICE_UNAVAILABLE</p>
      </div>

      <div class="home__card">
        <h2 class="home__card-title">本迭代已交付</h2>
        <ul class="home__list">
          <li v-for="item in baselineItems" :key="item">{{ item }}</li>
        </ul>
      </div>

      <div class="home__card">
        <h2 class="home__card-title">下一步</h2>
        <p class="home__desc home__desc--small">
          迭代 I2 将交付商品目录与检索：分类树、商品列表/详情、SKU 与库存展示。点击右上角登录或注册即可体验会员功能。
        </p>
      </div>
    </div>
  </section>
</template>

<style scoped lang="scss">
.home {
  &__hero {
    padding: 32px 0 40px;
    max-width: 720px;
  }

  &__eyebrow {
    color: var(--guda-primary);
    font-size: 13px;
    letter-spacing: 3px;
    text-transform: uppercase;
    margin-bottom: 12px;
  }

  &__title {
    font-size: 40px;
    line-height: 1.2;
    margin-bottom: 16px;
  }

  &__desc {
    color: var(--guda-text-muted);
    line-height: 1.8;

    &--small {
      font-size: 14px;
    }
  }

  &__grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 20px;
  }

  &__card {
    background: var(--guda-surface);
    border: 1px solid var(--guda-border);
    border-radius: var(--guda-radius);
    padding: 24px;
    min-height: 180px;
  }

  &__card-title {
    font-size: 16px;
    margin-bottom: 16px;
  }

  &__status {
    color: var(--guda-text-muted);
  }

  &__checks {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }

  &__check {
    font-size: 13px;
    padding: 4px 10px;
    border-radius: 999px;

    &--ok {
      color: var(--guda-success);
      background: #ecfdf3;
    }

    &--fail {
      color: var(--guda-danger);
      background: #fef2f2;
    }
  }

  &__hint {
    margin-top: 16px;
    font-size: 12px;
    line-height: 1.6;
    color: var(--guda-text-muted);
  }

  &__list {
    margin: 0;
    padding-left: 18px;
    color: var(--guda-text-muted);
    font-size: 14px;
    line-height: 2;
  }
}

@media (max-width: 991px) {
  .home__grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 767px) {
  .home {
    &__title {
      font-size: 30px;
    }

    &__grid {
      grid-template-columns: 1fr;
    }
  }
}
</style>

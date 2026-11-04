<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { fetchHealth, type HealthStatus } from '@/api/health'

const health = ref<HealthStatus | null>(null)
const healthLoading = ref(true)
const healthFailed = ref(false)

const baselineItems = [
  '统一响应体与五类异常结构',
  'X-Request-ID 与 JSON 结构化日志',
  '/healthz/ 依赖探活（DB + Redis）',
  'OpenAPI 契约与 Swagger UI',
  'Vue 3 + TS + Pinia + Router + Axios 骨架',
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
      <h1 class="home__title">工程基线就绪</h1>
      <p class="home__desc">
        迭代 I0 已搭建前端与后端的最小可运行骨架，后续商品、购物车、订单与支付能力将在此之上叠加。
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
          迭代 I1 将交付会员账号体系：注册登录、JWT 刷新、地址管理与个人中心。当前页面会在该迭代接入真实导航与登录入口。
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

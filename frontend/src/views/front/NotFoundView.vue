<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()
</script>

<template>
  <section class="not-found">
    <p class="not-found__code">404</p>
    <h1 class="not-found__title">页面不存在</h1>
    <p class="not-found__desc">访问的地址可能已被移除或输入有误。</p>
    <el-button type="primary" @click="router.push('/')">返回首页</el-button>
  </section>
</template>

<style scoped lang="scss">
.not-found {
  padding: 80px 0;
  text-align: center;

  &__code {
    font-size: 72px;
    font-weight: 700;
    color: var(--guda-primary);
  }

  &__title {
    font-size: 22px;
    margin: 8px 0 12px;
  }

  &__desc {
    color: var(--guda-text-muted);
    margin-bottom: 24px;
  }
}
</style>

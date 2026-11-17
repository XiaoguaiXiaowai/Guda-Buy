<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import { fetchCmsPage } from '@/api/cms'
import type { CmsPage } from '@/types/cms'
import { formatDateTime } from '@/utils/format'

const route = useRoute()
const page = ref<CmsPage | null>(null)
const loading = ref(true)
const notFound = ref(false)

const slug = computed(() => String(route.params.slug ?? ''))

async function load() {
  loading.value = true
  notFound.value = false
  page.value = null
  try {
    page.value = await fetchCmsPage(slug.value)
  } catch {
    notFound.value = true
  } finally {
    loading.value = false
  }
}

watch(
  slug,
  () => {
    if (slug.value) {
      void load()
    }
  },
  { immediate: true },
)
</script>

<template>
  <section class="cms-page">
    <el-skeleton v-if="loading" :rows="8" animated />

    <el-result
      v-else-if="notFound"
      icon="warning"
      title="页面不存在或未发布"
      sub-title="内容可能尚未发布，或已下线。"
    >
      <template #extra>
        <RouterLink class="cms-page__back" to="/">返回首页</RouterLink>
      </template>
    </el-result>

    <article v-else-if="page" class="cms-page__article">
      <nav class="cms-page__breadcrumb">
        <RouterLink to="/">首页</RouterLink>
        <span>/</span>
        <span>{{ page.section.name }}</span>
      </nav>
      <h1 class="cms-page__title">{{ page.title }}</h1>
      <p class="cms-page__meta">发布于 {{ formatDateTime(page.published_at) }}</p>
      <!-- 正文由服务端白名单清洗后返回，前端直接渲染 -->
      <!-- eslint-disable-next-line vue/no-v-html -->
      <div class="cms-page__content" v-html="page.content" />
    </article>
  </section>
</template>

<style scoped lang="scss">
.cms-page {
  max-width: 820px;

  &__breadcrumb {
    display: flex;
    gap: 8px;
    color: var(--guda-text-muted);
    font-size: 13px;
    margin-bottom: 18px;

    a {
      color: var(--guda-text-muted);
      text-decoration: none;

      &:hover {
        color: var(--guda-primary);
      }
    }
  }

  &__title {
    font-size: 34px;
    line-height: 1.3;
    margin-bottom: 10px;
  }

  &__meta {
    color: var(--guda-text-muted);
    font-size: 13px;
    padding-bottom: 20px;
    border-bottom: 1px solid var(--guda-border);
    margin-bottom: 24px;
  }

  &__content {
    line-height: 1.9;
    font-size: 15px;

    :deep(h2) {
      font-size: 22px;
      margin: 28px 0 12px;
    }

    :deep(h3) {
      font-size: 18px;
      margin: 22px 0 10px;
    }

    :deep(p) {
      margin: 0 0 14px;
    }

    :deep(ul),
    :deep(ol) {
      padding-left: 22px;
      margin-bottom: 14px;
    }

    :deep(img) {
      max-width: 100%;
      border-radius: var(--guda-radius);
    }

    :deep(a) {
      color: var(--guda-primary);
    }

    :deep(table) {
      width: 100%;
      border-collapse: collapse;
      margin-bottom: 16px;

      th,
      td {
        border: 1px solid var(--guda-border);
        padding: 8px 12px;
      }
    }
  }

  &__back {
    color: #fff;
    background: var(--guda-primary);
    padding: 8px 20px;
    border-radius: 999px;
    text-decoration: none;
  }
}
</style>

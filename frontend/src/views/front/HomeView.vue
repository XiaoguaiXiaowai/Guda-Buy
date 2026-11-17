<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { fetchCmsHome } from '@/api/cms'
import { fetchHealth, type HealthStatus } from '@/api/health'
import type { CmsHome } from '@/types/cms'
import { formatPriceRange, resolveImageUrl } from '@/utils/catalog'
import { announcementLevelLabel, announcementLevelTone } from '@/utils/cms'

const router = useRouter()

const home = ref<CmsHome | null>(null)
const health = ref<HealthStatus | null>(null)
const loading = ref(true)

onMounted(async () => {
  try {
    home.value = await fetchCmsHome()
  } catch {
    home.value = null
  } finally {
    loading.value = false
  }
  try {
    health.value = await fetchHealth()
  } catch {
    health.value = null
  }
})

function openProduct(publicId: string) {
  void router.push(`/product/${publicId}`)
}
</script>

<template>
  <section class="home">
    <div class="home__hero">
      <p class="home__eyebrow">GUDA 在线电商网站</p>
      <h1 class="home__title">精选好物，一站购齐</h1>
      <p class="home__desc">浏览在售商品与品牌内容，运营可通过内容后台维护首页轮播、公告与页面。</p>
      <div class="home__cta">
        <RouterLink class="home__cta-primary" to="/products">浏览商品</RouterLink>
        <RouterLink class="home__cta-link" to="/user/profile">进入我的</RouterLink>
      </div>
    </div>

    <el-skeleton v-if="loading" class="home__skeleton" :rows="5" animated />

    <template v-else>
      <!-- 轮播 -->
      <section v-if="home?.banners.length" class="home__block">
        <el-carousel class="home__carousel" height="320px" :interval="5000" arrow="hover">
          <el-carousel-item v-for="banner in home.banners" :key="banner.public_id">
            <RouterLink
              v-if="banner.link_url.startsWith('/')"
              class="home__banner"
              :to="banner.link_url"
            >
              <img :src="resolveImageUrl(banner.image)" :alt="banner.title || '轮播'" />
            </RouterLink>
            <a
              v-else-if="banner.link_url"
              class="home__banner"
              :href="banner.link_url"
              target="_blank"
              rel="noopener noreferrer"
            >
              <img :src="resolveImageUrl(banner.image)" :alt="banner.title || '轮播'" />
            </a>
            <div v-else class="home__banner">
              <img :src="resolveImageUrl(banner.image)" :alt="banner.title || '轮播'" />
            </div>
          </el-carousel-item>
        </el-carousel>
      </section>

      <!-- 公告 -->
      <section v-if="home?.announcements.length" class="home__block home__announcements">
        <div class="home__block-header">
          <h2>公告</h2>
        </div>
        <ul class="home__announcement-list">
          <li v-for="item in home.announcements" :key="item.public_id">
            <el-tag :type="announcementLevelTone(item.level)" effect="plain" size="small">
              {{ announcementLevelLabel(item.level) }}
            </el-tag>
            <div class="home__announcement-body">
              <strong>{{ item.title }}</strong>
              <p v-if="item.content">{{ item.content }}</p>
            </div>
          </li>
        </ul>
      </section>

      <!-- 推荐商品 -->
      <section v-if="home?.recommended_products.length" class="home__block">
        <div class="home__block-header">
          <h2>热门推荐</h2>
          <RouterLink class="home__more" to="/products">查看全部</RouterLink>
        </div>
        <div class="home__product-grid">
          <article
            v-for="product in home.recommended_products"
            :key="product.public_id"
            class="home__product"
            @click="openProduct(product.public_id)"
          >
            <div class="home__product-media">
              <img
                v-if="product.main_image"
                :src="resolveImageUrl(product.main_image)"
                :alt="product.name"
                loading="lazy"
              />
              <span v-else class="home__product-placeholder">{{ product.name.slice(0, 1) }}</span>
            </div>
            <div class="home__product-body">
              <p class="home__product-category">{{ product.category.name }}</p>
              <h3>{{ product.name }}</h3>
              <div class="home__product-footer">
                <strong>{{ formatPriceRange(product.price_min, product.price_max) }}</strong>
                <span>已售 {{ product.sales_count }}</span>
              </div>
            </div>
          </article>
        </div>
      </section>
    </template>

    <p v-if="health" class="home__health">
      服务状态：数据库 {{ health.db }} · Redis {{ health.redis }}
    </p>
  </section>
</template>

<style scoped lang="scss">
.home {
  &__hero {
    padding: 8px 0 32px;
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
  }

  &__cta {
    display: flex;
    align-items: center;
    gap: 16px;
    margin-top: 22px;
    font-size: 14px;
  }

  &__cta-primary {
    background: var(--guda-primary);
    color: #fff;
    padding: 10px 22px;
    border-radius: 999px;
    text-decoration: none;

    &:hover {
      opacity: 0.9;
    }
  }

  &__cta-link {
    color: var(--guda-text);

    &:hover {
      color: var(--guda-primary);
    }
  }

  &__skeleton {
    margin: 12px 0 24px;
  }

  &__block {
    margin-bottom: 40px;
  }

  &__block-header {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    margin-bottom: 16px;

    h2 {
      font-size: 22px;
    }
  }

  &__more {
    color: var(--guda-text-muted);
    font-size: 13px;
    text-decoration: none;

    &:hover {
      color: var(--guda-primary);
    }
  }

  &__carousel {
    border-radius: var(--guda-radius);
    overflow: hidden;
  }

  &__banner {
    display: block;
    width: 100%;
    height: 100%;

    img {
      width: 100%;
      height: 100%;
      object-fit: cover;
      display: block;
    }
  }

  &__announcements {
    background: var(--guda-surface);
    border: 1px solid var(--guda-border);
    border-radius: var(--guda-radius);
    padding: 20px 24px;
  }

  &__announcement-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 12px;

    li {
      display: flex;
      align-items: flex-start;
      gap: 12px;
    }
  }

  &__announcement-body {
    font-size: 14px;
    line-height: 1.6;

    p {
      color: var(--guda-text-muted);
      margin-top: 2px;
    }
  }

  &__product-grid {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 20px;
  }

  &__product {
    background: var(--guda-surface);
    border: 1px solid var(--guda-border);
    border-radius: var(--guda-radius);
    overflow: hidden;
    cursor: pointer;
    transition:
      transform 0.2s ease,
      box-shadow 0.2s ease;

    &:hover {
      transform: translateY(-2px);
      box-shadow: 0 8px 24px rgb(31 35 40 / 8%);
    }
  }

  &__product-media {
    aspect-ratio: 1 / 1;
    background: var(--guda-bg);

    img {
      width: 100%;
      height: 100%;
      object-fit: cover;
      display: block;
    }
  }

  &__product-placeholder {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 100%;
    color: var(--guda-text-muted);
    font-size: 32px;
  }

  &__product-body {
    padding: 14px 16px 16px;

    h3 {
      font-size: 15px;
      margin: 4px 0 10px;
      line-height: 1.4;
    }
  }

  &__product-category {
    color: var(--guda-text-muted);
    font-size: 12px;
  }

  &__product-footer {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    font-size: 13px;

    strong {
      color: var(--guda-danger);
      font-size: 16px;
    }

    span {
      color: var(--guda-text-muted);
    }
  }

  &__health {
    margin-top: 8px;
    color: var(--guda-text-muted);
    font-size: 12px;
  }
}

@media (max-width: 991px) {
  .home__product-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 767px) {
  .home {
    &__title {
      font-size: 30px;
    }

    &__product-grid {
      grid-template-columns: 1fr;
    }
  }
}
</style>

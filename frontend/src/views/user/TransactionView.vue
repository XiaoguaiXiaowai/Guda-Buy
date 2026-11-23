<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import { fetchOrders, fetchOrderSummary } from '@/api/order'
import type { OrderBrief, OrderSummary } from '@/types/order'
import { resolveImageUrl } from '@/utils/catalog'
import { formatCurrency, formatDateTime } from '@/utils/format'
import { orderStatusLabel, orderStatusTone } from '@/utils/order'

const summary = ref<OrderSummary | null>(null)
const orders = ref<OrderBrief[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(10)
const loading = ref(true)
const failed = ref(false)

const cards = computed(() => {
  const counts = summary.value?.counts ?? {}
  const amounts = summary.value?.amounts ?? {}
  return [
    { key: 'ALL', label: '全部订单', count: counts.ALL ?? 0, amount: amounts.ALL ?? '0.00' },
    {
      key: 'PENDING_PAYMENT',
      label: '待支付',
      count: counts.PENDING_PAYMENT ?? 0,
      amount: amounts.PENDING_PAYMENT ?? '0.00',
    },
    { key: 'PAID', label: '已支付', count: counts.PAID ?? 0, amount: amounts.PAID ?? '0.00' },
    {
      key: 'SHIPPED',
      label: '已发货',
      count: counts.SHIPPED ?? 0,
      amount: amounts.SHIPPED ?? '0.00',
    },
    {
      key: 'COMPLETED',
      label: '已完成',
      count: counts.COMPLETED ?? 0,
      amount: amounts.COMPLETED ?? '0.00',
    },
  ]
})

async function load(): Promise<void> {
  loading.value = true
  failed.value = false
  try {
    const [summaryData, pageData] = await Promise.all([
      fetchOrderSummary(),
      fetchOrders({ page: page.value, page_size: pageSize.value }),
    ])
    summary.value = summaryData
    orders.value = pageData.results
    total.value = pageData.count
  } catch {
    failed.value = true
  } finally {
    loading.value = false
  }
}

function changePage(value: number): void {
  page.value = value
  void load()
}

onMounted(() => {
  void load()
})
</script>

<template>
  <section class="transactions">
    <header class="transactions__header">
      <div>
        <h1>交易记录</h1>
        <p>按订单状态汇总数量与金额，点击单条可进入订单详情。</p>
      </div>
      <nav class="user-tabs" aria-label="个人中心导航">
        <RouterLink to="/user/profile">个人资料</RouterLink>
        <RouterLink to="/user/addresses">收货地址</RouterLink>
        <RouterLink to="/user/orders">我的订单</RouterLink>
        <RouterLink to="/user/transactions">交易记录</RouterLink>
        <RouterLink to="/user/notifications">消息中心</RouterLink>
      </nav>
    </header>

    <el-skeleton v-if="loading" class="transactions__skeleton" :rows="5" animated />

    <el-result
      v-else-if="failed"
      icon="warning"
      title="交易记录加载失败"
      sub-title="请检查网络后重试。"
    >
      <template #extra>
        <el-button type="primary" @click="load">重新加载</el-button>
      </template>
    </el-result>

    <template v-else>
      <div class="transactions__summary">
        <div v-for="card in cards" :key="card.key" class="summary-card">
          <span class="summary-card__label">{{ card.label }}</span>
          <strong class="summary-card__count">{{ card.count }}</strong>
          <span class="summary-card__amount">{{ formatCurrency(card.amount) }}</span>
        </div>
        <div class="summary-card summary-card--paid">
          <span class="summary-card__label">累计支付</span>
          <strong class="summary-card__count">
            {{ formatCurrency(summary?.paid_amount ?? '0.00') }}
          </strong>
          <span class="summary-card__amount">已支付 / 已发货 / 已完成</span>
        </div>
      </div>

      <el-empty v-if="!orders.length" description="暂无交易记录">
        <RouterLink to="/products">
          <el-button type="primary">去逛逛</el-button>
        </RouterLink>
      </el-empty>

      <template v-else>
        <div class="transactions__list">
          <RouterLink
            v-for="order in orders"
            :key="order.order_no"
            class="transaction-row"
            :to="`/user/orders/${order.order_no}`"
          >
            <div class="transaction-row__goods">
              <div class="transaction-row__media">
                <img
                  v-if="order.items[0]?.main_image"
                  :src="resolveImageUrl(order.items[0].main_image)"
                  :alt="order.items[0].product_name"
                  loading="lazy"
                />
                <span v-else>{{ order.items[0]?.product_name.slice(0, 1) ?? '订' }}</span>
              </div>
              <div class="transaction-row__info">
                <strong>{{ order.items[0]?.product_name ?? '订单商品' }}</strong>
                <span>{{ order.order_no }} · 共 {{ order.total_quantity }} 件</span>
              </div>
            </div>
            <span class="transaction-row__time">{{ formatDateTime(order.created_at) }}</span>
            <el-tag :type="orderStatusTone(order.status)" effect="light">
              {{ orderStatusLabel(order.status, order.status_text) }}
            </el-tag>
            <strong class="transaction-row__amount">
              {{ formatCurrency(order.payable_amount) }}
            </strong>
          </RouterLink>
        </div>

        <el-pagination
          v-if="total > pageSize"
          class="transactions__pagination"
          layout="prev, pager, next"
          :current-page="page"
          :page-size="pageSize"
          :total="total"
          @current-change="changePage"
        />
      </template>
    </template>
  </section>
</template>

<style scoped lang="scss">
.transactions {
  &__header {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    gap: 16px;
    margin-bottom: 20px;

    h1 {
      font-size: 26px;
      margin-bottom: 6px;
    }

    p {
      color: var(--guda-text-muted);
      font-size: 13px;
    }
  }

  &__summary {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 12px;
    margin-bottom: 24px;
  }

  &__list {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  &__pagination {
    margin-top: 24px;
    justify-content: flex-end;
  }

  &__skeleton {
    padding: 24px;
    background: var(--guda-surface);
    border: 1px solid var(--guda-border);
    border-radius: var(--guda-radius);
  }
}

.summary-card {
  background: var(--guda-surface);
  border: 1px solid var(--guda-border);
  border-radius: var(--guda-radius);
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 4px;

  &--paid {
    border-color: var(--guda-primary);
  }

  &__label {
    font-size: 12px;
    color: var(--guda-text-muted);
  }

  &__count {
    font-size: 22px;
    color: var(--guda-text);
  }

  &__amount {
    font-size: 12px;
    color: var(--guda-text-muted);
  }
}

.transaction-row {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 14px 18px;
  background: var(--guda-surface);
  border: 1px solid var(--guda-border);
  border-radius: var(--guda-radius);
  color: inherit;
  text-decoration: none;
  transition: border-color 0.2s ease;

  &:hover {
    border-color: var(--guda-primary);
  }

  &__goods {
    display: flex;
    align-items: center;
    gap: 12px;
    min-width: 0;
    flex: 1;
  }

  &__media {
    width: 48px;
    height: 48px;
    border-radius: 8px;
    overflow: hidden;
    background: var(--guda-bg-muted);
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--guda-text-muted);
    flex-shrink: 0;

    img {
      width: 100%;
      height: 100%;
      object-fit: cover;
    }
  }

  &__info {
    display: flex;
    flex-direction: column;
    gap: 4px;
    min-width: 0;

    strong {
      font-size: 14px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    span {
      font-size: 12px;
      color: var(--guda-text-muted);
    }
  }

  &__time {
    font-size: 12px;
    color: var(--guda-text-muted);
    min-width: 140px;
  }

  &__amount {
    font-size: 15px;
    min-width: 80px;
    text-align: right;
  }
}

.user-tabs {
  display: flex;
  gap: 20px;
  font-size: 14px;
  flex-wrap: wrap;

  a {
    color: var(--guda-text-muted);
    text-decoration: none;
    padding-bottom: 4px;
    border-bottom: 2px solid transparent;

    &.router-link-active {
      color: var(--guda-primary);
      border-color: var(--guda-primary);
    }
  }
}

@media (max-width: 768px) {
  .transaction-row {
    flex-wrap: wrap;

    &__time {
      min-width: 0;
    }
  }
}
</style>

<script setup lang="ts">
import { ElMessage, ElMessageBox } from 'element-plus'
import { onMounted, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'

import { cancelOrder, confirmOrder, fetchOrders } from '@/api/order'
import type { OrderBrief, OrderStatus } from '@/types/order'
import { resolveImageUrl } from '@/utils/catalog'
import { formatCurrency, formatDateTime } from '@/utils/format'
import { ORDER_STATUS_TABS, orderStatusLabel, orderStatusTone } from '@/utils/order'

const router = useRouter()
const orders = ref<OrderBrief[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(10)
const activeStatus = ref<OrderStatus | ''>('')
const loading = ref(true)
const failed = ref(false)
const mutatingNo = ref('')

async function load(): Promise<void> {
  loading.value = true
  failed.value = false
  try {
    const data = await fetchOrders({
      status: activeStatus.value || undefined,
      page: page.value,
      page_size: pageSize.value,
    })
    orders.value = data.results
    total.value = data.count
  } catch {
    orders.value = []
    failed.value = true
  } finally {
    loading.value = false
  }
}

function switchStatus(status: OrderStatus | ''): void {
  if (activeStatus.value === status) {
    return
  }
  activeStatus.value = status
  page.value = 1
  void load()
}

function changePage(value: number): void {
  page.value = value
  void load()
}

async function pay(order: OrderBrief): Promise<void> {
  await router.push({ name: 'payment', params: { orderNo: order.order_no } })
}

async function cancel(order: OrderBrief): Promise<void> {
  const confirmed = await ElMessageBox.confirm(
    `确认取消订单 ${order.order_no}？取消后库存将立即释放。`,
    '取消订单',
    { type: 'warning', confirmButtonText: '取消订单', cancelButtonText: '再想想' },
  ).catch(() => false)
  if (!confirmed) {
    return
  }
  mutatingNo.value = order.order_no
  try {
    await cancelOrder(order.order_no)
    ElMessage.success('订单已取消')
    await load()
  } finally {
    mutatingNo.value = ''
  }
}

async function confirmReceipt(order: OrderBrief): Promise<void> {
  const confirmed = await ElMessageBox.confirm(
    `确认已收到订单 ${order.order_no} 的商品？确认后订单将完成。`,
    '确认收货',
    { confirmButtonText: '确认收货', cancelButtonText: '取消' },
  ).catch(() => false)
  if (!confirmed) {
    return
  }
  mutatingNo.value = order.order_no
  try {
    await confirmOrder(order.order_no)
    ElMessage.success('已确认收货')
    await load()
  } finally {
    mutatingNo.value = ''
  }
}

onMounted(() => {
  void load()
})
</script>

<template>
  <section class="orders">
    <header class="orders__header">
      <div>
        <h1>我的订单</h1>
        <p>支付、发货与确认收货状态实时同步。</p>
      </div>
      <nav class="user-tabs" aria-label="个人中心导航">
        <RouterLink to="/user/profile">个人资料</RouterLink>
        <RouterLink to="/user/addresses">收货地址</RouterLink>
        <RouterLink to="/user/orders">我的订单</RouterLink>
      </nav>
    </header>

    <div class="order-tabs" role="tablist">
      <button
        v-for="tab in ORDER_STATUS_TABS"
        :key="tab.value || 'all'"
        type="button"
        role="tab"
        class="order-tabs__item"
        :class="{ 'is-active': activeStatus === tab.value }"
        :aria-selected="activeStatus === tab.value"
        @click="switchStatus(tab.value)"
      >
        {{ tab.label }}
      </button>
    </div>

    <el-skeleton v-if="loading" class="orders__skeleton" :rows="8" animated />

    <el-result
      v-else-if="failed"
      icon="warning"
      title="订单加载失败"
      sub-title="请检查网络后重试。"
    >
      <template #extra>
        <el-button type="primary" @click="load">重新加载</el-button>
      </template>
    </el-result>

    <el-empty v-else-if="!orders.length" description="暂无订单">
      <RouterLink to="/products">
        <el-button type="primary">去逛逛</el-button>
      </RouterLink>
    </el-empty>

    <template v-else>
      <div class="orders__list">
        <article v-for="order in orders" :key="order.order_no" class="order-card">
          <header class="order-card__header">
            <div class="order-card__meta">
              <span class="order-card__no">{{ order.order_no }}</span>
              <span class="order-card__time">{{ formatDateTime(order.created_at) }}</span>
            </div>
            <el-tag :type="orderStatusTone(order.status)" effect="light">
              {{ orderStatusLabel(order.status, order.status_text) }}
            </el-tag>
          </header>

          <div class="order-card__body">
            <RouterLink
              v-for="item in order.items"
              :key="item.sku_public_id"
              class="order-goods"
              :to="`/product/${item.product_public_id}`"
            >
              <div class="order-goods__media">
                <img
                  v-if="item.main_image"
                  :src="resolveImageUrl(item.main_image)"
                  :alt="item.product_name"
                  loading="lazy"
                />
                <span v-else>{{ item.product_name.slice(0, 1) }}</span>
              </div>
              <div class="order-goods__info">
                <strong>{{ item.product_name }}</strong>
                <span>{{ item.sku_spec }} · × {{ item.quantity }}</span>
              </div>
            </RouterLink>
          </div>

          <footer class="order-card__footer">
            <div class="order-card__amount">
              <span>共 {{ order.total_quantity }} 件，实付</span>
              <strong>{{ formatCurrency(order.payable_amount) }}</strong>
            </div>
            <div class="order-card__actions">
              <RouterLink :to="`/user/orders/${order.order_no}`">
                <el-button size="small">查看详情</el-button>
              </RouterLink>
              <el-button
                v-if="order.can_cancel"
                size="small"
                :loading="mutatingNo === order.order_no"
                @click="cancel(order)"
              >
                取消订单
              </el-button>
              <el-button
                v-if="order.can_pay"
                size="small"
                type="primary"
                @click="pay(order)"
              >
                去支付
              </el-button>
              <el-button
                v-if="order.can_confirm"
                size="small"
                type="success"
                :loading="mutatingNo === order.order_no"
                @click="confirmReceipt(order)"
              >
                确认收货
              </el-button>
            </div>
          </footer>
        </article>
      </div>

      <el-pagination
        v-if="total > pageSize"
        class="orders__pagination"
        layout="prev, pager, next"
        :current-page="page"
        :page-size="pageSize"
        :total="total"
        @current-change="changePage"
      />
    </template>
  </section>
</template>

<style scoped lang="scss">
.orders {
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

  &__list {
    display: flex;
    flex-direction: column;
    gap: 16px;
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

.user-tabs {
  display: flex;
  gap: 20px;
  font-size: 14px;

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

.order-tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 20px;
  flex-wrap: wrap;

  &__item {
    border: 1px solid var(--guda-border);
    background: var(--guda-surface);
    color: var(--guda-text-muted);
    border-radius: 999px;
    padding: 7px 16px;
    font-size: 13px;
    cursor: pointer;
    transition: all 0.2s ease;

    &:hover {
      color: var(--guda-primary);
      border-color: var(--guda-primary-soft);
    }

    &.is-active {
      background: var(--guda-primary);
      border-color: var(--guda-primary);
      color: #fff;
    }
  }
}

.order-card {
  background: var(--guda-surface);
  border: 1px solid var(--guda-border);
  border-radius: var(--guda-radius);
  overflow: hidden;

  &__header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 14px 20px;
    background: #fafaf9;
    border-bottom: 1px solid var(--guda-border);
  }

  &__meta {
    display: flex;
    align-items: baseline;
    gap: 14px;
    flex-wrap: wrap;
  }

  &__no {
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 13px;
    color: var(--guda-text);
  }

  &__time {
    color: var(--guda-text-muted);
    font-size: 12px;
  }

  &__body {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 12px 20px;
    padding: 16px 20px;
  }

  &__footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    padding: 14px 20px;
    border-top: 1px solid var(--guda-border);
    flex-wrap: wrap;
  }

  &__amount {
    display: flex;
    align-items: baseline;
    gap: 8px;
    color: var(--guda-text-muted);
    font-size: 13px;

    strong {
      color: var(--guda-primary);
      font-size: 20px;
    }
  }

  &__actions {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-left: auto;
    flex-wrap: wrap;

    a {
      text-decoration: none;
    }
  }
}

.order-goods {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
  color: inherit;
  text-decoration: none;

  &:hover strong {
    color: var(--guda-primary);
  }

  &__media {
    width: 56px;
    height: 56px;
    flex: none;
    border-radius: 8px;
    overflow: hidden;
    background: #f5f5f4;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #d6d3d1;
    font-size: 20px;

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
    font-size: 14px;

    strong {
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    span {
      color: var(--guda-text-muted);
      font-size: 12px;
    }
  }
}

@media (max-width: 767px) {
  .orders__header {
    flex-direction: column;
    align-items: flex-start;
  }

  .order-card__body {
    grid-template-columns: 1fr;
  }

  .order-card__footer {
    flex-direction: column;
    align-items: flex-start;
  }

  .order-card__actions {
    margin-left: 0;
  }
}
</style>

<script setup lang="ts">
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import { cancelOrder, confirmOrder, fetchOrderDetail } from '@/api/order'
import type { OrderDetail } from '@/types/order'
import { resolveImageUrl } from '@/utils/catalog'
import { formatCurrency, formatDateTime } from '@/utils/format'
import { orderStatusLabel, orderStatusTone } from '@/utils/order'

const route = useRoute()
const router = useRouter()
const orderNo = computed(() => String(route.params.orderNo ?? ''))

const order = ref<OrderDetail | null>(null)
const loading = ref(true)
const failed = ref(false)
const acting = ref(false)

const latestPayment = computed(() => order.value?.payments[0] ?? null)

async function load(): Promise<void> {
  loading.value = true
  failed.value = false
  try {
    order.value = await fetchOrderDetail(orderNo.value)
  } catch {
    order.value = null
    failed.value = true
  } finally {
    loading.value = false
  }
}

async function pay(): Promise<void> {
  if (!order.value) {
    return
  }
  await router.push({ name: 'payment', params: { orderNo: order.value.order_no } })
}

async function cancel(): Promise<void> {
  if (!order.value) {
    return
  }
  const confirmed = await ElMessageBox.confirm(
    '确认取消该订单？取消后锁定库存将立即释放。',
    '取消订单',
    { type: 'warning', confirmButtonText: '取消订单', cancelButtonText: '再想想' },
  ).catch(() => false)
  if (!confirmed) {
    return
  }
  acting.value = true
  try {
    order.value = await cancelOrder(order.value.order_no)
    ElMessage.success('订单已取消')
  } finally {
    acting.value = false
  }
}

async function confirmReceipt(): Promise<void> {
  if (!order.value) {
    return
  }
  const confirmed = await ElMessageBox.confirm(
    '确认已收到商品？确认后订单将完成，且不可撤销。',
    '确认收货',
    { confirmButtonText: '确认收货', cancelButtonText: '取消' },
  ).catch(() => false)
  if (!confirmed) {
    return
  }
  acting.value = true
  try {
    order.value = await confirmOrder(order.value.order_no)
    ElMessage.success('已确认收货')
  } finally {
    acting.value = false
  }
}

onMounted(() => {
  void load()
})
</script>

<template>
  <section class="order-detail">
    <header class="order-detail__header">
      <div>
        <RouterLink class="order-detail__back" to="/user/orders">← 返回订单列表</RouterLink>
        <h1>订单详情</h1>
        <p>
          订单号 <span class="order-detail__no">{{ orderNo }}</span>
        </p>
      </div>
      <nav class="user-tabs" aria-label="个人中心导航">
        <RouterLink to="/user/profile">个人资料</RouterLink>
        <RouterLink to="/user/addresses">收货地址</RouterLink>
        <RouterLink to="/user/orders">我的订单</RouterLink>
      </nav>
    </header>

    <el-skeleton v-if="loading" :rows="10" animated />

    <el-result
      v-else-if="failed || !order"
      icon="warning"
      title="订单不存在或加载失败"
      sub-title="请返回订单列表后重试。"
    >
      <template #extra>
        <RouterLink to="/user/orders">
          <el-button type="primary">返回订单列表</el-button>
        </RouterLink>
      </template>
    </el-result>

    <template v-else>
      <section class="status-panel">
        <div class="status-panel__main">
          <el-tag :type="orderStatusTone(order.status)" effect="dark" size="large">
            {{ orderStatusLabel(order.status, order.status_text) }}
          </el-tag>
          <p v-if="order.can_pay" class="status-panel__hint">
            请在 {{ formatDateTime(order.pay_expires_at) }} 前完成支付，超时订单将自动取消。
          </p>
          <p v-else-if="order.status === 'SHIPPED'" class="status-panel__hint">
            商品已发出，运单号 {{ order.tracking_no || '待补充' }}。
          </p>
          <p v-else-if="order.status === 'CANCELLED'" class="status-panel__hint">
            取消原因：{{ order.cancel_reason || '用户取消' }}
          </p>
          <p v-else-if="order.status === 'COMPLETED'" class="status-panel__hint">
            交易已完成，可在评价期限内分享使用体验。
          </p>
        </div>
        <div class="status-panel__actions">
          <el-button v-if="order.can_cancel" :loading="acting" @click="cancel">
            取消订单
          </el-button>
          <el-button v-if="order.can_pay" type="primary" @click="pay">去支付</el-button>
          <el-button
            v-if="order.can_confirm"
            type="success"
            :loading="acting"
            @click="confirmReceipt"
          >
            确认收货
          </el-button>
          <RouterLink
            v-if="order.status === 'COMPLETED'"
            :to="`/user/orders/${order.order_no}/review`"
          >
            <el-button type="primary" plain>评价订单</el-button>
          </RouterLink>
        </div>
      </section>

      <div class="order-detail__grid">
        <div class="order-detail__main">
          <section class="panel">
            <header class="panel__header">
              <h2>收货信息</h2>
            </header>
            <div class="address-block">
              <p class="address-block__line">
                <strong>{{ order.address.receiver_name }}</strong>
                <span>{{ order.address.phone }}</span>
              </p>
              <p class="address-block__detail">
                {{ order.address.province }} {{ order.address.city }} {{ order.address.district }}
                {{ order.address.detail }}
              </p>
              <p v-if="order.address.postal_code" class="address-block__postal">
                邮编 {{ order.address.postal_code }}
              </p>
            </div>
          </section>

          <section class="panel">
            <header class="panel__header">
              <h2>商品清单</h2>
              <span class="panel__hint">共 {{ order.total_quantity }} 件</span>
            </header>
            <RouterLink
              v-for="item in order.items"
              :key="item.sku_public_id"
              class="goods"
              :to="`/product/${item.product_public_id}`"
            >
              <div class="goods__media">
                <img
                  v-if="item.main_image"
                  :src="resolveImageUrl(item.main_image)"
                  :alt="item.product_name"
                  loading="lazy"
                />
                <span v-else>{{ item.product_name.slice(0, 1) }}</span>
              </div>
              <div class="goods__info">
                <strong>{{ item.product_name }}</strong>
                <span>{{ item.sku_spec }}</span>
              </div>
              <span class="goods__price">{{ formatCurrency(item.unit_price) }}</span>
              <span class="goods__quantity">× {{ item.quantity }}</span>
              <strong class="goods__subtotal">{{ formatCurrency(item.item_amount) }}</strong>
            </RouterLink>
          </section>

          <section class="panel">
            <header class="panel__header">
              <h2>订单流转</h2>
            </header>
            <el-timeline class="status-timeline">
              <el-timeline-item
                v-for="log in order.status_logs"
                :key="`${log.to_status}-${log.created_at}`"
                :timestamp="formatDateTime(log.created_at)"
                :type="orderStatusTone(log.to_status)"
                placement="top"
              >
                <strong>{{ log.to_status_text }}</strong>
                <span v-if="log.remark" class="status-timeline__remark">· {{ log.remark }}</span>
              </el-timeline-item>
            </el-timeline>
          </section>
        </div>

        <aside class="order-detail__aside">
          <section class="panel">
            <header class="panel__header">
              <h2>金额明细</h2>
            </header>
            <dl class="amounts">
              <div>
                <dt>商品小计</dt>
                <dd>{{ formatCurrency(order.items_amount) }}</dd>
              </div>
              <div>
                <dt>运费</dt>
                <dd>
                  {{
                    order.shipping_amount === '0.00'
                      ? '免运费'
                      : formatCurrency(order.shipping_amount)
                  }}
                </dd>
              </div>
              <div v-if="order.discount_amount !== '0.00'">
                <dt>优惠</dt>
                <dd>-{{ formatCurrency(order.discount_amount) }}</dd>
              </div>
              <div v-if="order.coupon">
                <dt>优惠券</dt>
                <dd>{{ order.coupon.name }}</dd>
              </div>
            </dl>
            <div class="amounts__total">
              <span>应付金额</span>
              <strong>{{ formatCurrency(order.payable_amount) }}</strong>
            </div>
          </section>

          <section class="panel">
            <header class="panel__header">
              <h2>支付信息</h2>
            </header>
            <dl v-if="latestPayment" class="amounts">
              <div>
                <dt>支付单号</dt>
                <dd class="amounts__mono">{{ latestPayment.payment_no }}</dd>
              </div>
              <div>
                <dt>支付渠道</dt>
                <dd>{{ latestPayment.channel_text }}</dd>
              </div>
              <div>
                <dt>支付状态</dt>
                <dd>{{ latestPayment.status_text }}</dd>
              </div>
              <div>
                <dt>支付时间</dt>
                <dd>{{ formatDateTime(latestPayment.paid_at) }}</dd>
              </div>
            </dl>
            <p v-else class="panel__hint">暂无支付记录</p>
          </section>

          <section class="panel">
            <header class="panel__header">
              <h2>订单信息</h2>
            </header>
            <dl class="amounts">
              <div>
                <dt>下单时间</dt>
                <dd>{{ formatDateTime(order.created_at) }}</dd>
              </div>
              <div v-if="order.paid_at">
                <dt>支付时间</dt>
                <dd>{{ formatDateTime(order.paid_at) }}</dd>
              </div>
              <div v-if="order.shipped_at">
                <dt>发货时间</dt>
                <dd>{{ formatDateTime(order.shipped_at) }}</dd>
              </div>
              <div v-if="order.completed_at">
                <dt>完成时间</dt>
                <dd>{{ formatDateTime(order.completed_at) }}</dd>
              </div>
              <div v-if="order.cancelled_at">
                <dt>取消时间</dt>
                <dd>{{ formatDateTime(order.cancelled_at) }}</dd>
              </div>
              <div v-if="order.tracking_no">
                <dt>运单号</dt>
                <dd class="amounts__mono">{{ order.tracking_no }}</dd>
              </div>
              <div>
                <dt>订单备注</dt>
                <dd>{{ order.remark || '无' }}</dd>
              </div>
            </dl>
          </section>
        </aside>
      </div>
    </template>
  </section>
</template>

<style scoped lang="scss">
.order-detail {
  &__header {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    gap: 16px;
    margin-bottom: 20px;

    h1 {
      font-size: 26px;
      margin: 6px 0;
    }

    p {
      color: var(--guda-text-muted);
      font-size: 13px;
    }
  }

  &__back {
    color: var(--guda-primary);
    font-size: 13px;
    text-decoration: none;
  }

  &__no {
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    color: var(--guda-text);
  }

  &__grid {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 360px;
    gap: 20px;
    align-items: start;
    margin-top: 16px;
  }

  &__main {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  &__aside {
    display: flex;
    flex-direction: column;
    gap: 16px;
    position: sticky;
    top: 88px;
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

.status-panel {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 20px;
  background: var(--guda-surface);
  border: 1px solid var(--guda-border);
  border-radius: var(--guda-radius);
  flex-wrap: wrap;

  &__main {
    display: flex;
    align-items: center;
    gap: 14px;
    flex-wrap: wrap;
  }

  &__hint {
    color: var(--guda-text-muted);
    font-size: 13px;
  }

  &__actions {
    display: flex;
    gap: 8px;
  }
}

.panel {
  background: var(--guda-surface);
  border: 1px solid var(--guda-border);
  border-radius: var(--guda-radius);
  padding: 20px;

  &__header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 14px;

    h2 {
      font-size: 16px;
    }
  }

  &__hint {
    color: var(--guda-text-muted);
    font-size: 12px;
  }
}

.address-block {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 14px;

  &__line {
    display: flex;
    align-items: baseline;
    gap: 10px;

    span {
      color: var(--guda-text-muted);
      font-size: 13px;
    }
  }

  &__detail {
    color: var(--guda-text);
    line-height: 1.6;
  }

  &__postal {
    color: var(--guda-text-muted);
    font-size: 12px;
  }
}

.goods {
  display: grid;
  grid-template-columns: 64px minmax(0, 1fr) 90px 60px 100px;
  align-items: center;
  gap: 12px;
  padding: 10px 0;
  color: inherit;
  text-decoration: none;

  & + & {
    border-top: 1px dashed var(--guda-border);
  }

  &:hover .goods__info strong {
    color: var(--guda-primary);
  }

  &__media {
    width: 64px;
    height: 64px;
    border-radius: 8px;
    overflow: hidden;
    background: #f5f5f4;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #d6d3d1;
    font-size: 22px;

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

  &__price,
  &__quantity {
    color: var(--guda-text-muted);
    font-size: 13px;
  }

  &__subtotal {
    color: var(--guda-primary);
    font-size: 15px;
    text-align: right;
  }
}

.amounts {
  display: flex;
  flex-direction: column;
  gap: 10px;

  div {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 12px;
    font-size: 13px;
  }

  dt {
    color: var(--guda-text-muted);
    flex: none;
  }

  dd {
    text-align: right;
    word-break: break-all;
  }

  &__mono {
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 12px;
  }

  &__total {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    margin-top: 16px;
    padding-top: 14px;
    border-top: 1px dashed var(--guda-border);
    font-size: 14px;

    strong {
      color: var(--guda-primary);
      font-size: 24px;
    }
  }
}

.status-timeline {
  padding-left: 2px;

  &__remark {
    margin-left: 8px;
    color: var(--guda-text-muted);
    font-size: 12px;
  }
}

@media (max-width: 991px) {
  .order-detail__grid {
    grid-template-columns: 1fr;
  }

  .order-detail__aside {
    position: static;
  }
}

@media (max-width: 767px) {
  .order-detail__header {
    flex-direction: column;
    align-items: flex-start;
  }

  .goods {
    grid-template-columns: 56px minmax(0, 1fr) auto;

    &__price,
    &__quantity {
      display: none;
    }

    &__subtotal {
      grid-column: 2 / 4;
      text-align: left;
    }
  }
}
</style>

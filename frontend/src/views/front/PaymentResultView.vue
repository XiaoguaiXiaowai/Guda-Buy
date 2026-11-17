<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

import { fetchOrderDetail } from '@/api/order'
import type { OrderDetail } from '@/types/order'
import { formatCurrency, formatDateTime } from '@/utils/format'

const route = useRoute()
const orderNo = computed(() => String(route.params.orderNo ?? ''))
const paymentNo = computed(() => String(route.query.paymentNo ?? ''))
const status = computed(() => String(route.query.status ?? '').toUpperCase())

const order = ref<OrderDetail | null>(null)
const loading = ref(true)

const succeeded = computed(() => status.value === 'SUCCESS')
const paidAt = computed(() => {
  if (order.value?.paid_at) {
    return order.value.paid_at
  }
  return order.value?.payments.find((item) => item.status === 'SUCCESS')?.paid_at ?? null
})

onMounted(async () => {
  try {
    order.value = await fetchOrderDetail(orderNo.value)
  } catch {
    order.value = null
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <section class="result">
    <el-skeleton v-if="loading" :rows="6" animated />
    <template v-else>
      <el-result
        :icon="succeeded ? 'success' : 'error'"
        :title="succeeded ? '支付成功' : '支付失败'"
        :sub-title="
          succeeded
            ? '订单已进入待发货状态，可在订单详情查看进度。'
            : '支付未完成，订单仍为待支付，可重新发起支付。'
        "
      >
        <template #extra>
          <dl class="result__meta">
            <div>
              <dt>订单号</dt>
              <dd>{{ orderNo }}</dd>
            </div>
            <div v-if="paymentNo">
              <dt>支付单号</dt>
              <dd>{{ paymentNo }}</dd>
            </div>
            <div v-if="order">
              <dt>支付金额</dt>
              <dd class="result__amount">{{ formatCurrency(order.payable_amount) }}</dd>
            </div>
            <div v-if="paidAt">
              <dt>支付时间</dt>
              <dd>{{ formatDateTime(paidAt) }}</dd>
            </div>
          </dl>

          <div class="result__actions">
            <RouterLink v-if="succeeded" :to="`/user/orders/${orderNo}`">
              <el-button type="primary">查看订单</el-button>
            </RouterLink>
            <template v-else>
              <RouterLink :to="`/pay/${orderNo}`">
                <el-button type="primary">重新支付</el-button>
              </RouterLink>
              <RouterLink :to="`/user/orders/${orderNo}`">
                <el-button>查看订单</el-button>
              </RouterLink>
            </template>
            <RouterLink to="/products">
              <el-button text>继续购物</el-button>
            </RouterLink>
          </div>
        </template>
      </el-result>
    </template>
  </section>
</template>

<style scoped lang="scss">
.result {
  max-width: 720px;
  margin: 40px auto 0;

  &__meta {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 14px 24px;
    margin: 0 auto 24px;
    padding: 18px 22px;
    background: var(--guda-surface);
    border: 1px solid var(--guda-border);
    border-radius: var(--guda-radius);
    text-align: left;

    div {
      display: flex;
      flex-direction: column;
      gap: 4px;
      min-width: 0;
    }

    dt {
      color: var(--guda-text-muted);
      font-size: 12px;
    }

    dd {
      font-size: 13px;
      word-break: break-all;
    }
  }

  &__amount {
    color: var(--guda-primary);
    font-size: 20px;
    font-weight: 700;
  }

  &__actions {
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    gap: 10px;
  }
}
</style>

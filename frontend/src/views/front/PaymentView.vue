<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import { fetchOrderDetail } from '@/api/order'
import { startMockPayment, submitPaymentCallback } from '@/api/payment'
import type { OrderDetail } from '@/types/order'
import type { PaymentCallbackStatus, PaymentCashier, PaymentChannel } from '@/types/payment'
import { formatCurrency, formatDateTime } from '@/utils/format'
import { orderStatusLabel, orderStatusTone } from '@/utils/order'

interface ChannelOption {
  value: PaymentChannel
  label: string
  hint: string
}

const CHANNELS: ChannelOption[] = [
  { value: 'ALIPAY_MOCK', label: '支付宝（模拟）', hint: '演示渠道' },
  { value: 'WECHAT_MOCK', label: '微信支付（模拟）', hint: '演示渠道' },
  { value: 'BALANCE_MOCK', label: '余额支付（模拟）', hint: '演示渠道' },
]

const route = useRoute()
const router = useRouter()
const orderNo = computed(() => String(route.params.orderNo ?? ''))

const order = ref<OrderDetail | null>(null)
const cashier = ref<PaymentCashier | null>(null)
const channel = ref<PaymentChannel>('ALIPAY_MOCK')
const loading = ref(true)
const failed = ref(false)
const initiating = ref(false)
const paying = ref(false)

const payable = computed(() => order.value?.can_pay ?? false)

async function initiate(): Promise<void> {
  initiating.value = true
  try {
    cashier.value = await startMockPayment(orderNo.value, channel.value)
  } catch {
    cashier.value = null
  } finally {
    initiating.value = false
  }
}

async function load(): Promise<void> {
  loading.value = true
  failed.value = false
  try {
    order.value = await fetchOrderDetail(orderNo.value)
    if (!order.value.can_pay) {
      return
    }
    const latestChannel = order.value.payments[0]?.channel
    if (CHANNELS.some((item) => item.value === latestChannel)) {
      channel.value = latestChannel as PaymentChannel
    }
    await initiate()
  } catch {
    order.value = null
    failed.value = true
  } finally {
    loading.value = false
  }
}

async function pay(outcome: PaymentCallbackStatus): Promise<void> {
  if (!cashier.value) {
    return
  }
  paying.value = true
  try {
    const result = await submitPaymentCallback({
      payment_no: cashier.value.payment_no,
      amount: cashier.value.amount,
      status: outcome,
      signature: cashier.value.sign,
    })
    ElMessage[result.status === 'SUCCESS' ? 'success' : 'warning'](
      result.status === 'SUCCESS' ? '模拟支付成功' : '模拟支付失败，可重新发起支付',
    )
    await router.replace({
      name: 'payment-result',
      params: { orderNo: orderNo.value },
      query: { paymentNo: result.payment_no, status: result.status },
    })
  } finally {
    paying.value = false
  }
}

watch(channel, () => {
  if (payable.value && !loading.value) {
    void initiate()
  }
})

onMounted(() => {
  void load()
})
</script>

<template>
  <section class="cashier">
    <header class="cashier__header">
      <div>
        <RouterLink class="cashier__back" :to="`/user/orders/${orderNo}`">
          ← 返回订单详情
        </RouterLink>
        <h1>模拟收银台</h1>
        <p>订单号 <span class="cashier__no">{{ orderNo }}</span></p>
      </div>
      <el-tag type="warning" effect="plain">演示支付，不会产生真实扣款</el-tag>
    </header>

    <el-skeleton v-if="loading" :rows="8" animated />

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

    <el-result
      v-else-if="!payable"
      icon="info"
      title="当前订单无需支付"
      :sub-title="`订单状态：${orderStatusLabel(order.status, order.status_text)}`"
    >
      <template #extra>
        <RouterLink :to="`/user/orders/${order.order_no}`">
          <el-button type="primary">查看订单详情</el-button>
        </RouterLink>
      </template>
    </el-result>

    <div v-else class="cashier__grid">
      <section class="panel">
        <header class="panel__header">
          <h2>订单信息</h2>
          <el-tag :type="orderStatusTone(order.status)" effect="light">
            {{ orderStatusLabel(order.status, order.status_text) }}
          </el-tag>
        </header>
        <dl class="amounts">
          <div>
            <dt>商品件数</dt>
            <dd>{{ order.total_quantity }} 件</dd>
          </div>
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
          <div>
            <dt>支付截止</dt>
            <dd>{{ formatDateTime(order.pay_expires_at) }}</dd>
          </div>
        </dl>
        <div class="amounts__total">
          <span>应付金额</span>
          <strong>{{ formatCurrency(order.payable_amount) }}</strong>
        </div>

        <div class="channels">
          <p class="channels__title">选择支付渠道</p>
          <button
            v-for="item in CHANNELS"
            :key="item.value"
            type="button"
            class="channel"
            :class="{ 'is-active': channel === item.value }"
            @click="channel = item.value"
          >
            <span class="channel__label">{{ item.label }}</span>
            <span class="channel__hint">{{ item.hint }}</span>
          </button>
        </div>
      </section>

      <aside class="cashier__aside">
        <section class="panel">
          <header class="panel__header">
            <h2>收银台</h2>
          </header>
          <el-alert
            title="演示支付，不会产生真实扣款"
            type="warning"
            :closable="false"
            show-icon
          />
          <template v-if="cashier">
            <dl class="amounts cashier__detail">
              <div>
                <dt>支付单号</dt>
                <dd class="amounts__mono">{{ cashier.payment_no }}</dd>
              </div>
              <div>
                <dt>支付渠道</dt>
                <dd>{{ cashier.channel_text }}</dd>
              </div>
              <div>
                <dt>支付金额</dt>
                <dd>{{ formatCurrency(cashier.amount) }}</dd>
              </div>
            </dl>
            <div class="cashier__actions">
              <el-button type="success" :loading="paying" @click="pay('SUCCESS')">
                模拟支付成功
              </el-button>
              <el-button type="danger" plain :loading="paying" @click="pay('FAILED')">
                模拟支付失败
              </el-button>
            </div>
            <p class="cashier__tip">切换渠道会关闭当前支付单并重新生成。</p>
          </template>
          <el-skeleton v-else :rows="3" animated />
        </section>
      </aside>
    </div>
  </section>
</template>

<style scoped lang="scss">
.cashier {
  &__header {
    display: flex;
    align-items: flex-start;
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
  }

  &__aside {
    position: sticky;
    top: 88px;
  }

  &__detail {
    margin-top: 16px;
  }

  &__actions {
    display: flex;
    gap: 8px;
    margin-top: 16px;

    :deep(.el-button) {
      flex: 1;
    }
  }

  &__tip {
    margin-top: 10px;
    color: var(--guda-text-muted);
    font-size: 12px;
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

.channels {
  margin-top: 20px;

  &__title {
    color: var(--guda-text-muted);
    font-size: 13px;
    margin-bottom: 10px;
  }
}

.channel {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding: 12px 14px;
  margin-bottom: 8px;
  background: var(--guda-surface);
  border: 1px solid var(--guda-border);
  border-radius: 8px;
  cursor: pointer;
  transition:
    border-color 0.2s,
    background 0.2s;
  font: inherit;
  color: inherit;

  &:hover {
    border-color: var(--guda-primary);
  }

  &.is-active {
    border-color: var(--guda-primary);
    background: rgba(192, 132, 252, 0.08);
  }

  &__label {
    font-size: 14px;
  }

  &__hint {
    color: var(--guda-text-muted);
    font-size: 12px;
  }
}

@media (max-width: 991px) {
  .cashier__grid {
    grid-template-columns: 1fr;
  }

  .cashier__aside {
    position: static;
  }
}

@media (max-width: 767px) {
  .cashier__header {
    flex-direction: column;
  }
}
</style>

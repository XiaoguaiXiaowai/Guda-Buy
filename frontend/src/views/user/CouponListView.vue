<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import { claimCoupon, fetchAvailableCoupons, fetchMyCoupons } from '@/api/coupon'
import type { AvailableCoupon, MyCoupons } from '@/types/coupon'
import { couponConditionLabel, couponValueLabel, userCouponStatusTone } from '@/utils/coupon'
import { formatDateTime } from '@/utils/format'

type TabName = 'unused' | 'used' | 'expired'

const loading = ref(false)
const claimingId = ref('')
const available = ref<AvailableCoupon[]>([])
const mine = ref<MyCoupons>({
  unused: [],
  used: [],
  expired: [],
  counts: { unused: 0, used: 0, expired: 0 },
})
const activeTab = ref<TabName>('unused')

const tabs = computed(() => [
  { name: 'unused' as TabName, label: `未使用 (${mine.value.counts.unused})` },
  { name: 'used' as TabName, label: `已使用 (${mine.value.counts.used})` },
  { name: 'expired' as TabName, label: `已过期 (${mine.value.counts.expired})` },
])

const current = computed(() => mine.value[activeTab.value])
const emptyText = computed(
  () => `暂无${tabs.value.find((tab) => tab.name === activeTab.value)?.label ?? ''}的优惠券`,
)

async function load(): Promise<void> {
  loading.value = true
  try {
    const [availableData, myData] = await Promise.all([fetchAvailableCoupons(), fetchMyCoupons()])
    available.value = availableData
    mine.value = myData
  } finally {
    loading.value = false
  }
}

async function claim(coupon: AvailableCoupon): Promise<void> {
  if (!coupon.can_claim) {
    return
  }
  claimingId.value = coupon.public_id
  try {
    await claimCoupon(coupon.public_id)
    ElMessage.success(`已领取「${coupon.name}」`)
    await load()
  } finally {
    claimingId.value = ''
  }
}

onMounted(() => {
  void load()
})
</script>

<template>
  <section class="coupon-page">
    <header class="coupon-page__header">
      <div>
        <h1>优惠券</h1>
        <p>领取后可在结算页抵扣，过期不再补发。</p>
      </div>
      <RouterLink class="coupon-page__link" to="/user/orders">查看我的订单</RouterLink>
    </header>

    <el-skeleton v-if="loading" :rows="10" animated />

    <template v-else>
      <section class="coupon-section">
        <div class="coupon-section__header">
          <h2>领券中心</h2>
          <span>{{ available.length }} 张可领</span>
        </div>

        <el-empty v-if="!available.length" description="暂无可领取的优惠券" />

        <div v-else class="coupon-grid">
          <article
            v-for="coupon in available"
            :key="coupon.public_id"
            class="coupon-card"
            :class="{ 'is-disabled': !coupon.can_claim }"
          >
            <div class="coupon-card__value">
              <strong>{{ couponValueLabel(coupon) }}</strong>
              <small>{{ couponConditionLabel(coupon.min_amount) }}</small>
            </div>
            <div class="coupon-card__body">
              <strong>{{ coupon.name }}</strong>
              <span>{{ coupon.scope_summary }}</span>
              <span>有效期至 {{ formatDateTime(coupon.valid_to) }}</span>
            </div>
            <el-button
              size="small"
              type="primary"
              :loading="claimingId === coupon.public_id"
              :disabled="!coupon.can_claim"
              @click="claim(coupon)"
            >
              {{ coupon.can_claim ? '立即领取' : coupon.reason || '不可领取' }}
            </el-button>
          </article>
        </div>
      </section>

      <section class="coupon-section">
        <el-tabs v-model="activeTab">
          <el-tab-pane v-for="tab in tabs" :key="tab.name" :label="tab.label" :name="tab.name" />
        </el-tabs>

        <el-empty v-if="!current.length" :description="emptyText" />

        <div v-else class="coupon-grid">
          <article
            v-for="item in current"
            :key="item.public_id"
            class="coupon-card"
            :class="`is-${item.status.toLowerCase()}`"
          >
            <div class="coupon-card__value">
              <strong>{{ couponValueLabel(item.coupon) }}</strong>
              <small>{{ couponConditionLabel(item.coupon.min_amount) }}</small>
            </div>
            <div class="coupon-card__body">
              <strong>{{ item.coupon.name }}</strong>
              <span>{{ item.coupon.scope_summary }}</span>
              <span>有效期至 {{ formatDateTime(item.expires_at) }}</span>
              <RouterLink v-if="item.order_no" :to="`/user/orders/${item.order_no}`">
                订单 {{ item.order_no }}
              </RouterLink>
            </div>
            <el-tag :type="userCouponStatusTone(item.status)" effect="light">
              {{ item.status_text }}
            </el-tag>
          </article>
        </div>
      </section>
    </template>
  </section>
</template>

<style scoped lang="scss">
.coupon-page {
  display: flex;
  flex-direction: column;
  gap: 20px;

  &__header {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    gap: 16px;

    h1 {
      font-size: 26px;
      margin-bottom: 6px;
    }

    p {
      color: var(--guda-text-muted);
      font-size: 13px;
    }
  }

  &__link {
    color: var(--guda-primary);
    font-size: 14px;
    text-decoration: none;
  }
}

.coupon-section {
  background: var(--guda-surface);
  border: 1px solid var(--guda-border);
  border-radius: var(--guda-radius);
  padding: 20px;

  &__header {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    margin-bottom: 16px;

    h2 {
      font-size: 17px;
    }

    span {
      color: var(--guda-text-muted);
      font-size: 12px;
    }
  }
}

.coupon-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 14px;
}

.coupon-card {
  display: grid;
  grid-template-columns: 104px minmax(0, 1fr) auto;
  align-items: center;
  gap: 12px;
  padding: 14px;
  border: 1px solid var(--guda-border);
  border-radius: 12px;
  background: linear-gradient(120deg, #fff7f2 0%, #fff 60%);

  &.is-disabled,
  &.is-used,
  &.is-expired {
    background: #fafafa;
    opacity: 0.78;
  }

  &__value {
    display: flex;
    flex-direction: column;
    gap: 4px;
    align-items: center;
    padding-right: 12px;
    border-right: 1px dashed var(--guda-border);

    strong {
      color: var(--guda-primary);
      font-size: 18px;
      text-align: center;
      line-height: 1.3;
    }

    small {
      color: var(--guda-text-muted);
      font-size: 12px;
      text-align: center;
    }
  }

  &__body {
    display: flex;
    flex-direction: column;
    gap: 4px;
    min-width: 0;
    font-size: 12px;
    color: var(--guda-text-muted);

    strong {
      color: var(--guda-text);
      font-size: 14px;
    }

    a {
      color: var(--guda-primary);
      text-decoration: none;
    }
  }
}
</style>

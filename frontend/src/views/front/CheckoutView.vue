<script setup lang="ts">
import type { AxiosError } from 'axios'
import { ElMessage } from 'element-plus'
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink, useRouter } from 'vue-router'

import { fetchCart } from '@/api/cart'
import { createOrder, fetchOrderPreview } from '@/api/order'
import { listAddresses } from '@/api/user'
import { useCartStore } from '@/stores/cart'
import type { ApiError } from '@/types/api'
import type { CartPayload } from '@/types/cart'
import type { OrderPreview } from '@/types/order'
import type { Address } from '@/types/user'
import { resolveImageUrl } from '@/utils/catalog'
import { couponConditionLabel, couponValueLabel } from '@/utils/coupon'
import { formatCurrency, formatDateTime } from '@/utils/format'

const router = useRouter()
const cartStore = useCartStore()

const addresses = ref<Address[]>([])
const cart = ref<CartPayload | null>(null)
const selectedIds = ref<string[]>([])
const selectedAddressId = ref('')
const selectedCouponId = ref('')
const preview = ref<OrderPreview | null>(null)
const remark = ref('')
const idempotencyKey = ref(newIdempotencyKey())
const loading = ref(true)
const previewLoading = ref(false)
const submitting = ref(false)
const failed = ref(false)
const previewError = ref('')

const selectedCount = computed(() => selectedIds.value.length)
const hasAddress = computed(() => addresses.value.length > 0)
const selectedCouponUnusable = computed(
  () => !!selectedCouponId.value && !!preview.value?.coupon && !preview.value.coupon.usable,
)

function newIdempotencyKey(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`
}

async function load(): Promise<void> {
  loading.value = true
  failed.value = false
  try {
    const [cartData, addressData] = await Promise.all([fetchCart(), listAddresses()])
    cart.value = cartData
    addresses.value = addressData
    selectedIds.value = cartData.items
      .filter((item) => item.is_selected && item.status === 'VALID')
      .map((item) => item.public_id)
    selectedAddressId.value =
      addressData.find((address) => address.is_default)?.public_id ??
      addressData[0]?.public_id ??
      ''
    selectedCouponId.value = ''
    await refreshPreview()
  } catch {
    failed.value = true
  } finally {
    loading.value = false
  }
}

async function refreshPreview(): Promise<void> {
  previewError.value = ''
  if (!selectedIds.value.length || !selectedAddressId.value) {
    preview.value = null
    return
  }
  previewLoading.value = true
  try {
    preview.value = await fetchOrderPreview({
      cart_item_public_ids: selectedIds.value,
      address_public_id: selectedAddressId.value,
      user_coupon_public_id: selectedCouponId.value || undefined,
    })
  } catch (error) {
    preview.value = null
    const detail = (error as AxiosError<ApiError>).response?.data
    previewError.value = detail?.message ?? '结算信息加载失败，请刷新后重试'
  } finally {
    previewLoading.value = false
  }
}

function selectAddress(publicId: string): void {
  if (selectedAddressId.value === publicId) {
    return
  }
  selectedAddressId.value = publicId
}

watch(selectedAddressId, () => {
  idempotencyKey.value = newIdempotencyKey()
  void refreshPreview()
})

function selectCoupon(publicId: string): void {
  if (selectedCouponId.value === publicId) {
    return
  }
  selectedCouponId.value = publicId
}

watch(selectedCouponId, () => {
  idempotencyKey.value = newIdempotencyKey()
  void refreshPreview()
})

function regenerateKey(): void {
  idempotencyKey.value = newIdempotencyKey()
}

async function submit(): Promise<void> {
  if (!preview.value || !selectedAddressId.value || !selectedIds.value.length) {
    ElMessage.warning('请先选择收货地址与结算商品')
    return
  }
  if (selectedCouponUnusable.value) {
    ElMessage.warning(`所选优惠券不可用：${preview.value.coupon?.reason ?? '请重新选择'}`)
    return
  }
  submitting.value = true
  try {
    const order = await createOrder(
      {
        cart_item_public_ids: selectedIds.value,
        address_public_id: selectedAddressId.value,
        user_coupon_public_id: selectedCouponId.value || undefined,
        remark: remark.value.trim(),
      },
      idempotencyKey.value,
    )
    await cartStore.refreshCount()
    ElMessage.success('订单提交成功，请在 30 分钟内完成支付')
    await router.replace(`/user/orders/${order.order_no}`)
  } finally {
    submitting.value = false
  }
}

onMounted(() => {
  void load()
})
</script>

<template>
  <section class="checkout">
    <header class="checkout__header">
      <div>
        <h1>确认订单</h1>
        <p>提交后将锁定库存 30 分钟，请及时完成支付。</p>
      </div>
      <RouterLink class="checkout__back" to="/cart">返回购物车</RouterLink>
    </header>

    <el-skeleton v-if="loading" :rows="8" animated />

    <el-result
      v-else-if="failed"
      icon="warning"
      title="结算信息加载失败"
      sub-title="请检查网络后重试。"
    >
      <template #extra>
        <el-button type="primary" @click="load">重新加载</el-button>
      </template>
    </el-result>

    <el-empty v-else-if="!selectedCount" description="没有勾选可结算的商品">
      <el-button type="primary" @click="router.push('/cart')">返回购物车</el-button>
    </el-empty>

    <template v-else>
      <div class="checkout__steps">
        <span class="is-done">1 购物车</span>
        <span class="is-active">2 确认订单</span>
        <span>3 完成</span>
      </div>

      <div class="checkout__grid">
        <div class="checkout__main">
          <section class="panel">
            <header class="panel__header">
              <h2>收货地址</h2>
              <RouterLink class="panel__link" to="/user/addresses" target="_blank">
                管理地址
              </RouterLink>
            </header>

            <el-empty v-if="!hasAddress" description="还没有收货地址">
              <RouterLink to="/user/addresses" target="_blank">
                <el-button type="primary">去添加地址</el-button>
              </RouterLink>
            </el-empty>

            <div v-else class="address-list">
              <button
                v-for="address in addresses"
                :key="address.public_id"
                type="button"
                class="address-option"
                :class="{ 'is-active': address.public_id === selectedAddressId }"
                @click="selectAddress(address.public_id)"
              >
                <span class="address-option__radio" />
                <span class="address-option__body">
                  <span class="address-option__line">
                    <strong>{{ address.receiver_name }}</strong>
                    <span>{{ address.phone }}</span>
                    <el-tag v-if="address.is_default" size="small" effect="light">默认</el-tag>
                  </span>
                  <span class="address-option__detail">
                    {{ address.province }} {{ address.city }} {{ address.district }}
                    {{ address.detail }}
                  </span>
                </span>
              </button>
            </div>
          </section>

          <section class="panel">
            <header class="panel__header">
              <h2>商品清单</h2>
              <span class="panel__hint">共 {{ selectedCount }} 项</span>
            </header>

            <article
              v-for="item in preview?.items ?? []"
              :key="item.cart_item_public_id"
              class="goods"
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
            </article>
          </section>

          <section class="panel">
            <header class="panel__header">
              <h2>优惠券</h2>
              <RouterLink class="panel__link" to="/user/coupons" target="_blank">
                我的优惠券
              </RouterLink>
            </header>

            <el-skeleton v-if="previewLoading" :rows="2" animated />
            <el-empty
              v-else-if="!preview?.coupons.length"
              description="暂无可用优惠券"
              :image-size="56"
            />
            <div v-else class="coupon-list">
              <button
                type="button"
                class="coupon-option"
                :class="{ 'is-active': !selectedCouponId }"
                @click="selectCoupon('')"
              >
                <span class="coupon-option__radio" />
                <span class="coupon-option__body">
                  <strong>不使用优惠券</strong>
                </span>
              </button>
              <button
                v-for="coupon in preview.coupons"
                :key="coupon.user_coupon_id"
                type="button"
                class="coupon-option"
                :class="{
                  'is-active': coupon.user_coupon_id === selectedCouponId,
                  'is-disabled': !coupon.usable,
                }"
                :disabled="!coupon.usable"
                @click="selectCoupon(coupon.user_coupon_id)"
              >
                <span class="coupon-option__radio" />
                <span class="coupon-option__body">
                  <span class="coupon-option__line">
                    <strong class="coupon-option__value">{{ couponValueLabel(coupon) }}</strong>
                    <span class="coupon-option__name">{{ coupon.name }}</span>
                    <el-tag v-if="coupon.usable" size="small" type="danger" effect="plain">
                      -{{ formatCurrency(coupon.discount_amount) }}
                    </el-tag>
                  </span>
                  <span class="coupon-option__meta">
                    {{ couponConditionLabel(coupon.min_amount) }} · {{ coupon.scope_summary }} ·
                    {{ formatDateTime(coupon.expires_at) }} 到期
                  </span>
                  <span v-if="!coupon.usable" class="coupon-option__reason">
                    {{ coupon.reason }}
                  </span>
                </span>
              </button>
            </div>
            <p v-if="selectedCouponUnusable" class="coupon-warning">
              所选优惠券已不可用，请重新选择后再提交。
            </p>
          </section>

          <section class="panel">
            <header class="panel__header">
              <h2>订单备注</h2>
            </header>
            <el-input
              v-model="remark"
              type="textarea"
              :rows="2"
              maxlength="200"
              show-word-limit
              placeholder="选填，如对配送时间的要求"
              @input="regenerateKey"
            />
          </section>
        </div>

        <aside class="checkout__aside">
          <section class="summary">
            <h2>金额明细</h2>

            <div v-if="previewLoading" class="summary__loading">
              <el-skeleton :rows="4" animated />
            </div>

            <el-alert
              v-else-if="previewError"
              type="warning"
              :closable="false"
              show-icon
              :title="previewError"
            >
              <template #default>
                <el-button link type="primary" @click="refreshPreview">重新试算</el-button>
              </template>
            </el-alert>

            <template v-else-if="preview">
              <dl class="summary__rows">
                <div>
                  <dt>商品小计</dt>
                  <dd>{{ formatCurrency(preview.items_amount) }}</dd>
                </div>
                <div>
                  <dt>运费</dt>
                  <dd>
                    {{
                      preview.shipping_amount === '0.00'
                        ? '免运费'
                        : formatCurrency(preview.shipping_amount)
                    }}
                  </dd>
                </div>
                <div v-if="preview.discount_amount !== '0.00'">
                  <dt>优惠</dt>
                  <dd>-{{ formatCurrency(preview.discount_amount) }}</dd>
                </div>
              </dl>

              <p class="summary__tip">
                满 {{ formatCurrency(preview.free_shipping_threshold) }} 免运费
              </p>

              <div class="summary__total">
                <span>应付金额</span>
                <strong>{{ formatCurrency(preview.payable_amount) }}</strong>
              </div>
            </template>

            <el-button
              type="primary"
              size="large"
              class="summary__submit"
              :loading="submitting"
              :disabled="
                !preview ||
                  previewLoading ||
                  !!previewError ||
                  !selectedAddressId ||
                  selectedCouponUnusable
              "
              @click="submit"
            >
              提交订单
            </el-button>
            <p class="summary__legal">提交即表示同意商城交易规则，库存将在支付超时后自动释放。</p>
          </section>
        </aside>
      </div>
    </template>
  </section>
</template>

<style scoped lang="scss">
.checkout {
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

  &__back {
    color: var(--guda-primary);
    font-size: 14px;
    text-decoration: none;
  }

  &__steps {
    display: flex;
    gap: 18px;
    align-items: center;
    margin-bottom: 20px;
    font-size: 13px;
    color: var(--guda-text-muted);

    span {
      padding-bottom: 4px;
      border-bottom: 2px solid transparent;
    }

    .is-done {
      color: var(--guda-text);
    }

    .is-active {
      color: var(--guda-primary);
      border-color: var(--guda-primary);
      font-weight: 600;
    }
  }

  &__grid {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 360px;
    gap: 20px;
    align-items: start;
  }

  &__main {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  &__aside {
    position: sticky;
    top: 88px;
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
    margin-bottom: 16px;

    h2 {
      font-size: 16px;
    }
  }

  &__link {
    color: var(--guda-primary);
    font-size: 13px;
    text-decoration: none;
  }

  &__hint {
    color: var(--guda-text-muted);
    font-size: 12px;
  }
}

.address-list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.address-option {
  display: flex;
  gap: 10px;
  text-align: left;
  padding: 14px;
  border: 1px solid var(--guda-border);
  border-radius: 10px;
  background: var(--guda-surface);
  cursor: pointer;
  transition:
    border-color 0.2s ease,
    box-shadow 0.2s ease;

  &:hover {
    border-color: var(--guda-primary-soft);
  }

  &.is-active {
    border-color: var(--guda-primary);
    box-shadow: 0 0 0 1px var(--guda-primary-soft) inset;
  }

  &__radio {
    width: 16px;
    height: 16px;
    margin-top: 3px;
    border-radius: 50%;
    border: 1px solid var(--guda-border);
    flex: none;
  }

  &.is-active &__radio {
    border: 5px solid var(--guda-primary);
  }

  &__body {
    display: flex;
    flex-direction: column;
    gap: 6px;
    min-width: 0;
  }

  &__line {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
    font-size: 14px;

    span {
      color: var(--guda-text-muted);
      font-size: 13px;
    }
  }

  &__detail {
    color: var(--guda-text-muted);
    font-size: 13px;
    line-height: 1.5;
  }
}

.coupon-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.coupon-option {
  display: flex;
  gap: 10px;
  width: 100%;
  text-align: left;
  padding: 12px 14px;
  border: 1px solid var(--guda-border);
  border-radius: 10px;
  background: var(--guda-surface);
  cursor: pointer;
  transition:
    border-color 0.2s ease,
    opacity 0.2s ease;

  &:hover:not(.is-disabled) {
    border-color: var(--guda-primary-soft);
  }

  &.is-active {
    border-color: var(--guda-primary);
    box-shadow: 0 0 0 1px var(--guda-primary-soft) inset;
  }

  &.is-disabled {
    cursor: not-allowed;
    opacity: 0.62;
    background: #fafafa;
  }

  &__radio {
    width: 16px;
    height: 16px;
    margin-top: 3px;
    border-radius: 50%;
    border: 1px solid var(--guda-border);
    flex: none;
  }

  &.is-active &__radio {
    border: 5px solid var(--guda-primary);
  }

  &__body {
    display: flex;
    flex-direction: column;
    gap: 4px;
    min-width: 0;
    font-size: 13px;
  }

  &__line {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }

  &__value {
    color: var(--guda-primary);
    font-size: 15px;
  }

  &__name {
    font-weight: 600;
  }

  &__meta {
    color: var(--guda-text-muted);
    font-size: 12px;
  }

  &__reason {
    color: var(--guda-danger, #c0392b);
    font-size: 12px;
  }
}

.coupon-warning {
  margin-top: 10px;
  color: var(--guda-danger, #c0392b);
  font-size: 12px;
}

.goods {
  display: grid;
  grid-template-columns: 64px minmax(0, 1fr) 90px 60px 100px;
  align-items: center;
  gap: 12px;
  padding: 10px 0;

  & + & {
    border-top: 1px dashed var(--guda-border);
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

.summary {
  background: var(--guda-surface);
  border: 1px solid var(--guda-border);
  border-radius: var(--guda-radius);
  padding: 20px;

  h2 {
    font-size: 16px;
    margin-bottom: 16px;
  }

  &__rows {
    display: flex;
    flex-direction: column;
    gap: 12px;

    div {
      display: flex;
      align-items: center;
      justify-content: space-between;
      font-size: 14px;
    }

    dt {
      color: var(--guda-text-muted);
    }

    dd {
      color: var(--guda-text);
    }
  }

  &__tip {
    margin-top: 10px;
    color: var(--guda-text-muted);
    font-size: 12px;
  }

  &__total {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    margin-top: 18px;
    padding-top: 16px;
    border-top: 1px dashed var(--guda-border);
    font-size: 14px;

    strong {
      color: var(--guda-primary);
      font-size: 26px;
    }
  }

  &__submit {
    width: 100%;
    margin-top: 18px;
  }

  &__legal {
    margin-top: 10px;
    color: var(--guda-text-muted);
    font-size: 12px;
    line-height: 1.6;
  }

  &__loading {
    padding: 4px 0;
  }
}

@media (max-width: 991px) {
  .checkout__grid {
    grid-template-columns: 1fr;
  }

  .checkout__aside {
    position: static;
  }
}

@media (max-width: 767px) {
  .checkout__header {
    flex-direction: column;
    align-items: flex-start;
  }

  .address-list {
    grid-template-columns: 1fr;
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

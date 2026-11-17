<script setup lang="ts">
import { ElMessage, ElMessageBox } from 'element-plus'
import { onMounted, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'

import { clearCart, deleteCartItem, fetchCart, updateCartItem } from '@/api/cart'
import { useCartStore } from '@/stores/cart'
import type { CartItem, CartPayload } from '@/types/cart'
import { cartStatusTone } from '@/utils/cart'
import { resolveImageUrl } from '@/utils/catalog'
import { formatCurrency } from '@/utils/format'

const router = useRouter()
const cartStore = useCartStore()

const cart = ref<CartPayload | null>(null)
const loading = ref(true)
const failed = ref(false)
const mutatingId = ref('')
const clearing = ref(false)

async function load(): Promise<void> {
  loading.value = true
  failed.value = false
  try {
    cart.value = await fetchCart()
  } catch {
    cart.value = null
    failed.value = true
  } finally {
    loading.value = false
  }
}

async function refreshAll(): Promise<void> {
  await Promise.all([load(), cartStore.refreshCount()])
}

async function toggleSelection(item: CartItem, checked: boolean): Promise<void> {
  mutatingId.value = item.public_id
  try {
    await updateCartItem(item.public_id, { is_selected: checked })
    await load()
  } finally {
    mutatingId.value = ''
  }
}

async function handleQuantity(item: CartItem, value: number | undefined): Promise<void> {
  if (!value || value === item.quantity) {
    return
  }
  mutatingId.value = item.public_id
  try {
    await updateCartItem(item.public_id, { quantity: value })
    await refreshAll()
  } catch {
    await load()
  } finally {
    mutatingId.value = ''
  }
}

async function removeItem(item: CartItem): Promise<void> {
  try {
    await ElMessageBox.confirm(`确认删除「${item.product.name} · ${item.spec_text}」？`, '删除商品', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return
  }
  mutatingId.value = item.public_id
  try {
    await deleteCartItem(item.public_id)
    ElMessage.success('已删除')
    await refreshAll()
  } finally {
    mutatingId.value = ''
  }
}

async function clearSelected(): Promise<void> {
  if (!cart.value?.summary.selected_count) {
    ElMessage.warning('请先勾选要清空的商品')
    return
  }
  try {
    await ElMessageBox.confirm('确认清空所有已勾选的商品？', '清空已选', {
      confirmButtonText: '清空',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return
  }
  clearing.value = true
  try {
    const deleted = await clearCart(true)
    ElMessage.success(`已清空 ${deleted} 项`)
    await refreshAll()
  } finally {
    clearing.value = false
  }
}

function checkout(): void {
  if (!cart.value?.summary.can_checkout) {
    ElMessage.warning('请先勾选有效商品')
    return
  }
  ElMessage.info('结算与支付将在 I5 交付')
  void router.push('/products')
}

onMounted(() => {
  void load()
})
</script>

<template>
  <section class="cart">
    <header class="cart__header">
      <div>
        <h1>购物车</h1>
        <p>商品状态实时校验；失效或库存不足的商品不计入结算金额。</p>
      </div>
      <RouterLink class="cart__continue" to="/products">继续购物</RouterLink>
    </header>

    <el-skeleton v-if="loading" :rows="6" animated />

    <el-result
      v-else-if="failed"
      icon="warning"
      title="购物车加载失败"
      sub-title="请检查网络后重试。"
    >
      <template #extra>
        <el-button type="primary" @click="load">重新加载</el-button>
      </template>
    </el-result>

    <el-empty v-else-if="!cart?.items.length" description="购物车还是空的">
      <el-button type="primary" @click="router.push('/products')">去逛逛</el-button>
    </el-empty>

    <template v-else-if="cart">
      <div class="cart__list">
        <article
          v-for="item in cart.items"
          :key="item.public_id"
          class="cart-row"
          :class="{ 'is-invalid': item.status !== 'VALID' }"
        >
          <el-checkbox
            :model-value="item.is_selected"
            :disabled="item.status !== 'VALID' || mutatingId === item.public_id"
            @change="(checked: boolean) => toggleSelection(item, checked)"
          />

          <RouterLink class="cart-row__media" :to="`/product/${item.product.public_id}`">
            <img
              v-if="item.product.main_image"
              :src="resolveImageUrl(item.product.main_image)"
              :alt="item.product.name"
              loading="lazy"
            />
            <span v-else>{{ item.product.name.slice(0, 1) }}</span>
          </RouterLink>

          <div class="cart-row__info">
            <RouterLink class="cart-row__name" :to="`/product/${item.product.public_id}`">
              {{ item.product.name }}
            </RouterLink>
            <span class="cart-row__spec">{{ item.spec_text }}</span>
            <div class="cart-row__status">
              <el-tag :type="cartStatusTone(item.status)" effect="light" size="small">
                {{ item.status_text }}
              </el-tag>
              <span v-if="item.status_reason" class="cart-row__reason">
                {{ item.status_reason }}
              </span>
            </div>
          </div>

          <span class="cart-row__price">{{ formatCurrency(item.sale_price) }}</span>

          <el-input-number
            class="cart-row__quantity"
            :model-value="item.quantity"
            :min="1"
            :max="Math.min(99, Math.max(item.stock, 1))"
            :disabled="item.status !== 'VALID' || mutatingId === item.public_id"
            size="small"
            @change="(value: number | undefined) => handleQuantity(item, value)"
          />

          <strong class="cart-row__subtotal">{{ formatCurrency(item.subtotal) }}</strong>

          <el-button
            link
            type="danger"
            :disabled="mutatingId === item.public_id"
            @click="removeItem(item)"
          >
            删除
          </el-button>
        </article>
      </div>

      <footer class="cart__summary">
        <div class="cart__stats">
          <span>共 {{ cart.summary.items_count }} 种 / {{ cart.summary.total_quantity }} 件</span>
          <span>已选 {{ cart.summary.selected_count }} 项有效商品</span>
        </div>
        <div class="cart__actions">
          <el-button :loading="clearing" @click="clearSelected">清空已选</el-button>
          <span class="cart__amount">
            合计
            <strong>{{ formatCurrency(cart.summary.items_amount) }}</strong>
          </span>
          <el-button type="primary" size="large" :disabled="!cart.summary.can_checkout" @click="checkout">
            去结算
          </el-button>
        </div>
      </footer>
    </template>
  </section>
</template>

<style scoped lang="scss">
.cart {
  &__header {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    gap: 16px;
    margin-bottom: 24px;

    h1 {
      font-size: 26px;
      margin-bottom: 6px;
    }

    p {
      color: var(--guda-text-muted);
      font-size: 13px;
    }
  }

  &__continue {
    color: var(--guda-primary);
    font-size: 14px;
    text-decoration: none;
  }

  &__list {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  &__summary {
    position: sticky;
    bottom: 16px;
    margin-top: 24px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    padding: 16px 20px;
    background: var(--guda-surface);
    border: 1px solid var(--guda-border);
    border-radius: var(--guda-radius);
    box-shadow: 0 12px 28px rgba(17, 24, 39, 0.08);
    flex-wrap: wrap;
  }

  &__stats {
    display: flex;
    gap: 18px;
    color: var(--guda-text-muted);
    font-size: 13px;
  }

  &__actions {
    display: flex;
    align-items: center;
    gap: 16px;
    margin-left: auto;
  }

  &__amount {
    font-size: 14px;

    strong {
      color: var(--guda-primary);
      font-size: 24px;
      margin-left: 6px;
    }
  }
}

.cart-row {
  display: grid;
  grid-template-columns: 24px 88px minmax(0, 1fr) 100px 132px 110px 60px;
  align-items: center;
  gap: 14px;
  padding: 14px 18px;
  background: var(--guda-surface);
  border: 1px solid var(--guda-border);
  border-radius: var(--guda-radius);

  &.is-invalid {
    background: #fafafa;

    .cart-row__media,
    .cart-row__name,
    .cart-row__price,
    .cart-row__subtotal {
      opacity: 0.55;
    }
  }

  &__media {
    width: 88px;
    height: 88px;
    border-radius: 10px;
    overflow: hidden;
    background: #f5f5f4;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #d6d3d1;
    font-size: 28px;

    img {
      width: 100%;
      height: 100%;
      object-fit: cover;
    }
  }

  &__info {
    display: flex;
    flex-direction: column;
    gap: 6px;
    min-width: 0;
  }

  &__name {
    color: var(--guda-text);
    font-size: 15px;
    text-decoration: none;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;

    &:hover {
      color: var(--guda-primary);
    }
  }

  &__spec {
    color: var(--guda-text-muted);
    font-size: 13px;
  }

  &__status {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  &__reason {
    color: var(--guda-text-muted);
    font-size: 12px;
  }

  &__price {
    color: var(--guda-text);
    font-size: 14px;
  }

  &__subtotal {
    color: var(--guda-primary);
    font-size: 16px;
    text-align: right;
  }
}

@media (max-width: 900px) {
  .cart-row {
    grid-template-columns: 24px 72px minmax(0, 1fr) auto;
    grid-template-areas:
      'check media info delete'
      '. quantity quantity subtotal';

    .cart-row__media {
      grid-area: media;
      width: 72px;
      height: 72px;
    }

    .cart-row__info {
      grid-area: info;
    }

    .cart-row__price {
      display: none;
    }

    .cart-row__quantity {
      grid-area: quantity;
      justify-self: start;
    }

    .cart-row__subtotal {
      grid-area: subtotal;
    }

    :deep(.el-checkbox) {
      grid-area: check;
    }

    :deep(.el-button) {
      grid-area: delete;
    }
  }
}
</style>

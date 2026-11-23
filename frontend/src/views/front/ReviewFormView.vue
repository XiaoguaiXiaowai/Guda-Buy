<script setup lang="ts">
import type { UploadUserFile } from 'element-plus'
import { ElMessage } from 'element-plus'
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

import { fetchOrderReview, submitOrderReview, uploadReviewImage } from '@/api/review'
import type { ReviewEligibility } from '@/types/review'
import { resolveImageUrl } from '@/utils/catalog'
import { formatDateTime } from '@/utils/format'
import { remainingImageSlots, reviewStatusLabel, reviewStatusTone } from '@/utils/review'

const route = useRoute()
const orderNo = computed(() => String(route.params.orderNo))

const state = ref<ReviewEligibility | null>(null)
const loading = ref(true)
const failed = ref(false)
const submitting = ref(false)
const rating = ref(5)
const content = ref('')
const anonymous = ref(false)
const selectedSku = ref('')
const fileList = ref<UploadUserFile[]>([])

const review = computed(() => state.value?.review ?? null)
const existingImages = computed(() => review.value?.images ?? [])
const imageSlots = computed(() => remainingImageSlots(existingImages.value.length))
const canEdit = computed(() => state.value?.can_review ?? false)

const MAX_CONTENT = 500
const MAX_IMAGE_BYTES = 5 * 1024 * 1024
const ALLOWED_TYPES = ['image/jpeg', 'image/png', 'image/webp']

async function load(showLoading = true): Promise<void> {
  if (showLoading) {
    loading.value = true
  }
  failed.value = false
  try {
    const data = await fetchOrderReview(orderNo.value)
    state.value = data
    rating.value = data.review?.rating ?? 5
    content.value = data.review?.content ?? ''
    anonymous.value = data.review?.is_anonymous ?? false
    selectedSku.value =
      data.review?.sku_public_id ??
      (data.items.length === 1 ? data.items[0].sku_public_id : '')
  } catch {
    state.value = null
    failed.value = true
  } finally {
    loading.value = false
  }
}

function validate(): boolean {
  if (rating.value < 1 || rating.value > 5) {
    ElMessage.warning('请选择 1–5 星评分')
    return false
  }
  const text = content.value.trim()
  if (text.length < 5 || text.length > MAX_CONTENT) {
    ElMessage.warning('评价内容需 5–500 字')
    return false
  }
  if (state.value?.requires_sku && !selectedSku.value) {
    ElMessage.warning('请选择要评价的商品')
    return false
  }
  for (const file of fileList.value) {
    if (!file.raw) {
      continue
    }
    if (!ALLOWED_TYPES.includes(file.raw.type)) {
      ElMessage.warning('仅支持 jpg/png/webp 图片')
      return false
    }
    if (file.raw.size > MAX_IMAGE_BYTES) {
      ElMessage.warning('单张图片不能超过 5MB')
      return false
    }
  }
  return fileList.value.length <= imageSlots.value
}

async function submit(): Promise<void> {
  if (!validate()) {
    return
  }
  submitting.value = true
  try {
    const payload = await submitOrderReview(orderNo.value, {
      rating: rating.value,
      content: content.value.trim(),
      is_anonymous: anonymous.value,
      ...(state.value?.requires_sku ? { sku_public_id: selectedSku.value } : {}),
    })

    const reviewId = payload.review?.public_id
    const files: File[] = []
    for (const item of fileList.value) {
      if (item.raw) {
        files.push(item.raw)
      }
    }
    let failedUploads = 0
    if (reviewId) {
      for (const file of files) {
        try {
          await uploadReviewImage(reviewId, file)
        } catch {
          failedUploads += 1
        }
      }
    }

    if (failedUploads) {
      ElMessage.warning(`评价已提交，${failedUploads} 张图片上传失败，可稍后补充`)
    } else {
      ElMessage.success('评价已提交，等待审核')
    }
    fileList.value = []
    await load(false)
  } finally {
    submitting.value = false
  }
}

onMounted(() => {
  void load()
})
</script>

<template>
  <section class="review-page">
    <RouterLink class="review-page__back" :to="`/user/orders/${orderNo}`">
      ← 返回订单详情
    </RouterLink>

    <el-skeleton v-if="loading" :rows="8" animated />

    <el-result
      v-else-if="failed"
      icon="warning"
      title="订单不存在或无权访问"
      sub-title="请返回订单列表确认后再试。"
    >
      <template #extra>
        <RouterLink to="/user/orders">
          <el-button type="primary">返回订单列表</el-button>
        </RouterLink>
      </template>
    </el-result>

    <template v-else-if="state">
      <header class="review-page__header">
        <div>
          <p class="review-page__eyebrow">订单评价</p>
          <h1>评价订单 {{ state.order_no }}</h1>
          <p v-if="state.window_expires_at" class="review-page__hint">
            评价截止：{{ formatDateTime(state.window_expires_at) }}
          </p>
        </div>
        <el-tag v-if="review" :type="reviewStatusTone(review.status)" effect="dark">
          {{ reviewStatusLabel(review.status, review.status_text) }}
        </el-tag>
      </header>

      <el-alert
        v-if="review && review.status === 'PENDING'"
        title="评价已提交，正在等待人工审核"
        description="审核通过后会展示在商品详情页，可在消息中心查看审核结果。"
        type="warning"
        show-icon
        :closable="false"
      />
      <el-alert
        v-if="review && review.status === 'APPROVED'"
        title="评价已通过审核"
        description="感谢你的分享，评价已展示在商品详情页。"
        type="success"
        show-icon
        :closable="false"
      />
      <el-alert
        v-if="review && review.status === 'REJECTED'"
        :title="`评价未通过审核：${review.reject_reason || '不符合评价规范'}`"
        description="你可以修改评价内容后重新提交，重新提交后需再次等待审核。"
        type="error"
        show-icon
        :closable="false"
      />
      <el-alert
        v-if="!state.can_review && !review"
        :title="state.reason || '当前订单暂不可评价'"
        type="info"
        show-icon
        :closable="false"
      />

      <section v-if="review && !canEdit" class="review-card">
        <div class="review-card__head">
          <strong>{{ review.product_name }}</strong>
          <el-rate :model-value="review.rating" disabled />
        </div>
        <p class="review-card__spec">{{ review.sku_spec }}</p>
        <p class="review-card__content">{{ review.content }}</p>
        <div v-if="review.images.length" class="review-card__images">
          <el-image
            v-for="image in review.images"
            :key="image.public_id"
            :src="resolveImageUrl(image.image)"
            :preview-src-list="review.images.map((item) => resolveImageUrl(item.image))"
            fit="cover"
            preview-teleported
          />
        </div>
      </section>

      <el-form v-if="canEdit" class="review-form" label-position="top" @submit.prevent="submit">
        <el-form-item v-if="state.requires_sku" label="评价商品" required>
          <el-select v-model="selectedSku" placeholder="请选择要评价的商品">
            <el-option
              v-for="item in state.items"
              :key="item.sku_public_id"
              :label="`${item.product_name} · ${item.sku_spec}`"
              :value="item.sku_public_id"
            />
          </el-select>
        </el-form-item>
        <el-form-item v-else-if="state.items.length" label="评价商品">
          <span>{{ state.items[0].product_name }} · {{ state.items[0].sku_spec }}</span>
        </el-form-item>

        <el-form-item label="评分" required>
          <el-rate v-model="rating" show-text :texts="['很差', '较差', '一般', '满意', '非常满意']" />
        </el-form-item>

        <el-form-item label="评价内容" required>
          <el-input
            v-model="content"
            type="textarea"
            :rows="5"
            :maxlength="MAX_CONTENT"
            show-word-limit
            placeholder="说说商品的材质、版型、上身效果等真实体验（5–500 字）"
          />
        </el-form-item>

        <el-form-item label="匿名展示">
          <el-checkbox v-model="anonymous">
            匿名评价（昵称脱敏展示，不显示用户名）
          </el-checkbox>
        </el-form-item>

        <el-form-item label="评价图片（选填）">
          <div class="review-form__uploader">
            <div v-if="existingImages.length" class="review-form__existing">
              <el-image
                v-for="image in existingImages"
                :key="image.public_id"
                :src="resolveImageUrl(image.image)"
                fit="cover"
              />
            </div>
            <el-upload
              v-if="imageSlots > 0"
              v-model:file-list="fileList"
              list-type="picture-card"
              :auto-upload="false"
              :limit="imageSlots"
              accept="image/jpeg,image/png,image/webp"
            >
              <span class="review-form__plus">+</span>
            </el-upload>
            <p class="review-form__hint">
              最多 3 张，单张不超过 5MB；已上传 {{ existingImages.length }} 张。
            </p>
          </div>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" native-type="submit" :loading="submitting">
            {{ review?.status === 'REJECTED' ? '重新提交评价' : '提交评价' }}
          </el-button>
          <RouterLink :to="`/user/orders/${orderNo}`">
            <el-button>取消</el-button>
          </RouterLink>
        </el-form-item>
      </el-form>
    </template>
  </section>
</template>

<style scoped lang="scss">
.review-page {
  max-width: 760px;
  margin: 0 auto;

  &__back {
    display: inline-block;
    margin-bottom: 16px;
    color: var(--guda-text-muted);
    font-size: 13px;
  }

  &__header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 16px;
    margin-bottom: 16px;
  }

  &__eyebrow {
    color: var(--guda-text-muted);
    font-size: 12px;
    letter-spacing: 2px;
    margin-bottom: 6px;
  }

  h1 {
    font-size: 24px;
    margin-bottom: 6px;
  }

  &__hint {
    color: var(--guda-text-muted);
    font-size: 13px;
  }
}

.review-card {
  margin-top: 16px;
  padding: 20px;
  border-radius: 12px;
  background: #fff;
  box-shadow: 0 6px 24px rgba(17, 24, 39, 0.06);

  &__head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
  }

  &__spec {
    margin-top: 4px;
    color: var(--guda-text-muted);
    font-size: 12px;
  }

  &__content {
    margin: 12px 0;
    line-height: 1.7;
    white-space: pre-wrap;
  }

  &__images {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;

    :deep(.el-image) {
      width: 96px;
      height: 96px;
      border-radius: 8px;
      overflow: hidden;
    }
  }
}

.review-form {
  margin-top: 16px;
  padding: 20px;
  border-radius: 12px;
  background: #fff;
  box-shadow: 0 6px 24px rgba(17, 24, 39, 0.06);

  &__uploader {
    width: 100%;
  }

  &__existing {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-bottom: 10px;

    :deep(.el-image) {
      width: 96px;
      height: 96px;
      border-radius: 8px;
      overflow: hidden;
    }
  }

  &__plus {
    font-size: 22px;
    color: var(--guda-text-muted);
  }

  &__hint {
    margin-top: 8px;
    color: var(--guda-text-muted);
    font-size: 12px;
  }
}
</style>

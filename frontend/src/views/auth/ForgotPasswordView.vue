<script setup lang="ts">
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage } from 'element-plus'
import { reactive, ref } from 'vue'

import { requestPasswordReset } from '@/api/user'

const formRef = ref<FormInstance>()
const submitting = ref(false)
const submitted = ref(false)
const form = reactive({ email: '' })

const rules: FormRules = {
  email: [
    { required: true, message: '请输入注册邮箱', trigger: 'blur' },
    { type: 'email', message: '邮箱格式不正确', trigger: 'blur' },
  ],
}

async function submit() {
  if (!formRef.value) {
    return
  }
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) {
    return
  }
  submitting.value = true
  try {
    await requestPasswordReset(form.email.trim())
    submitted.value = true
    ElMessage.success('如果该邮箱已注册，重置邮件将很快送达')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <section class="auth-page">
    <div class="auth-card">
      <header class="auth-card__header">
        <p class="auth-card__eyebrow">GUDA 商城</p>
        <h1 class="auth-card__title">找回密码</h1>
        <p class="auth-card__desc">输入注册邮箱，我们会发送一次性重置链接（30 分钟内有效）。</p>
      </header>

      <el-alert
        v-if="submitted"
        type="success"
        :closable="false"
        title="重置邮件已受理"
        description="请前往邮箱查收；若未收到，请确认邮箱是否已注册。"
        class="auth-card__alert"
      />

      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" @submit.prevent>
        <el-form-item label="注册邮箱" prop="email">
          <el-input
            v-model="form.email"
            size="large"
            placeholder="请输入注册邮箱"
            autocomplete="email"
            @keyup.enter="submit"
          />
        </el-form-item>

        <el-button
          class="auth-card__submit"
          type="primary"
          size="large"
          :loading="submitting"
          @click="submit"
        >
          发送重置邮件
        </el-button>
      </el-form>

      <p class="auth-card__footer">
        想起密码了？
        <RouterLink class="auth-link" to="/login">返回登录</RouterLink>
      </p>
    </div>
  </section>
</template>

<script setup lang="ts">
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage } from 'element-plus'
import { onUnmounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { sendEmailCode } from '@/api/user'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const formRef = ref<FormInstance>()
const submitting = ref(false)
const sending = ref(false)
const countdown = ref(0)
let timer: ReturnType<typeof setInterval> | null = null

const form = reactive({
  email: '',
  email_code: '',
  username: '',
  password: '',
  confirmPassword: '',
})

const rules: FormRules = {
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '邮箱格式不正确', trigger: 'blur' },
  ],
  email_code: [
    { required: true, message: '请输入验证码', trigger: 'blur' },
    { pattern: /^\d{6}$/, message: '验证码为 6 位数字', trigger: 'blur' },
  ],
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    {
      pattern: /^[A-Za-z][A-Za-z0-9_]{2,19}$/,
      message: '3–20 位，以字母开头，仅含字母、数字、下划线',
      trigger: 'blur',
    },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 8, max: 64, message: '密码长度需为 8–64 位', trigger: 'blur' },
    {
      pattern: /^(?=.*[A-Za-z])(?=.*\d).+$/,
      message: '密码需同时包含字母与数字',
      trigger: 'blur',
    },
  ],
  confirmPassword: [
    { required: true, message: '请再次输入密码', trigger: 'blur' },
    {
      validator: (_rule, value, callback) => {
        if (value !== form.password) {
          callback(new Error('两次输入的密码不一致'))
        } else {
          callback()
        }
      },
      trigger: 'blur',
    },
  ],
}

function startCountdown() {
  countdown.value = 60
  timer = setInterval(() => {
    countdown.value -= 1
    if (countdown.value <= 0 && timer) {
      clearInterval(timer)
      timer = null
    }
  }, 1000)
}

async function sendCode() {
  if (!formRef.value) {
    return
  }
  const valid = await formRef.value.validateField('email').catch(() => false)
  if (!valid) {
    return
  }
  sending.value = true
  try {
    await sendEmailCode(form.email.trim())
    ElMessage.success('验证码已发送，请查收邮箱')
    startCountdown()
  } finally {
    sending.value = false
  }
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
    await auth.register({
      email: form.email.trim(),
      email_code: form.email_code.trim(),
      username: form.username.trim(),
      password: form.password,
    })
    ElMessage.success('注册成功，已为你自动登录')
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/user/profile'
    await router.replace(redirect)
  } finally {
    submitting.value = false
  }
}

onUnmounted(() => {
  if (timer) {
    clearInterval(timer)
  }
})
</script>

<template>
  <section class="auth-page">
    <div class="auth-card">
      <header class="auth-card__header">
        <p class="auth-card__eyebrow">GUDA 商城</p>
        <h1 class="auth-card__title">创建账号</h1>
        <p class="auth-card__desc">注册后可保存收货地址并查看订单。</p>
      </header>

      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" @submit.prevent>
        <el-form-item label="邮箱" prop="email">
          <el-input
            v-model="form.email"
            size="large"
            placeholder="用于接收验证码与找回密码"
            autocomplete="email"
          />
        </el-form-item>

        <el-form-item label="邮箱验证码" prop="email_code">
          <div class="auth-card__code">
            <el-input
              v-model="form.email_code"
              size="large"
              maxlength="6"
              placeholder="6 位数字"
            />
            <el-button
              size="large"
              :loading="sending"
              :disabled="countdown > 0"
              @click="sendCode"
            >
              {{ countdown > 0 ? `${countdown}s 后重发` : '获取验证码' }}
            </el-button>
          </div>
        </el-form-item>

        <el-form-item label="用户名" prop="username">
          <el-input
            v-model="form.username"
            size="large"
            placeholder="3–20 位字母、数字或下划线"
            autocomplete="username"
          />
        </el-form-item>

        <el-form-item label="密码" prop="password">
          <el-input
            v-model="form.password"
            size="large"
            type="password"
            show-password
            placeholder="8–64 位，需包含字母与数字"
            autocomplete="new-password"
          />
        </el-form-item>

        <el-form-item label="确认密码" prop="confirmPassword">
          <el-input
            v-model="form.confirmPassword"
            size="large"
            type="password"
            show-password
            placeholder="请再次输入密码"
            autocomplete="new-password"
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
          注册并登录
        </el-button>
      </el-form>

      <p class="auth-card__footer">
        已有账号？
        <RouterLink class="auth-link" to="/login">直接登录</RouterLink>
      </p>
    </div>
  </section>
</template>

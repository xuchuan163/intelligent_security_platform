<script setup lang="ts">
import { KeyRound, LogIn, Shield } from 'lucide-vue-next'
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { api } from '../api/client'
import { isJwtAuthMode, storeAuthTokens } from '../auth/session'
import { startTokenRefreshLoop } from '../auth/tokenRefresh'
import { useScopeContext } from '../composables/useScopeContext'
import type { AuthTokenPair } from '../types/api'

const router = useRouter()
const route = useRoute()
const scopeContext = useScopeContext()

const tenantId = ref('CSCEC')
const userId = ref('mock-admin')
const password = ref('Demo@12345')
const loading = ref(false)
const oauthLoading = ref(false)
const errorMessage = ref('')

async function completeTokenLogin(result: AuthTokenPair) {
  storeAuthTokens(result.access_token, result.refresh_token)
  api.setBearerToken(result.access_token)
  await scopeContext.initializeFromAuth(result.user)
  startTokenRefreshLoop()
  await router.replace('/dashboard')
}

async function submitLogin() {
  loading.value = true
  errorMessage.value = ''
  try {
    const result = await api.login({
      tenant_id: tenantId.value,
      user_id: userId.value,
      password: password.value,
    })
    await completeTokenLogin(result)
  } catch {
    errorMessage.value = '登录失败，请确认账号密码、后端已启动且已执行 seed_demo_data.py。'
  } finally {
    loading.value = false
  }
}

async function submitOAuthMockLogin() {
  oauthLoading.value = true
  errorMessage.value = ''
  try {
    const authorize = await api.oauthAuthorize()
    const callbackUrl = new URL(authorize.authorize_url, window.location.origin)
    const code = callbackUrl.searchParams.get('code')
    if (!code) {
      throw new Error('missing code')
    }
    const result = await api.oauthCallback({
      code,
      state: callbackUrl.searchParams.get('state'),
    })
    await completeTokenLogin(result)
  } catch {
    errorMessage.value =
      'OAuth2 演示登录失败。请确认后端 OAUTH_MOCK_ENABLED=true 且已 seed mock-admin 账号。'
  } finally {
    oauthLoading.value = false
  }
}

onMounted(async () => {
  const accessToken = typeof route.query.access_token === 'string' ? route.query.access_token : null
  const refreshToken = typeof route.query.refresh_token === 'string' ? route.query.refresh_token : null
  if (!accessToken || !refreshToken) return

  loading.value = true
  errorMessage.value = ''
  try {
    storeAuthTokens(accessToken, refreshToken)
    api.setBearerToken(accessToken)
    const user = await api.me()
    await scopeContext.initializeFromAuth(user)
    startTokenRefreshLoop()
    await router.replace('/dashboard')
  } catch {
    errorMessage.value = 'OAuth2 回调令牌无效，请重新登录。'
  } finally {
    loading.value = false
  }
})

const authModeLabel = isJwtAuthMode() ? 'JWT 认证模式' : 'Mock 演示模式'
</script>

<template>
  <div class="login-shell">
    <section class="login-card panel">
      <div class="login-brand">
        <span class="brand-mark">
          <Shield :size="22" stroke-width="2.2" />
        </span>
        <div>
          <p class="eyebrow">Phase 3-F / Auth</p>
          <h1>中建智慧安全平台</h1>
          <p class="muted-text">使用演示账号登录，获取 Bearer Token 访问全站 API。</p>
          <span class="status-chip login-mode-chip">{{ authModeLabel }}</span>
        </div>
      </div>

      <form class="form-grid login-form" @submit.prevent="submitLogin">
        <label>
          <span>租户</span>
          <input v-model="tenantId" autocomplete="organization" />
        </label>
        <label>
          <span>用户 ID</span>
          <input v-model="userId" autocomplete="username" />
        </label>
        <label class="form-span">
          <span>密码</span>
          <input v-model="password" type="password" autocomplete="current-password" />
        </label>
        <p class="muted-text form-span">
          演示账号：<code>mock-admin</code> / <code>Demo@12345</code>（平台管理员）；
          <code>U-PM-P001</code>（项目 P001）
        </p>
        <div class="action-row form-span">
          <button type="submit" class="action-button action-primary" :disabled="loading || oauthLoading">
            <LogIn :size="16" />
            {{ loading ? '登录中…' : '账号密码登录' }}
          </button>
          <button
            type="button"
            class="action-button"
            :disabled="loading || oauthLoading"
            @click="submitOAuthMockLogin"
          >
            <KeyRound :size="16" />
            {{ oauthLoading ? 'OAuth 跳转中…' : '集团 OAuth2（演示占位）' }}
          </button>
        </div>
        <p class="muted-text form-span">
          OAuth2 占位流程：<code>GET /auth/oauth/authorize</code> → mock 回调
          <code>/auth/oauth/callback</code>；正式 IdP 接入前 live 模式返回 501。
        </p>
        <p v-if="errorMessage" class="empty-state form-span">{{ errorMessage }}</p>
        <p v-if="!isJwtAuthMode()" class="muted-text form-span">
          当前为 Mock 模式，可直接
          <button type="button" class="link-button" @click="router.replace('/dashboard')">进入演示驾驶舱</button>
          ，无需登录。
        </p>
      </form>
    </section>
  </div>
</template>

<style scoped>
.login-mode-chip {
  margin-top: 10px;
}

.link-button {
  border: 0;
  background: transparent;
  color: var(--accent);
  padding: 0;
  font: inherit;
  font-weight: 600;
  cursor: pointer;
  text-decoration: underline;
}
</style>

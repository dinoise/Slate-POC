<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useGoogleAuth } from '../composables/useGoogleAuth'

const router = useRouter()
const { user, loading, error, initialize } = useGoogleAuth()

onMounted(() => {
  initialize()
})

function continuar() {
  router.push('/')
}
</script>

<template>
  <div class="login-page">
    <div class="login-card">
      <div class="login-logo">
        <span class="pi pi-shield logo-icon" />
      </div>
      <h1 class="login-title">Slate Admin</h1>
      <p class="login-subtitle">Inicia sesión con tu cuenta de Google</p>

      <div v-if="loading" class="login-loading">
        <span class="pi pi-spin pi-spinner" />
      </div>

      <div v-else-if="user" class="login-success">
        <div class="user-avatar">
          <img v-if="user.picture" :src="user.picture" :alt="user.name" class="avatar-img" />
          <span v-else class="pi pi-user avatar-fallback" />
        </div>
        <p class="user-name">{{ user.name }}</p>
        <p class="user-email">{{ user.email }}</p>
        <button class="continue-btn" @click="continuar">
          Continuar al dashboard
          <span class="pi pi-arrow-right" />
        </button>
      </div>

      <div v-else class="login-prompt">
        <p class="login-hint">Se abrirá el selector de cuenta de Google…</p>
        <p v-if="error" class="login-error">{{ error }}</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  background: var(--p-surface-950, #0a0a0a);
}

.login-card {
  background: var(--p-surface-900);
  border: 1px solid var(--p-surface-700);
  border-radius: 16px;
  padding: 2.5rem 2rem;
  width: 100%;
  max-width: 360px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.75rem;
  text-align: center;
}

.login-logo {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: var(--p-surface-800);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 0.5rem;
}

.logo-icon {
  font-size: 1.6rem;
  color: var(--p-primary-400);
}

.login-title {
  font-size: 1.4rem;
  font-weight: 700;
  color: var(--p-surface-0);
  margin: 0;
}

.login-subtitle {
  font-size: 0.875rem;
  color: var(--p-surface-400);
  margin: 0 0 1rem;
}

.login-loading {
  font-size: 1.5rem;
  color: var(--p-surface-400);
  padding: 1rem;
}

.login-success {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
  width: 100%;
}

.user-avatar {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  overflow: hidden;
  border: 2px solid var(--p-surface-600);
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--p-surface-800);
}

.avatar-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.avatar-fallback {
  font-size: 1.4rem;
  color: var(--p-surface-400);
}

.user-name {
  font-weight: 600;
  color: var(--p-surface-100);
  margin: 0.25rem 0 0;
}

.user-email {
  font-size: 0.85rem;
  color: var(--p-surface-400);
  margin: 0 0 0.75rem;
}

.continue-btn {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  background: var(--p-primary-500);
  color: #fff;
  border: none;
  border-radius: 8px;
  padding: 0.65rem 1.25rem;
  font-size: 0.9rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s;
  width: 100%;
  justify-content: center;
}

.continue-btn:hover {
  background: var(--p-primary-400);
}

.login-prompt {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  align-items: center;
}

.login-hint {
  font-size: 0.85rem;
  color: var(--p-surface-500);
  margin: 0;
}

.login-error {
  font-size: 0.85rem;
  color: var(--p-red-400);
  margin: 0;
}
</style>

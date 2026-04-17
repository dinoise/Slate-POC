<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useGoogleAuth } from '../composables/useGoogleAuth'

const router = useRouter()
const { user, error, promptSuppressed, initialize, renderButton } = useGoogleAuth()

const buttonContainer = ref<HTMLElement | null>(null)

// Cuando One Tap es suprimido, renderizamos el botón explícito de Google
watch(promptSuppressed, (suppressed) => {
  if (suppressed && buttonContainer.value) {
    renderButton(buttonContainer.value)
  }
})

// Si el usuario ya se autenticó, redirige
watch(user, (u) => {
  if (u) router.push('/')
}, { immediate: true })

onMounted(() => {
  initialize()
})
</script>

<template>
  <div class="login-page">
    <div class="login-card">
      <div class="login-logo">
        <span class="pi pi-shield logo-icon" />
      </div>
      <h1 class="login-title">Slate Admin</h1>
      <p class="login-subtitle">Inicia sesión con tu cuenta de Google</p>

      <template v-if="user">
        <div class="user-avatar">
          <img v-if="user.picture" :src="user.picture" :alt="user.name" class="avatar-img" />
          <span v-else class="pi pi-user avatar-fallback" />
        </div>
        <p class="user-name">{{ user.name }}</p>
        <p class="user-email">{{ user.email }}</p>
        <p class="login-hint">Redirigiendo…</p>
      </template>

      <template v-else>
        <!-- Botón explícito de Google — siempre montado en el DOM,
             GIS lo rellena cuando One Tap es suprimido -->
        <div ref="buttonContainer" class="google-button-container" />

        <p v-if="!promptSuppressed" class="login-hint">
          Se abrirá el selector de cuenta de Google…
        </p>
        <p v-if="error" class="login-error">{{ error }}</p>
      </template>
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
  margin: 0;
}

.google-button-container {
  margin: 0.5rem 0;
  min-height: 44px;
  display: flex;
  justify-content: center;
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

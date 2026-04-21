<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useGoogleAuth } from '@slate/composables'

const router = useRouter()
const { user, error, promptSuppressed, renderButton } = useGoogleAuth()

const buttonContainer = ref<HTMLElement | null>(null)

watch(promptSuppressed, (suppressed) => {
  if (suppressed && buttonContainer.value) {
    renderButton(buttonContainer.value)
  }
})

watch(user, (u) => {
  if (u) router.push('/report')
}, { immediate: true })
</script>

<template>
  <div class="min-h-dvh bg-base-200 flex items-center justify-center p-4">
    <div class="card bg-base-100 shadow-xl w-full max-w-sm">
      <div class="card-body items-center text-center gap-4">
        <!-- Logo -->
        <div class="avatar placeholder">
          <div class="bg-primary text-primary-content rounded-full w-14">
            <span class="text-2xl">📋</span>
          </div>
        </div>

        <div>
          <h1 class="card-title text-xl justify-center">Slate Reporter</h1>
          <p class="text-base-content/60 text-sm mt-1">Reporta un siniestro con tu cuenta de Google</p>
        </div>

        <!-- Autenticado — redirigiendo -->
        <template v-if="user">
          <div class="avatar">
            <div class="w-12 rounded-full ring ring-primary ring-offset-base-100 ring-offset-2">
              <img v-if="user.picture" :src="user.picture" :alt="user.name" />
              <div v-else class="bg-neutral text-neutral-content flex items-center justify-center w-full h-full">
                <span>{{ user.name.charAt(0) }}</span>
              </div>
            </div>
          </div>
          <p class="font-semibold">{{ user.name }}</p>
          <p class="text-sm text-base-content/60">{{ user.email }}</p>
          <span class="loading loading-dots loading-md text-primary" />
        </template>

        <!-- Login -->
        <template v-else>
          <div ref="buttonContainer" class="flex justify-center min-h-11" />

          <p v-if="!promptSuppressed" class="text-sm text-base-content/50">
            Se abrirá el selector de cuenta de Google…
          </p>
          <div v-if="error" role="alert" class="alert alert-error text-sm">
            <span>{{ error }}</span>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

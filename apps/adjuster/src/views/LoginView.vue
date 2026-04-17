<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useGoogleAuth } from '@slate/composables'

const router = useRouter()
const { user, error, promptSuppressed, initialize, renderButton } = useGoogleAuth()

const buttonContainer = ref<HTMLElement | null>(null)

watch(promptSuppressed, (suppressed) => {
  if (suppressed && buttonContainer.value) {
    renderButton(buttonContainer.value)
  }
})

watch(user, (u) => {
  if (u) router.push('/')
}, { immediate: true })

onMounted(() => {
  initialize()
})
</script>

<template>
  <v-container
    class="d-flex align-center justify-center"
    style="min-height: 100dvh;"
  >
    <v-card
      width="360"
      color="surface"
      rounded="xl"
      elevation="8"
      class="pa-6 text-center"
    >
      <!-- Logo -->
      <v-avatar color="primary" size="56" class="mb-4">
        <v-icon size="28">mdi-account-hard-hat</v-icon>
      </v-avatar>

      <h1 class="text-h6 font-weight-bold mb-1">Slate Ajustador</h1>
      <p class="text-body-2 text-medium-emphasis mb-6">
        Inicia sesión con tu cuenta de Google
      </p>

      <!-- Autenticado — redirigiendo -->
      <template v-if="user">
        <v-avatar size="48" class="mb-3">
          <v-img v-if="user.picture" :src="user.picture" :alt="user.name" />
          <v-icon v-else>mdi-account</v-icon>
        </v-avatar>
        <p class="text-body-1 font-weight-medium">{{ user.name }}</p>
        <p class="text-caption text-medium-emphasis mb-3">{{ user.email }}</p>
        <v-progress-linear indeterminate color="primary" rounded />
      </template>

      <!-- Login -->
      <template v-else>
        <!-- GIS renderiza el botón aquí cuando One Tap es suprimido -->
        <div ref="buttonContainer" class="d-flex justify-center mb-3" style="min-height: 44px;" />

        <p v-if="!promptSuppressed" class="text-caption text-medium-emphasis">
          Se abrirá el selector de cuenta de Google…
        </p>
        <v-alert v-if="error" type="error" density="compact" class="mt-3 text-left">
          {{ error }}
        </v-alert>
      </template>
    </v-card>
  </v-container>
</template>

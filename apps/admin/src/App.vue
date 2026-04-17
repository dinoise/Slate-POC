<script setup lang="ts">
import { onMounted } from 'vue'
import AppLayout from './components/layout/AppLayout.vue'
import { useGoogleAuth } from './composables/useGoogleAuth'

const { initialize } = useGoogleAuth()

// Restaura el token del sessionStorage en cada carga de página.
// Sin esto, _authToken en el api-client queda null tras un reload
// aunque el usuario ya estuviera autenticado.
onMounted(() => {
  initialize()
})
</script>

<template>
  <AppLayout />
</template>

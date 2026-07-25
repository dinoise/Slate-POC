<script setup lang="ts">
import { onMounted } from 'vue'
import Toast from 'primevue/toast'
import AppLayout from './components/layout/AppLayout.vue'
import { useGoogleAuth } from '@slate/composables'

const { initialize } = useGoogleAuth()

onMounted(() => {
  initialize()
})
</script>

<template>
  <AppLayout />
  <Toast position="bottom-right" />
</template>

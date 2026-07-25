<script setup lang="ts">
import { onMounted } from 'vue'
import { RouterView } from 'vue-router'
import { useGoogleAuth } from '@slate/composables'

const { initialize } = useGoogleAuth()
onMounted(() => initialize())
</script>

<template>
  <v-app>
    <RouterView />
  </v-app>
</template>

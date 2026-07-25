<script setup lang="ts">
defineProps<{
  icon?: string
  title?: string
  message?: string
  error?: string | null
}>()
</script>

<template>
  <div class="empty-state">
    <span v-if="error" class="pi pi-exclamation-circle empty-state__icon empty-state__icon--error" />
    <span v-else :class="`pi ${icon ?? 'pi-inbox'} empty-state__icon`" />
    <p class="empty-state__title">{{ error ? 'Ocurrió un error' : (title ?? 'Sin resultados') }}</p>
    <p class="empty-state__message">{{ error ?? (message ?? 'No hay datos para mostrar.') }}</p>
  </div>
</template>

<style scoped>
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  padding: 3rem 1rem;
  color: var(--p-surface-400);
}

.empty-state__icon {
  font-size: 2.5rem;
  opacity: 0.5;
}

.empty-state__icon--error {
  color: var(--p-red-400);
  opacity: 0.8;
}

.empty-state__title {
  font-size: 1rem;
  font-weight: 600;
  color: var(--p-surface-300);
  margin-top: 0.25rem;
}

.empty-state__message {
  font-size: 0.85rem;
  color: var(--p-surface-500);
}
</style>

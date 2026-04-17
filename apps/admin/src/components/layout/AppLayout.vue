<script setup lang="ts">
import AppSidebar from './AppSidebar.vue'
</script>

<template>
  <div class="app-layout">
    <AppSidebar />
    <div class="app-main">
      <header class="app-topbar">
        <slot name="topbar" />
      </header>
      <main class="app-content">
        <router-view />
      </main>
    </div>
  </div>
</template>

<style scoped>
.app-layout {
  display: flex;
  height: 100vh;
  overflow: hidden;
  background: var(--p-surface-950);
}

.app-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.app-topbar {
  height: 56px;
  display: flex;
  align-items: center;
  padding: 0 1.5rem;
  background: var(--p-surface-900);
  border-bottom: 1px solid var(--p-surface-700);
  flex-shrink: 0;
}

.app-content {
  flex: 1;
  overflow-y: auto;
  padding: 1.5rem;
}
</style>

<script setup lang="ts">
import { useRoute } from 'vue-router'
import Menu from 'primevue/menu'

const route = useRoute()

const items = [
  {
    label: 'Panel',
    items: [
      { label: 'Dashboard', icon: 'pi pi-home', route: '/' },
    ],
  },
  {
    label: 'Operaciones',
    items: [
      { label: 'Incidentes', icon: 'pi pi-exclamation-triangle', route: '/incidents' },
      { label: 'Ajustadores', icon: 'pi pi-users', route: '/adjusters' },
      { label: 'Asignaciones', icon: 'pi pi-link', route: '/assignments' },
    ],
  },
  {
    label: 'Análisis',
    items: [
      { label: 'Optimización', icon: 'pi pi-sliders-h', route: '/optimization' },
      { label: 'Demanda', icon: 'pi pi-chart-bar', route: '/demand' },
      { label: 'Posicionamiento', icon: 'pi pi-map-marker', route: '/positioning' },
    ],
  },
  {
    label: 'Configuración',
    items: [
      { label: 'Usuarios', icon: 'pi pi-user', route: '/users' },
      { label: 'Ajustes', icon: 'pi pi-cog', route: '/settings' },
    ],
  },
]
</script>

<template>
  <aside class="app-sidebar">
    <div class="sidebar-header">
      <span class="pi pi-compass sidebar-logo" />
      <span class="sidebar-title">Despacho</span>
    </div>
    <Menu :model="items" class="sidebar-menu">
      <template #item="{ item }">
        <router-link
          v-if="item.route"
          :to="item.route"
          class="sidebar-item"
          :class="{ 'sidebar-item--active': route.path === item.route }"
        >
          <span :class="item.icon" />
          <span>{{ item.label }}</span>
        </router-link>
      </template>
    </Menu>
  </aside>
</template>

<style scoped>
.app-sidebar {
  width: 240px;
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--p-surface-900);
  border-right: 1px solid var(--p-surface-700);
  flex-shrink: 0;
}

.sidebar-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 1.25rem 1rem;
  border-bottom: 1px solid var(--p-surface-700);
}

.sidebar-logo {
  font-size: 1.5rem;
  color: var(--p-primary-400);
}

.sidebar-title {
  font-size: 1.1rem;
  font-weight: 700;
  color: var(--p-surface-0);
  letter-spacing: 0.05em;
}

.sidebar-menu {
  flex: 1;
  background: transparent !important;
  border: none !important;
  padding: 0.5rem 0;
  overflow-y: auto;
}

.sidebar-item {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.6rem 1rem;
  border-radius: 6px;
  margin: 0 0.5rem;
  color: var(--p-surface-300);
  text-decoration: none;
  font-size: 0.9rem;
  transition: background 0.15s, color 0.15s;
}

.sidebar-item:hover {
  background: var(--p-surface-700);
  color: var(--p-surface-0);
}

.sidebar-item--active {
  background: var(--p-primary-900);
  color: var(--p-primary-300);
  font-weight: 600;
}
</style>

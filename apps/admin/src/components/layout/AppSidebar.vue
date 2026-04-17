<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'
import Menu from 'primevue/menu'
import { useGoogleAuth } from '@slate/composables'

const route = useRoute() ?? { path: '' }
const router = useRouter()
const { user, signOut } = useGoogleAuth()

function handleSignOut() {
  signOut()
  router.push('/login')
}

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

    <div class="sidebar-footer">
      <div v-if="user" class="user-info">
        <img v-if="user.picture" :src="user.picture" :alt="user.name" class="user-avatar" />
        <span v-else class="pi pi-user user-avatar-fallback" />
        <div class="user-text">
          <span class="user-name">{{ user.name }}</span>
          <span class="user-email">{{ user.email }}</span>
        </div>
      </div>
      <button class="logout-btn" @click="handleSignOut">
        <span class="pi pi-sign-out" />
        <span>Cerrar sesión</span>
      </button>
    </div>
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

.sidebar-footer {
  border-top: 1px solid var(--p-surface-700);
  padding: 0.75rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.25rem 0.25rem;
  overflow: hidden;
}

.user-avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  flex-shrink: 0;
  object-fit: cover;
}

.user-avatar-fallback {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--p-surface-700);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.9rem;
  color: var(--p-surface-400);
  flex-shrink: 0;
}

.user-text {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.user-name {
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--p-surface-100);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.user-email {
  font-size: 0.7rem;
  color: var(--p-surface-500);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.logout-btn {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.55rem 0.75rem;
  border-radius: 6px;
  border: none;
  background: transparent;
  color: var(--p-surface-400);
  font-size: 0.875rem;
  cursor: pointer;
  width: 100%;
  transition: background 0.15s, color 0.15s;
}

.logout-btn:hover {
  background: var(--p-surface-700);
  color: var(--p-red-400);
}
</style>

import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import { createPinia } from 'pinia'
import { createVuetify } from 'vuetify'
import App from '../App.vue'

const router = createRouter({
  history: createMemoryHistory(),
  routes: [{ path: '/', component: { template: '<div />' } }],
})

const vuetify = createVuetify()

describe('App', () => {
  it('mounts without errors', async () => {
    const wrapper = mount(App, {
      global: {
        plugins: [router, createPinia(), vuetify],
      },
    })
    await router.isReady()
    expect(wrapper.exists()).toBe(true)
  })
})

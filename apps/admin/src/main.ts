import './style.css'
import { createApp } from 'vue'

// InputChips emite un warning de deprecación interno de PrimeVue v4 que apunta
// a AutoComplete, pero AutoComplete no soporta tags libres (string[]).
// El issue #5744 está cerrado sin fix real — se suprime el ruido hasta que
// PrimeVue lo resuelva correctamente.
if (import.meta.env.DEV) {
  const _warn = console.warn.bind(console)
  console.warn = (...args: unknown[]) => {
    if (typeof args[0] === 'string' && args[0].includes('Deprecated since v4')) return
    _warn(...args)
  }
}
import { createPinia } from 'pinia'
import PrimeVue from 'primevue/config'
import ToastService from 'primevue/toastservice'
import Tooltip from 'primevue/tooltip'
import Aura from '@primeuix/themes/aura'
import 'primeicons/primeicons.css'

import App from './App.vue'
import router from './router'

const app = createApp(App)

app.use(createPinia())
app.use(router)
app.use(PrimeVue, {
  theme: {
    preset: Aura,
    options: {
      darkModeSelector: '.dark',
    },
  },
})
app.use(ToastService)
app.directive('tooltip', Tooltip)

app.mount('#app')

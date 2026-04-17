import { fileURLToPath } from 'node:url'
import { mergeConfig, defineConfig, configDefaults } from 'vitest/config'
import viteConfig from './vite.config'

export default mergeConfig(
  viteConfig,
  defineConfig({
    test: {
      environment: 'jsdom',
      // vuetify imports CSS directly from node_modules — Node can't handle it.
      // Inlining tells vitest to run vuetify through vite-node instead of Node.
      server: {
        deps: {
          inline: ['vuetify'],
        },
      },
      // Polyfill ResizeObserver, IntersectionObserver, CSS.supports for jsdom
      setupFiles: ['./src/__tests__/setup.ts'],
      exclude: [...configDefaults.exclude, 'e2e/**'],
      root: fileURLToPath(new URL('./', import.meta.url)),
      coverage: {
        provider: 'v8',
        reporter: ['text', 'json-summary', 'json'],
        reportsDirectory: './coverage',
        thresholds: { lines: 0 },
      },
    },
  }),
)

/**
 * Vitest setup file — polyfills for jsdom missing browser APIs used by Vuetify 4.
 *
 * jsdom does not implement ResizeObserver, IntersectionObserver, or CSS.supports,
 * all of which Vuetify 4 requires. We stub them so component tests don't throw.
 */

// ResizeObserver — used by VApp layout system
globalThis.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}

// IntersectionObserver — used by some Vuetify scroll/lazy components
globalThis.IntersectionObserver = class {
  observe() {}
  unobserve() {}
  disconnect() {}
  root = null
  rootMargin = ''
  thresholds = []
  takeRecords() { return [] }
  scrollMargin = ''
} as unknown as typeof IntersectionObserver

// CSS.supports — used by Vuetify feature detection
if (!globalThis.CSS) {
  globalThis.CSS = { supports: () => false } as unknown as typeof CSS
}

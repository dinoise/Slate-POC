/// <reference types="vite/client" />

// leaflet-ant-path has no bundled type declarations — ambient shim so
// `import 'leaflet-ant-path'` is accepted by vue-tsc without @ts-ignore.
declare module 'leaflet-ant-path'

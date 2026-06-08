/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_AUTH_MODE?: 'mock' | 'jwt'
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

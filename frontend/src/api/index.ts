import { httpApi } from './http'
import { mockApi } from './mock'

// Defaults to the in-browser mock so the app is fully demoable without the
// Django backend running. Set VITE_USE_MOCK=false (and VITE_API_URL) in
// .env.local once the real REST endpoints described in api/http.ts exist.
const USE_MOCK = import.meta.env.VITE_USE_MOCK !== 'false'

export const api = USE_MOCK ? mockApi : httpApi
export const isMockApi = USE_MOCK

export * from './types'

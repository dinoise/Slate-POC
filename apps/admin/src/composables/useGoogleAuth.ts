import { ref } from 'vue'
import { setAuthToken } from '@slate/api-client'

declare global {
  interface Window {
    google: {
      accounts: {
        id: {
          initialize: (config: object) => void
          prompt: (callback?: (notification: PromptNotification) => void) => void
          renderButton: (element: HTMLElement, config: object) => void
          disableAutoSelect: () => void
        }
      }
    }
  }
}

interface PromptNotification {
  // Estos métodos existen en One Tap legacy pero pueden no estar en FedCM
  isNotDisplayed?: () => boolean
  isSkippedMoment?: () => boolean
  isDismissedMoment?: () => boolean
  getNotDisplayedReason?: () => string
  getSkippedReason?: () => string
  getDismissedReason?: () => string
}

interface GoogleCredentialResponse {
  credential: string
}

interface DecodedToken {
  email: string
  name: string
  picture?: string
  exp: number
  aud: string
}

export interface AuthUser {
  email: string
  name: string
  picture?: string
}

const user = ref<AuthUser | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)
// true cuando One Tap fue suprimido — LoginView muestra el botón explícito
const promptSuppressed = ref(false)

function parseJwt(token: string): DecodedToken {
  const part = token.split('.')[1]
  if (!part) throw new Error('Invalid JWT')
  const base64 = part.replace(/-/g, '+').replace(/_/g, '/')
  return JSON.parse(decodeURIComponent(
    atob(base64).split('').map((c) =>
      '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2)
    ).join(''),
  ))
}

function isTokenExpired(token: string): boolean {
  try {
    const { exp } = parseJwt(token)
    return Date.now() / 1000 > exp - 30
  } catch {
    return true
  }
}

function handleCredentialResponse(response: GoogleCredentialResponse) {
  try {
    const decoded = parseJwt(response.credential)
    user.value = { email: decoded.email, name: decoded.name, picture: decoded.picture }
    setAuthToken(response.credential)
    sessionStorage.setItem('gid_token', response.credential)
    error.value = null
    promptSuppressed.value = false
  } catch {
    error.value = 'Error al procesar credencial de Google'
  }
}

export function useGoogleAuth() {
  function initialize() {
    const clientId = (import.meta as ImportMeta & { env: { VITE_GOOGLE_CLIENT_ID: string } })
      .env.VITE_GOOGLE_CLIENT_ID

    if (!clientId) {
      error.value = 'VITE_GOOGLE_CLIENT_ID no configurado'
      return
    }

    // Restore token from session if still valid
    const stored = sessionStorage.getItem('gid_token')
    if (stored && !isTokenExpired(stored)) {
      handleCredentialResponse({ credential: stored })
    }

    const script = document.createElement('script')
    script.src = 'https://accounts.google.com/gsi/client'
    script.async = true
    script.defer = true
    script.onload = () => {
      window.google.accounts.id.initialize({
        client_id: clientId,
        callback: handleCredentialResponse,
        auto_select: true,
        cancel_on_tap_outside: false,
      })

      if (!user.value) {
        // Callback de diagnóstico compatible con FedCM y One Tap legacy.
        // isNotDisplayed/isSkippedMoment serán deprecated con FedCM obligatorio —
        // el botón explícito (renderButton) es el fallback recomendado por Google.
        window.google.accounts.id.prompt((notification) => {
          const notDisplayed = notification.isNotDisplayed?.()
          const skipped = notification.isSkippedMoment?.()
          if (notDisplayed || skipped) {
            const reason = notDisplayed
              ? notification.getNotDisplayedReason?.()
              : notification.getSkippedReason?.()
            console.info('[GIS] One Tap suprimido:', reason ?? 'unknown')
            promptSuppressed.value = true
          }
        })
      }
    }
    document.head.appendChild(script)
  }

  function renderButton(element: HTMLElement) {
    if (!window.google) return
    window.google.accounts.id.renderButton(element, {
      type: 'standard',
      theme: 'filled_black',
      size: 'large',
      text: 'signin_with',
      shape: 'rectangular',
      width: 280,
    })
  }

  function signOut() {
    if (window.google) window.google.accounts.id.disableAutoSelect()
    sessionStorage.removeItem('gid_token')
    setAuthToken(null)
    user.value = null
  }

  function isAuthenticated(): boolean {
    const stored = sessionStorage.getItem('gid_token')
    return !!stored && !isTokenExpired(stored)
  }

  return { user, loading, error, promptSuppressed, initialize, renderButton, signOut, isAuthenticated }
}

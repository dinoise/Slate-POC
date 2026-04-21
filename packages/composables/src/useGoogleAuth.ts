import { ref } from 'vue'
import { setAuthToken, onUnauthorized } from '@slate/api-client'

declare global {
  interface Window {
    google: {
      accounts: {
        id: {
          initialize: (config: object) => void
          prompt: () => void
          renderButton: (element: HTMLElement, config: object) => void
          disableAutoSelect: () => void
        }
      }
    }
  }
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
// Guard: initialize() must only run once per page load
let _initialized = false

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
    if (_initialized) return
    _initialized = true

    // When any API request returns 401, clear the session and re-prompt
    onUnauthorized(() => {
      sessionStorage.removeItem('gid_token')
      setAuthToken(null)
      user.value = null
      // Re-trigger One Tap — Google will silently re-issue if the user has an active session
      if (window.google) {
        window.google.accounts.id.prompt()
        setTimeout(() => { if (!user.value) promptSuppressed.value = true }, 500)
      }
    })

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
        use_fedcm_for_prompt: true,
      })

      if (!user.value) {
        // Con FedCM el prompt es gestionado por el browser — no hay callback de estado.
        // Si no hay interacción en 500ms asumimos que fue suprimido y mostramos el botón.
        window.google.accounts.id.prompt()
        setTimeout(() => {
          if (!user.value) promptSuppressed.value = true
        }, 500)
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

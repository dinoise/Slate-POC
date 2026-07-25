import { ref, onUnmounted, type Ref } from 'vue'

export interface GeolocationState {
  latitude: Ref<number | null>
  longitude: Ref<number | null>
  accuracy: Ref<number | null>
  error: Ref<string | null>
  supported: boolean
}

/**
 * Reactive wrapper around navigator.geolocation.
 * Watches position continuously and cleans up on unmount.
 */
export function useGeolocation(): GeolocationState {
  const latitude = ref<number | null>(null)
  const longitude = ref<number | null>(null)
  const accuracy = ref<number | null>(null)
  const error = ref<string | null>(null)
  const supported = 'geolocation' in navigator

  let watchId: number | null = null

  if (supported) {
    watchId = navigator.geolocation.watchPosition(
      (pos) => {
        latitude.value = pos.coords.latitude
        longitude.value = pos.coords.longitude
        accuracy.value = pos.coords.accuracy
        error.value = null
      },
      (err) => {
        error.value = err.message
      },
      { enableHighAccuracy: true, timeout: 10_000 },
    )
  } else {
    error.value = 'Geolocation not supported by this browser'
  }

  onUnmounted(() => {
    if (watchId !== null) navigator.geolocation.clearWatch(watchId)
  })

  return { latitude, longitude, accuracy, error, supported }
}

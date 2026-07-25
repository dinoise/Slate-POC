/**
 * Date formatting utilities anchored to America/Mexico_City.
 *
 * All timestamps stored in the DB are UTC. These helpers convert them
 * to local CDMX time for display, regardless of the browser's own timezone.
 */

const MX_TZ = 'America/Mexico_City'
const MX_LOCALE = 'es-MX'

/** Full date + time: "28/04/2026, 18:35" */
export function formatMXDate(
  iso: string | Date | null | undefined,
  opts: Intl.DateTimeFormatOptions = {},
): string {
  if (!iso) return '—'
  const date = typeof iso === 'string' ? new Date(iso) : iso
  if (isNaN(date.getTime())) return '—'
  return new Intl.DateTimeFormat(MX_LOCALE, {
    timeZone: MX_TZ,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    ...opts,
  }).format(date)
}

/** Time only: "18:35" */
export function formatMXTime(iso: string | Date | null | undefined): string {
  return formatMXDate(iso, {
    year: undefined,
    month: undefined,
    day: undefined,
    hour: '2-digit',
    minute: '2-digit',
  })
}

/**
 * Returns the current { dia, hora } slot in CDMX local time.
 * dia: 0=Mon … 6=Sun  (matches Python weekday() convention used by the demand model)
 * hora: 0–23
 *
 * Replaces raw `new Date().getDay()` / `new Date().getHours()` which use
 * the browser's local timezone instead of CDMX.
 */
export function getMXCurrentSlot(): { dia: number; hora: number } {
  const now = new Date()

  // Extract numeric parts in CDMX timezone using a fixed reference date format
  const fmt = new Intl.DateTimeFormat('en-CA', {
    timeZone: MX_TZ,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
    weekday: 'long',
  })

  const parts = fmt.formatToParts(now)
  const get = (type: string) => parts.find((p) => p.type === type)?.value ?? '0'

  const hora = parseInt(get('hour'), 10)

  // Map English weekday name → Python weekday() index (0=Mon … 6=Sun)
  const weekdayMap: Record<string, number> = {
    Monday: 0,
    Tuesday: 1,
    Wednesday: 2,
    Thursday: 3,
    Friday: 4,
    Saturday: 5,
    Sunday: 6,
  }
  const dia = weekdayMap[get('weekday')] ?? 0

  return { dia, hora }
}

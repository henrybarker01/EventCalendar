import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import { api, type Event } from '../api/client'
import { localDateStr } from '../utils/date'
import { useBookmarksStore } from './bookmarks'
import { useHiddenStore } from './hidden'
import { useRemindersStore } from './reminders'

// Theme chip for events the API gave no theme.
export const NO_THEME = 'Overig'

export const DISTANCE_OPTIONS = [
  { value: 'all', label: 'Alle afstanden' },
  { value: 'local', label: 'Gemeente Barneveld' },
  { value: '10', label: 'Tot 10 km' },
  { value: '15', label: 'Tot 15 km' },
  { value: '25', label: 'Tot 25 km' },
] as const
export type DistanceFilter = (typeof DISTANCE_OPTIONS)[number]['value']

export const DATE_PRESETS = [
  { value: 'today', label: 'Vandaag' },
  { value: 'weekend', label: 'Dit weekend' },
  { value: 'week', label: 'Komende 7 dagen' },
] as const
export type DatePreset = (typeof DATE_PRESETS)[number]['value'] | ''

// Theme and distance choices are remembered per device.
const SAVED_FILTERS_KEY = 'eventview.filters'

function loadSavedFilters(): { themes: string[]; distance: DistanceFilter } {
  const fallback = { themes: [], distance: 'all' as DistanceFilter }
  try {
    const saved = JSON.parse(localStorage.getItem(SAVED_FILTERS_KEY) ?? '{}')
    return {
      themes: Array.isArray(saved.themes) ? saved.themes.filter((t: unknown) => typeof t === 'string') : [],
      distance: DISTANCE_OPTIONS.some(o => o.value === saved.distance) ? saved.distance : 'all',
    }
  } catch {
    return fallback
  }
}

// [first, last] day (inclusive, local) of a date preset.
function presetRange(preset: DatePreset): [string, string] | null {
  if (!preset) return null
  const today = new Date()
  const start = new Date(today)
  const end = new Date(today)
  if (preset === 'weekend') {
    const dow = today.getDay() // 0 = Sunday, 6 = Saturday
    if (dow !== 0) {
      start.setDate(today.getDate() + (dow === 6 ? 0 : 6 - dow))
      end.setDate(today.getDate() + 7 - dow)
    }
  } else if (preset === 'week') {
    end.setDate(today.getDate() + 6)
  }
  return [localDateStr(start), localDateStr(end)]
}

export const useEventsStore = defineStore('events', () => {
  const events = ref<Event[]>([])
  const attractions = ref<Event[]>([])
  const sources = ref<string[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const hasFetched = ref(false)

  const selectedSource = ref<string>('')
  const fromDate = ref<string>('')
  const toDate = ref<string>('')
  const search = ref<string>('')
  const datePreset = ref<DatePreset>('')

  const saved = loadSavedFilters()
  const themes = ref<string[]>(saved.themes)
  const distance = ref<DistanceFilter>(saved.distance)

  watch([themes, distance], () => {
    try {
      localStorage.setItem(SAVED_FILTERS_KEY, JSON.stringify({ themes: themes.value, distance: distance.value }))
    } catch {
      // Storage unavailable (private mode, blocked): the filters just aren't remembered.
    }
  }, { deep: true })

  // Without a from-date filter, events are loaded from this date on (plus ones
  // still running), so past rows can't fill the API's limit before upcoming
  // ones. The calendar moves it back when it shows earlier days.
  const loadedFrom = ref<string>(localDateStr(new Date()))
  let latestRequest = 0
  let fetchedAt = 0

  // Hidden, search and distance. Theme chip counts are based on this, so they
  // show what each theme would add.
  function passesBase(e: Event): boolean {
    if (useHiddenStore().isHidden(e.id)) return false
    const q = search.value.toLowerCase()
    if (q && !e.title.toLowerCase().includes(q) && !(e.description ?? '').toLowerCase().includes(q)) return false
    if (distance.value === 'local') return e.municipality === 'Barneveld'
    if (distance.value !== 'all') return e.distance_km !== null && e.distance_km <= Number(distance.value)
    return true
  }

  function hasSelectedTheme(e: Event): boolean {
    if (!themes.value.length) return true
    return e.themes.length
      ? e.themes.some(t => themes.value.includes(t))
      : themes.value.includes(NO_THEME)
  }

  function inDatePreset(e: Event): boolean {
    const range = presetRange(datePreset.value)
    if (!range || !e.event_date) return true
    return e.event_date <= range[1] && (e.end_date ?? e.event_date) >= range[0]
  }

  function toggleTheme(theme: string) {
    themes.value = themes.value.includes(theme)
      ? themes.value.filter(t => t !== theme)
      : [...themes.value, theme]
  }

  const baseEvents = computed(() => events.value.filter(e => passesBase(e) && inDatePreset(e)))
  const baseAttractions = computed(() => attractions.value.filter(passesBase))
  const filtered = computed(() => baseEvents.value.filter(hasSelectedTheme))
  const filteredAttractions = computed(() => baseAttractions.value.filter(hasSelectedTheme))

  async function fetchEvents() {
    const request = ++latestRequest
    loading.value = true
    error.value = null
    try {
      const [evts, attrs] = await Promise.all([
        api.getEvents({ source: selectedSource.value || undefined, event_type: 'event', from_date: fromDate.value || loadedFrom.value, to_date: toDate.value || undefined, limit: 5000 }),
        api.getEvents({ source: selectedSource.value || undefined, event_type: 'attraction', limit: 5000 }),
      ])
      if (request !== latestRequest) return // a newer fetch has replaced this one
      events.value = evts
      attractions.value = attrs
      hasFetched.value = true
      fetchedAt = Date.now()
      const all = [...evts, ...attrs]
      useBookmarksStore().initFromEvents(all)
      useHiddenStore().initFromEvents(all)
      useRemindersStore().fetchReminders()
    } catch (e: any) {
      if (request === latestRequest) error.value = e.message ?? 'Failed to load events'
    } finally {
      if (request === latestRequest) loading.value = false
    }
  }

  // Make sure events from `date` on are loaded (the calendar's first visible day).
  async function loadFrom(date: string) {
    const extend = date < loadedFrom.value
    if (extend) loadedFrom.value = date
    if (!hasFetched.value || (extend && !fromDate.value)) await fetchEvents()
  }

  // The list views stay alive between visits (KeepAlive), so they refresh old
  // data when shown again. The current list stays on screen meanwhile.
  function refreshIfStale(maxAgeMs = 10 * 60 * 1000) {
    if (hasFetched.value && !loading.value && Date.now() - fetchedAt > maxAgeMs) fetchEvents()
  }

  async function fetchSources() {
    sources.value = await api.getSources()
  }

  return {
    events, attractions, sources, loading, error, hasFetched,
    baseEvents, baseAttractions, filtered, filteredAttractions,
    selectedSource, fromDate, toDate, search, datePreset, themes, distance,
    passesBase, hasSelectedTheme, toggleTheme, fetchEvents, loadFrom, refreshIfStale, fetchSources,
  }
})

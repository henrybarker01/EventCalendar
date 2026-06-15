import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api, type Event } from '../api/client'

export const useEventsStore = defineStore('events', () => {
  const events = ref<Event[]>([])
  const sources = ref<string[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  const selectedSource = ref<string>('')
  const fromDate = ref<string>('')
  const toDate = ref<string>('')
  const search = ref<string>('')

  const filtered = computed(() => {
    const q = search.value.toLowerCase()
    return events.value.filter(e => {
      if (q && !e.title.toLowerCase().includes(q) && !(e.description ?? '').toLowerCase().includes(q)) return false
      return true
    })
  })

  async function fetchEvents() {
    loading.value = true
    error.value = null
    try {
      events.value = await api.getEvents({
        source: selectedSource.value || undefined,
        from_date: fromDate.value || undefined,
        to_date: toDate.value || undefined,
        limit: 500,
      })
    } catch (e: any) {
      error.value = e.message ?? 'Failed to load events'
    } finally {
      loading.value = false
    }
  }

  async function fetchSources() {
    sources.value = await api.getSources()
  }

  return { events, sources, loading, error, filtered, selectedSource, fromDate, toDate, search, fetchEvents, fetchSources }
})

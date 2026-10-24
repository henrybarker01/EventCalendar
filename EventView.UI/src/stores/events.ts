import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api, type Event } from '../api/client'
import { useBookmarksStore } from './bookmarks'
import { useHiddenStore } from './hidden'
import { useRemindersStore } from './reminders'

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

  const filtered = computed(() => {
    const q = search.value.toLowerCase()
    const hiddenStore = useHiddenStore()
    return events.value.filter(e =>
      !hiddenStore.isHidden(e.id) &&
      (!q || e.title.toLowerCase().includes(q) || (e.description ?? '').toLowerCase().includes(q))
    )
  })

  const filteredAttractions = computed(() => {
    const q = search.value.toLowerCase()
    const hiddenStore = useHiddenStore()
    return attractions.value.filter(e =>
      !hiddenStore.isHidden(e.id) &&
      (!q || e.title.toLowerCase().includes(q) || (e.description ?? '').toLowerCase().includes(q))
    )
  })

  async function fetchEvents() {
    loading.value = true
    error.value = null
    try {
      const [evts, attrs] = await Promise.all([
        api.getEvents({ source: selectedSource.value || undefined, event_type: 'event', from_date: fromDate.value || undefined, to_date: toDate.value || undefined, limit: 5000 }),
        api.getEvents({ source: selectedSource.value || undefined, event_type: 'attraction', limit: 5000 }),
      ])
      events.value = evts
      attractions.value = attrs
      hasFetched.value = true
      const all = [...evts, ...attrs]
      useBookmarksStore().initFromEvents(all)
      useHiddenStore().initFromEvents(all)
      useRemindersStore().fetchReminders()
    } catch (e: any) {
      error.value = e.message ?? 'Failed to load events'
    } finally {
      loading.value = false
    }
  }

  async function fetchSources() {
    sources.value = await api.getSources()
  }

  return { events, attractions, sources, loading, error, hasFetched, filtered, filteredAttractions, selectedSource, fromDate, toDate, search, fetchEvents, fetchSources }
})

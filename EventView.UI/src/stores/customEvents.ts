import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api, type CustomEvent } from '../api/client'
import { usePushNotifications } from '../composables/usePushNotifications'

export const useCustomEventsStore = defineStore('customEvents', () => {
  const events = ref<CustomEvent[]>([])

  const byDate = computed(() => {
    const map: Record<string, CustomEvent[]> = {}
    for (const e of events.value) {
      if (!map[e.event_date]) map[e.event_date] = []
      map[e.event_date].push(e)
    }
    return map
  })

  async function load() {
    events.value = await api.getCustomEvents()
  }

  async function add(title: string, eventDate: string): Promise<CustomEvent> {
    // Own items get automatic reminders too (see bookmarks.toggle).
    void usePushNotifications().ensureSubscription()
    const ev = await api.createCustomEvent(title, eventDate)
    events.value.push(ev)
    events.value.sort((a, b) => (a.event_date > b.event_date ? 1 : -1))
    return ev
  }

  async function remove(id: number) {
    await api.deleteCustomEvent(id)
    events.value = events.value.filter(e => e.id !== id)
  }

  return { events, byDate, load, add, remove }
})

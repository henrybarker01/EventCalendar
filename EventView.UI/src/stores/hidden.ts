import { defineStore } from 'pinia'
import { reactive } from 'vue'
import { api } from '../api/client'
import type { Event } from '../api/client'

export const useHiddenStore = defineStore('hidden', () => {
  const hiddenIds = reactive(new Set<number>())

  function isHidden(id: number): boolean {
    return hiddenIds.has(id)
  }

  function initFromEvents(events: Event[]) {
    hiddenIds.clear()
    for (const e of events) {
      if (e.is_hidden) hiddenIds.add(e.id)
    }
  }

  async function hide(id: number) {
    hiddenIds.add(id)
    await api.hideEvent(id)
  }

  async function unhide(id: number) {
    hiddenIds.delete(id)
    await api.unhideEvent(id)
  }

  return { hiddenIds, isHidden, initFromEvents, hide, unhide }
})

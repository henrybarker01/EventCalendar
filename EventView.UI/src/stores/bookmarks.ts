import { defineStore } from 'pinia'
import { reactive } from 'vue'
import { api, type Event } from '../api/client'
import { usePushNotifications } from '../composables/usePushNotifications'

export const useBookmarksStore = defineStore('bookmarks', () => {
  const bookmarkedIds = reactive(new Set<number>())
  const chosenDates = reactive(new Map<number, string>())

  function isBookmarked(id: number): boolean {
    return bookmarkedIds.has(id)
  }

  function getChosenDate(id: number): string | null {
    return chosenDates.get(id) ?? null
  }

  function initFromEvents(events: Event[]) {
    bookmarkedIds.clear()
    chosenDates.clear()
    for (const e of events) {
      if (e.is_bookmarked) {
        bookmarkedIds.add(e.id)
        if (e.bookmark_date) chosenDates.set(e.id, e.bookmark_date)
      }
    }
  }

  function syncEvent(id: number, isMarked: boolean, bookmarkDate?: string | null) {
    if (isMarked) {
      bookmarkedIds.add(id)
      if (bookmarkDate) chosenDates.set(id, bookmarkDate)
    } else {
      bookmarkedIds.delete(id)
      chosenDates.delete(id)
    }
  }

  async function toggle(id: number, chosenDate?: string) {
    if (bookmarkedIds.has(id)) {
      bookmarkedIds.delete(id)
      chosenDates.delete(id)
      await api.removeBookmark(id)
    } else {
      // Planned items get automatic reminders: ask for notification permission
      // (only the first time) while we're still inside the click.
      void usePushNotifications().ensureSubscription()
      bookmarkedIds.add(id)
      if (chosenDate) chosenDates.set(id, chosenDate)
      await api.addBookmark(id, chosenDate)
    }
  }

  return { bookmarkedIds, chosenDates, isBookmarked, getChosenDate, initFromEvents, syncEvent, toggle }
})

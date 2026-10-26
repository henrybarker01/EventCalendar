<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { api, type Digest } from '../api/client'
import { useBookmarksStore } from '../stores/bookmarks'
import { useHiddenStore } from '../stores/hidden'
import { useRemindersStore } from '../stores/reminders'
import { localDateStr } from '../utils/date'
import EventCard from '../components/EventCard.vue'

// The page behind the daily "N nieuwe evenementen" notification (/nieuw/<id>);
// /nieuw on its own shows the latest one.
const props = defineProps<{ id?: string }>()
const bookmarksStore = useBookmarksStore()
const hiddenStore = useHiddenStore()

const digest = ref<Digest | null>(null)
const loading = ref(true)
const notFound = ref(false)

async function load() {
  loading.value = true
  notFound.value = false
  try {
    const d = await api.getDigest(props.id ? Number(props.id) : undefined)
    // Opened straight from a notification, the agenda may not have loaded:
    // merge these events' starred/hidden state in without resetting the rest.
    for (const e of d.events) {
      bookmarksStore.syncEvent(e.id, e.is_bookmarked, e.bookmark_date)
      if (e.is_hidden) hiddenStore.hiddenIds.add(e.id)
    }
    digest.value = d
    useRemindersStore().fetchReminders()
  } catch {
    digest.value = null
    notFound.value = true
  } finally {
    loading.value = false
  }
}

const todayStr = localDateStr(new Date())

// Events that have ended since the notification, or that you hid, drop out.
const events = computed(() =>
  (digest.value?.events ?? []).filter(e =>
    !hiddenStore.isHidden(e.id) && (e.end_date ?? e.event_date ?? todayStr) >= todayStr
  )
)

const sentLabel = computed(() => {
  if (!digest.value) return ''
  const d = new Date(digest.value.sent_at)
  const day = d.toLocaleDateString('nl-NL', { weekday: 'short', day: 'numeric', month: 'long' })
  return `${day} om ${d.toLocaleTimeString('nl-NL', { hour: '2-digit', minute: '2-digit' })}`
})

watch(() => props.id, load, { immediate: true })
</script>

<template>
  <RouterLink to="/" class="back-link">← Agenda</RouterLink>

  <p v-if="loading" class="status-msg">Laden...</p>
  <p v-else-if="notFound" class="status-msg">
    Nog geen melding met nieuwe evenementen. Elke dag om 18:00 krijg je er een als er iets nieuws bij is gekomen.
  </p>
  <template v-else-if="digest">
    <h2 class="new-events-title">Nieuwe evenementen</h2>
    <p class="new-events-sub">
      Melding van {{ sentLabel }} · {{ events.length }} {{ events.length === 1 ? 'evenement' : 'evenementen' }}
    </p>
    <p v-if="!events.length" class="status-msg">Alles uit deze melding is al voorbij of verborgen.</p>
    <div v-else class="event-grid">
      <EventCard v-for="e in events" :key="e.id" :event="e" />
    </div>
  </template>
</template>

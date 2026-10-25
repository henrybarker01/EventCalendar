<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import type { Event } from '../api/client'
import { useBookmarksStore } from '../stores/bookmarks'
import { useHiddenStore } from '../stores/hidden'
import { useRemindersStore } from '../stores/reminders'
import { usePushNotifications } from '../composables/usePushNotifications'
import ReminderModal from './ReminderModal.vue'

const props = defineProps<{ event: Event; displayDate?: string }>()
const router = useRouter()
const bookmarksStore = useBookmarksStore()
const hiddenStore = useHiddenStore()
const remindersStore = useRemindersStore()
const { ensureSubscription } = usePushNotifications()

const showModal = ref(false)
const pickedDate = ref('')
const showReminderModal = ref(false)
const pendingSubscription = ref<{ endpoint: string; p256dh: string; auth: string } | null>(null)

function handleBookmarkClick() {
  if (bookmarksStore.isBookmarked(props.event.id)) {
    bookmarksStore.toggle(props.event.id)
  } else if (props.event.event_type === 'attraction') {
    pickedDate.value = ''
    showModal.value = true
  } else {
    bookmarksStore.toggle(props.event.id)
  }
}

function confirmDate() {
  if (!pickedDate.value) return
  bookmarksStore.toggle(props.event.id, pickedDate.value)
  showModal.value = false
}

async function handleReminderClick() {
  if (remindersStore.hasReminder(props.event.id)) {
    const reminder = remindersStore.getReminder(props.event.id)
    if (reminder) await remindersStore.removeReminder(reminder.id)
    return
  }

  const sub = await ensureSubscription()
  if (!sub) {
    alert('Sta meldingen toe in je browser en probeer opnieuw.')
    return
  }

  pendingSubscription.value = sub
  showReminderModal.value = true
}

async function confirmReminder(remindAt: string) {
  if (!pendingSubscription.value) return
  await remindersStore.addReminder(props.event.id, remindAt, pendingSubscription.value)
  showReminderModal.value = false
  pendingSubscription.value = null
}

function formatDate(d: string) {
  return new Date(d).toLocaleDateString('nl-NL', { weekday: 'short', day: 'numeric', month: 'long', year: 'numeric' })
}

// Multi-day events show their range, so one that's already running doesn't look past.
const dateLabel = computed(() => {
  const start = props.displayDate ?? props.event.event_date
  if (!start) return null
  const end = props.event.end_date
  return end && end !== start ? `${formatDate(start)} t/m ${formatDate(end)}` : formatDate(start)
})

function proxyUrl(url: string) {
  return `/api/image-proxy?url=${encodeURIComponent(url)}`
}
</script>

<template>
  <article class="event-card" @click="router.push(`/events/${event.id}`)">
    <button
      class="hide-btn"
      title="Niet meer tonen"
      @click.stop="hiddenStore.hide(event.id)"
    >✕</button>
    <button
      class="reminder-btn"
      :class="{ 'has-reminder': remindersStore.hasReminder(event.id) }"
      :title="remindersStore.hasReminder(event.id) ? 'Herinnering annuleren' : 'Herinnering instellen'"
      @click.stop="handleReminderClick"
    >🔔</button>
    <button
      class="bookmark-btn"
      :class="{ 'is-bookmarked': bookmarksStore.isBookmarked(event.id) }"
      :title="bookmarksStore.isBookmarked(event.id) ? 'Verwijder boeking' : 'Boek dit'"
      @click.stop="handleBookmarkClick"
    >{{ bookmarksStore.isBookmarked(event.id) ? '★' : '☆' }}</button>
    <img v-if="event.image_url" :src="proxyUrl(event.image_url)" :alt="event.title" class="event-card-img" loading="lazy" />
    <div v-else class="event-card-img-placeholder">🗓️</div>
    <div class="event-card-body">
      <div v-if="event.category" class="badge-row">
        <span v-for="cat in event.category.split(',')" :key="cat" class="badge">{{ cat.trim() }}</span>
      </div>
      <p class="event-card-title">{{ event.title }}</p>
      <p v-if="dateLabel" class="event-card-date">{{ dateLabel }}</p>
      <p v-if="event.location" class="event-card-location">📍 {{ event.location }}</p>
      <p v-if="event.description" class="event-card-desc">{{ event.description }}</p>
    </div>
  </article>

  <Teleport to="body">
    <div v-if="showModal" class="modal-overlay" @click.self="showModal = false">
      <div class="modal">
        <h3 class="modal-title">Wanneer wil je dit doen?</h3>
        <p class="modal-event-name">{{ event.title }}</p>
        <input class="modal-date-input" type="date" v-model="pickedDate" />
        <div class="modal-actions">
          <button class="modal-btn modal-btn--cancel" @click="showModal = false">Annuleer</button>
          <button class="modal-btn modal-btn--confirm" :disabled="!pickedDate" @click="confirmDate">
            Toevoegen aan kalender
          </button>
        </div>
      </div>
    </div>
  </Teleport>

  <Teleport to="body">
    <ReminderModal
      v-if="showReminderModal"
      :event="event"
      @confirm="confirmReminder"
      @cancel="showReminderModal = false"
    />
  </Teleport>
</template>

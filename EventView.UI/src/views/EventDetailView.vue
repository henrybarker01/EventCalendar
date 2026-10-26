<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { api, type Event } from '../api/client'
import { useBookmarksStore } from '../stores/bookmarks'

const props = defineProps<{ id: string }>()
const router = useRouter()
const bookmarksStore = useBookmarksStore()
const event = ref<Event | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)

const showDatePicker = ref(false)
const pickedDate = ref('')

onMounted(async () => {
  try {
    const e = await api.getEvent(Number(props.id))
    event.value = e
    bookmarksStore.syncEvent(e.id, e.is_bookmarked, e.bookmark_date)
  } catch (e: any) {
    error.value = e.message ?? 'Niet gevonden'
  } finally {
    loading.value = false
  }
})

// Back to the list at the same spot; opened from a shared link there's no
// in-app page to return to, so open the agenda instead of leaving the app.
function goBack() {
  if (window.history.state?.back) router.back()
  else router.push('/')
}

function handleBookmarkClick() {
  if (!event.value) return
  if (bookmarksStore.isBookmarked(event.value.id)) {
    bookmarksStore.toggle(event.value.id)
  } else if (event.value.event_type === 'attraction') {
    pickedDate.value = ''
    showDatePicker.value = true
  } else {
    bookmarksStore.toggle(event.value.id)
  }
}

function confirmDate() {
  if (!event.value || !pickedDate.value) return
  bookmarksStore.toggle(event.value.id, pickedDate.value)
  showDatePicker.value = false
}

function formatDate(d: string) {
  return new Date(d).toLocaleDateString('nl-NL', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })
}

function proxyUrl(url: string) {
  return `/api/image-proxy?url=${encodeURIComponent(url)}`
}
</script>

<template>
  <div class="event-detail">
    <a class="back-link" href="#" @click.prevent="goBack">← Terug</a>

    <p v-if="loading" class="status-msg">Laden...</p>
    <p v-else-if="error" class="status-msg">⚠️ {{ error }}</p>
    <template v-else-if="event">
      <img v-if="event.image_url" :src="proxyUrl(event.image_url)" :alt="event.title" class="event-detail-img" />

      <div v-if="event.category" class="badge-row" style="margin-bottom:.75rem">
        <span v-for="cat in event.category.split(',')" :key="cat" class="badge">{{ cat.trim() }}</span>
      </div>

      <h2>{{ event.title }}</h2>
      <p v-if="!event.is_active" class="event-gone" style="margin-bottom:.75rem">⚠️ Niet meer in de agenda van de bron: mogelijk afgelast of verplaatst</p>

      <div class="event-detail-meta">
        <span v-if="event.event_date">🗓️ {{ formatDate(event.event_date) }}<template v-if="event.end_date && event.end_date !== event.event_date"> t/m {{ formatDate(event.end_date) }}</template></span>
        <span v-if="event.location">📍 {{ event.location }}<template v-if="event.distance_km !== null && event.distance_km >= 1"> · {{ Math.round(event.distance_km) }} km van Barneveld</template></span>
        <span v-if="event.price">💶 {{ event.price }}</span>
      </div>

      <div class="event-detail-actions">
        <template v-if="event.event_type === 'attraction' && !bookmarksStore.isBookmarked(event.id)">
          <div v-if="showDatePicker" class="inline-date-picker">
            <input type="date" v-model="pickedDate" class="modal-date-input" />
            <button class="modal-btn modal-btn--confirm" :disabled="!pickedDate" @click="confirmDate">
              Toevoegen
            </button>
            <button class="modal-btn modal-btn--cancel" @click="showDatePicker = false">
              Annuleer
            </button>
          </div>
          <button v-else class="bookmark-action-btn" @click="handleBookmarkClick">
            ☆ Plan een datum
          </button>
        </template>
        <button
          v-else
          class="bookmark-action-btn"
          :class="{ 'is-bookmarked': bookmarksStore.isBookmarked(event.id) }"
          @click="handleBookmarkClick"
        >
          {{ bookmarksStore.isBookmarked(event.id) ? '★ Geboekt' : '☆ Boek dit' }}
        </button>

        <a :href="event.source_url" target="_blank" rel="noopener" class="btn">
          Meer info →
        </a>
      </div>

      <p v-if="event.description" class="event-detail-desc">{{ event.description }}</p>
    </template>
  </div>
</template>

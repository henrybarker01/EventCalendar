<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { api, type Event } from '../api/client'

const props = defineProps<{ id: string }>()
const router = useRouter()
const event = ref<Event | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)

onMounted(async () => {
  try {
    event.value = await api.getEvent(Number(props.id))
  } catch (e: any) {
    error.value = e.message ?? 'Niet gevonden'
  } finally {
    loading.value = false
  }
})

function formatDate(d: string) {
  return new Date(d).toLocaleDateString('nl-NL', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })
}
</script>

<template>
  <div class="event-detail">
    <a class="back-link" href="#" @click.prevent="router.back()">← Terug</a>

    <p v-if="loading" class="status-msg">Laden...</p>
    <p v-else-if="error" class="status-msg">⚠️ {{ error }}</p>
    <template v-else-if="event">
      <img v-if="event.image_url" :src="event.image_url" :alt="event.title" class="event-detail-img" />

      <div v-if="event.category" class="badge-row" style="margin-bottom:.75rem">
        <span v-for="cat in event.category.split(',')" :key="cat" class="badge">{{ cat.trim() }}</span>
      </div>

      <h2>{{ event.title }}</h2>

      <div class="event-detail-meta">
        <span>🗓️ {{ formatDate(event.event_date) }}</span>
        <span v-if="event.location">📍 {{ event.location }}</span>
        <span v-if="event.price">💶 {{ event.price }}</span>
      </div>

      <p v-if="event.description" class="event-detail-desc">{{ event.description }}</p>

      <a :href="event.source_url" target="_blank" rel="noopener" class="btn">
        Meer info →
      </a>
    </template>
  </div>
</template>

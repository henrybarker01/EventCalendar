<script setup lang="ts">
import { useRouter } from 'vue-router'
import type { Event } from '../api/client'

const props = defineProps<{ event: Event }>()
const router = useRouter()

function formatDate(d: string) {
  return new Date(d).toLocaleDateString('nl-NL', { weekday: 'short', day: 'numeric', month: 'long', year: 'numeric' })
}

function proxyUrl(url: string) {
  return `/api/image-proxy?url=${encodeURIComponent(url)}`
}
</script>

<template>
  <article class="event-card" @click="router.push(`/events/${event.id}`)">
    <img v-if="event.image_url" :src="proxyUrl(event.image_url)" :alt="event.title" class="event-card-img" loading="lazy" />
    <div v-else class="event-card-img-placeholder">🗓️</div>
    <div class="event-card-body">
      <div v-if="event.category" class="badge-row">
        <span v-for="cat in event.category.split(',')" :key="cat" class="badge">{{ cat.trim() }}</span>
      </div>
      <p class="event-card-title">{{ event.title }}</p>
      <p class="event-card-date">{{ formatDate(event.event_date) }}</p>
      <p v-if="event.location" class="event-card-location">📍 {{ event.location }}</p>
      <p v-if="event.description" class="event-card-desc">{{ event.description }}</p>
    </div>
  </article>
</template>

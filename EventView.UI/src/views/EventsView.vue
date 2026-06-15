<script setup lang="ts">
import { onMounted, watch } from 'vue'
import { useEventsStore } from '../stores/events'
import EventCard from '../components/EventCard.vue'

const store = useEventsStore()

onMounted(() => {
  store.fetchSources()
  store.fetchEvents()
})

watch([() => store.selectedSource, () => store.fromDate, () => store.toDate], () => {
  store.fetchEvents()
})
</script>

<template>
  <div class="filter-bar">
    <input
      v-model="store.search"
      type="search"
      placeholder="Zoeken..."
    />
    <select v-model="store.selectedSource">
      <option value="">Alle bronnen</option>
      <option v-for="s in store.sources" :key="s" :value="s">{{ s }}</option>
    </select>
    <input v-model="store.fromDate" type="date" title="Vanaf" />
    <input v-model="store.toDate" type="date" title="Tot" />
  </div>

  <p v-if="store.loading" class="status-msg">Laden...</p>
  <p v-else-if="store.error" class="status-msg">⚠️ {{ store.error }}</p>
  <template v-else>
    <p class="result-count">{{ store.filtered.length }} evenement{{ store.filtered.length !== 1 ? 'en' : '' }}</p>
    <p v-if="store.filtered.length === 0" class="status-msg">Geen evenementen gevonden.</p>
    <div v-else class="event-grid">
      <EventCard v-for="event in store.filtered" :key="event.id" :event="event" />
    </div>
  </template>
</template>

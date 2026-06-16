<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useEventsStore } from '../stores/events'
import EventCard from '../components/EventCard.vue'

const store = useEventsStore()
const activeTab = ref<'events' | 'attractions'>('events')

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
    <input v-model="store.search" type="search" placeholder="Zoeken..." />
    <select v-model="store.selectedSource">
      <option value="">Alle bronnen</option>
      <option v-for="s in store.sources" :key="s" :value="s">{{ s }}</option>
    </select>
    <template v-if="activeTab === 'events'">
      <input v-model="store.fromDate" type="date" title="Vanaf" />
      <input v-model="store.toDate" type="date" title="Tot" />
    </template>
  </div>

  <div class="tab-bar">
    <button
      class="tab-btn"
      :class="{ active: activeTab === 'events' }"
      @click="activeTab = 'events'"
    >
      Evenementen
      <span class="tab-count">{{ store.filtered.length }}</span>
    </button>
    <button
      class="tab-btn"
      :class="{ active: activeTab === 'attractions' }"
      @click="activeTab = 'attractions'"
    >
      Te doen
      <span class="tab-count">{{ store.filteredAttractions.length }}</span>
    </button>
  </div>

  <p v-if="store.loading" class="status-msg">Laden...</p>
  <p v-else-if="store.error" class="status-msg">⚠️ {{ store.error }}</p>
  <template v-else>
    <template v-if="activeTab === 'events'">
      <p v-if="store.filtered.length === 0" class="status-msg">Geen evenementen gevonden.</p>
      <div v-else class="event-grid">
        <EventCard v-for="event in store.filtered" :key="event.id" :event="event" />
      </div>
    </template>
    <template v-else>
      <p v-if="store.filteredAttractions.length === 0" class="status-msg">Geen activiteiten gevonden.</p>
      <div v-else class="event-grid">
        <EventCard v-for="event in store.filteredAttractions" :key="event.id" :event="event" />
      </div>
    </template>
  </template>
</template>

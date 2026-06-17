<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useEventsStore } from '../stores/events'
import { useBookmarksStore } from '../stores/bookmarks'
import { useCustomEventsStore } from '../stores/customEvents'
import { useHiddenStore } from '../stores/hidden'
import EventCard from '../components/EventCard.vue'

const store = useEventsStore()
const bookmarksStore = useBookmarksStore()
const customEventsStore = useCustomEventsStore()
const hiddenStore = useHiddenStore()

const showHidden = ref(false)

const hiddenEvents = computed(() =>
  activeTab.value === 'attractions'
    ? store.attractions.filter(e => hiddenStore.isHidden(e.id))
    : store.events.filter(e => hiddenStore.isHidden(e.id))
)
const activeTab = ref<'events' | 'attractions' | 'booked'>('events')

const todayStr = new Date().toISOString().slice(0, 10)

const bookedUpcoming = computed(() => {
  const all = [...store.events, ...store.attractions]
  return all
    .filter(e => bookmarksStore.isBookmarked(e.id))
    .map(e => ({
      event: e,
      date: e.event_type === 'attraction'
        ? bookmarksStore.getChosenDate(e.id)
        : e.event_date,
    }))
    .filter(x => x.date && x.date >= todayStr)
    .sort((a, b) => (a.date! > b.date! ? 1 : -1))
})

const upcomingCustom = computed(() =>
  customEventsStore.events
    .filter(e => e.event_date >= todayStr)
    .slice()
    .sort((a, b) => (a.event_date > b.event_date ? 1 : -1))
)

const plannedCount = computed(() => bookedUpcoming.value.length + upcomingCustom.value.length)

function formatDate(dateStr: string) {
  return new Date(dateStr + 'T00:00:00').toLocaleDateString('nl-NL', { day: 'numeric', month: 'long' })
}

onMounted(() => {
  store.fetchSources()
  store.fetchEvents()
  customEventsStore.load()
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
    <button class="tab-btn" :class="{ active: activeTab === 'events' }" @click="activeTab = 'events'">
      Evenementen
      <span class="tab-count">{{ store.filtered.length }}</span>
    </button>
    <button class="tab-btn" :class="{ active: activeTab === 'attractions' }" @click="activeTab = 'attractions'">
      Te doen
      <span class="tab-count">{{ store.filteredAttractions.length }}</span>
    </button>
    <button class="tab-btn" :class="{ active: activeTab === 'booked' }" @click="activeTab = 'booked'">
      Gepland
      <span class="tab-count">{{ plannedCount }}</span>
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

    <template v-else-if="activeTab === 'attractions'">
      <p v-if="store.filteredAttractions.length === 0" class="status-msg">Geen activiteiten gevonden.</p>
      <div v-else class="event-grid">
        <EventCard v-for="event in store.filteredAttractions" :key="event.id" :event="event" />
      </div>
    </template>

    <!-- Hidden events section (events + attractions tabs only) -->
    <template v-if="activeTab !== 'booked' && hiddenEvents.length > 0">
      <button class="hidden-toggle" @click="showHidden = !showHidden">
        {{ showHidden ? '▾' : '▸' }} Verborgen ({{ hiddenEvents.length }})
      </button>
      <div v-if="showHidden" class="hidden-list">
        <div v-for="event in hiddenEvents" :key="event.id" class="hidden-item">
          <span class="hidden-item-title">{{ event.title }}</span>
          <span v-if="event.event_date" class="hidden-item-date">{{ event.event_date }}</span>
          <button class="hidden-item-restore" @click="hiddenStore.unhide(event.id)">Terugzetten</button>
        </div>
      </div>
    </template>

    <template v-else>
      <p v-if="plannedCount === 0" class="status-msg">Nog niets gepland. Klik op ★ bij een evenement om het toe te voegen.</p>
      <template v-else>
        <div class="event-grid">
          <EventCard
            v-for="{ event, date } in bookedUpcoming"
            :key="'e-' + event.id"
            :event="event"
            :displayDate="date ?? undefined"
          />
        </div>
        <div v-if="upcomingCustom.length" class="custom-planned-list">
          <h3 class="custom-planned-title">Eigen agenda</h3>
          <div
            v-for="ev in upcomingCustom"
            :key="'c-' + ev.id"
            class="custom-planned-item"
          >
            <span class="custom-planned-date">{{ formatDate(ev.event_date) }}</span>
            <span class="custom-planned-title-text">{{ ev.title }}</span>
            <button class="custom-planned-delete" @click="customEventsStore.remove(ev.id)" title="Verwijderen">×</button>
          </div>
        </div>
      </template>
    </template>
  </template>
</template>

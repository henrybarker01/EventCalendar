<script setup lang="ts">
import { ref, computed, onActivated, onMounted, watch } from 'vue'
import { api, type Event } from '../api/client'
import { usePushNotifications } from '../composables/usePushNotifications'
import { useEventsStore, DATE_PRESETS, type DatePreset } from '../stores/events'
import { useBookmarksStore } from '../stores/bookmarks'
import { useCustomEventsStore } from '../stores/customEvents'
import { useHiddenStore } from '../stores/hidden'
import { localDateStr } from '../utils/date'
import EventCard from '../components/EventCard.vue'
import EventFilters from '../components/EventFilters.vue'

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

const todayStr = localDateStr(new Date())

// Hide past events unless the user has explicitly set a from-date filter.
// Multi-day events stay until their last day.
const isUpcoming = (e: Event) => !!store.fromDate || !e.event_date || (e.end_date ?? e.event_date) >= todayStr

const filteredEvents = computed(() => store.filtered.filter(isUpcoming))

// Attractions have no from_date filter in the API, so always hide past ones.
const filteredAttractions = computed(() =>
  store.filteredAttractions.filter(e => !e.event_date || e.event_date >= todayStr)
)

// What the theme chips count: the current tab's list before the theme filter.
const themeBase = computed(() =>
  activeTab.value === 'attractions' ? store.baseAttractions : store.baseEvents.filter(isUpcoming)
)

// A quick-date button and the from/to inputs replace each other.
function togglePreset(preset: DatePreset) {
  store.datePreset = store.datePreset === preset ? '' : preset
  if (store.datePreset) {
    store.fromDate = ''
    store.toDate = ''
  }
}

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
    .filter(x => x.date && (x.event.end_date ?? x.date) >= todayStr)
    .sort((a, b) => (a.date! > b.date! ? 1 : -1))
})

const upcomingCustom = computed(() =>
  customEventsStore.events
    .filter(e => e.event_date >= todayStr)
    .slice()
    .sort((a, b) => (a.event_date > b.event_date ? 1 : -1))
)

const plannedCount = computed(() => bookedUpcoming.value.length + upcomingCustom.value.length)

// Planned items get automatic reminders (sent by the API) on every device that allowed them.
const { isSupported: pushSupported, permission, ensureSubscription } = usePushNotifications()
const testResult = ref('')

async function sendTestPush() {
  testResult.value = 'Versturen...'
  try {
    await ensureSubscription()
    const devices = await api.sendTestPush()
    testResult.value = devices
      ? `Verstuurd naar ${devices} ${devices === 1 ? 'apparaat' : 'apparaten'}`
      : 'Geen apparaat bereikt'
  } catch {
    testResult.value = 'Versturen mislukt'
  }
}

function formatDate(dateStr: string) {
  return new Date(dateStr + 'T00:00:00').toLocaleDateString('nl-NL', { day: 'numeric', month: 'long' })
}

onMounted(() => {
  store.fetchSources()
  store.fetchEvents()
  customEventsStore.load()
})

// Kept alive between visits (see App.vue): only refresh data that has gone stale.
onActivated(() => store.refreshIfStale())

watch([() => store.selectedSource, () => store.fromDate, () => store.toDate], () => {
  store.fetchEvents()
})

watch([() => store.fromDate, () => store.toDate], ([from, to]) => {
  if (from || to) store.datePreset = ''
})
</script>

<template>
  <!-- Filters don't apply to Gepland: your plans always show. -->
  <EventFilters v-if="activeTab !== 'booked'" :items="themeBase">
    <select v-model="store.selectedSource">
      <option value="">Alle bronnen</option>
      <option v-for="s in store.sources" :key="s" :value="s">{{ s }}</option>
    </select>
    <template v-if="activeTab === 'events'">
      <input v-model="store.fromDate" type="date" title="Vanaf" />
      <input v-model="store.toDate" type="date" title="Tot" />
      <div class="chip-row">
        <button
          v-for="p in DATE_PRESETS"
          :key="p.value"
          class="filter-chip"
          :class="{ active: store.datePreset === p.value }"
          @click="togglePreset(p.value)"
        >{{ p.label }}</button>
      </div>
    </template>
  </EventFilters>

  <div class="tab-bar">
    <button class="tab-btn" :class="{ active: activeTab === 'events' }" @click="activeTab = 'events'">
      Evenementen
      <span class="tab-count">{{ filteredEvents.length }}</span>
    </button>
    <button class="tab-btn" :class="{ active: activeTab === 'attractions' }" @click="activeTab = 'attractions'">
      Te doen
      <span class="tab-count">{{ filteredAttractions.length }}</span>
    </button>
    <button class="tab-btn" :class="{ active: activeTab === 'booked' }" @click="activeTab = 'booked'">
      Gepland
      <span class="tab-count">{{ plannedCount }}</span>
    </button>
  </div>

  <!-- A refresh keeps the current list on screen, so the scroll position survives. -->
  <p v-if="store.loading && !store.hasFetched" class="status-msg">Laden...</p>
  <p v-else-if="store.error && !store.hasFetched" class="status-msg">⚠️ {{ store.error }}</p>
  <template v-else>
    <template v-if="activeTab === 'events'">
      <p v-if="filteredEvents.length === 0" class="status-msg">Geen evenementen gevonden.</p>
      <div v-else class="event-grid">
        <EventCard v-for="event in filteredEvents" :key="event.id" :event="event" />
      </div>
    </template>

    <template v-else-if="activeTab === 'attractions'">
      <p v-if="filteredAttractions.length === 0" class="status-msg">Geen activiteiten gevonden.</p>
      <div v-else class="event-grid">
        <EventCard v-for="event in filteredAttractions" :key="event.id" :event="event" />
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
      <p class="plan-reminder-note">
        <template v-if="permission === 'granted'">
          🔔 Je krijgt een melding 5 dagen en 1 dag van tevoren, om 19:00.
          <button class="link-btn" @click="sendTestPush">Stuur testmelding</button>
          <span v-if="testResult"> · {{ testResult }}</span>
        </template>
        <template v-else-if="pushSupported && permission === 'default'">
          🔔 Zet meldingen aan voor een herinnering 5 dagen en 1 dag van tevoren.
          <button class="link-btn" @click="ensureSubscription">Meldingen aanzetten</button>
        </template>
        <template v-else>🔕 Meldingen staan uit in deze browser, dus herinneringen komen hier niet aan.</template>
      </p>
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

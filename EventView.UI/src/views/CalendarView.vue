<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useEventsStore } from '../stores/events'
import { useBookmarksStore } from '../stores/bookmarks'
import { useCustomEventsStore } from '../stores/customEvents'
import type { Event } from '../api/client'

const router = useRouter()
const eventsStore = useEventsStore()
const bookmarksStore = useBookmarksStore()
const customEventsStore = useCustomEventsStore()

const today = new Date()
const todayStr = today.toISOString().slice(0, 10)
const currentMonthStart = ref(new Date(today.getFullYear(), today.getMonth(), 1))

const WEEKDAYS = ['Ma', 'Di', 'Wo', 'Do', 'Vr', 'Za', 'Zo']
const MONTHS = [
  'Januari', 'Februari', 'Maart', 'April', 'Mei', 'Juni',
  'Juli', 'Augustus', 'September', 'Oktober', 'November', 'December',
]
const MAX_CHIPS = 2

function prevMonth() {
  const d = new Date(currentMonthStart.value)
  d.setMonth(d.getMonth() - 1)
  currentMonthStart.value = d
}

function nextMonth() {
  const d = new Date(currentMonthStart.value)
  d.setMonth(d.getMonth() + 1)
  currentMonthStart.value = d
}

const monthLabel = computed(() => {
  const d = currentMonthStart.value
  return `${MONTHS[d.getMonth()]} ${d.getFullYear()}`
})

const gridCells = computed(() => {
  const year = currentMonthStart.value.getFullYear()
  const month = currentMonthStart.value.getMonth()
  const firstDay = new Date(year, month, 1)
  const startDow = (firstDay.getDay() + 6) % 7
  const gridStart = new Date(firstDay)
  gridStart.setDate(gridStart.getDate() - startDow)

  return Array.from({ length: 42 }, (_, i) => {
    const d = new Date(gridStart)
    d.setDate(gridStart.getDate() + i)
    const dateStr = d.toISOString().slice(0, 10)
    return { date: d, dateStr, isCurrentMonth: d.getMonth() === month, isToday: dateStr === todayStr }
  })
})

function displayDate(e: Event): string | null {
  if (e.event_type === 'attraction') {
    return bookmarksStore.isBookmarked(e.id) ? bookmarksStore.getChosenDate(e.id) : null
  }
  return e.event_date
}

const eventsByDate = computed(() => {
  const map: Record<string, Event[]> = {}
  for (const e of [...eventsStore.events, ...eventsStore.attractions]) {
    const d = displayDate(e)
    if (!d) continue
    if (!map[d]) map[d] = []
    map[d].push(e)
  }
  return map
})

// Merged, ordered chip list per date — used by the grid template
type Chip =
  | { kind: 'scraped'; id: number; title: string; booked: boolean }
  | { kind: 'custom';  id: number; title: string }

function chipPriority(c: Chip): number {
  if (c.kind === 'custom') return 0
  if (c.kind === 'scraped' && c.booked) return 1
  return 2
}

const cellChips = computed((): Record<string, Chip[]> => {
  const result: Record<string, Chip[]> = {}

  for (const [date, evts] of Object.entries(eventsByDate.value)) {
    result[date] = evts.map(e => ({
      kind: 'scraped', id: e.id, title: e.title,
      booked: bookmarksStore.isBookmarked(e.id),
    }))
  }
  for (const [date, evts] of Object.entries(customEventsStore.byDate)) {
    if (!result[date]) result[date] = []
    result[date].push(...evts.map(e => ({ kind: 'custom' as const, id: e.id, title: e.title })))
  }

  for (const date in result) {
    result[date].sort((a, b) => chipPriority(a) - chipPriority(b))
  }

  return result
})

const bookedEvents = computed(() => {
  const all = [...eventsStore.events, ...eventsStore.attractions]
  return all
    .filter(e => bookmarksStore.isBookmarked(e.id))
    .map(e => ({ event: e, date: displayDate(e) }))
    .filter(x => x.date)
    .sort((a, b) => (a.date! > b.date! ? 1 : -1))
})

// ── Day-detail modal ("+N meer") ────────────────────────────────────
const dayModal = ref<{ dateStr: string; label: string } | null>(null)

function openDay(dateStr: string) {
  dayModal.value = { dateStr, label: formatDayLabel(dateStr) }
}

// ── Add-custom-event modal ──────────────────────────────────────────
const addModal = ref<{ dateStr: string; label: string } | null>(null)
const newTitle = ref('')
const saving = ref(false)
const saveError = ref('')

const QUICK_EMOJI = ['🎂','🎉','🏃','🍕','🎬','🛒','✈️','🎵','💪','🏊','🎮','📚','🌿','🐶','❤️']

function openAdd(dateStr: string, label: string) {
  addModal.value = { dateStr, label }
  newTitle.value = ''
  saveError.value = ''
}

function appendEmoji(emoji: string) {
  newTitle.value += emoji
}

async function confirmAdd() {
  if (!addModal.value || !newTitle.value.trim() || saving.value) return
  saving.value = true
  saveError.value = ''
  try {
    await customEventsStore.add(newTitle.value.trim(), addModal.value.dateStr)
    addModal.value = null
  } catch {
    saveError.value = 'Opslaan mislukt. Probeer het opnieuw.'
  } finally {
    saving.value = false
  }
}

function formatDayLabel(dateStr: string) {
  return new Date(dateStr + 'T00:00:00').toLocaleDateString('nl-NL', {
    weekday: 'long', day: 'numeric', month: 'long',
  })
}

onMounted(async () => {
  if (!eventsStore.hasFetched) eventsStore.fetchEvents()
  await customEventsStore.load()
})
</script>

<template>
  <div>
    <!-- Booked / custom summary -->
    <div v-if="bookedEvents.length || customEventsStore.events.length" class="booked-summary">
      <h3 class="booked-summary-title">
        Geplande activiteiten ({{ bookedEvents.length + customEventsStore.events.filter(e => e.event_date >= todayStr).length }})
      </h3>
      <div class="booked-list">
        <div
          v-for="{ event, date } in bookedEvents"
          :key="'b-' + event.id"
          class="booked-item"
          @click="router.push(`/events/${event.id}`)"
        >
          <span class="booked-item-title">{{ event.title }}</span>
          <span class="booked-item-date">{{ new Date(date!).toLocaleDateString('nl-NL', { day: 'numeric', month: 'short' }) }}</span>
        </div>
        <div
          v-for="ev in customEventsStore.events.filter(e => e.event_date >= todayStr).sort((a,b) => a.event_date > b.event_date ? 1 : -1)"
          :key="'c-' + ev.id"
          class="booked-item booked-item--custom"
        >
          <span class="booked-item-title">{{ ev.title }}</span>
          <span class="booked-item-date">{{ new Date(ev.event_date).toLocaleDateString('nl-NL', { day: 'numeric', month: 'short' }) }}</span>
        </div>
      </div>
    </div>
    <p v-else class="status-msg" style="padding:1rem 0 1.5rem">
      Klik op + op een dag om iets toe te voegen, of ster bij een evenement.
    </p>

    <!-- Month navigation -->
    <div class="calendar-header">
      <button class="cal-nav" @click="prevMonth">&#8249;</button>
      <h2 class="cal-month-label">{{ monthLabel }}</h2>
      <button class="cal-nav" @click="nextMonth">&#8250;</button>
    </div>

    <p v-if="eventsStore.loading" class="status-msg">Laden...</p>

    <!-- Calendar grid -->
    <div v-else class="calendar-grid">
      <div v-for="wd in WEEKDAYS" :key="wd" class="cal-weekday">{{ wd }}</div>

      <div
        v-for="cell in gridCells"
        :key="cell.dateStr"
        class="cal-cell"
        :class="{
          'cal-cell--other-month': !cell.isCurrentMonth,
          'cal-cell--today': cell.isToday,
        }"
      >
        <div class="cal-cell-header">
          <span class="cal-day-num">{{ cell.date.getDate() }}</span>
          <button
            v-if="cell.isCurrentMonth"
            class="cal-add-btn"
            title="Toevoegen"
            @click="openAdd(cell.dateStr, formatDayLabel(cell.dateStr))"
          >+</button>
        </div>

        <div class="cal-chips">
          <template v-for="chip in (cellChips[cell.dateStr] ?? []).slice(0, MAX_CHIPS)" :key="chip.kind + chip.id">
            <!-- Scraped event -->
            <span
              v-if="chip.kind === 'scraped'"
              class="cal-chip"
              :class="{ 'cal-chip--booked': chip.booked }"
              @click="router.push(`/events/${chip.id}`)"
            >{{ chip.title }}</span>

            <!-- Custom event -->
            <span v-else class="cal-chip cal-chip--custom">
              <span class="cal-chip-label">{{ chip.title }}</span>
              <button class="cal-chip-delete" title="Verwijderen" @click.stop="customEventsStore.remove(chip.id)">×</button>
            </span>
          </template>

          <!-- Overflow badge -->
          <button
            v-if="(cellChips[cell.dateStr] ?? []).length > MAX_CHIPS"
            class="cal-more"
            @click="openDay(cell.dateStr)"
          >+{{ (cellChips[cell.dateStr] ?? []).length - MAX_CHIPS }} meer</button>
        </div>
      </div>
    </div>

    <!-- Day-detail modal -->
    <Teleport to="body">
      <div v-if="dayModal" class="modal-overlay" @click.self="dayModal = null">
        <div class="modal">
          <h3 class="modal-title">{{ dayModal.label }}</h3>
          <div class="day-detail-list">
            <template v-for="chip in (cellChips[dayModal.dateStr] ?? [])" :key="chip.kind + chip.id">
              <div
                v-if="chip.kind === 'scraped'"
                class="day-detail-item"
                @click="router.push(`/events/${chip.id}`); dayModal = null"
              >
                <span v-if="chip.booked" class="day-detail-star">★</span>
                <span class="day-detail-title">{{ chip.title }}</span>
              </div>
              <div v-else class="day-detail-item day-detail-item--custom">
                <span class="day-detail-title">{{ chip.title }}</span>
                <button class="cal-chip-delete" title="Verwijderen" @click.stop="customEventsStore.remove(chip.id)">×</button>
              </div>
            </template>
          </div>
          <div class="modal-actions">
            <button class="modal-btn modal-btn--cancel" @click="dayModal = null">Sluiten</button>
            <button class="modal-btn modal-btn--confirm" @click="openAdd(dayModal.dateStr, dayModal.label); dayModal = null">+ Toevoegen</button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- Add-event modal -->
    <Teleport to="body">
      <div v-if="addModal" class="modal-overlay" @click.self="addModal = null">
        <div class="modal">
          <h3 class="modal-title">Toevoegen</h3>
          <p class="modal-event-name">{{ addModal.label }}</p>
          <input
            class="modal-date-input"
            type="text"
            v-model="newTitle"
            placeholder="Bijv. 🎂 Verjaardag of 🏃 Hardlopen"
            maxlength="200"
            autofocus
            @keydown.enter="confirmAdd"
            @keydown.esc="addModal = null"
          />
          <div class="emoji-quickpick">
            <button
              v-for="e in QUICK_EMOJI"
              :key="e"
              class="emoji-btn"
              type="button"
              @click="appendEmoji(e)"
            >{{ e }}</button>
          </div>
          <p v-if="saveError" class="modal-error">{{ saveError }}</p>
          <div class="modal-actions">
            <button class="modal-btn modal-btn--cancel" @click="addModal = null">Annuleer</button>
            <button class="modal-btn modal-btn--confirm" :disabled="!newTitle.trim() || saving" @click="confirmAdd">
              {{ saving ? 'Opslaan...' : 'Toevoegen' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

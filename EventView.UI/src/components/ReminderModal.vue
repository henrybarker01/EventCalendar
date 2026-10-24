<script setup lang="ts">
import { ref, computed } from 'vue'
import type { Event } from '../api/client'

const props = defineProps<{ event: Event }>()
const emit = defineEmits<{
  confirm: [remindAt: string]
  cancel: []
}>()

const now = new Date()
const selected = ref('')
const customDatetime = ref('')

interface Option { label: string; value: string }

function addDays(base: Date, n: number): Date {
  const d = new Date(base)
  d.setDate(d.getDate() + n)
  return d
}

const options = computed<Option[]>(() => {
  if (!props.event.event_date) return []
  const eventDay = new Date(props.event.event_date + 'T09:00:00')
  const candidates: { label: string; date: Date }[] = [
    { label: 'Ochtend van het evenement', date: eventDay },
    { label: '1 dag van tevoren', date: addDays(eventDay, -1) },
    { label: '3 dagen van tevoren', date: addDays(eventDay, -3) },
    { label: '1 week van tevoren', date: addDays(eventDay, -7) },
  ]
  return candidates
    .filter(c => c.date > now)
    .map(c => ({ label: c.label, value: c.date.toISOString() }))
})

const isConfirmable = computed(() =>
  selected.value !== '' && (selected.value !== 'custom' || customDatetime.value !== '')
)

function confirm() {
  if (!isConfirmable.value) return
  const iso = selected.value === 'custom'
    ? new Date(customDatetime.value).toISOString()
    : selected.value
  emit('confirm', iso)
}
</script>

<template>
  <div class="modal-overlay" @click.self="emit('cancel')">
    <div class="modal">
      <h3 class="modal-title">Herinnering instellen</h3>
      <p class="modal-event-name">{{ event.title }}</p>

      <div class="reminder-options">
        <label v-for="opt in options" :key="opt.value" class="reminder-option">
          <input type="radio" v-model="selected" :value="opt.value" />
          {{ opt.label }}
        </label>
        <label class="reminder-option">
          <input type="radio" v-model="selected" value="custom" />
          Aangepast tijdstip
        </label>
      </div>

      <input
        v-if="selected === 'custom'"
        type="datetime-local"
        v-model="customDatetime"
        class="modal-date-input"
      />

      <div class="modal-actions">
        <button class="modal-btn modal-btn--cancel" @click="emit('cancel')">Annuleer</button>
        <button class="modal-btn modal-btn--confirm" :disabled="!isConfirmable" @click="confirm">
          Instellen
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.reminder-options {
  display: flex;
  flex-direction: column;
  gap: .55rem;
}
.reminder-option {
  display: flex;
  align-items: center;
  gap: .55rem;
  font-size: .9rem;
  cursor: pointer;
}
.reminder-option input[type="radio"] {
  accent-color: var(--c-primary);
  width: 16px;
  height: 16px;
  cursor: pointer;
}
</style>

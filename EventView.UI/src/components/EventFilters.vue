<script setup lang="ts">
import { computed } from 'vue'
import type { Event } from '../api/client'
import { useEventsStore, NO_THEME, DISTANCE_OPTIONS } from '../stores/events'

// `items`: the events the theme counts are based on, with every other filter
// already applied.
const props = defineProps<{ items: Event[] }>()
const store = useEventsStore()

const themeChips = computed(() => {
  const counts = new Map<string, number>()
  for (const e of props.items) {
    for (const t of e.themes.length ? e.themes : [NO_THEME]) counts.set(t, (counts.get(t) ?? 0) + 1)
  }
  // A selected theme stays visible (to deselect it) even when nothing matches now.
  for (const t of store.themes) if (!counts.has(t)) counts.set(t, 0)
  return [...counts]
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => (a.name === NO_THEME ? 1 : b.name === NO_THEME ? -1 : a.name.localeCompare(b.name, 'nl')))
})
</script>

<template>
  <div class="filter-bar">
    <input v-model="store.search" type="search" placeholder="Zoeken..." />
    <select v-model="store.distance" title="Afstand vanaf Barneveld">
      <option v-for="o in DISTANCE_OPTIONS" :key="o.value" :value="o.value">{{ o.label }}</option>
    </select>
    <slot />
    <div v-if="themeChips.length" class="chip-row">
      <button
        v-for="t in themeChips"
        :key="t.name"
        class="filter-chip"
        :class="{ active: store.themes.includes(t.name) }"
        @click="store.toggleTheme(t.name)"
      >{{ t.name }} <span class="filter-chip-count">{{ t.count }}</span></button>
      <button v-if="store.themes.length" class="filter-chip-clear" @click="store.themes = []">Wis thema's</button>
    </div>
  </div>
</template>

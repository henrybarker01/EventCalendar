<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { usePushNotifications } from './composables/usePushNotifications'

const { isSupported, ensureSubscription } = usePushNotifications()

const showBanner = ref(false)

onMounted(() => {
  if (isSupported && Notification.permission === 'default') {
    showBanner.value = true
  }
})

async function enableNotifications() {
  showBanner.value = false
  await ensureSubscription()
}
</script>

<template>
  <header class="app-header">
    <h1>📅 EventView</h1>
    <nav>
      <RouterLink to="/">Agenda</RouterLink>
      <RouterLink to="/kalender">Kalender</RouterLink>
    </nav>
  </header>

  <div v-if="showBanner" class="notif-banner">
    <span>🔔 Sta meldingen toe om herinneringen te ontvangen.</span>
    <button class="notif-banner-enable" @click="enableNotifications">Inschakelen</button>
    <button class="notif-banner-dismiss" @click="showBanner = false" aria-label="Sluiten">✕</button>
  </div>

  <main class="container">
    <!-- The list views stay alive while an event is open, so going back
         returns to the same tab, month and scroll position. -->
    <RouterView v-slot="{ Component }">
      <KeepAlive :include="['EventsView', 'CalendarView']">
        <component :is="Component" />
      </KeepAlive>
    </RouterView>
  </main>
</template>

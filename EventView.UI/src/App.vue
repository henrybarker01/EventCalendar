<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { usePushNotifications } from './composables/usePushNotifications'

const { isSupported, ensureSubscription } = usePushNotifications()

const showBanner = ref(false)

// The banner asks once per device: after "Inschakelen" or ✕ it stays away
// (the Gepland tab has its own button to turn notifications on later).
const BANNER_ANSWERED_KEY = 'eventview.notifBannerAnswered'

function bannerAnswered(): boolean {
  try {
    return localStorage.getItem(BANNER_ANSWERED_KEY) === '1'
  } catch {
    return false
  }
}

function closeBanner() {
  showBanner.value = false
  try {
    localStorage.setItem(BANNER_ANSWERED_KEY, '1')
  } catch {
    // Storage unavailable (private mode): the banner just asks again next time.
  }
}

onMounted(() => {
  if (isSupported && Notification.permission === 'default' && !bannerAnswered()) {
    showBanner.value = true
  }
  // Already allowed: (re-)register this device so automatic reminders reach it.
  if (isSupported && Notification.permission === 'granted') {
    ensureSubscription()
  }
})

async function enableNotifications() {
  closeBanner()
  await ensureSubscription()
}
</script>

<template>
  <header class="app-header">
    <h1>📅 EventView</h1>
    <nav>
      <RouterLink to="/">Agenda</RouterLink>
      <RouterLink to="/kalender">Kalender</RouterLink>
      <RouterLink to="/nieuw">Nieuw</RouterLink>
    </nav>
  </header>

  <div v-if="showBanner" class="notif-banner">
    <span>🔔 Sta meldingen toe om herinneringen te ontvangen.</span>
    <button class="notif-banner-enable" @click="enableNotifications">Inschakelen</button>
    <button class="notif-banner-dismiss" @click="closeBanner" aria-label="Sluiten">✕</button>
  </div>

  <main class="container">
    <!-- The list views stay alive while an event is open, so going back
         returns to the same tab, month and scroll position. -->
    <RouterView v-slot="{ Component }">
      <KeepAlive :include="['EventsView', 'CalendarView', 'NewEventsView']">
        <component :is="Component" />
      </KeepAlive>
    </RouterView>
  </main>
</template>

import { ref } from 'vue'
import { api } from '../api/client'

type SubData = { endpoint: string; p256dh: string; auth: string }

function urlBase64ToUint8Array(base64String: string): Uint8Array<ArrayBuffer> {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4)
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/')
  const rawData = window.atob(base64)
  const output = new Uint8Array(rawData.length)
  for (let i = 0; i < rawData.length; i++) output[i] = rawData.charCodeAt(i)
  return output
}

const cachedVapidKey = ref<string | null>(null)

async function getVapidKey(): Promise<string> {
  if (!cachedVapidKey.value) {
    cachedVapidKey.value = await api.getVapidPublicKey()
  }
  return cachedVapidKey.value
}

export function usePushNotifications() {
  const isSupported = 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window
  const permission = ref<NotificationPermission>(isSupported ? Notification.permission : 'denied')

  async function ensureSubscription(): Promise<SubData | null> {
    if (!isSupported) return null

    if (Notification.permission === 'default') {
      permission.value = await Notification.requestPermission()
    } else {
      permission.value = Notification.permission
    }
    if (permission.value !== 'granted') return null

    const reg = await navigator.serviceWorker.register('/sw.js')
    await navigator.serviceWorker.ready

    let sub = await reg.pushManager.getSubscription()
    if (!sub) {
      const vapidKey = await getVapidKey()
      sub = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(vapidKey),
      })
    }

    const json = sub.toJSON() as { endpoint: string; keys: { p256dh: string; auth: string } }
    const data = { endpoint: json.endpoint, p256dh: json.keys.p256dh, auth: json.keys.auth }
    // Automatic reminders for planned items go to every registered device.
    await api.registerPushSubscription(data).catch(() => {})
    return data
  }

  return { isSupported, permission, ensureSubscription }
}

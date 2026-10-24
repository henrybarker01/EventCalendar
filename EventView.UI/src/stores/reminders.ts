import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api, type Reminder } from '../api/client'

export const useRemindersStore = defineStore('reminders', () => {
  const reminders = ref<Reminder[]>([])

  function hasReminder(eventId: number): boolean {
    return reminders.value.some(r => r.event_id === eventId)
  }

  function getReminder(eventId: number): Reminder | undefined {
    return reminders.value.find(r => r.event_id === eventId)
  }

  async function fetchReminders() {
    reminders.value = await api.getReminders()
  }

  async function addReminder(
    eventId: number,
    remindAt: string,
    subscription: { endpoint: string; p256dh: string; auth: string },
  ) {
    const reminder = await api.createReminder(eventId, remindAt, subscription)
    const idx = reminders.value.findIndex(r => r.event_id === eventId)
    if (idx >= 0) {
      reminders.value[idx] = reminder
    } else {
      reminders.value.push(reminder)
    }
  }

  async function removeReminder(reminderId: number) {
    await api.deleteReminder(reminderId)
    reminders.value = reminders.value.filter(r => r.id !== reminderId)
  }

  return { reminders, hasReminder, getReminder, fetchReminders, addReminder, removeReminder }
})

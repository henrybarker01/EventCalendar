import axios from 'axios'

const http = axios.create({ baseURL: '/api' })

export interface Event {
  id: number
  event_type: 'event' | 'attraction'
  title: string
  event_date: string | null
  end_date: string | null
  location: string | null
  description: string | null
  image_url: string | null
  source_url: string
  source_name: string
  category: string | null
  price: string | null
  is_active: boolean
  is_bookmarked: boolean
  bookmark_date: string | null
  is_hidden: boolean
}

export interface CustomEvent {
  id: number
  title: string
  event_date: string
  created_at: string
}

export interface Reminder {
  id: number
  event_id: number
  remind_at: string
  sent: boolean
  created_at: string
}

export interface ScrapingLog {
  id: number
  source_name: string
  status: string
  events_found: number
  events_new: number
  error_message: string | null
}

export const api = {
  getEvents(params?: {
    source?: string
    event_type?: string
    from_date?: string
    to_date?: string
    active_only?: boolean
    limit?: number
    offset?: number
  }) {
    return http.get<Event[]>('/events', { params }).then(r => r.data)
  },

  getEvent(id: number) {
    return http.get<Event>(`/events/${id}`).then(r => r.data)
  },

  getSources() {
    return http.get<string[]>('/sources').then(r => r.data)
  },

  getLogs() {
    return http.get<ScrapingLog[]>('/logs').then(r => r.data)
  },

  getBookmarks() {
    return http.get<Event[]>('/bookmarks').then(r => r.data)
  },

  addBookmark(eventId: number, chosenDate?: string) {
    const params = chosenDate ? { chosen_date: chosenDate } : undefined
    return http.post(`/bookmarks/${eventId}`, null, { params }).then(r => r.data)
  },

  removeBookmark(eventId: number) {
    return http.delete(`/bookmarks/${eventId}`).then(r => r.data)
  },

  getCustomEvents() {
    return http.get<CustomEvent[]>('/custom-events').then(r => r.data)
  },

  createCustomEvent(title: string, eventDate: string) {
    return http.post<CustomEvent>('/custom-events', { title, event_date: eventDate }).then(r => r.data)
  },

  deleteCustomEvent(id: number) {
    return http.delete(`/custom-events/${id}`).then(r => r.data)
  },

  hideEvent(eventId: number) {
    return http.post(`/hidden/${eventId}`).then(r => r.data)
  },

  unhideEvent(eventId: number) {
    return http.delete(`/hidden/${eventId}`).then(r => r.data)
  },

  getVapidPublicKey() {
    return http.get<{ public_key: string }>('/push/vapid-key').then(r => r.data.public_key)
  },

  getReminders() {
    return http.get<Reminder[]>('/reminders').then(r => r.data)
  },

  createReminder(
    eventId: number,
    remindAt: string,
    subscription: { endpoint: string; p256dh: string; auth: string },
  ) {
    return http.post<Reminder>('/reminders', {
      event_id: eventId,
      remind_at: remindAt,
      subscription,
    }).then(r => r.data)
  },

  deleteReminder(reminderId: number) {
    return http.delete(`/reminders/${reminderId}`).then(r => r.data)
  },
}

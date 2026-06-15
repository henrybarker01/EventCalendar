import axios from 'axios'

const http = axios.create({ baseURL: '/api' })

export interface Event {
  id: number
  title: string
  event_date: string
  end_date: string | null
  location: string | null
  description: string | null
  image_url: string | null
  source_url: string
  source_name: string
  category: string | null
  price: string | null
  is_active: boolean
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
}

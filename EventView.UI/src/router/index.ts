import { createRouter, createWebHashHistory } from 'vue-router'
import EventsView from '../views/EventsView.vue'
import EventDetailView from '../views/EventDetailView.vue'
import CalendarView from '../views/CalendarView.vue'

export default createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', component: EventsView },
    { path: '/events/:id', component: EventDetailView, props: true },
    { path: '/kalender', component: CalendarView },
  ],
  scrollBehavior: () => ({ top: 0 }),
})

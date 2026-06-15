import { createRouter, createWebHashHistory } from 'vue-router'
import EventsView from '../views/EventsView.vue'
import EventDetailView from '../views/EventDetailView.vue'

export default createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', component: EventsView },
    { path: '/events/:id', component: EventDetailView, props: true },
  ],
  scrollBehavior: () => ({ top: 0 }),
})

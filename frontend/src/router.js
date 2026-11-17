import { createRouter, createWebHistory } from 'vue-router'
import Home from './pages/Home.vue'
import Lines from './pages/Lines.vue'
import Pickups from './pages/Pickups.vue'
import Close from './pages/Close.vue'
import Variance from './pages/Variance.vue'
import Settings from './pages/Settings.vue'

export default createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: Home },
    { path: '/lines', component: Lines },
    { path: '/pickups', component: Pickups },
    { path: '/close', component: Close },
    { path: '/variance', component: Variance },
    { path: '/settings', component: Settings },
  ],
})

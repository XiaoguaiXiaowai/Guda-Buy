import { createPinia } from 'pinia'
import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'

import App from './App.vue'
import router from './router'
import { useAuthStore } from './stores/auth'
import './styles/index.scss'

const pinia = createPinia()
const app = createApp(App)
app.use(pinia).use(router).use(ElementPlus)
app.mount('#app')

void useAuthStore(pinia).restoreOnBoot()

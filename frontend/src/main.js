import { createApp } from 'vue'
import App from './App.vue'
import Toast from "vue-toastification"
import "vue-toastification/dist/index.css"

const app = createApp(App)

// Toast yapılandırması
const toastOptions = {
    position: "top-right",
    timeout: 3000,
    closeOnClick: true,
    pauseOnFocusLoss: true,
    pauseOnHover: true,
    draggable: true,
    draggablePercent: 0.6,
    showCloseButtonOnHover: false,
    hideProgressBar: false,
    closeButton: "button",
    icon: true,
    rtl: false
}

app.use(Toast, toastOptions)
app.mount('#app') 
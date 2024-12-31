import { defineStore } from 'pinia'
import { ref } from 'vue'
import { config } from '../config'

export const useAuthStore = defineStore('auth', () => {
  const isAuthenticated = ref(false)
  const csrfToken = ref('')
  const user = ref(null)

  async function login(username: string, password: string) {
    try {
      const response = await fetch(`${config.API_URL}/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ username, password }),
        credentials: 'include'
      })

      if (!response.ok) {
        throw new Error('Giriş başarısız')
      }

      const data = await response.json()
      csrfToken.value = data.csrf_token
      isAuthenticated.value = true
      user.value = data.user
      
      return true
    } catch (error) {
      console.error('Giriş hatası:', error)
      return false
    }
  }

  async function logout() {
    try {
      await fetch(`${config.API_URL}/logout`, {
        method: 'POST',
        headers: {
          'X-CSRF-Token': csrfToken.value
        },
        credentials: 'include'
      })
    } finally {
      isAuthenticated.value = false
      csrfToken.value = ''
      user.value = null
    }
  }

  async function checkAuth() {
    try {
      const response = await fetch(`${config.API_URL}/check-auth`, {
        credentials: 'include'
      })

      if (response.ok) {
        const data = await response.json()
        isAuthenticated.value = true
        user.value = data.user
        return true
      }
    } catch (error) {
      console.error('Auth kontrolü hatası:', error)
    }

    isAuthenticated.value = false
    user.value = null
    return false
  }

  return {
    isAuthenticated,
    csrfToken,
    user,
    login,
    logout,
    checkAuth
  }
}) 
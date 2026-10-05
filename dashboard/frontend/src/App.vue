<template>
  <div class="min-h-screen flex flex-col bg-[#070b14] text-slate-100">
    <template v-if="authenticated">
      <Navbar />
      <div class="max-w-7xl w-full mx-auto px-6 pt-3 text-right">
        <button class="text-sm text-slate-400 hover:text-cyan-300" @click="logout">Cerrar sesión</button>
      </div>
      <main class="flex-1 max-w-7xl w-full mx-auto p-6 md:p-8"><router-view /></main>
    </template>
    <main v-else class="flex-1 flex items-center justify-center px-6">
      <form v-if="!checking" class="w-full max-w-sm rounded-xl border border-slate-700 bg-slate-900 p-8" @submit.prevent="login">
        <h1 class="text-2xl font-bold text-cyan-300 mb-2">SecLab Dashboard</h1>
        <p class="text-sm text-slate-400 mb-6">Accede como tester con la contraseña del laboratorio.</p>
        <label for="username" class="block text-sm mb-2">Usuario</label>
        <input id="username" value="tester" name="username" autocomplete="username" readonly class="w-full rounded bg-slate-800 p-3 mb-4 text-slate-300" />
        <label for="password" class="block text-sm mb-2">Contraseña</label>
        <input id="password" v-model="password" type="password" autocomplete="current-password" required class="w-full rounded bg-slate-800 p-3 mb-4 border border-slate-600 focus:border-cyan-400 outline-none" />
        <p v-if="error" role="alert" class="text-sm text-red-300 mb-4">{{ error }}</p>
        <button type="submit" :disabled="busy" class="w-full rounded bg-cyan-400 text-slate-950 font-bold py-3 disabled:opacity-50">{{ busy ? 'Entrando…' : 'Entrar' }}</button>
      </form>
      <p v-else class="text-slate-400">Comprobando sesión…</p>
    </main>
    <footer class="border-t border-slate-800 px-6 py-4 text-xs font-mono text-slate-400 text-center">SecLab-SBF · Acceso privado · Evidence-First</footer>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import Navbar from './components/Navbar.vue'
import { api } from './api'
const authenticated = ref(false)
const checking = ref(true)
const busy = ref(false)
const password = ref('')
const error = ref('')
function sessionExpired() { authenticated.value = false; password.value = '' }
async function login() {
  busy.value = true; error.value = ''
  try { await api.login(password.value); password.value = ''; authenticated.value = true }
  catch (err) { error.value = err.message }
  finally { busy.value = false }
}
async function logout() {
  try { await api.logout(); sessionExpired() }
  catch (err) { error.value = err.message }
}
onMounted(async () => {
  localStorage.removeItem('seclab_token')
  window.addEventListener('seclab-session-expired', sessionExpired)
  try { await api.session(); authenticated.value = true } catch { authenticated.value = false }
  finally { checking.value = false }
})
onUnmounted(() => window.removeEventListener('seclab-session-expired', sessionExpired))
</script>

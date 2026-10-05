<template>
  <div class="min-h-screen flex flex-col bg-[#070b14] text-slate-100">
    <Navbar />

    <main class="flex-1 max-w-7xl w-full mx-auto p-6 md:p-8">
      <router-view />
    </main>

    <footer class="border-t border-[#1b253b] bg-[#0b101d] px-6 py-4 text-xs font-mono text-slate-400">
      <div class="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-2">
        <div class="flex items-center space-x-2">
          <span class="w-2 h-2 rounded-full bg-emerald-400"></span>
          <span>SecLab-SBF | Estación Táctica v1.0.0</span>
          <span>•</span>
          <span>Principio Evidence-First</span>
        </div>
        <div class="flex items-center space-x-4 text-slate-400">
          <span>Puerto Dashboard: :8080</span>
          <span>•</span>
          <span>Terminal: :7681</span>
          <span>•</span>
          <span>Acceso Privado</span>
        </div>
      </div>
    </footer>
  </div>
</template>

<script setup>
import Navbar from './components/Navbar.vue'
</script>

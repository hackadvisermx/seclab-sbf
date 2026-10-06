import { createRouter, createWebHistory } from 'vue-router'
import DashboardView from '../views/DashboardView.vue'
import EngagementsView from '../views/EngagementsView.vue'
import NewAuditWizardView from '../views/NewAuditWizardView.vue'
import EngagementDetailView from '../views/EngagementDetailView.vue'
import VaultView from '../views/VaultView.vue'
import HelpView from '../views/HelpView.vue'
import TrashView from '../views/TrashView.vue'
import TerminalView from '../views/TerminalView.vue'
import ChatView from '../views/ChatView.vue'

const routes = [
  { path: '/', name: 'Dashboard', component: DashboardView },
  { path: '/engagements', name: 'Engagements', component: EngagementsView },
  { path: '/wizard', name: 'NewAuditWizard', component: NewAuditWizardView },
  { path: '/engagements/:type/:id', name: 'EngagementDetail', component: EngagementDetailView },
  { path: '/chat', name: 'Chat', component: ChatView },
  { path: '/trash', name: 'Trash', component: TrashView },
  { path: '/terminal', name: 'Terminal', component: TerminalView },
  { path: '/vault', name: 'Vault', component: VaultView },
  { path: '/help', name: 'Help', component: HelpView },
]

export const router = createRouter({
  history: createWebHistory(),
  routes,
})

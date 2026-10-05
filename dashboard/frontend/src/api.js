const API_BASE = '/api/v1'

async function request(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint}`
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {})
  }

  const token = localStorage.getItem('seclab_token')
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const res = await fetch(url, { ...options, headers })
  if (!res.ok) {
    let errorDetail = 'Error en la petición'
    try {
      const errJson = await res.json()
      errorDetail = errJson.detail || JSON.stringify(errJson)
    } catch {
      errorDetail = await res.text()
    }
    throw new Error(errorDetail)
  }
  return res.json()
}

export const api = {
  // Engagements
  getEngagements: () => request('/engagements'),
  createEngagement: (data) => request('/engagements', { method: 'POST', body: JSON.stringify(data) }),
  getEngagementDetail: (id, type = 'engagement') => request(`/engagements/${id}?type=${type}`),
  updateNotes: (id, content, type = 'engagement') => request(`/engagements/${id}/notes?type=${type}`, { method: 'PUT', body: JSON.stringify({ content }) }),

  // Alcance
  getScope: (id, type = 'engagement') => request(`/scope/${id}?type=${type}`),
  updateScope: (id, data, type = 'engagement') => request(`/scope/${id}?type=${type}`, { method: 'PUT', body: JSON.stringify(data) }),
  checkScope: (target, engagementId, type = 'engagement') => request(`/scope/check?type=${type}`, { method: 'POST', body: JSON.stringify({ target, engagement_id: engagementId }) }),

  // Hallazgos & CVSS
  getFindings: (id, type = 'engagement') => request(`/findings/${id}?type=${type}`),
  getFinding: (id, slug, type = 'engagement') => request(`/findings/${id}/${slug}?type=${type}`),
  saveFinding: (id, data, type = 'engagement') => request(`/findings/${id}?type=${type}`, { method: 'POST', body: JSON.stringify(data) }),
  deleteFinding: (id, slug, type = 'engagement') => request(`/findings/${id}/${slug}?type=${type}`, { method: 'DELETE' }),
  calculateCvss: (metrics) => request('/findings/cvss-calc', { method: 'POST', body: JSON.stringify(metrics) }),

  // Tactical API Key Vault
  getVaultKeys: () => request('/vault'),
  upsertVaultKey: (data) => request('/vault', { method: 'POST', body: JSON.stringify(data) }),
  updateVaultKey: (provider, data) => request(`/vault/${provider}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteVaultKey: (provider) => request(`/vault/${provider}`, { method: 'DELETE' }),
  testVaultKey: (provider) => request(`/vault/${provider}/test`, { method: 'POST' }),

  // Tactical Proxy Gateway
  proxyChat: (messages, provider = null, model = null, profile = null) => {
    const qs = profile ? `?profile=${profile}` : ''
    return request(`/proxy/ai/chat${qs}`, { method: 'POST', body: JSON.stringify({ messages, provider, model }) })
  },
  getProxyStats: () => request('/proxy/stats'),
  getProxyHistory: (limit = 20) => request(`/proxy/history?limit=${limit}`),

  // Copiloto Táctico & Agentes
  getCopilotAgents: () => request('/copilot/agents'),
  getCopilotContext: (engId, agent = 'triage-agent', type = 'engagement') => request(`/copilot/context/${engId}?agent=${agent}&type=${type}`),
  sendCopilotChat: (data) => request('/copilot/chat', { method: 'POST', body: JSON.stringify(data) }),

  // Logs & Reportes
  getLogs: (id, lines = 500, type = 'engagement') => request(`/logs/${id}?lines=${lines}&type=${type}`),
  compileReport: (id, type = 'engagement') => request(`/reports/${id}/compile?type=${type}`, { method: 'POST' }),
  previewReport: (id, type = 'engagement') => request(`/reports/${id}/preview?type=${type}`),
  packReport: (id, type = 'engagement') => request(`/reports/${id}/pack?type=${type}`, { method: 'POST' }),

  // Checklist & Metodología
  getChecklist: (id, type = 'engagement') => request(`/checklist/${id}?type=${type}`),
  getNextStep: (id, prompt = false, type = 'engagement') => request(`/checklist/${id}/next?prompt=${prompt}&type=${type}`),

  // Centro de Ayuda & Telemetría
  getCheatsheet: () => request('/help/cheatsheet'),
  getSkills: () => request('/help/skills'),
  getSkillDetail: (id) => request(`/help/skills/${id}`),
  getTelemetry: () => request('/system/telemetry'),
  getSystemInfo: () => request('/system/info'),

  // Botín, Banderas CTF & Artefactos
  getLoot: (id, type = 'engagement') => request(`/loot/${id}?type=${type}`),
  saveCredential: (id, data, type = 'engagement') => request(`/loot/${id}/credentials?type=${type}`, { method: 'POST', body: JSON.stringify(data) }),
  deleteCredential: (id, credId, type = 'engagement') => request(`/loot/${id}/credentials/${credId}?type=${type}`, { method: 'DELETE' }),
  getFlags: (id, type = 'reto') => request(`/loot/${id}/flags?type=${type}`),
  saveFlags: (id, data, type = 'reto') => request(`/loot/${id}/flags?type=${type}`, { method: 'POST', body: JSON.stringify(data) }),
  getArtifacts: (id, folder = 'recon', type = 'engagement') => request(`/loot/${id}/artifacts?folder=${folder}&type=${type}`),
  getArtifactContent: (id, path, type = 'engagement') => request(`/loot/${id}/artifacts/content?path=${encodeURIComponent(path)}&type=${type}`),

  // Reportes & Descarga
  compileReport: (id, type = 'engagement') => request(`/reports/${id}/compile?type=${type}`, { method: 'POST' }),
  previewReport: (id, type = 'engagement') => request(`/reports/${id}/preview?type=${type}`),
  packReport: (id, type = 'engagement') => request(`/reports/${id}/pack?type=${type}`, { method: 'POST' }),
  getDownloadReportUrl: (id, type = 'engagement') => `/api/v1/reports/${id}/download?type=${type}`,

  // VPN Táctica & Gestión de Credenciales
  getVpnStatus: () => request('/vpn/status'),
  getSavedVpnCredentials: () => request('/vpn/saved-credentials'),
  connectVpn: (data) => {
    const payload = typeof data === 'string' ? { profile: data } : data
    return request('/vpn/connect', { method: 'POST', body: JSON.stringify(payload) })
  },
  disconnectVpn: () => request('/vpn/disconnect', { method: 'POST' }),
  switchVpn: (data) => {
    const payload = typeof data === 'string' ? { profile: data } : data
    return request('/vpn/switch', { method: 'POST', body: JSON.stringify(payload) })
  },
  deleteSavedVpnCredentials: (profile) => request(`/vpn/saved-credentials/${profile}`, { method: 'DELETE' }),

  // Pipeline de Reconocimiento & Scope Guard
  getReconStatus: (id, type = 'engagement') => request(`/recon/${id}/status?type=${type}`),
  runRecon: (id, data, type = 'engagement') => request(`/recon/${id}/run?type=${type}`, { method: 'POST', body: JSON.stringify(data) }),
  getReconLog: (id, lines = 200, type = 'engagement') => request(`/recon/${id}/log?lines=${lines}&type=${type}`),
}

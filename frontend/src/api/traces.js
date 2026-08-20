const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'

async function request(path, options = {}) {
  const response = await fetch(`${API_URL}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  })
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}))
    throw new Error(payload.detail || `Request failed (${response.status})`)
  }
  return response.json()
}

export const getTraces = () => request('/traces')
export const getHealth = () => request('/health')
export const getTrace = (traceId) => request(`/traces/${traceId}`)
export const getTraceSummary = (traceId) => request(`/traces/${traceId}/summary`)
export const createTrace = (input) => request('/traces', { method: 'POST', body: JSON.stringify({ input }) })
export const createEvent = (traceId, event) => request(`/traces/${traceId}/events`, { method: 'POST', body: JSON.stringify(event) })
export const completeTrace = (traceId, output) => request(`/traces/${traceId}/complete`, { method: 'POST', body: JSON.stringify({ output }) })
export const failTrace = (traceId, errorMessage) => request(`/traces/${traceId}/fail`, { method: 'POST', body: JSON.stringify({ error_message: errorMessage }) })

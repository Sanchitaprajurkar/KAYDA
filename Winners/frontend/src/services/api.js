// ============================================================
//  NINE REALMS — Tribunal Backend API Client
// ============================================================

const API_BASE_URL = 'http://localhost:8000/api'

export async function checkBackendHealth() {
  try {
    const res = await fetch(`${API_BASE_URL}/health`)
    return await res.json()
  } catch (err) {
    console.warn('[NineRealms API] Backend offline, using local store:', err)
    return null
  }
}

export async function startTrial(query, asOfDate = '2027-01-25') {
  const res = await fetch(`${API_BASE_URL}/trial/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, as_of_date: asOfDate }),
  })
  if (!res.ok) throw new Error(`Trial start failed: ${res.statusText}`)
  return await res.json()
}

export async function getCaseDetails(caseId) {
  const res = await fetch(`${API_BASE_URL}/trial/case/${caseId}`)
  if (!res.ok) throw new Error(`Failed to fetch case: ${res.statusText}`)
  return await res.json()
}

export async function getCorpusDocument(docId) {
  const res = await fetch(`${API_BASE_URL}/corpus/documents/${docId}`)
  if (!res.ok) throw new Error(`Document ${docId} not found`)
  return await res.json()
}

export async function getCorpusFeed(asOfDate = '2027-01-25', limit = 20) {
  const res = await fetch(`${API_BASE_URL}/corpus/feed?as_of_date=${asOfDate}&limit=${limit}`)
  if (!res.ok) throw new Error(`Failed to load feed: ${res.statusText}`)
  return await res.json()
}

export function subscribeToTrialEvents(caseId, onEvent, onError) {
  const eventSource = new EventSource(`${API_BASE_URL}/trial/case/${caseId}/stream`)
  
  eventSource.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      onEvent(data)
    } catch (err) {
      console.error('Failed to parse SSE event data', err)
    }
  }

  eventSource.onerror = (err) => {
    if (onError) onError(err)
    eventSource.close()
  }

  return () => eventSource.close()
}

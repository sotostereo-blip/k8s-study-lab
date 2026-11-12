async function request(path, options = {}) {
  const res = await fetch(`/api${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
    body: options.body ? JSON.stringify(options.body) : undefined,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

export const api = {
  exams: () => request('/exams'),
  glossary: () => request('/glossary'),
  stats: (exam = 'kcna') => request(`/stats?exam_id=${exam}`),
  practiceNext: (exam = 'kcna', domain, n = 10) =>
    request(`/practice/next?exam_id=${exam}&n=${n}${domain ? `&domain=${domain}` : ''}`),
  answer: (body) => request('/practice/answer', { method: 'POST', body }),
  examStart: (body) => request('/exam/start', { method: 'POST', body }),
  examSubmit: (id, answers) => request(`/exam/${id}/submit`, { method: 'POST', body: { answers } }),
  englishEvent: (kind, ref) => request('/english/event', { method: 'POST', body: { kind, ref } }),
  labs: () => request('/labs'),
  labStatus: () => request('/labs/status'),
  labStart: (id) => request(`/labs/${id}/start`, { method: 'POST' }),
  labStop: () => request('/labs/stop', { method: 'POST' }),
  labCheck: (id) => request(`/labs/${id}/check`, { method: 'POST' }),
  labSolution: (id) => request(`/labs/${id}/solution`),
  mockStart: (tasks) => request('/mock/start', { method: 'POST', body: { tasks } }),
  mockCurrent: () => request('/mock/current'),
  mockSubmit: (id) => request(`/mock/${id}/submit`, { method: 'POST' }),
  mockAbandon: (id) => request(`/mock/${id}/abandon`, { method: 'POST' }),
}

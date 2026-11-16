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
  history: (cert) => request(`/history?cert_id=${cert}`),
  progressSummary: () => request('/progress/summary'),
  progressImport: async (file) => {
    const res = await fetch('/api/progress/import', {
      method: 'POST', headers: { 'Content-Type': 'application/octet-stream' }, body: file,
    })
    const out = await res.json().catch(() => ({}))
    if (!res.ok) throw new Error(out.detail || `HTTP ${res.status}`)
    return out
  },
  exams: () => request('/exams'),
  certifications: () => request('/certifications'),
  glossary: () => request('/glossary'),
  vocabulary: () => request('/vocabulary'),
  englishNext: (kind, n = 10) => request(`/english/next?n=${n}${kind ? `&kind=${kind}` : ''}`),
  englishAnswer: (item_id, selected) => request('/english/answer', { method: 'POST', body: { item_id, selected } }),
  englishStats: () => request('/english/stats'),
  stats: (exam = 'kcna') => request(`/stats?exam_id=${exam}`),
  practiceNext: (exam = 'kcna', domain, n = 10) =>
    request(`/practice/next?exam_id=${exam}&n=${n}${domain ? `&domain=${domain}` : ''}`),
  answer: (body) => request('/practice/answer', { method: 'POST', body }),
  examStart: (body) => request('/exam/start', { method: 'POST', body }),
  examSubmit: (id, answers, domc = {}) => request(`/exam/${id}/submit`, { method: 'POST', body: { answers, domc } }),
  examDomc: (id, question_id, responses) => request(`/exam/${id}/domc`, { method: 'POST', body: { question_id, responses } }),
  englishEvent: (kind, ref) => request('/english/event', { method: 'POST', body: { kind, ref } }),
  labs: (track) => request(`/labs?track_id=${track}`),
  labStatus: () => request('/labs/status'),
  labStart: (id) => request(`/labs/${id}/start`, { method: 'POST' }),
  labStop: () => request('/labs/stop', { method: 'POST' }),
  labCheck: (id) => request(`/labs/${id}/check`, { method: 'POST' }),
  labSolution: (id) => request(`/labs/${id}/solution`),
  mockStart: (track, tasks) => request('/mock/start', { method: 'POST', body: { track_id: track, tasks } }),
  mockCurrent: (track) => request(`/mock/current?track_id=${track}`),
  mockSubmit: (id) => request(`/mock/${id}/submit`, { method: 'POST' }),
  interviewCategories: () => request('/interview/categories'),
  interviewNext: (category, level, n = 10) =>
    request(`/interview/next?n=${n}${category ? `&category=${category}` : ''}${level ? `&level=${level}` : ''}`),
  interviewReview: (id) => request(`/interview/${id}/review`),
  interviewGrade: (body) => request('/interview/grade', { method: 'POST', body }),
  interviewMockStart: (body) => request('/interview/mock/start', { method: 'POST', body }),
  interviewMockFinish: (id) => request(`/interview/mock/${id}/finish`, { method: 'POST' }),
  aiStatus: () => request('/ai/status'),
  practiceExplain: (body) => request('/practice/explain', { method: 'POST', body }),
  interviewFeedback: (body) => request('/interview/feedback', { method: 'POST', body }),
  interviewStats: () => request('/interview/stats'),
  interviewPhrases: () => request('/interview/phrases'),
  mockAbandon: (id) => request(`/mock/${id}/abandon`, { method: 'POST' }),
  plan: (cert) => request(`/plan?cert_id=${cert}`),
  planSet: (cert, body) => request(`/plan?cert_id=${cert}`, { method: 'PUT', body }),
  path: () => request('/path'),
  earnedSet: (cert, body) => request(`/earned?cert_id=${cert}`, { method: 'PUT', body }),
  earnedDelete: (cert) => request(`/earned?cert_id=${cert}`, { method: 'DELETE' }),
  planDelete: (cert) => request(`/plan?cert_id=${cert}`, { method: 'DELETE' }),
}

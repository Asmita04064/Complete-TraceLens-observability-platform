import { useEffect, useMemo, useState } from 'react'
import { getHealth, getTrace, getTraceSummary, getTraces } from './api/traces.js'

const typeLabels = { llm_call: 'LLM call', tool_call: 'Tool call', database_query: 'Database query' }
const typeIcons = { llm_call: '✦', tool_call: '↗', database_query: '⌁' }

function formatDuration(value) {
  const duration = Number(value)
  return value == null || !Number.isFinite(duration) ? '—' : `${duration} ms`
}

function formatDate(value) {
  if (!value) return '—'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '—' : date.toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })
}

function getBarWidth(value, total) {
  const duration = Number(value)
  const totalDuration = Number(total)
  if (!Number.isFinite(duration) || !Number.isFinite(totalDuration) || totalDuration <= 0) return 4
  return Math.max(4, Math.min(100, (duration / totalDuration) * 100))
}

function Status({ value }) {
  const status = value || 'unknown'
  return <span className={`status status-${status}`}>{status}</span>
}

function App() {
  const [currentView, setCurrentView] = useState('dashboard')
  const [traces, setTraces] = useState([])
  const [selectedTraceId, setSelectedTraceId] = useState(null)
  const [detail, setDetail] = useState(null)
  const [summary, setSummary] = useState(null)
  const [query, setQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [loading, setLoading] = useState(true)
  const [detailLoading, setDetailLoading] = useState(false)
  const [summaryLoading, setSummaryLoading] = useState(false)
  const [error, setError] = useState('')
  const [apiOnline, setApiOnline] = useState(null)
  const [refreshing, setRefreshing] = useState(false)

  async function loadTraces() {
    if (refreshing) return
    setRefreshing(true)
    setLoading(true)
    setError('')
    try {
      const nextTraces = await getTraces()
      if (!Array.isArray(nextTraces)) throw new Error('Expected /traces to return an array')
      setTraces(nextTraces)
      setApiOnline(true)
    } catch (requestError) {
      console.error('Unable to load traces:', requestError)
      setTraces([])
      setApiOnline(false)
      setError('Unable to load traces. Check that the backend is running.')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }

  useEffect(() => {
    let cancelled = false
    getHealth()
      .then((health) => {
        if (!cancelled) setApiOnline(health?.status === 'healthy')
      })
      .catch((requestError) => {
        console.error('Unable to check API health:', requestError)
        if (!cancelled) setApiOnline(false)
      })
    loadTraces()
    return () => { cancelled = true }
  }, [])

  useEffect(() => {
    if (!selectedTraceId) return
    let cancelled = false
    setDetailLoading(true)
    setSummaryLoading(true)
    setDetail(null)
    setSummary(null)

    getTrace(selectedTraceId)
      .then((nextDetail) => {
        if (!nextDetail || typeof nextDetail !== 'object' || !Array.isArray(nextDetail.events)) {
          throw new Error('Expected trace detail with an events array')
        }
        if (!cancelled) setDetail(nextDetail)
      })
      .catch((requestError) => {
        console.error(`Unable to load trace ${selectedTraceId}:`, requestError)
        if (!cancelled) setError('Unable to load trace details. Check that the backend is running.')
      })
      .finally(() => {
        if (!cancelled) setDetailLoading(false)
      })

    getTraceSummary(selectedTraceId)
      .then((nextSummary) => {
        if (!nextSummary || typeof nextSummary !== 'object') throw new Error('Expected a trace summary object')
        if (!cancelled) setSummary(nextSummary)
      })
      .catch((requestError) => {
        console.error(`Unable to load summary for trace ${selectedTraceId}:`, requestError)
        if (!cancelled) setError('Trace loaded, but its summary could not be retrieved.')
      })
      .finally(() => {
        if (!cancelled) setSummaryLoading(false)
      })

    return () => { cancelled = true }
  }, [selectedTraceId])

  const filteredTraces = useMemo(() => traces.filter((trace) => {
    const matchesQuery = `${trace.trace_id || ''} ${trace.input || ''} ${trace.status || ''}`.toLowerCase().includes(query.toLowerCase())
    return matchesQuery && (statusFilter === 'all' || trace.status === statusFilter)
  }), [traces, query, statusFilter])

  const metrics = {
    total: traces.length,
    running: traces.filter((trace) => trace.status === 'running').length,
    completed: traces.filter((trace) => trace.status === 'completed').length,
    failed: traces.filter((trace) => trace.status === 'failed').length,
    average: (() => {
      const completedDurations = traces.filter((trace) => trace.status === 'completed' && Number.isFinite(Number(trace.duration_ms))).map((trace) => Number(trace.duration_ms))
      return completedDurations.length ? Math.round(completedDurations.reduce((sum, duration) => sum + duration, 0) / completedDurations.length) : null
    })(),
  }

  function openTrace(traceId) {
    setSelectedTraceId(traceId)
    setError('')
    setCurrentView('trace-detail')
  }

  function showTraces() {
    setCurrentView('traces')
    setError('')
  }

  const selectedListTrace = traces.find((trace) => trace.trace_id === selectedTraceId)

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand"><span className="brand-mark">T</span><span>TraceLens</span></div>
        <nav><button className={`nav-item ${currentView === 'dashboard' ? 'active' : ''}`} onClick={() => setCurrentView('dashboard')}><span>◈</span> Dashboard</button><button className={`nav-item ${currentView !== 'dashboard' ? 'active' : ''}`} onClick={showTraces}><span>⌘</span> Traces</button></nav>
        <div className="sidebar-foot"><div className={`connection-label ${apiOnline === false ? 'offline' : ''}`}><span className="pulse" /> API {apiOnline === false ? 'offline' : apiOnline === true ? 'connected' : 'checking'}</div><small>FastAPI · PostgreSQL</small><div className="sidebar-version"><strong>TraceLens</strong><span>Agent observability</span><span>v0.1.0</span></div></div>
      </aside>
      <main className="main-content">
        <header className="topbar"><div><p className="eyebrow">OPERATIONS / {currentView === 'dashboard' ? 'OVERVIEW' : currentView === 'traces' ? 'TRACES' : 'TRACE DETAIL'}</p><h1>{currentView === 'dashboard' ? 'Agent observability dashboard' : currentView === 'traces' ? 'Traces' : 'Trace details'}</h1><p className="lede">{currentView === 'dashboard' ? 'Monitor every model, tool, and data operation across your agent executions.' : currentView === 'traces' ? 'Inspect every agent execution and its events.' : 'Follow every model, tool, and data step in one execution view.'}</p></div><div className="header-actions"><div className={`api-status ${apiOnline === false ? 'offline' : ''}`}><span /> API {apiOnline === false ? 'Offline' : apiOnline === true ? 'Connected' : 'Checking'}</div><button className="refresh" onClick={loadTraces} disabled={refreshing}><span className={refreshing ? 'spinner' : 'refresh-icon'}>↻</span> <span>{refreshing ? 'Refreshing' : 'Refresh data'}</span></button></div></header>
        {error && <div className="alert">{error}<button onClick={() => setError('')}>Dismiss</button></div>}
        {currentView === 'dashboard' && <section className="metric-grid">
          <Metric label="Total traces" value={metrics.total} note="All executions" accent="teal" loading={loading} />
          <Metric label="Running" value={metrics.running} note="Currently in progress" accent="amber" loading={loading} />
          <Metric label="Completed" value={metrics.completed} note="Successful executions" accent="green" loading={loading} />
          <Metric label="Failed" value={metrics.failed} note="Require attention" accent="red" loading={loading} />
          <Metric label="Average duration" value={formatDuration(metrics.average)} note="Across completed traces" accent="blue" loading={loading} />
        </section>}
        {currentView === 'dashboard' && <section className="workspace-grid">
          <div className="panel trace-panel">
            <div className="panel-heading"><div><p className="eyebrow">EXECUTION LOG</p><h2>Recent traces</h2></div><span className="count">{filteredTraces.length} visible</span></div>
            <div className="filters"><div className="search"><span>⌕</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search traces or prompts" />{query && <button className="clear-search" title="Clear search" onClick={() => setQuery('')}>×</button>}</div><select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}><option value="all">All statuses</option><option value="running">Running</option><option value="completed">Completed</option><option value="failed">Failed</option></select></div>
            {loading ? <TraceListSkeleton /> : filteredTraces.length === 0 ? <EmptyTraceState filtered={Boolean(query || statusFilter !== 'all')} /> : <div className="trace-list">{filteredTraces.map((trace) => <button className="trace-row" key={trace.trace_id || trace.input} onClick={() => trace.trace_id && openTrace(trace.trace_id)}><span className="trace-main"><strong>{trace.input || 'Untitled execution'}</strong><small>{trace.trace_id || '—'}</small></span><Status value={trace.status} /><span className="row-meta">{trace.event_count == null ? '—' : trace.event_count} events</span><span className="row-meta">{formatDuration(trace.duration_ms)}</span><span className="row-date">{formatDate(trace.started_at)}</span><span className="arrow">→</span></button>)}</div>}
          </div>
          <TraceDetail detail={detail} summary={summary} loading={detailLoading} summaryLoading={summaryLoading} />
        </section>}
        {currentView === 'traces' && <section className="panel trace-panel dedicated-traces"><div className="panel-heading"><div><p className="eyebrow">TRACE EXPLORER</p><h2>All executions</h2></div><span className="count">{filteredTraces.length} visible</span></div><div className="filters"><div className="search"><span>⌕</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search traces or prompts" />{query && <button className="clear-search" title="Clear search" onClick={() => setQuery('')}>×</button>}</div><select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}><option value="all">All statuses</option><option value="running">Running</option><option value="completed">Completed</option><option value="failed">Failed</option></select></div>{loading ? <TraceListSkeleton /> : filteredTraces.length === 0 ? <EmptyTraceState filtered={Boolean(query || statusFilter !== 'all')} /> : <div className="trace-list">{filteredTraces.map((trace) => <button className="trace-row" key={trace.trace_id || trace.input} onClick={() => trace.trace_id && openTrace(trace.trace_id)}><span className="trace-main"><strong>{trace.input || 'Untitled execution'}</strong><small>{trace.trace_id || '—'}</small></span><Status value={trace.status} /><span className="row-meta">{trace.event_count == null ? '—' : trace.event_count} events</span><span className="row-meta">{formatDuration(trace.duration_ms)}</span><span className="row-date">{formatDate(trace.started_at)}</span><span className="arrow">→</span></button>)}</div>}</section>}
        {currentView === 'trace-detail' && <div className="detail-page"><button className="back-button" onClick={showTraces}>← Back to traces</button><TraceDetail detail={detail} summary={summary} listTrace={selectedListTrace} loading={detailLoading} summaryLoading={summaryLoading} /></div>}
      </main>
    </div>
  )
}

function Metric({ label, value, note, accent, loading }) { return <div className={`metric-card accent-${accent}`}><div className="metric-top"><span>{label}</span><i /></div>{loading ? <div className="metric-skeleton" /> : <strong>{value}</strong>}<small>{note}</small></div> }

function TraceListSkeleton() { return <div className="trace-list skeleton-list">{[1, 2, 3].map((row) => <div className="skeleton-row" key={row}><span /><span /><span /><span /></div>)}</div> }
function EmptyTraceState({ filtered }) { return <div className="empty-state"><strong>{filtered ? 'No traces found' : 'No agent executions yet'}</strong><span>{filtered ? 'Try changing your search or status filter.' : 'Create a trace to start monitoring your agent.'}</span></div> }

function TraceDetail({ detail, summary, loading, summaryLoading, listTrace }) {
  if (loading) return <div className="panel detail-panel state">Loading traces...</div>
  if (!detail) return <div className="panel detail-panel state">No traces found.</div>
  const events = Array.isArray(detail.events) ? detail.events : []
  const breakdown = summary ? [['LLM Duration', summary.llm_duration_ms], ['Tool Duration', summary.tool_duration_ms], ['Database Duration', summary.database_duration_ms]] : []
  return <div className="panel detail-panel"><div className="panel-heading"><div><p className="eyebrow">TRACE INSPECTOR</p><h2>Trace details</h2></div><Status value={detail.status} /></div><div className="trace-id">{detail.trace_id || '—'}</div><div className="info-grid detail-info"><Info label="Trace ID" value={detail.trace_id || '—'} /><Info label="Status" value={detail.status || '—'} /><Info label="Input" value={detail.input || '—'} /><Info label="Output" value={detail.output || '—'} /><Info label="Duration" value={formatDuration(detail.duration_ms)} /><Info label="Started At" value={formatDate(listTrace?.started_at)} /><Info label="Completed At" value={formatDate(listTrace?.completed_at)} /></div>{summary ? <><div className="section-label">Summary metrics</div><div className="summary-grid"><SummaryMetric label="Total Events" value={summary.total_events ?? '—'} /><SummaryMetric label="Successful Events" value={summary.successful_events ?? '—'} /><SummaryMetric label="Failed Events" value={summary.failed_events ?? '—'} /><SummaryMetric label="Total Duration" value={formatDuration(summary.total_duration_ms)} /><SummaryMetric label="Total Event Duration" value={formatDuration(summary.total_event_duration_ms)} /><SummaryMetric label="LLM Duration" value={formatDuration(summary.llm_duration_ms)} /><SummaryMetric label="Tool Duration" value={formatDuration(summary.tool_duration_ms)} /><SummaryMetric label="Database Duration" value={formatDuration(summary.database_duration_ms)} /></div></> : <div className="summary-state">{summaryLoading ? 'Loading summary...' : 'Summary unavailable.'}</div>}<div className="section-label">Execution timeline</div>{events.length === 0 ? <div className="state timeline-empty">No events found.</div> : <div className="timeline">{events.map((event, index) => <div className="timeline-item" key={event.event_id || `${event.sequence_number}-${index}`}><div className={`event-icon event-${event.status || 'unknown'}`}>{typeIcons[event.event_type] || '·'}</div><div className="event-content"><div className="event-title"><strong>{event.sequence_number ?? index + 1}. {typeLabels[event.event_type] || event.event_type || 'Unknown event'}</strong><Status value={event.status} /></div><div className="event-component">Component: {event.component || '—'}</div><div className="event-meta"><span>Status: {event.status || '—'}</span><span>Duration: {formatDuration(event.duration_ms)}</span><span>{event.parent_event_id == null ? 'Parent: —' : `Parent Event: ${event.parent_event_id}`}</span><span>Event ID: {event.event_id || '—'}</span></div></div>{index < events.length - 1 && <div className="timeline-line" />}</div>)}</div>}<div className="section-label">Latency breakdown</div><div className="breakdown">{breakdown.map(([label, value]) => <div className="bar-row" key={label}><span>{label}</span><div className="bar"><i style={{ width: `${getBarWidth(value, summary?.total_event_duration_ms)}%` }} /></div><strong>{formatDuration(value)}</strong></div>)}</div></div>
}

function Info({ label, value }) { return <div><small>{label}</small><strong>{value}</strong></div> }
function SummaryMetric({ label, value }) { return <div className="summary-metric"><small>{label}</small><strong>{value}</strong></div> }

export default App

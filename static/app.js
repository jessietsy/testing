// ── Element references ─────────────────────────────────────────────────────
const fileInput       = document.getElementById('file-input')
const uploadBox       = document.getElementById('upload-box')
const browseBtn       = document.getElementById('browse-btn')
const selectedFile    = document.getElementById('selected-file')
const evaluateBtn     = document.getElementById('evaluate-btn')
const loadingSection  = document.getElementById('loading-section')
const loadingMessage  = document.getElementById('loading-message')
const resultsSection  = document.getElementById('results-section')
const errorSection    = document.getElementById('error-section')
const errorMessage    = document.getElementById('error-message')

let selectedZip = null

// ── File selection ─────────────────────────────────────────────────────────
browseBtn.addEventListener('click', () => fileInput.click())

uploadBox.addEventListener('dragover', e => {
    e.preventDefault()
    uploadBox.style.borderColor = '#4f46e5'
})

uploadBox.addEventListener('dragleave', () => {
    uploadBox.style.borderColor = '#ccc'
})

uploadBox.addEventListener('drop', e => {
    e.preventDefault()
    uploadBox.style.borderColor = '#ccc'
    const file = e.dataTransfer.files[0]
    if (file && file.name.endsWith('.zip')) handleFileSelected(file)
})

fileInput.addEventListener('change', () => {
    if (fileInput.files[0]) handleFileSelected(fileInput.files[0])
})

function handleFileSelected(file) {
    selectedZip = file
    selectedFile.textContent = 'Selected: ' + file.name
    selectedFile.classList.remove('hidden')
    evaluateBtn.classList.remove('hidden')
}

// ── Evaluation ─────────────────────────────────────────────────────────────
evaluateBtn.addEventListener('click', runEvaluation)

async function runEvaluation() {
    if (!selectedZip) return

    showLoading('Uploading project...')

    const formData = new FormData()
    formData.append('file', selectedZip)

    // Update loading message while waiting
    const messages = [
        [4000,  'Building Docker container...'],
        [10000, 'Starting application...'],
        [20000, 'Running load test...'],
        [40000, 'Collecting metrics...'],
        [55000, 'Evaluating with AI...']
    ]
    const timers = messages.map(([delay, msg]) =>
        setTimeout(() => { loadingMessage.textContent = msg }, delay)
    )

    try {
        const response = await fetch('/evaluate', {
            method: 'POST',
            body: formData
        })

        timers.forEach(clearTimeout)

        const data = await response.json()

        if (!response.ok) {
            const detail = data.details
                ? (Array.isArray(data.details) ? data.details.join(', ') : data.details)
                : ''
            showError((data.error || 'Something went wrong') + (detail ? ': ' + detail : ''))
            return
        }

        showResults(data)

    } catch (err) {
        timers.forEach(clearTimeout)
        showError('Could not reach the server. Make sure Flask is running.')
        console.error(err)
    }
}

// ── Display results ────────────────────────────────────────────────────────
function showResults(data) {
    hideAll()
    resultsSection.classList.remove('hidden')

    const metrics    = data.metrics || {}
    const aggregate  = metrics.aggregate || {}
    const scores     = data.scores || {}
    const perEndpoint = scores.endpoint_scores || {}
    const evaluation = data.evaluation || {}
    const subChars   = scores.sub_characteristics || {}

    // Overall banner
    renderOverallBanner(scores, evaluation)

    // Sub-characteristic scores
    renderSubChar('time',     subChars.time_behaviour)
    renderSubChar('resource', subChars.resource_utilisation)
    renderSubChar('capacity', subChars.capacity)

    // Aggregate metrics
    renderAggregate(aggregate)

    // Endpoint table
    renderEndpointTable(perEndpoint)

    // Endpoint detail cards
    renderEndpointCards(perEndpoint)

    // AI evaluation
    renderAiEvaluation(evaluation)

    // Run errors
    renderRunErrors(data.run_errors || [])
}

// ── Overall banner ─────────────────────────────────────────────────────────
function renderOverallBanner(scores, evaluation) {
    const rating  = (evaluation.overall_rating || 'Unknown').toLowerCase()
    const banner  = document.getElementById('overall-banner')
    banner.className = 'overall-banner banner-' + rating

    document.getElementById('overall-rating').textContent =
        evaluation.overall_rating || '—'
    document.getElementById('overall-score').textContent =
        scores.overall_score !== undefined ? scores.overall_score : '—'
    document.getElementById('overall-grade').textContent =
        scores.grade || '—'
    document.getElementById('overall-summary').textContent =
        evaluation.summary || ''
}

// ── Sub-characteristic card ────────────────────────────────────────────────
function renderSubChar(prefix, subChar) {
    if (!subChar) return

    const score = subChar.score !== undefined ? subChar.score : 0
    const grade = subChar.grade || 'F'

    document.getElementById(prefix + '-score').textContent = score
    document.getElementById(prefix + '-grade').textContent = grade
    document.getElementById(prefix + '-grade').className =
        'grade-pill grade-' + grade

    const bar = document.getElementById(prefix + '-bar')
    bar.style.width = score + '%'
    bar.className = 'score-bar bar-' + grade.toLowerCase()
}

// ── Aggregate metrics ──────────────────────────────────────────────────────
function renderAggregate(agg) {
    setValue('agg-total-requests',  agg.total_requests)
    setValue('agg-failed-requests', agg.failed_requests)
    setValue('agg-failure-rate',    agg.failure_rate_percent !== undefined
        ? agg.failure_rate_percent + '%' : '—')
    setValue('agg-cpu-peak',        agg.cpu_peak_percent !== undefined
        ? agg.cpu_peak_percent + '%' : '—')
    setValue('agg-cpu-avg',         agg.cpu_average_percent !== undefined
        ? agg.cpu_average_percent + '%' : '—')
    setValue('agg-mem-peak',        agg.memory_peak_mb !== undefined
        ? agg.memory_peak_mb + ' MB' : '—')
    setValue('agg-mem-avg',         agg.memory_average_mb !== undefined
        ? agg.memory_average_mb + ' MB' : '—')
    setValue('agg-users',           agg.concurrent_users)
}

function setValue(id, value) {
    const el = document.getElementById(id)
    if (el) el.textContent = value !== undefined && value !== null ? value : '—'
}

// ── Endpoint table ─────────────────────────────────────────────────────────
function renderEndpointTable(perEndpoint) {
    const tbody = document.getElementById('endpoint-tbody')
    tbody.innerHTML = ''

    const entries = Object.entries(perEndpoint)
    if (entries.length === 0) {
        const tr = document.createElement('tr')
        tr.innerHTML = '<td colspan="10" style="text-align:center;color:#999;padding:2rem">No endpoint data available</td>'
        tbody.appendChild(tr)
        return
    }

    entries.forEach(([key, ep]) => {
        const m = ep.metrics || {}
        const s = ep.scoring || {}
        const score = s.score !== undefined ? s.score : null
        const grade = s.grade || '—'

        const tr = document.createElement('tr')

        // Score colour class
        let scoreClass = ''
        if (score !== null) {
            if (score >= 75) scoreClass = 'score-high'
            else if (score >= 50) scoreClass = 'score-medium'
            else scoreClass = 'score-low'
        }

        // Failure rate colour
        const failRate = m.failure_rate_percent !== undefined
            ? m.failure_rate_percent : null
        const failClass = failRate !== null && failRate > 5
            ? 'failure-high' : 'failure-ok'

        tr.innerHTML = `
            <td><span class="method-badge method-${ep.method}">${ep.method}</span></td>
            <td style="font-family:monospace;font-size:0.82rem">${ep.sanitised_path || ep.path || '—'}</td>
            <td style="font-size:0.82rem;color:#666">${ep.category_description || ep.category || '—'}</td>
            <td class="score-cell ${scoreClass}">${score !== null ? score : '—'}</td>
            <td><span class="table-grade grade-${grade}">${grade}</span></td>
            <td>${m.avg_response_time_ms !== undefined ? m.avg_response_time_ms : '—'}</td>
            <td>${m.p95_response_time_ms !== undefined ? m.p95_response_time_ms : '—'}</td>
            <td>${m.total_requests !== undefined ? m.total_requests : '—'}</td>
            <td>${m.failed_requests !== undefined ? m.failed_requests : '—'}</td>
            <td class="${failClass}">${failRate !== null ? failRate + '%' : '—'}</td>
        `
        tbody.appendChild(tr)
    })
}

// ── Endpoint detail cards ──────────────────────────────────────────────────
function renderEndpointCards(perEndpoint) {
    const container = document.getElementById('endpoint-cards')
    container.innerHTML = ''

    Object.entries(perEndpoint).forEach(([key, ep]) => {
        const m = ep.metrics || {}
        const s = ep.scoring || {}
        const metricScores = s.metric_scores || {}
        const score = s.score !== undefined ? s.score : null
        const grade = s.grade || '—'

        // Colour based on grade
        const scoreColours = {
            A: '#059669', B: '#3b82f6', C: '#d97706', D: '#ef4444', F: '#9ca3af'
        }
        const colour = scoreColours[grade] || '#9ca3af'

        const card = document.createElement('div')
        card.className = 'endpoint-detail-card'

        // Metric score rows
        const metricScoreRows = Object.entries(metricScores).map(([metric, val]) => {
            const label = formatMetricLabel(metric)
            const colour = val >= 75 ? '#059669' : val >= 50 ? '#d97706' : '#ef4444'
            return `
                <div class="metric-score-row">
                    <span class="metric-score-label">${label}</span>
                    <span class="metric-score-value" style="color:${colour}">${val}/100</span>
                </div>
            `
        }).join('')

        card.innerHTML = `
            <div class="endpoint-detail-header">
                <div>
                    <div>
                        <span class="method-badge method-${ep.method}">${ep.method}</span>
                    </div>
                    <div class="endpoint-detail-path">${ep.path || '—'}</div>
                    <div class="endpoint-detail-category">${ep.category_description || ep.category || ''}</div>
                </div>
                <div class="endpoint-score-display">
                    <span class="endpoint-score-number" style="color:${colour}">
                        ${score !== null ? score : '—'}
                    </span>
                    <span class="endpoint-score-grade grade-pill grade-${grade}">${grade}</span>
                </div>
            </div>

            <div class="endpoint-metrics-row">
                <div class="endpoint-metric-item">
                    <div class="endpoint-metric-label">Avg response</div>
                    <div class="endpoint-metric-value">
                        ${m.avg_response_time_ms !== undefined ? m.avg_response_time_ms + 'ms' : '—'}
                    </div>
                </div>
                <div class="endpoint-metric-item">
                    <div class="endpoint-metric-label">P95 response</div>
                    <div class="endpoint-metric-value">
                        ${m.p95_response_time_ms !== undefined ? m.p95_response_time_ms + 'ms' : '—'}
                    </div>
                </div>
                <div class="endpoint-metric-item">
                    <div class="endpoint-metric-label">Requests</div>
                    <div class="endpoint-metric-value">
                        ${m.total_requests !== undefined ? m.total_requests : '—'}
                    </div>
                </div>
                <div class="endpoint-metric-item">
                    <div class="endpoint-metric-label">Failure rate</div>
                    <div class="endpoint-metric-value" style="color:${
                        m.failure_rate_percent > 5 ? '#ef4444' : '#059669'
                    }">
                        ${m.failure_rate_percent !== undefined ? m.failure_rate_percent + '%' : '—'}
                    </div>
                </div>
            </div>

            ${metricScoreRows ? `
                <div class="metric-scores-section">
                    <p class="block-label">Metric scores</p>
                    ${metricScoreRows}
                </div>
            ` : ''}
        `
        container.appendChild(card)
    })
}

function formatMetricLabel(metric) {
    const labels = {
        'avg_response_time_ms': 'Avg response time',
        'p95_response_time_ms': 'P95 response time',
        'failure_rate_percent': 'Failure rate'
    }
    return labels[metric] || metric
}

// ── AI evaluation ──────────────────────────────────────────────────────────
function renderAiEvaluation(evaluation) {
    // Sub-characteristics
    renderEvalSection('time',     evaluation.time_behaviour)
    renderEvalSection('resource', evaluation.resource_utilisation)
    renderEvalSection('capacity', evaluation.capacity)

    // Endpoint findings from AI
    const endpointFindings = evaluation.endpoint_findings || []
    const epSection = document.getElementById('endpoint-findings-section')

    if (endpointFindings.length > 0) {
        epSection.classList.remove('hidden')
        const list = document.getElementById('endpoint-findings-list')
        list.innerHTML = ''

        endpointFindings.forEach(finding => {
            const score = finding.score !== undefined ? finding.score : null
            const colour = score !== null
                ? (score >= 75 ? '#059669' : score >= 50 ? '#d97706' : '#ef4444')
                : '#9ca3af'

            const card = document.createElement('div')
            card.className = 'endpoint-finding-card'
            card.innerHTML = `
                <div class="finding-score-badge" style="color:${colour}">
                    ${score !== null ? score : '—'}
                </div>
                <div class="finding-content">
                    <div class="finding-endpoint-name">${finding.endpoint || '—'}</div>
                    <div class="finding-issue">${finding.issue || ''}</div>
                    <div class="finding-recommendation">${finding.recommendation || ''}</div>
                </div>
            `
            list.appendChild(card)
        })
    } else {
        epSection.classList.add('hidden')
    }

    // Priority issues
    const priorityIssues = evaluation.priority_issues || []
    const ul = document.getElementById('priority-issues')
    ul.innerHTML = ''
    priorityIssues.forEach(issue => {
        const li = document.createElement('li')
        li.textContent = issue
        ul.appendChild(li)
    })
}

function renderEvalSection(prefix, data) {
    if (!data) return

    const rating = (data.rating || '').toLowerCase()
    const badge = document.getElementById(prefix + '-rating')
    if (badge) {
        badge.textContent = data.rating || '—'
        badge.className = 'rating-badge rating-' + rating
    }

    renderList(prefix + '-findings', data.findings || [], '·')
    renderList(prefix + '-recommendations', data.recommendations || [], '→')
}

function renderList(id, items, prefix) {
    const ul = document.getElementById(id)
    if (!ul) return
    ul.innerHTML = ''
    items.forEach(item => {
        const li = document.createElement('li')
        li.textContent = item
        ul.appendChild(li)
    })
}

// ── Run errors ─────────────────────────────────────────────────────────────
function renderRunErrors(errors) {
    const box = document.getElementById('run-errors-box')
    const list = document.getElementById('run-errors-list')
    list.innerHTML = ''

    const meaningful = errors.filter(e => e && e.trim().length > 0)
    if (meaningful.length === 0) {
        box.classList.add('hidden')
        return
    }

    box.classList.remove('hidden')
    meaningful.forEach(err => {
        const li = document.createElement('li')
        li.textContent = err
        list.appendChild(li)
    })
}

// ── State helpers ──────────────────────────────────────────────────────────
function showLoading(message) {
    hideAll()
    loadingSection.classList.remove('hidden')
    loadingMessage.textContent = message
}

function showError(message) {
    hideAll()
    errorSection.classList.remove('hidden')
    errorMessage.textContent = message
}

function hideAll() {
    loadingSection.classList.add('hidden')
    resultsSection.classList.add('hidden')
    errorSection.classList.add('hidden')
}

// ── Reset ──────────────────────────────────────────────────────────────────
document.getElementById('reset-btn').addEventListener('click', resetForm)
document.getElementById('error-reset-btn').addEventListener('click', resetForm)

function resetForm() {
    hideAll()
    selectedZip = null
    selectedFile.classList.add('hidden')
    evaluateBtn.classList.add('hidden')
    fileInput.value = ''
}
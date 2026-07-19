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
const seedSection     = document.getElementById('seed-section')

// ── Default thresholds ─────────────────────────────────────────────────────
const DEFAULT_THRESHOLDS = {
    simple_read: {
        description: 'Simple data retrieval by ID',
        excellent: 50,
        good: 150,
        fair: 400
    },
    list_read: {
        description: 'Retrieving a list or collection',
        excellent: 100,
        good: 300,
        fair: 800
    },
    search: {
        description: 'Search or filter operation',
        excellent: 200,
        good: 500,
        fair: 1500
    },
    create: {
        description: 'Creating a new resource',
        excellent: 100,
        good: 300,
        fair: 800
    },
    update: {
        description: 'Updating an existing resource',
        excellent: 100,
        good: 300,
        fair: 800
    },
    delete: {
        description: 'Deleting a resource',
        excellent: 50,
        good: 150,
        fair: 400
    },
    file_operation: {
        description: 'File upload, download or image operation',
        excellent: 500,
        good: 1500,
        fair: 5000
    }
}

// Track which categories are present in the current project
let detectedCategories = []


let selectedZip = null
let detectionData = null

function categoriseEndpoint(method, path) {
    const p = path.toLowerCase()
    if (/\/(image|file|upload|download|attachment)/.test(p)) return 'file_operation'
    if (/\/(search|filter|query|find)/.test(p)) return 'search'
    if (method === 'POST') return 'create'
    if (method === 'PUT' || method === 'PATCH') return 'update'
    if (method === 'DELETE') return 'delete'
    if (method === 'GET') {
        return /\/\d+$|\/[a-f0-9-]{36}$/.test(path) ? 'simple_read' : 'list_read'
    }
    return 'simple_read'
}

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

// ── Threshold collapsible ──────────────────────────────────────────────────
document.getElementById('threshold-toggle').addEventListener('click', () => {
    const panel = document.getElementById('threshold-panel')
    const icon = document.getElementById('toggle-icon')
    const isOpen = !panel.classList.contains('hidden')

    if (isOpen) {
        panel.classList.add('hidden')
        icon.classList.remove('open')
    } else {
        panel.classList.remove('hidden')
        icon.classList.add('open')
    }
})

function renderThresholdPanel(endpoints) {
    // Work out which categories this project actually uses
    const categoriesInProject = new Set()
    endpoints.forEach(ep => {
        const cat = categoriseEndpoint(ep.method.toUpperCase(), ep.path)
        categoriesInProject.add(cat)
    })

    detectedCategories = Array.from(categoriesInProject)

    const container = document.getElementById('threshold-categories')
    container.innerHTML = ''

    detectedCategories.forEach(category => {
        const defaults = DEFAULT_THRESHOLDS[category]
        if (!defaults) return

        const block = document.createElement('div')
        block.className = 'threshold-category'
        block.dataset.category = category

        block.innerHTML = `
            <div class="threshold-category-header">
                <span class="method-badge" style="background:#ede9fe;color:#3730a3;font-family:inherit">
                    ${category.replace(/_/g, ' ')}
                </span>
                <span class="threshold-category-desc">${defaults.description}</span>
            </div>
            <div class="threshold-fields">
                <div class="threshold-field">
                    <span class="threshold-band-label band-excellent">Excellent</span>
                    <div class="threshold-input-wrapper">
                        <input
                            type="number"
                            class="threshold-input"
                            id="thresh-${category}-excellent"
                            value="${defaults.excellent}"
                            min="1"
                            data-default="${defaults.excellent}"
                        >
                        <span class="threshold-unit">ms</span>
                    </div>
                    <span style="font-size:0.7rem;color:#aaa">under this = excellent</span>
                </div>
                <div class="threshold-field">
                    <span class="threshold-band-label band-good">Good</span>
                    <div class="threshold-input-wrapper">
                        <input
                            type="number"
                            class="threshold-input"
                            id="thresh-${category}-good"
                            value="${defaults.good}"
                            min="1"
                            data-default="${defaults.good}"
                        >
                        <span class="threshold-unit">ms</span>
                    </div>
                    <span style="font-size:0.7rem;color:#aaa">under this = good</span>
                </div>
                <div class="threshold-field">
                    <span class="threshold-band-label band-fair">Fair</span>
                    <div class="threshold-input-wrapper">
                        <input
                            type="number"
                            class="threshold-input"
                            id="thresh-${category}-fair"
                            value="${defaults.fair}"
                            min="1"
                            data-default="${defaults.fair}"
                        >
                        <span class="threshold-unit">ms</span>
                    </div>
                    <span style="font-size:0.7rem;color:#aaa">under this = fair</span>
                </div>
            </div>
        `
        container.appendChild(block)
    })

    // Mark inputs as modified when changed
    container.querySelectorAll('.threshold-input').forEach(input => {
        input.addEventListener('input', () => {
            const isModified = input.value !== input.dataset.default
            input.classList.toggle('modified', isModified)
            validateThresholdRow(input)
        })
    })
}

function validateThresholdRow(changedInput) {
    // Get category from input id e.g. thresh-simple_read-excellent
    const parts = changedInput.id.split('-')
    const band = parts[parts.length - 1]
    const category = parts.slice(1, parts.length - 1).join('-')

    const excellent = parseInt(document.getElementById(`thresh-${category}-excellent`).value)
    const good = parseInt(document.getElementById(`thresh-${category}-good`).value)
    const fair = parseInt(document.getElementById(`thresh-${category}-fair`).value)

    // Thresholds must be ascending: excellent < good < fair
    const excellentInput = document.getElementById(`thresh-${category}-excellent`)
    const goodInput = document.getElementById(`thresh-${category}-good`)
    const fairInput = document.getElementById(`thresh-${category}-fair`)

    if (excellent >= good || good >= fair) {
        excellentInput.style.borderColor = '#dc2626'
        goodInput.style.borderColor = '#dc2626'
        fairInput.style.borderColor = '#dc2626'
    } else {
        // Restore modified or default border
        ;[excellentInput, goodInput, fairInput].forEach(el => {
            el.style.borderColor = ''
        })
    }
}

function readThresholds() {
    /**
     * Read all threshold inputs and return a dict of custom thresholds.
     * Only includes categories where at least one value was modified.
     * Returns null if nothing was changed (use defaults).
     */
    const customThresholds = {}
    let anyModified = false

    detectedCategories.forEach(category => {
        const excellentEl = document.getElementById(`thresh-${category}-excellent`)
        const goodEl = document.getElementById(`thresh-${category}-good`)
        const fairEl = document.getElementById(`thresh-${category}-fair`)

        if (!excellentEl) return

        const excellent = parseInt(excellentEl.value)
        const good = parseInt(goodEl.value)
        const fair = parseInt(fairEl.value)

        const defaults = DEFAULT_THRESHOLDS[category]
        const isModified = (
            excellent !== defaults.excellent ||
            good !== defaults.good ||
            fair !== defaults.fair
        )

        if (isModified) anyModified = true

        customThresholds[category] = {
            excellent,
            good,
            fair,
            modified: isModified
        }
    })

    return anyModified ? customThresholds : null
}

function thresholdsAreValid() {
    let valid = true
    detectedCategories.forEach(category => {
        const excellent = parseInt(document.getElementById(`thresh-${category}-excellent`)?.value || 0)
        const good = parseInt(document.getElementById(`thresh-${category}-good`)?.value || 0)
        const fair = parseInt(document.getElementById(`thresh-${category}-fair`)?.value || 0)
        if (excellent >= good || good >= fair) valid = false
    })
    return valid
}

// Reset button
document.getElementById('reset-thresholds-btn').addEventListener('click', () => {
    detectedCategories.forEach(category => {
        const defaults = DEFAULT_THRESHOLDS[category]
        ;['excellent', 'good', 'fair'].forEach(band => {
            const input = document.getElementById(`thresh-${category}-${band}`)
            if (input) {
                input.value = defaults[band]
                input.classList.remove('modified')
                input.style.borderColor = ''
            }
        })
    })
})


// ── Evaluation ─────────────────────────────────────────────────────────────
evaluateBtn.addEventListener('click', runDetection)

// After /detect returns
async function runDetection() {
    if (!selectedZip) return

    showLoading('Uploading and detecting project...')

    const formData = new FormData()
    formData.append('file', selectedZip)

    try{
        const response = await fetch('/detect', {
            method: 'POST',
            body: formData
        })
        const data = await response.json()

        if (!response.ok) {
            showError(data.error || 'Detection failed', data.details)
            return 
        }

    detectionData = data
    console.log('Detection data:', detectionData)
    if (data.has_writes) {
        // Show seed config form pre-populated with suggestion
        showSeedForm(data)
    } else {
        // No writes — go straight to evaluation
        await runEvaluation(null)
    }
} catch (err) {
    showError('Could not reach the server. Make sure Flask is running.')
    console.error(err)
}

function showSeedForm(data) {
    hideAll()
    seedSection.classList.remove('hidden')

    const endpointsList = document.getElementById('detected-endpoints-list')
    endpointsList.innerHTML = data.endpoints.map(ep => `
        <span class="detected-endpoint-tag">
            <span class="method-badge method-${ep.method}">${ep.method}</span>
            ${ep.path}
        </span>
    `).join('')

    
const postEndpoints = data.endpoints.filter(ep => ep.method.toUpperCase() === 'POST')
    const deleteEndpoints = data.endpoints.filter(ep => ep.method.toUpperCase() === 'DELETE')

    const createSelect = document.getElementById('seed-create-endpoint')
    createSelect.innerHTML = postEndpoints.map(ep =>
        `<option value="${ep.path}">${ep.method} ${ep.path}</option>`
    ).join('')

    const deleteSelect = document.getElementById('seed-delete-endpoint')
    deleteSelect.innerHTML = [
        '<option value="">None</option>',
        ...deleteEndpoints.map(ep =>
            `<option value="${ep.path}">${ep.method} ${ep.path}</option>`
        )
    ].join('')

const suggestion = data.seed_suggestion
    const noteEl = document.getElementById('seed-suggestion-note')

    if (suggestion) {
        noteEl.className = 'seed-form-note has-suggestion'
        noteEl.textContent = 'We suggested this based on your entity classes. Review and adjust if needed before running.'

        if (suggestion.create_endpoint) {
            createSelect.value = suggestion.create_endpoint
        }
        if (suggestion.create_body) {
            document.getElementById('seed-body').value =
                JSON.stringify(suggestion.create_body, null, 2)
        }
        if (suggestion.id_field) {
            document.getElementById('seed-id-field').value = suggestion.id_field
        }
        if (suggestion.delete_endpoint) {
            deleteSelect.value = suggestion.delete_endpoint
        }
    } else {
        noteEl.className = 'seed-form-note no-suggestion'
        noteEl.textContent = 'We could not auto-suggest seed data for this project. Fill in the fields below or skip to use basic testing.'
    }
const writeCount = data.endpoints.filter(ep =>
        ['POST', 'PUT', 'PATCH', 'DELETE'].includes(ep.method.toUpperCase())
    ).length
    document.getElementById('seed-note').textContent =
        `${writeCount} write endpoint${writeCount !== 1 ? 's' : ''} detected. Provide test data to enable isolated per-user load testing.`


        renderThresholdPanel(data.endpoints)

if (data.create_content_type === 'multipart') {
    document.getElementById('seed-suggestion-note').innerHTML +=
        '<br><strong>Note:</strong> This endpoint accepts multipart/form-data. ' +
        'A fake image will be included automatically for seeding.'
}
}



document.getElementById('run-with-seed-btn').addEventListener('click', async () => {
    const bodyText = document.getElementById('seed-body').value.trim()
    console.log(bodyText)
    const errorEl = document.getElementById('seed-body-error')

    // Validate JSON
    let body
    try {
        body = bodyText ? JSON.parse(bodyText) : {}
        errorEl.classList.add('hidden')
    } catch (e) {
        errorEl.classList.remove('hidden')
        return
    }

    const seedConfig = {
        create_endpoint: document.getElementById('seed-create-endpoint').value,
        create_body: body,
        id_field: document.getElementById('seed-id-field').value || 'id',
        delete_endpoint: document.getElementById('seed-delete-endpoint').value || null
    }

    await runEvaluation(seedConfig)
})

document.getElementById('skip-seed-btn').addEventListener('click', async () => {
    await runEvaluation(null)
})}

async function runEvaluation(seedConfig) {
    // if (!selectedZip) return
    if (!thresholdsAreValid()) {
        alert('Threshold values are invalid. Excellent must be less than Good, which must be less than Fair.')
        return
    }

    const customThresholds = readThresholds()

    showLoading('Building Docker container...')
    const timers = [
        setTimeout(() => { loadingMessage.textContent = 'Starting application...' }, 8000),
        setTimeout(() => { loadingMessage.textContent = 'Running load test...' }, 20000),
        setTimeout(() => { loadingMessage.textContent = 'Collecting metrics...' }, 40000),
        setTimeout(() => { loadingMessage.textContent = 'Evaluating with AI...' }, 55000)
    ]
    // const formData = new FormData()
    // formData.append('file', selectedZip)


    try {
        const response = await fetch('/evaluate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                endpoints: detectionData.endpoints,
                port: detectionData.port,
                filename: selectedZip ? selectedZip.name : 'unknown.zip',
                seed_config: seedConfig,
                custom_thresholds: customThresholds // null if no changes, or dict of modified thresholds
            })
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

        showResults(data, seedConfig, customThresholds)

    } catch (err) {
        timers.forEach(clearTimeout)
        showError('Could not reach the server. Make sure Flask is running.')
        console.error(err)
    }
}


// ── Display results ────────────────────────────────────────────────────────
function showResults(data, seedConfig, customThresholds) {
    hideAll()
    resultsSection.classList.remove('hidden')

    const metrics    = data.metrics || {}
    const aggregate  = metrics.aggregate || {}
    const scores     = data.scores || {}
    const perEndpoint = scores.endpoint_scores || {}
    const evaluation = data.evaluation || {}
    const subChars   = scores.sub_characteristics || {}
    const strategy = data.test_strategy || 'basic'

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

    // Thresholds
    renderStrategyBadge(strategy, customThresholds)
}

function renderStrategyBadge(strategy, customThresholds) {
    const row = document.getElementById('strategy-badge-row')

    const strategyHtml = strategy === 'isolated'
        ? `<span class="strategy-badge strategy-isolated">✓ Isolated testing</span>`
        : `<span class="strategy-badge strategy-basic">⚠ Basic testing</span>`

    const thresholdHtml = customThresholds
        ? `<span class="thresholds-badge">⚙ Custom thresholds applied</span>`
        : ''

    row.innerHTML = strategyHtml + thresholdHtml
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
    seedSection.classList.add('hidden')
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
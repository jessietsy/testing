const fileInput = document.getElementById('file-input')
const uploadBox = document.getElementById('upload-box')
const browseBtn = document.getElementById('browse-btn')
const selectedFile = document.getElementById('selected-file')
const evaluateBtn = document.getElementById('evaluate-btn')
const loading = document.getElementById('loading')
const loadingMessage = document.getElementById('loading-message')
const results = document.getElementById('results')
const errorSection = document.getElementById('error-section')
const errorMessage = document.getElementById('error-message')

let selectedZip = null
let scoreClass = 'good'

// File selection
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
    selectedFile.textContent = `Selected: ${file.name}`
    selectedFile.classList.remove('hidden')
    evaluateBtn.classList.remove('hidden')
}

// Evaluation
evaluateBtn.addEventListener('click', runEvaluation)

async function runEvaluation() {
    if (!selectedZip) return

    showLoading('Uploading project...')

    const formData = new FormData()
    formData.append('file', selectedZip)

    try {
        // Update message while waiting
        setTimeout(() => setLoadingMessage('Building Docker container...'), 3000)
        setTimeout(() => setLoadingMessage('Running project and collecting metrics...'), 8000)
        setTimeout(() => setLoadingMessage('Analysing with Gemini...'), 20000)

        const response = await fetch('/evaluate', {
            method: 'POST',
            body: formData
        })

        const data = await response.json()

        if (!response.ok) {
            showError(data.error || 'Something went wrong', data.details)
            return
        }

        showResults(data)

    } catch (err) {
        showError('Could not reach the server. Make sure Flask is running.')
    }
}

function setLoadingMessage(msg) {
    loadingMessage.textContent = msg
}

// Display results
function showResults(data) {
    hideAll()
    results.classList.remove('hidden')

    const ev = data.evaluation
    const metrics = data.metrics

    // Overall banner
    const banner = document.getElementById('overall-banner')
    const ratingClass = ev.overall_rating.toLowerCase()
    banner.className = `overall-banner banner-${ratingClass}`
    document.getElementById('overall-rating').textContent = `Overall: ${ev.overall_rating}`
    document.getElementById('overall-summary').textContent = ev.summary

    // Metrics
    // document.getElementById('startup-time').textContent =
    //     metrics.startup_time_seconds !== undefined ? `${metrics.startup_time_seconds}s` : '—'
    document.getElementById('peak-cpu').textContent =
        metrics.aggregate.cpu_peak_percent !== undefined ? `${metrics.aggregate.cpu_peak_percent}%` : '—'
    document.getElementById('avg-cpu').textContent =
        metrics.aggregate.cpu_average_percent !== undefined ? `${metrics.aggregate.cpu_average_percent}%` : '—'
    document.getElementById('peak-memory').textContent =
        metrics.aggregate .memory_peak_mb !== undefined ? `${metrics.aggregate.memory_peak_mb} MB` : '—'
    document.getElementById('avg-memory').textContent =
        metrics.aggregate.memory_average_mb !== undefined ? `${metrics.aggregate.memory_average_mb} MB` : '—'
    document.getElementById('total-requests').textContent =
        metrics.aggregate.total_requests !== undefined ? metrics.aggregate.total_requests : '—'
    document.getElementById('failed-requests').textContent =
        metrics.aggregate.failed_requests !== undefined ? metrics.aggregate.failed_requests : '—'


    // Characteristics
    renderCharacteristic('time', ev.time_behaviour)
    renderCharacteristic('resource', ev.resource_utilisation)
    renderCharacteristic('capacity', ev.capacity)

    // Priority issues
    const priorityList = document.getElementById('priority-issues')
    priorityList.innerHTML = ''
    ev.priority_issues.forEach(issue => {
        const li = document.createElement('li')
        li.textContent = issue
        priorityList.appendChild(li)
    })
// Endpoint findings
renderEndpointFindings(ev.endpoint_findings)
}


function renderCharacteristic(prefix, data) {
    const rating = data.rating.toLowerCase()
    const badge = document.getElementById(`${prefix}-rating`)
    badge.textContent = data.rating
    badge.className = `rating-badge badge-${rating}`

    renderList(`${prefix}-findings`, data.findings)
    renderList(`${prefix}-recommendations`, data.recommendations)
}

function renderList(elementId, items) {
    const ul = document.getElementById(elementId)
    ul.innerHTML = ''
    items.forEach(item => {
        const li = document.createElement('li')
        li.textContent = item
        ul.appendChild(li)
    })
}

function renderEndpointFindings(endpoints) {
    const container = document.getElementById('endpoint-findings-list')
    container.innerHTML = ''
let scoreClass = 'good'

if (ep.score < 60) scoreClass = 'poor'
else if (ep.score < 80) scoreClass = 'fair'


    if (!endpoints || endpoints.length === 0) {
        container.innerHTML = '<p>No endpoint findings available.</p>'
        return
    }

    endpoints.forEach(ep => {
        const card = document.createElement('div')
        card.classList.add('endpoint-card')

let scoreClass = 'excellent'

if (ep.score < 50) scoreClass = 'poor'
else if (ep.score < 70) scoreClass = 'fair'
else if (ep.score < 85) scoreClass = 'good'

card.innerHTML = `
    <div class="endpoint-header">
        <h4>${ep.endpoint}</h4>
        <span class="endpoint-score ${scoreClass}">
            ${ep.score}/100
        </span>
    </div>

    <div class="endpoint-section">
        <span class="endpoint-section-label">Finding</span>
        <p>${ep.issue}</p>
    </div>

    <div class="endpoint-section">
        <span class="endpoint-section-label">Recommendation</span>
        <p>${ep.recommendation}</p>
    </div>
`

        container.appendChild(card)
    })
}
// State helpers
function showLoading(message) {
    hideAll()
    loading.classList.remove('hidden')
    loadingMessage.textContent = message
}

function showError(message, details) {
    hideAll()
    errorSection.classList.remove('hidden')
    errorMessage.textContent = details
        ? `${message}: ${Array.isArray(details) ? details.join(', ') : details}`
        : message
}

function hideAll() {
    loading.classList.add('hidden')
    results.classList.add('hidden')
    errorSection.classList.add('hidden')
}

// Reset buttons
document.getElementById('reset-btn').addEventListener('click', resetForm)
document.getElementById('error-reset-btn').addEventListener('click', resetForm)

function resetForm() {
    hideAll()
    selectedZip = null
    selectedFile.classList.add('hidden')
    evaluateBtn.classList.add('hidden')
    fileInput.value = ''
}
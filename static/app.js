document.getElementById('evaluate-btn').addEventListener('click', function() {
const fileInput = document.getElementById('file-input')
const file = fileInput.files[0]

if (!file) {
    document.getElementById('status').textContent = 'Please select a file first'
    return
}

document.getElementById('status').textContent = 'Evaluating...'
document.getElementById('results').innerHTML = ''

const formData = new FormData()
formData.append('file', file)

fetch('/evaluate', {
    method: 'POST',
    body: formData
})
.then(function(response) {
    return response.json()
})
.then(function(data) {
    document.getElementById('status').textContent = ''

    if (data.error) {
        document.getElementById('results').innerHTML = '<p>Error: ' + data.error + '</p>'
        return
    }

    displayResults(data)
})
.catch(function(error) {
    document.getElementById('status').textContent = 'Something went wrong'
    console.log(error)
})


function displayResults(data) {
const metrics = data.metrics
const evaluation = data.evaluation
const resultsDiv = document.getElementById('results')

resultsDiv.innerHTML = `
    <h2>Overall Rating: ${evaluation.overall_rating}</h2>
    <p>${evaluation.summary}</p>

    <h2>Metrics</h2>
    <p>Average response time: ${metrics.avg_response_time_ms} ms</p>
    <p>95th percentile response time: ${metrics.p95_response_time_ms} ms</p>
    <p>Requests per second: ${metrics.requests_per_second}</p>
    <p>Peak CPU: ${metrics.cpu_peak_percent}%</p>
    <p>Average CPU: ${metrics.cpu_average_percent}%</p>
    <p>Peak memory: ${metrics.memory_peak_mb} MB</p>
    <p>Average memory: ${metrics.memory_average_mb} MB</p>
    <p>Total requests: ${metrics.total_requests}</p>
    <p>Failed requests: ${metrics.failed_requests}</p>
    <p>Failure rate: ${metrics.failure_rate_percent}%</p>
    <p>Concurrent users: ${metrics.concurrent_users}</p>

    <h2>Time Behaviour: ${evaluation.time_behaviour.rating}</h2>
    ${renderList('Findings', evaluation.time_behaviour.findings)}
    ${renderList('Recommendations', evaluation.time_behaviour.recommendations)}

    <h2>Resource Utilisation: ${evaluation.resource_utilisation.rating}</h2>
    ${renderList('Findings', evaluation.resource_utilisation.findings)}
    ${renderList('Recommendations', evaluation.resource_utilisation.recommendations)}

    <h2>Capacity: ${evaluation.capacity.rating}</h2>
    ${renderList('Findings', evaluation.capacity.findings)}
    ${renderList('Recommendations', evaluation.capacity.recommendations)}

    <h2>Priority Issues</h2>
    ${renderList('', evaluation.priority_issues)}
`
}

function renderList(title, items) {
const heading = title ? `<h3>${title}</h3>` : ''
const listItems = items.map(function(item) {
    return '<li>' + item + '</li>'
}).join('')
return heading + '<ul>' + listItems + '</ul>'
}


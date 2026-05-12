async function loadResults() {

    const response = await fetch("/evaluate");

    const data = await response.json();

    document.getElementById("score").textContent =
        "Performance Score: " + data.performance_score;

    document.getElementById("response").textContent =
        "Response Time: " + data.response_time + "ms";

    const issuesList = document.getElementById("issues");

    data.issues.forEach(issue => {
        const li = document.createElement("li");
        li.textContent = issue;
        issuesList.appendChild(li);
    });
}

loadResults();

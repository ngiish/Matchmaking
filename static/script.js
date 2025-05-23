document.getElementById('matchForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const data = {
        jobType: document.getElementById('jobType').value,
        location: document.getElementById('location').value
    };
    const response = await fetch('/match', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    });
    const matches = await response.json();
    if (matches.length > 0) {
        document.getElementById('results').innerHTML = '<h2>Top 3 Available Professionals:</h2>' +
            matches.map((m, index) => 
                `<p>${index + 1}. ${m.name} (${m.profession}) - County: ${m.county}, Rating: ${m.rating || 'N/A'}, Availability: ${m.available ? 'Yes' : 'No'}, Score: ${m.match_score}</p>`
            ).join('');
    } else {
        document.getElementById('results').innerHTML = '<h2>No professionals found.</h2>';
    }
});
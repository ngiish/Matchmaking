document.addEventListener('DOMContentLoaded', async () => {
    const jobTypeSelect = document.getElementById('jobType');
    const locationInput = document.getElementById('location');
    const locationSuggestions = document.getElementById('locationSuggestions');
    const searchResults = document.getElementById('searchResults');
    const summaryText = document.getElementById('summaryText');
    const filterForm = document.getElementById('filterForm');

    let currentJobType = "";
    let currentLocation = "";

    // Fetch counties from backend and populate datalist for autocomplete
    try {
        const response = await fetch('/counties');
        if (!response.ok) {
            throw new Error('Failed to fetch counties');
        }
        const counties = await response.json();
        counties.forEach(county => {
            const option = document.createElement('option');
            option.value = county;
            locationSuggestions.appendChild(option);
        });
    } catch (error) {
        console.error('Error fetching counties:', error);
        const option = document.createElement('option');
        option.value = "Nairobi";
        locationSuggestions.appendChild(option);
    }

    jobTypeSelect.addEventListener('change', () => {
        currentJobType = jobTypeSelect.value;
        currentLocation = locationInput.value.trim();
        if (currentJobType && currentLocation) {
            fetchMatches(currentJobType, currentLocation);
        }
    });

    locationInput.addEventListener('input', () => {
        currentLocation = locationInput.value.trim();
        if (currentJobType && currentLocation) {
            fetchMatches(currentJobType, currentLocation);
        }
    });

    filterForm.addEventListener('submit', (e) => {
        e.preventDefault();
        currentJobType = jobTypeSelect.value;
        currentLocation = locationInput.value.trim();
        if (currentJobType && currentLocation) {
            fetchMatches(currentJobType, currentLocation);
        }
    });

    async function fetchMatches(jobType, location) {
        try {
            const response = await fetch('/match', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ jobType, location })
            });
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const matches = await response.json();
            renderMatches(matches, jobType, location);
        } catch (error) {
            searchResults.innerHTML = `<p class="empty-state">Error: ${error.message}</p>`;
            summaryText.textContent = `Failed to fetch matches for "${jobType}" in "${location}".`;
        }
    }

    function renderMatches(matches, jobType, location) {
        searchResults.innerHTML = '';
        if (matches.length === 0) {
            summaryText.textContent = `No professionals found for "${jobType}" in "${location}".`;
            searchResults.innerHTML = `<p class="empty-state">No data available.</p>`;
            return;
        }

        summaryText.textContent = `Showing ${matches.length} professionals for "${jobType}" in "${location}".`;

        const container = document.createElement('div');
        container.className = 'search-item';

        const queryTitle = document.createElement('h3');
        queryTitle.textContent = `Search: "${jobType}" in "${location}"`;
        container.appendChild(queryTitle);

        matches.forEach(pro => {
            const proDiv = document.createElement('div');
            proDiv.style.marginBottom = '12px';
            proDiv.style.padding = '10px';
            proDiv.style.background = '#fff';
            proDiv.style.border = '1px solid #ddd';
            proDiv.style.borderRadius = '6px';

            proDiv.innerHTML = `
                <strong>${pro.name}</strong> — <em>${pro.county}</em><br/>
                Rating: ${pro.rating || 'N/A'} | Availability: ${pro.available ? 'Yes' : 'No'} | Match Score: ${pro.match_score}<br/>
            `;

            const btnGroup = document.createElement('div');
            btnGroup.className = 'btn-group';

            const manualMatchBtn = document.createElement('button');
            manualMatchBtn.textContent = 'Manual Match';
            manualMatchBtn.title = `Manually assign ${pro.name} to this search`;
            manualMatchBtn.onclick = () => alert(`Manual match triggered for ${pro.name} on "${jobType}"`);

            const flagBtn = document.createElement('button');
            flagBtn.textContent = 'Flag for Review';
            flagBtn.className = 'flag';
            flagBtn.title = `Flag this match for review`;
            flagBtn.onclick = () => alert(`Flagged match of ${pro.name} on "${jobType}" for review`);

            btnGroup.appendChild(manualMatchBtn);
            btnGroup.appendChild(flagBtn);
            proDiv.appendChild(btnGroup);

            container.appendChild(proDiv);
        });

        searchResults.appendChild(container);
    }
});
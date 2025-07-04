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
    container.className = 'space-y-4'; // Tailwind for vertical spacing

    const queryTitle = document.createElement('h3');
    queryTitle.className = 'text-lg font-semibold text-gray-800';
    queryTitle.textContent = `Search: "${jobType}" in "${location}"`;
    container.appendChild(queryTitle);

    matches.forEach(pro => {
      const proDiv = document.createElement('div');
      proDiv.className = 'results-card'; // Use the custom Tailwind class

      proDiv.innerHTML = `
        <strong class="text-gray-900">${pro.name}</strong> — <em class="text-gray-600">${pro.county}</em><br/>
        Rating: ${pro.rating || 'N/A'} | Availability: ${pro.available ? 'Yes' : 'No'} | Match Score: ${pro.match_score}<br/>
      `;

      const btnGroup = document.createElement('div');
      btnGroup.className = 'flex space-x-2 mt-2';

      const manualMatchBtn = document.createElement('button');
      manualMatchBtn.className = 'btn btn-outline px-3 py-1 text-sm text-green-600 border border-green-600 rounded-full hover:bg-green-600 hover:text-white transition duration-200';
      manualMatchBtn.textContent = 'Manual Match';
      manualMatchBtn.title = `Manually assign ${pro.name} to this search`;
      manualMatchBtn.onclick = () => alert(`Manual match triggered for ${pro.name} on "${jobType}"`);

      const flagBtn = document.createElement('button');
      flagBtn.className = 'btn btn-outline px-3 py-1 text-sm text-red-600 border border-red-600 rounded-full hover:bg-red-600 hover:text-white transition duration-200';
      flagBtn.textContent = 'Flag for Review';
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
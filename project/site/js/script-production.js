document.addEventListener('DOMContentLoaded', function() {
    // Tab Navigation
    const tabs = document.querySelectorAll('.tab');
    const tabContents = document.querySelectorAll('.tab-content');
    
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            // Remove active class from all tabs and contents
            tabs.forEach(t => t.classList.remove('active'));
            tabContents.forEach(content => content.classList.remove('active'));
            
            // Add active class to clicked tab and corresponding content
            tab.classList.add('active');
            const tabId = tab.getAttribute('data-tab');
            document.getElementById(tabId).classList.add('active');
            
            // Load professors if the name variation tab is clicked
            if (tabId === 'name-variation') {
                loadProfessors();
            }
        });
    });
    
    // Natural Language Search
    const askButton = document.getElementById('ask-button');
    askButton.addEventListener('click', naturalSearch);
    
    // Course Search
    const courseSearchButton = document.getElementById('course-search-button');
    courseSearchButton.addEventListener('click', searchCourses);
    
    // Professor Courses
    const professorButton = document.getElementById('professor-button');
    professorButton.addEventListener('click', findProfessorCourses);
    
    // Filter Courses
    const filterButton = document.getElementById('filter-button');
    filterButton.addEventListener('click', filterCourses);
    
    // Add Name Variation
    const variationButton = document.getElementById('variation-button');
    variationButton.addEventListener('click', addNameVariation);
    
    // Handle Enter key for inputs
    document.getElementById('natural-query').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') naturalSearch();
    });
    
    document.getElementById('course-query').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') searchCourses();
    });
    
    document.getElementById('professor-name').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') findProfessorCourses();
    });
    
    document.getElementById('name-variation-input').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') addNameVariation();
    });
});

// API Functions
async function naturalSearch() {
    const query = document.getElementById('natural-query').value.trim();
    const resultsContainer = document.getElementById('natural-results');
    
    if (!query) {
        resultsContainer.innerHTML = '<div class="error">Please enter a question or query</div>';
        return;
    }
    
    resultsContainer.innerHTML = '<div class="loading">Thinking about your question</div>';
    
    try {
        const response = await fetch('/search/unified', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ query: query })
        });
        
        const data = await response.json();
        
        if (data.query_type === "professor_courses") {
            // Show professor courses with a natural language summary
            displayProfessorQueryResults(data, resultsContainer);
        } else if (data.query_type === "course_search") {
            // Regular course search results
            displayCourseResults(data.data, resultsContainer);
        } else {
            resultsContainer.innerHTML = `<div class="info">${data.message || 'No results found for your query'}</div>`;
        }
    } catch (error) {
        resultsContainer.innerHTML = `<div class="error">Error: ${error.message}</div>`;
    }
}

async function searchCourses() {
    const query = document.getElementById('course-query').value.trim();
    const resultsContainer = document.getElementById('course-results');
    
    if (!query) {
        resultsContainer.innerHTML = '<div class="error">Please enter a search query</div>';
        return;
    }
    
    resultsContainer.innerHTML = '<div class="loading">Searching courses</div>';
    
    try {
        const response = await fetch(`/courses/search?query=${encodeURIComponent(query)}&limit=10`);
        const data = await response.json();
        
        displayCourseResults(data, resultsContainer);
    } catch (error) {
        resultsContainer.innerHTML = `<div class="error">Error: ${error.message}</div>`;
    }
}

async function filterCourses() {
    const year = document.getElementById('filter-year').value;
    const semester = document.getElementById('filter-semester').value;
    const resultsContainer = document.getElementById('filter-results');
    
    if (!year && !semester) {
        resultsContainer.innerHTML = '<div class="error">Please select at least one filter (year or semester)</div>';
        return;
    }
    
    resultsContainer.innerHTML = '<div class="loading">Finding courses</div>';
    
    let url = '/courses/filter';
    let params = [];
    if (year) params.push(`year=${year}`);
    if (semester) params.push(`semester=${semester}`);
    if (params.length > 0) url += '?' + params.join('&');
    
    try {
        const response = await fetch(url);
        const data = await response.json();
        
        displayCourseResults(data, resultsContainer);
    } catch (error) {
        resultsContainer.innerHTML = `<div class="error">Error: ${error.message}</div>`;
    }
}

async function findProfessorCourses() {
    const professorName = document.getElementById('professor-name').value.trim();
    const resultsContainer = document.getElementById('professor-results');
    
    if (!professorName) {
        resultsContainer.innerHTML = '<div class="error">Please enter a professor name</div>';
        return;
    }
    
    resultsContainer.innerHTML = '<div class="loading">Finding courses</div>';
    
    try {
        const response = await fetch(`/professors/${encodeURIComponent(professorName)}/courses`);
        
        if (!response.ok) {
            resultsContainer.innerHTML = '<div class="error">No courses found for this professor</div>';
            return;
        }
        
        const data = await response.json();
        displayProfessorResults(data, resultsContainer);
    } catch (error) {
        resultsContainer.innerHTML = `<div class="error">Error: ${error.message}</div>`;
    }
}

async function loadProfessors() {
    const select = document.getElementById('canonical-name');
    
    // Only load if not already loaded (with real data)
    if (select.options.length === 1 && select.options[0].value === '') {
        select.innerHTML = '<option value="">Loading professors...</option>';
        
        try {
            const response = await fetch('/professors');
            const professors = await response.json();
            select.innerHTML = '<option value="">Select a professor</option>';
            professors.forEach(prof => {
                const option = document.createElement('option');
                option.value = prof.name;
                option.textContent = prof.name;
                select.appendChild(option);
            });
        } catch (error) {
            select.innerHTML = '<option value="">Error loading professors</option>';
        }
    }
}

async function addNameVariation() {
    const canonicalName = document.getElementById('canonical-name').value;
    const variation = document.getElementById('name-variation-input').value.trim();
    const resultsContainer = document.getElementById('variation-result');
    
    if (!canonicalName) {
        resultsContainer.innerHTML = '<div class="error">Please select a professor</div>';
        return;
    }
    
    if (!variation) {
        resultsContainer.innerHTML = '<div class="error">Please enter a name variation</div>';
        return;
    }
    
    resultsContainer.innerHTML = '<div class="loading">Adding name variation</div>';
    
    try {
        const response = await fetch('/professors/add-variation', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ 
                canonical_name: canonicalName, 
                variation: variation 
            })
        });
         
        const data = await response.json();
         
        if (data.success) {
            resultsContainer.innerHTML = `
                <div class="success">
                    Added '${variation}' as a variation of '${canonicalName}'
                </div>
            `;
        } else {
            resultsContainer.innerHTML = `<div class="error">Failed to add name variation: ${data.message}</div>`;
        }
    } catch (error) {
        resultsContainer.innerHTML = `<div class="error">Error: ${error.message}</div>`;
    }
}

// Helper Functions
function displayCourseResults(courses, container) {
    if (!courses || courses.length === 0) {
        container.innerHTML = '<div class="error">No courses found</div>';
        return;
    }
    
    let html = '';
    
    courses.forEach(course => {
        html += `
            <div class="result-item">
                <div class="result-title">${course.title} (${course.course_code})</div>
                <div class="result-details">
                    Year: ${course.year}, Semester: ${course.semester}
                    ${course.ects ? `, ECTS: ${course.ects}` : ''}
                </div>
                <div class="result-content">${course.document}</div>
            </div>
        `;
    });
    
    container.innerHTML = html;
}

function displayProfessorQueryResults(data, container) {
    const professorName = data.data.professor_name;
    const courses = data.data.courses;
    
    let html = `
        <div class="result-summary">
            <h3>Professor Courses</h3>
            <p>${data.natural_response}</p>
        </div>
    `;
    
    courses.forEach(course => {
        html += `
            <div class="result-item">
                <div class="result-title">${course.title} (${course.course_code})</div>
                <div class="result-details">
                    Year: ${course.year}, Semester: ${course.semester}
                    ${course.ects ? `, ECTS: ${course.ects}` : ''}
                </div>
                <div class="result-content">${course.document}</div>
            </div>
        `;
    });
    
    container.innerHTML = html;
}

function displayProfessorResults(professorData, container) {
    let html = `
        <div class="result-summary">
            <h3>Professor: ${professorData.name}</h3>
            <p>Found ${professorData.courses.length} courses taught by this professor</p>
        </div>
    `;
    
    professorData.courses.forEach(course => {
        html += `
            <div class="result-item">
                <div class="result-title">${course.title} (${course.course_code})</div>
                <div class="result-details">
                    Year: ${course.year}, Semester: ${course.semester}
                    ${course.ects ? `, ECTS: ${course.ects}` : ''}
                </div>
                <div class="result-content">${course.document}</div>
            </div>
        `;
    });
    
    container.innerHTML = html;
}
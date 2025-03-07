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
    
    // Course Search
    const searchButton = document.getElementById('search-button');
    searchButton.addEventListener('click', unifiedSearch);
    
    // Filter Courses
    const filterButton = document.getElementById('filter-button');
    filterButton.addEventListener('click', filterCourses);
    
    // Professor Courses
    const professorButton = document.getElementById('professor-button');
    professorButton.addEventListener('click', findProfessorCourses);
    
    // Smart Professor Search
    const smartButton = document.getElementById('smart-button');
    smartButton.addEventListener('click', smartProfessorSearch);
    
    // Add Name Variation
    const variationButton = document.getElementById('variation-button');
    variationButton.addEventListener('click', addNameVariation);
    

    // Handle Enter key for inputs
    document.getElementById('search-query').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') unifiedSearch();
    });
    
    document.getElementById('professor-name').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') findProfessorCourses();
    });
    
    document.getElementById('smart-query').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') smartProfessorSearch();
    });
    
    document.getElementById('name-variation-input').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') addNameVariation();
    });
});

// API Functions

async function searchCourses() {
    const query = document.getElementById('search-query').value.trim();
    const limit = document.getElementById('search-limit').value;
    const resultsContainer = document.getElementById('search-results');
    
    if (!query) {
        resultsContainer.innerHTML = '<div class="error">Please enter a search query</div>';
        return;
    }
    
    resultsContainer.innerHTML = '<div class="loading">Searching courses</div>';
    
    try {
        const response = await fetch(`/courses/search?query=${encodeURIComponent(query)}&limit=${limit}`);
        const data = await response.json();
        
        displayCourseResults(data, resultsContainer);
    } catch (error) {
        resultsContainer.innerHTML = `<div class="error">Error: ${error.message}</div>`;
    }
}

async function filterCourses() {
    const year = document.getElementById('filter-year').value;
    const semester = document.getElementById('filter-semester').value;
    const limit = document.getElementById('filter-limit').value;
    const resultsContainer = document.getElementById('filter-results');
    
    if (!year && !semester) {
        resultsContainer.innerHTML = '<div class="error">Please specify at least one filter (year or semester)</div>';
        return;
    }
    
    resultsContainer.innerHTML = '<div class="loading">Filtering courses</div>';
    
    let url = `/courses/filter?limit=${limit}`;
    if (year) url += `&year=${year}`;
    if (semester) url += `&semester=${semester}`;
    
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

async function smartProfessorSearch() {
    const query = document.getElementById('smart-query').value.trim();
    const extractionContainer = document.getElementById('extraction-result');
    const resultsContainer = document.getElementById('smart-professor-results');
    
    if (!query) {
        extractionContainer.innerHTML = '<div class="error">Please enter a query</div>';
        resultsContainer.innerHTML = '';
        return;
    }
    
    extractionContainer.innerHTML = '<div class="loading">Analyzing query</div>';
    resultsContainer.innerHTML = '';
    
    try {
        // First extract the professor name
        const extractResponse = await fetch('/professors/extract', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ query: query })
        });
        
        const extractData = await extractResponse.json();
        
        if (!extractData.extracted_name) {
            extractionContainer.innerHTML = '<div class="error">No professor name found in the query</div>';
            return;
        }
        
        extractionContainer.innerHTML = `
            <div class="result-item">
                <div class="result-title">Extracted Professor Name</div>
                <div class="result-content">${extractData.extracted_name}</div>
            </div>
        `;
        
        // Then get the professor's courses
        resultsContainer.innerHTML = '<div class="loading">Finding courses</div>';
        
        const professorResponse = await fetch(`/professors/${encodeURIComponent(extractData.extracted_name)}/courses`);
        
        if (!professorResponse.ok) {
            resultsContainer.innerHTML = '<div class="error">No courses found for this professor</div>';
            return;
        }
        
        const professorData = await professorResponse.json();
        displayProfessorResults(professorData, resultsContainer);
    } catch (error) {
        extractionContainer.innerHTML = `<div class="error">Error: ${error.message}</div>`;
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
                 <div class="result-item">
                     <div class="result-title">Name Variation Added</div>
                     <div class="result-content">
                         Added '${variation}' as a variation of '${canonicalName}'
                     </div>
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
    if (courses.length === 0) {
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

async function unifiedSearch() {
    const query = document.getElementById('search-query').value.trim();
    const resultsContainer = document.getElementById('search-results');
    
    if (!query) {
        resultsContainer.innerHTML = '<div class="error">Please enter a search query</div>';
        return;
    }
    
    resultsContainer.innerHTML = '<div class="loading">Processing your query...</div>';
    
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
        <div class="result-item">
            <div class="result-title">Professor: ${professorData.name}</div>
            <div class="result-details">Found ${professorData.courses.length} courses</div>
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
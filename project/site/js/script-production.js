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

// Global session ID variable
let chatSessionId = null;

// Replace the existing natural search with these functions
document.addEventListener('DOMContentLoaded', function() {
    // Add this to your existing event listeners
    const chatSendButton = document.getElementById('chat-send-button');
    const chatInput = document.getElementById('chat-message-input');
    
    chatSendButton.addEventListener('click', sendChatMessage);
    chatInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') sendChatMessage();
    });
    
    // Optional: Add reset conversation button
    const resetChatButton = document.getElementById('reset-chat-button');
    if (resetChatButton) {
        resetChatButton.addEventListener('click', resetChatConversation);
    }
});

async function sendChatMessage() {
    const messageInput = document.getElementById('chat-message-input');
    const message = messageInput.value.trim();
    const chatHistory = document.getElementById('chat-history');
    
    if (!message) {
        return;
    }
    
    // Add user message to chat history
    appendMessage('user', message);
    
    // Clear input
    messageInput.value = '';
    
    // Add temporary thinking message
    const thinkingId = appendMessage('system', 'Thinking...');
    
    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                message: message,
                session_id: chatSessionId
            })
        });
        
        const data = await response.json();
        
        // Remove thinking message
        document.getElementById(thinkingId).remove();
        
        // Store session ID for future messages
        if (data.session_id) {
            chatSessionId = data.session_id;
        }
        
        // Add assistant response to chat history
        appendMessage('assistant', data.message);
        
        // If we have structured data, display it in a rich format
        if (data.data) {
            displayStructuredData(data);
        }
        
    } catch (error) {
        // Remove thinking message
        document.getElementById(thinkingId).remove();
        
        // Show error message
        appendMessage('system', `Error: ${error.message}`);
    }
}

function appendMessage(role, content) {
    const chatHistory = document.getElementById('chat-history');
    const messageId = 'msg-' + Date.now();
    const messageDiv = document.createElement('div');
    
    messageDiv.id = messageId;
    messageDiv.className = role + '-message';
    
    // For assistant messages, convert markdown-like formatting
    if (role === 'assistant') {
        // Simple formatting: bold, italic, code
        content = content
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/`(.*?)`/g, '<code>$1</code>')
            // Handle line breaks
            .replace(/\n/g, '<br>');
        
        messageDiv.innerHTML = content;
    } else {
        messageDiv.textContent = content;
    }
    
    chatHistory.appendChild(messageDiv);
    
    // Scroll to bottom
    chatHistory.scrollTop = chatHistory.scrollHeight;
    
    return messageId;
}

function displayStructuredData(data) {
    const chatHistory = document.getElementById('chat-history');
    const structuredDiv = document.createElement('div');
    structuredDiv.className = 'structured-data';
    
    let html = '<div class="structured-data-content">';
    
    // Process different data structures based on what's available
    if (data.data) {
        // Handle professor courses
        if (data.data.courses && Array.isArray(data.data.courses)) {
            html += '<h4>Courses:</h4>';
            data.data.courses.forEach(course => {
                html += `
                    <div class="structured-item">
                        <div class="item-title">${course.title || 'Unknown'} (${course.course_code || 'No code'})</div>
                        <div class="item-details">
                            ${course.year ? `Year: ${course.year}` : ''}
                            ${course.semester ? `, Semester: ${course.semester}` : ''}
                            ${course.ects ? `, ECTS: ${course.ects}` : ''}
                        </div>
                    </div>
                `;
            });
        }
        // Handle news items
        else if (data.data.news_items && Array.isArray(data.data.news_items)) {
            html += '<h4>Relevant News:</h4>';
            data.data.news_items.forEach(item => {
                html += `
                    <div class="structured-item">
                        <div class="item-title">${item.metadata?.title || "News Item"}</div>
                        <div class="item-date">${item.metadata?.date_published || ""}</div>
                    </div>
                `;
            });
        }
    }
    
    html += '</div>';
    
    // Only append if we have content to show
    if (html.length > 60) { // More than just the wrapper divs
        structuredDiv.innerHTML = html;
        chatHistory.appendChild(structuredDiv);
        chatHistory.scrollTop = chatHistory.scrollHeight;
    }
}

function resetChatConversation() {
    // Reset session ID
    chatSessionId = null;
    
    // Clear chat history
    const chatHistory = document.getElementById('chat-history');
    chatHistory.innerHTML = '';
    
    // Add welcome message
    appendMessage('system', 'Hello! I\'m your university assistant. Ask me anything about courses, professors, or other university information.');
}


function displayUnifiedResults(data, container) {
    // Handle error states
    if (!data || data.query_type === "no_results" || data.query_type === "banned_query" || data.query_type === "unknown") {
        container.innerHTML = `<div class="info">${data.message || 'No results found for your query'}</div>`;
        return;
    }
    
    let html = '';
    
    // Display natural language response if available
    if (data.natural_response) {
        html += `
            <div class="result-summary">
                <p>${data.natural_response}</p>
            </div>
        `;
    }
    
    // Process different data structures based on what's available, not on query_type
    if (data.data) {
        // Handle array of items
        if (Array.isArray(data.data)) {
            data.data.forEach(item => {
                html += renderResultItem(item);
            });
        } 
        // Handle nested data structures
        else if (typeof data.data === 'object') {
            // Handle professor courses
            if (data.data.courses && Array.isArray(data.data.courses)) {
                data.data.courses.forEach(course => {
                    html += renderResultItem(course);
                });
            }
            // Handle news items
            else if (data.data.news_items && Array.isArray(data.data.news_items)) {
                data.data.news_items.forEach(item => {
                    html += renderResultItem(item.content ? {
                        title: item.metadata?.title || "News Item",
                        date: item.metadata?.date_published || "",
                        content: item.content
                    } : item);
                });
            }
            // Fall back to generic object rendering
            else {
                html += renderGenericObject(data.data);
            }
        }
    }
    
    container.innerHTML = html || '<div class="info">No displayable results found</div>';
}

function renderResultItem(item) {
    let html = '<div class="result-item">';
    
    // Detect item type by available properties
    if (item.title && (item.course_code || item.id)) {
        // Course-like item
        html += `
            <div class="result-title">${item.title} ${item.course_code ? `(${item.course_code})` : ''}</div>
            <div class="result-details">
                ${item.year ? `Year: ${item.year}` : ''}
                ${item.semester ? `, Semester: ${item.semester}` : ''}
                ${item.ects ? `, ECTS: ${item.ects}` : ''}
            </div>
        `;
    } else if (item.title || item.date) {
        // News-like item
        html += `
            <div class="result-title">${item.title || "Item"}</div>
            ${item.date ? `<div class="result-details">${item.date}</div>` : ''}
        `;
    }
    
    // Include content for any item type
    if (item.document || item.content) {
        html += `<div class="result-content">${item.document || item.content}</div>`;
    }
    
    html += '</div>';
    return html;
}

function renderGenericObject(obj) {
    // Fallback for any other data structure
    let html = '<div class="result-item">';
    
    for (const [key, value] of Object.entries(obj)) {
        if (typeof value !== 'object' || value === null) {
            html += `<div><strong>${key}:</strong> ${value}</div>`;
        }
    }
    
    html += '</div>';
    return html;
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

function displayNewsResults(data, container) {
    if (!data || data.length === 0) {
        container.innerHTML = '<div class="error">No news found</div>';
        return;
    }
    
    let html = '';
    
    data.forEach(item => {
        html += `
            <div class="result-item">
                <div class="result-title">${item.title}</div>
                <div class="result-details">${item.date}</div>
                <div class="result-content">${item.content}</div>
            </div>
        `;
    });
    
    container.innerHTML = html;
}
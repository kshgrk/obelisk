// Main JavaScript file for Obelisk Chat
// Handles session management and chat functionality

// API Configuration
const API_BASE_URL = '';

// Application State
let currentSessionId = null;
let sessions = [];
let isLoading = false;

document.addEventListener('DOMContentLoaded', function() {
    console.log('Obelisk Chat initialized');
    
    // Load sessions on startup
    loadSessions();
    
    // Set up event handlers
    setupEventHandlers();
});

async function loadSessions() {
    try {
        console.log('Loading sessions...');
        setLoadingState(true);
        
        const response = await fetch(`${API_BASE_URL}/sessions`);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        console.log('Sessions API response:', data);
        
        // Use parser to process sessions data
        sessions = parseSessionsList(data);
        console.log('Parsed sessions:', sessions);
        
        renderSessions(sessions);
        
        // Load the first session by default if available and no session is currently loaded
        if (sessions.length > 0 && !currentSessionId) {
            loadSession(sessions[0].id);
        }
        
        setLoadingState(false);
    } catch (error) {
        console.error('Error loading sessions:', error);
        showError('Failed to load sessions. Please try again.');
        setLoadingState(false);
    }
}

function renderSessions(sessions) {
    const sessionList = document.querySelector('.session-list');
    if (!sessionList) {
        console.error('Session list element not found');
        return;
    }
    
    sessionList.innerHTML = '';
    
    if (sessions.length === 0) {
        sessionList.innerHTML = '<div class="no-sessions p-4 text-gray-400 text-center">No sessions found. Create a new session to get started.</div>';
        return;
    }
    
    sessions.forEach(session => {
        // Use parser function to create session element
        const sessionHTML = createSessionElement(session);
        const sessionElement = document.createElement('div');
        sessionElement.innerHTML = sessionHTML;
        const sessionItem = sessionElement.firstElementChild;
        
        // Add click event listener
        sessionItem.addEventListener('click', () => {
            loadSession(session.id);
            
            // Update active session styling
            document.querySelectorAll('.session-item').forEach(item => {
                item.classList.remove('border-blue-500', 'bg-gray-700');
                item.classList.add('border-transparent');
            });
            sessionItem.classList.remove('border-transparent');
            sessionItem.classList.add('border-blue-500', 'bg-gray-700');
        });
        
        sessionList.appendChild(sessionItem);
    });
}



async function loadSession(sessionId) {
    try {
        console.log('Loading session:', sessionId);
        currentSessionId = sessionId;
        
        // Show loading state
        const chatMessages = document.querySelector('.chat-messages');
        if (chatMessages) {
            chatMessages.innerHTML = '<div class="loading p-4 text-center text-gray-400">Loading conversation...</div>';
        }
        
        const response = await fetch(`${API_BASE_URL}/sessions/${sessionId}`);
        
        if (!response.ok) {
            if (response.status === 404) {
                throw new Error('Session not found');
            }
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const sessionData = await response.json();
        console.log('Session API response:', sessionData);
        
        // Debug the conversation structure
        debugConversationStructure(sessionData);
        
        // Validate and extract conversation data
        if (validateConversationData(sessionData)) {
            // Use dedicated conversation parser
            const messages = extractConversationMessages(sessionData.conversation_history);
            const sessionMetadata = extractSessionMetadata(sessionData);
            
            console.log('Extracted messages:', messages);
            console.log('Session metadata:', sessionMetadata);
            
            // Update session title in header
            updateSessionHeader(sessionMetadata);
            
            // Render conversation history
            renderConversationHistory(messages);
        } else {
            // Fallback to original parser
            const parsedSession = parseSessionDetails(sessionData);
            console.log('Using fallback parser, session details:', parsedSession);
            
            updateSessionHeader(parsedSession);
            renderConversationHistory(parsedSession.messages);
        }
        
    } catch (error) {
        console.error('Error loading session:', error);
        showError(`Failed to load session: ${error.message}`);
        
        // Clear messages on error
        const chatMessages = document.querySelector('.chat-messages');
        if (chatMessages) {
            chatMessages.innerHTML = '<div class="error p-4 text-center text-red-400">Failed to load conversation</div>';
        }
    }
}

function updateSessionHeader(sessionData) {
    const sessionTitle = document.querySelector('.session-title-header');
    if (sessionTitle) {
        const name = sessionData.name || `Session ${sessionData.id.substring(0, 8)}`;
        sessionTitle.textContent = name;
    }
    
    const sessionInfo = document.querySelector('.session-info');
    if (sessionInfo) {
        sessionInfo.innerHTML = `
            <span>${sessionData.messageCount || 0} messages</span>
            <span>•</span>
            <span class="capitalize">${sessionData.status}</span>
            ${sessionData.metadata?.model ? `<span>•</span><span>${sessionData.metadata.model.split('/').pop()}</span>` : ''}
        `;
    }
}

function renderConversationHistory(messages) {
    const chatMessages = document.querySelector('.chat-messages');
    if (!chatMessages) {
        console.error('Chat messages element not found');
        return;
    }
    
    chatMessages.innerHTML = '';
    
    if (!messages || messages.length === 0) {
        chatMessages.innerHTML = '<div class="no-messages p-8 text-center text-gray-400">No messages in this conversation yet. Start by sending a message!</div>';
        return;
    }
    
    // Use parser function to create message elements
    messages.forEach(message => {
        const messageHTML = createMessageElement(message);
        const messageElement = document.createElement('div');
        messageElement.innerHTML = messageHTML;
        chatMessages.appendChild(messageElement.firstElementChild);
    });
    
    // Scroll to bottom
    scrollToBottom();
}

function formatMessageContent(content, messageType = 'assistant') {
    if (!content) return '';
    
    // For assistant messages, use markdown rendering
    if (messageType === 'assistant') {
        // Check if marked is available and configure it properly
        if (typeof marked !== 'undefined') {
            try {
                // Configure marked with better options for chat
                marked.setOptions({
                    breaks: true,        // Convert line breaks to <br>
                    gfm: true,          // GitHub Flavored Markdown
                    headerIds: false,   // Don't add IDs to headers
                    mangle: false,      // Don't mangle email addresses
                    sanitize: false,    // We'll handle sanitization ourselves
                    silent: false       // Don't silently ignore errors
                });
                
                return marked.parse(content);
            } catch (error) {
                console.error('Markdown parsing error:', error);
                // Fallback to escaped text if markdown fails
                const escaped = content.replace(/</g, '&lt;').replace(/>/g, '&gt;');
                return escaped.replace(/\n/g, '<br>');
            }
        } else {
            console.warn('Marked library not loaded, using fallback rendering');
            // Fallback to basic formatting if marked isn't available
            return formatMarkdownFallback(content);
        }
    }
    
    // For user messages, use basic HTML escaping and line breaks
    const escaped = content.replace(/</g, '&lt;').replace(/>/g, '&gt;');
    return escaped.replace(/\n/g, '<br>');
}

// Fallback markdown formatter for basic formatting without marked
function formatMarkdownFallback(content) {
    if (!content) return '';
    
    let formatted = content;
    
    // Escape HTML first
    formatted = formatted.replace(/</g, '&lt;').replace(/>/g, '&gt;');
    
    // Handle headers
    formatted = formatted.replace(/^### (.+)$/gm, '<h3>$1</h3>');
    formatted = formatted.replace(/^## (.+)$/gm, '<h2>$1</h2>');
    formatted = formatted.replace(/^# (.+)$/gm, '<h1>$1</h1>');
    
    // Handle bold text
    formatted = formatted.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    
    // Handle italic text
    formatted = formatted.replace(/\*(.+?)\*/g, '<em>$1</em>');
    
    // Handle code blocks
    formatted = formatted.replace(/```([^`]+)```/g, '<pre><code>$1</code></pre>');
    
    // Handle inline code
    formatted = formatted.replace(/`([^`]+)`/g, '<code>$1</code>');
    
    // Handle lists
    formatted = formatted.replace(/^- (.+)$/gm, '<li>$1</li>');
    formatted = formatted.replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>');
    
    // Handle line breaks
    formatted = formatted.replace(/\n/g, '<br>');
    
    return formatted;
}

function formatTimestamp(timestamp) {
    if (!timestamp) return '';
    
    try {
        const date = new Date(timestamp);
        const now = new Date();
        const diffInHours = (now - date) / (1000 * 60 * 60);
        
        if (diffInHours < 1) {
            const minutes = Math.floor((now - date) / (1000 * 60));
            return `${minutes}m ago`;
        } else if (diffInHours < 24) {
            return `${Math.floor(diffInHours)}h ago`;
        } else if (diffInHours < 48) {
            return 'Yesterday';
        } else {
            return date.toLocaleDateString();
        }
    } catch (error) {
        console.error('Error formatting timestamp:', error);
        return timestamp;
    }
}

function scrollToBottom() {
    const chatMessages = document.querySelector('.chat-messages');
    if (chatMessages) {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
}

function setLoadingState(loading) {
    isLoading = loading;
    const loadingIndicator = document.querySelector('.loading-indicator');
    if (loadingIndicator) {
        loadingIndicator.style.display = loading ? 'block' : 'none';
    }
}

function showError(message) {
    // Create a simple error notification
    const errorDiv = document.createElement('div');
    errorDiv.className = 'error-notification';
    errorDiv.textContent = message;
    errorDiv.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: #f44336;
        color: white;
        padding: 12px 20px;
        border-radius: 4px;
        z-index: 1000;
        box-shadow: 0 2px 8px rgba(0,0,0,0.2);
    `;
    
    document.body.appendChild(errorDiv);
    
    // Remove after 5 seconds
    setTimeout(() => {
        if (errorDiv.parentNode) {
            errorDiv.parentNode.removeChild(errorDiv);
        }
    }, 5000);
}

async function createNewSession() {
    try {
        const response = await fetch(`${API_BASE_URL}/sessions`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                name: `New Session ${new Date().toLocaleTimeString()}`,
                metadata: {}
            })
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const newSession = await response.json();
        console.log('Created new session:', newSession);
        
        // Reload sessions to include the new one
        await loadSessions();
        
        // Load the new session
        loadSession(newSession.id);
        
    } catch (error) {
        console.error('Error creating new session:', error);
        showError('Failed to create new session. Please try again.');
    }
}

function setupEventHandlers() {
    // New session buttons (there might be multiple)
    const newSessionBtns = document.querySelectorAll('.new-session-btn');
    newSessionBtns.forEach(btn => {
        btn.addEventListener('click', createNewSession);
    });
    
    // Refresh sessions button
    const refreshBtn = document.querySelector('.refresh-sessions-btn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', () => loadSessions());
    }
    
    // Search sessions (if implemented)
    const searchInput = document.querySelector('.session-search');
    if (searchInput) {
        searchInput.addEventListener('input', debounce(searchSessions, 300));
    }
}

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

function searchSessions(event) {
    const query = event.target.value.toLowerCase();
    const sessionItems = document.querySelectorAll('.session-item');
    
    sessionItems.forEach(item => {
        const title = item.querySelector('.session-title').textContent.toLowerCase();
        const isVisible = title.includes(query);
        item.style.display = isVisible ? 'block' : 'none';
    });
}

// Export functions for global access
window.loadSessions = loadSessions;
window.loadSession = loadSession;
window.createNewSession = createNewSession; 
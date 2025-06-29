// Main JavaScript file for Obelisk Chat
// Handles session management and chat functionality with direct streaming

// API Configuration
const API_BASE_URL = '';
const BACKEND_API_URL = 'http://localhost:8001'; // Direct backend connection for streaming

// Application State
let currentSessionId = null;
let sessions = [];
let isLoading = false;
// SSE connection removed - now using direct streaming
let currentStreamingMessage = null;

document.addEventListener('DOMContentLoaded', function() {
    console.log('Obelisk Chat initialized');
    console.log('Backend API URL:', BACKEND_API_URL);
    console.log('Frontend API URL:', API_BASE_URL || 'relative paths');
    
    // Load sessions on startup
    loadSessions();
    
    // Set up event handlers
    setupEventHandlers();
    
    // Test backend connectivity
    testBackendConnection();
});

// === Direct Streaming Functions ===
// SSE removed - now using direct streaming from /chat endpoint

// Old SSE event handling removed - now handled directly in streaming response

/**
 * Start a new streaming message
 */
function startStreamingMessage(data) {
    console.log('🚀 Starting streaming message for session:', currentSessionId);
    
    // Create a new assistant message with streaming indicator
    const messageId = `streaming-${Date.now()}`;
    currentStreamingMessage = {
        id: messageId,
        type: 'assistant',
        content: '',
        isStreaming: true,
        timestamp: new Date()
    };
    
    console.log('Created streaming message object:', currentStreamingMessage);
    
    // Add the streaming message to the chat
    addStreamingMessageToChat(currentStreamingMessage);
    
    console.log('Streaming message added to chat UI');
}

/**
 * Update streaming message with new content
 */
function updateStreamingMessage(data) {
    if (!currentStreamingMessage) {
        console.warn('Received streaming content but no active streaming message');
        return;
    }
    
    // Append new content - extract from data.data.content based on backend event structure
    const content = data.data?.content || data.content; // Support both structures
    if (content) {
        console.log(`📝 Streaming content: "${content}" (length: ${content.length})`);
        currentStreamingMessage.content += content;
        
        // Update the message element in real-time
        const messageElement = document.querySelector(`[data-message-id="${currentStreamingMessage.id}"] .message-content`);
        if (messageElement) {
            messageElement.innerHTML = formatMessageContent(currentStreamingMessage.content, 'assistant') + '<span class="streaming-cursor">▊</span>';
        }
        
        // Auto-scroll to bottom
        scrollToBottom();
    }
}

/**
 * Complete streaming message
 */
function completeStreamingMessage(data) {
    if (!currentStreamingMessage) {
        console.warn('Received completion but no active streaming message');
        return;
    }
    
    console.log('Completing streaming message');
    
    // Update with final content if provided - extract from data.data.content based on backend event structure
    const finalContent = data.data?.content || data.content; // Support both structures
    if (finalContent) {
        currentStreamingMessage.content = finalContent;
    }
    
    // Remove streaming cursor and mark as complete
    const messageElement = document.querySelector(`[data-message-id="${currentStreamingMessage.id}"]`);
    if (messageElement) {
        const contentElement = messageElement.querySelector('.message-content');
        if (contentElement) {
            contentElement.innerHTML = formatMessageContent(currentStreamingMessage.content, 'assistant');
        }
        
        // Remove streaming class
        messageElement.classList.remove('streaming');
    }
    
    currentStreamingMessage = null;
    scrollToBottom();
}

/**
 * Handle streaming errors
 */
function handleStreamingError(data) {
    console.error('Streaming error:', data);
    
    if (currentStreamingMessage) {
        const messageElement = document.querySelector(`[data-message-id="${currentStreamingMessage.id}"]`);
        if (messageElement) {
            const contentElement = messageElement.querySelector('.message-content');
            if (contentElement) {
                contentElement.innerHTML = `<div class="error-message">Error: ${data.error || 'Failed to process message'}</div>`;
            }
            messageElement.classList.remove('streaming');
            messageElement.classList.add('error');
        }
        currentStreamingMessage = null;
    }
    
    const errorMessage = data.data?.error || data.error || 'Unknown error'; // Support both structures
    showError(`Chat error: ${errorMessage}`);
}

/**
 * Add a streaming message to the chat interface
 */
function addStreamingMessageToChat(message) {
    console.log('Adding streaming message to chat:', message.id);
    
    const chatMessages = document.querySelector('.chat-messages');
    if (!chatMessages) {
        console.error('❌ Chat messages container not found');
        return;
    }
    
    // Hide no-messages placeholder if it exists
    const noMessages = chatMessages.querySelector('.no-messages');
    if (noMessages) {
        console.log('Hiding no-messages placeholder');
        noMessages.style.display = 'none';
    }
    
    // Hide welcome message if it exists  
    const welcomeMessage = document.querySelector('.welcome-message');
    if (welcomeMessage) {
        console.log('Hiding welcome message');
        welcomeMessage.style.display = 'none';
    }
    
    const messageHTML = `
        <div class="message assistant-message streaming" data-message-id="${message.id}">
            <div class="message-content">${formatMessageContent(message.content, 'assistant')}<span class="streaming-cursor">▊</span></div>
            <div class="message-time">${formatTime(message.timestamp)}</div>
        </div>
    `;
    
    console.log('Inserting message HTML into chat');
    chatMessages.insertAdjacentHTML('beforeend', messageHTML);
    
    // Verify the message was added
    const addedMessage = document.querySelector(`[data-message-id="${message.id}"]`);
    if (addedMessage) {
        console.log('✅ Streaming message successfully added to DOM');
    } else {
        console.error('❌ Failed to add streaming message to DOM');
    }
    
    scrollToBottom();
}

/**
 * Send a message with direct streaming support
 */
async function sendMessage(messageText) {
    if (!currentSessionId || !messageText.trim()) {
        return;
    }

    try {
        console.log('Sending message:', messageText);
        
        // Add user message to chat immediately
        addMessageToChat('user', messageText.trim());
        
        // Clear input field
        const chatInput = document.querySelector('#chat-input');
        if (chatInput) {
            chatInput.value = '';
        }
        
        // Send message to backend with streaming enabled
        const response = await fetch(`${BACKEND_API_URL}/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                session_id: currentSessionId,
                message: messageText.trim(),
                stream: true
            })
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        // Check if it's a streaming response
        const contentType = response.headers.get('content-type');
        if (contentType && contentType.includes('text/event-stream')) {
            console.log('📡 Received streaming response, processing events...');
            await handleStreamingResponse(response);
        } else {
            // Non-streaming response
            const data = await response.json();
            console.log('Chat response:', data);
            if (data.response) {
                addMessageToChat('assistant', data.response);
            }
        }
        
    } catch (error) {
        console.error('Error sending message:', error);
        showError(`Failed to send message: ${error.message}`);
    }
}

/**
 * Handle streaming response from chat endpoint
 */
async function handleStreamingResponse(response) {
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let currentStreamingMessage = null;
    
    try {
        while (true) {
            const { done, value } = await reader.read();
            
            if (done) {
                console.log('📊 Streaming completed');
                break;
            }
            
            // Decode chunk and add to buffer
            buffer += decoder.decode(value, { stream: true });
            
            // Process complete lines
            const lines = buffer.split('\n');
            buffer = lines.pop() || ''; // Keep incomplete line in buffer
            
            for (const line of lines) {
                if (line.trim()) {
                    try {
                        // Handle SSE format: lines start with "data: " followed by JSON
                        let eventData;
                        if (line.startsWith('data: ')) {
                            // Extract JSON from SSE data line
                            const jsonStr = line.substring(6); // Remove "data: " prefix
                            eventData = JSON.parse(jsonStr);
                        } else if (line.startsWith('{')) {
                            // Direct JSON (fallback for other formats)
                            eventData = JSON.parse(line);
                        } else {
                            // Skip non-data lines (like keep-alive comments)
                            continue;
                        }
                        
                        console.log('📩 Stream event:', eventData.event, eventData.content);
                        
                        switch (eventData.event) {
                            case 'RunStarted':
                                console.log('🚀 Chat run started');
                                // Create new streaming message
                                currentStreamingMessage = {
                                    id: `stream-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
                                    content: '',
                                    timestamp: new Date()
                                };
                                addStreamingMessageToChat(currentStreamingMessage);
                                break;
                                
                            case 'RunResponse':
                                // Add character to streaming message
                                if (currentStreamingMessage) {
                                    currentStreamingMessage.content += eventData.content;
                                    updateStreamingMessageContent(currentStreamingMessage);
                                }
                                break;
                                
                            case 'RunCompleted':
                                console.log('✅ Chat run completed');
                                if (currentStreamingMessage) {
                                    // Finalize message with complete content
                                    currentStreamingMessage.content = eventData.content;
                                    completeStreamingMessageFinal(currentStreamingMessage);
                                    currentStreamingMessage = null;
                                }
                                
                                // Remove auto-refresh to prevent duplicate user messages
                                // Since we're already handling real-time updates, refresh is not needed
                                break;
                                
                            case 'RunError':
                                console.error('❌ Chat run error:', eventData.error);
                                if (currentStreamingMessage) {
                                    showStreamingError(currentStreamingMessage, eventData.error);
                                    currentStreamingMessage = null;
                                }
                                break;
                        }
                        
                    } catch (parseError) {
                        console.warn('⚠️ Failed to parse event:', line, parseError);
                    }
                }
            }
        }
    } catch (error) {
        console.error('❌ Streaming error:', error);
        showError(`Streaming failed: ${error.message}`);
    }
}

/**
 * Update streaming message content in real-time
 */
function updateStreamingMessageContent(message) {
    const messageElement = document.querySelector(`[data-message-id="${message.id}"] .message-content`);
    if (messageElement) {
        messageElement.innerHTML = formatMessageContent(message.content, 'assistant') + '<span class="streaming-cursor">▊</span>';
        scrollToBottom();
    }
}

/**
 * Complete streaming message (remove cursor, mark as final)
 */
function completeStreamingMessageFinal(message) {
    const messageElement = document.querySelector(`[data-message-id="${message.id}"]`);
    if (messageElement) {
        const contentElement = messageElement.querySelector('.message-content');
        if (contentElement) {
            contentElement.innerHTML = formatMessageContent(message.content, 'assistant');
        }
        messageElement.classList.remove('streaming');
    }
    scrollToBottom();
}

/**
 * Show streaming error
 */
function showStreamingError(message, error) {
    const messageElement = document.querySelector(`[data-message-id="${message.id}"]`);
    if (messageElement) {
        const contentElement = messageElement.querySelector('.message-content');
        if (contentElement) {
            contentElement.innerHTML = `<div class="error-message">Error: ${error}</div>`;
        }
        messageElement.classList.remove('streaming');
        messageElement.classList.add('error');
    }
}

/**
 * Add a streaming message to chat with blinking cursor
 */
function addStreamingMessageToChat(message) {
    const chatMessages = document.querySelector('.chat-messages');
    if (!chatMessages) return;

    const messageElement = document.createElement('div');
    messageElement.className = 'message assistant streaming';
    messageElement.setAttribute('data-message-id', message.id);
    
    messageElement.innerHTML = `
        <div class="message-avatar">
            <div class="assistant-avatar">AI</div>
        </div>
        <div class="message-content-wrapper">
            <div class="message-content">${message.content}<span class="streaming-cursor">▊</span></div>
            <div class="message-timestamp">${formatTimestamp(message.timestamp)}</div>
        </div>
    `;
    
    chatMessages.appendChild(messageElement);
    scrollToBottom();
}

/**
 * Add a regular message to chat (for user messages or fallback)
 */
function addMessageToChat(messageType, content, timestamp = new Date()) {
    const chatMessages = document.querySelector('.chat-messages');
    if (!chatMessages) return;
    
    // Hide no-messages placeholder if it exists
    const noMessages = chatMessages.querySelector('.no-messages');
    if (noMessages) {
        noMessages.style.display = 'none';
    }
    
    const message = {
        id: `msg-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
        type: messageType,
        content: content,
        timestamp: timestamp
    };
    
    const messageHTML = createMessageElement(message);
    const messageElement = document.createElement('div');
    messageElement.innerHTML = messageHTML;
    
    chatMessages.appendChild(messageElement.firstElementChild);
    scrollToBottom();
}

// === Session Management Functions ===

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
        
        // Disconnect any existing SSE connection
        // SSE disconnection removed
        
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
        
        // SSE connection no longer needed - using direct streaming from chat endpoint
        
        // Enable chat input after successful load
        if (typeof window.enableChatInput === 'function') {
            window.enableChatInput();
        }
        
        // Hide welcome message
        const welcomeMessage = document.querySelector('.welcome-message');
        if (welcomeMessage) {
            welcomeMessage.style.display = 'none';
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
        const response = await fetch(`${API_BASE_URL}/api/sessions`, {
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
window.sendMessage = sendMessage;
window.addMessageToChat = addMessageToChat;

// === Missing utility functions for conversation parsing ===

/**
 * Debug conversation structure for development
 */
function debugConversationStructure(sessionData) {
    console.log('Session data structure:', {
        hasConversationHistory: !!sessionData.conversation_history,
        conversationKeys: sessionData.conversation_history ? Object.keys(sessionData.conversation_history) : [],
        turnsLength: sessionData.conversation_history?.conversation_turns?.length || 0,
        firstTurn: sessionData.conversation_history?.conversation_turns?.[0] || null
    });
}

/**
 * Validate conversation data structure
 */
function validateConversationData(sessionData) {
    return sessionData.conversation_history && 
           sessionData.conversation_history.conversation_turns && 
           Array.isArray(sessionData.conversation_history.conversation_turns);
}

/**
 * Extract conversation messages from validated session data
 */
function extractConversationMessages(conversationHistory) {
    if (!conversationHistory || !conversationHistory.conversation_turns) {
        return [];
    }
    
    return parseConversationTurns(conversationHistory.conversation_turns);
}

/**
 * Extract session metadata
 */
function extractSessionMetadata(sessionData) {
    return {
        id: sessionData.session_id || sessionData.id,
        name: sessionData.name || `Session ${sessionData.session_id?.substring(0, 8) || 'Unknown'}`,
        status: sessionData.status || 'unknown',
        messageCount: sessionData.message_count || 0,
        metadata: sessionData.metadata || {}
    };
}

/**
 * Cleanup function when page unloads
 */
window.addEventListener('beforeunload', function() {
    // SSE cleanup removed - using direct streaming
});

// === Backend Connection Test ===
async function testBackendConnection() {
    try {
        console.log('Testing backend connection...');
        const response = await fetch(`${BACKEND_API_URL}/health`);
        if (response.ok) {
            const data = await response.json();
            console.log('✅ Backend connection successful:', data);
        } else {
            console.warn('⚠️ Backend health check failed:', response.status);
        }
    } catch (error) {
        console.error('❌ Backend connection failed:', error);
        showError('Backend connection failed. Some features may not work.');
    }
} 
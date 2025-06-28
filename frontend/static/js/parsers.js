/**
 * Parser functions for API responses
 */

/**
 * Parse sessions list API response
 * @param {Object} data - API response from /sessions
 * @returns {Array} Parsed sessions for UI display
 */
function parseSessionsList(data) {
    if (!data || !data.sessions || !Array.isArray(data.sessions)) {
        return [];
    }

    return data.sessions.map(session => ({
        id: session.id,
        name: session.name,
        status: session.status,
        createdAt: new Date(session.created_at),
        updatedAt: new Date(session.updated_at),
        messageCount: session.message_count,
        model: session.metadata?.model || 'Unknown',
        totalTokens: (session.metadata?.statistics?.total_tokens_input || 0) + 
                    (session.metadata?.statistics?.total_tokens_output || 0),
        // Format display date
        displayDate: formatDate(new Date(session.updated_at)),
        displayTime: formatTime(new Date(session.updated_at))
    }));
}

/**
 * Parse individual session API response
 * @param {Object} data - API response from /sessions/{id}
 * @returns {Object} Parsed session data with conversation history
 */
function parseSessionDetails(data) {
    if (!data) {
        return null;
    }

    const session = {
        id: data.session_id,
        name: data.name,
        status: data.status,
        createdAt: new Date(data.created_at),
        updatedAt: new Date(data.updated_at),
        messageCount: data.message_count,
        metadata: data.metadata,
        messages: []
    };

    // Parse conversation history
    if (data.conversation_history && data.conversation_history.conversation_turns) {
        session.messages = parseConversationTurns(data.conversation_history.conversation_turns);
    }

    return session;
}

/**
 * Parse conversation turns into a flat array of messages
 * @param {Array} turns - Array of conversation turns
 * @returns {Array} Flat array of messages in chronological order
 */
function parseConversationTurns(turns) {
    const messages = [];

    turns.forEach(turn => {
        // Add user message
        if (turn.user_message) {
            messages.push({
                id: turn.user_message.message_id,
                type: 'user',
                content: turn.user_message.content,
                timestamp: new Date(turn.user_message.timestamp),
                turnId: turn.turn_id,
                turnNumber: turn.turn_number,
                metadata: turn.user_message.metadata
            });
        }

        // Add assistant responses
        if (turn.assistant_responses && Array.isArray(turn.assistant_responses)) {
            turn.assistant_responses.forEach(response => {
                messages.push({
                    id: response.message_id,
                    type: 'assistant',
                    content: response.final_content || response.content,
                    timestamp: new Date(response.timestamp),
                    turnId: turn.turn_id,
                    turnNumber: turn.turn_number,
                    responseId: response.response_id,
                    isActive: response.is_active,
                    toolCalls: response.tool_calls || [],
                    mcpCalls: response.mcp_calls || [],
                    metadata: response.metadata
                });
            });
        }
    });

    // Sort messages by timestamp to ensure proper order
    return messages.sort((a, b) => a.timestamp - b.timestamp);
}

/**
 * Format date for display in sidebar
 * @param {Date} date 
 * @returns {string} Formatted date string
 */
function formatDate(date) {
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);
    
    const inputDate = new Date(date.getFullYear(), date.getMonth(), date.getDate());
    
    if (inputDate.getTime() === today.getTime()) {
        return 'Today';
    } else if (inputDate.getTime() === yesterday.getTime()) {
        return 'Yesterday';
    } else if (now - date < 7 * 24 * 60 * 60 * 1000) {
        return date.toLocaleDateString('en-US', { weekday: 'long' });
    } else {
        return date.toLocaleDateString('en-US', { 
            month: 'short', 
            day: 'numeric',
            year: date.getFullYear() !== now.getFullYear() ? 'numeric' : undefined
        });
    }
}

/**
 * Format time for display
 * @param {Date} date 
 * @returns {string} Formatted time string
 */
function formatTime(date) {
    return date.toLocaleTimeString('en-US', { 
        hour: 'numeric', 
        minute: '2-digit',
        hour12: true 
    });
}

/**
 * Create session display element
 * @param {Object} session - Parsed session object
 * @returns {string} HTML string for session item
 */
function createSessionElement(session) {
    const isActive = session.status === 'active';
    const statusClass = isActive ? 'text-green-400' : 'text-gray-500';
    
    return `
        <div class="session-item p-3 rounded-lg cursor-pointer hover:bg-gray-700 transition-colors border-l-2 border-transparent hover:border-blue-500" 
             data-session-id="${session.id}">
            <div class="flex justify-between items-start mb-1">
                <h3 class="font-medium text-white text-sm truncate flex-1">${escapeHtml(session.name)}</h3>
                <span class="text-xs ${statusClass} ml-2">●</span>
            </div>
            <div class="flex justify-between items-center text-xs text-gray-400">
                <span>${session.displayDate}</span>
                <span>${session.displayTime}</span>
            </div>
            <div class="flex justify-between items-center text-xs text-gray-500 mt-1">
                <span>${session.messageCount} messages</span>
                <span class="truncate ml-2 max-w-20" title="${session.model}">${session.model.split('/').pop()}</span>
            </div>
        </div>
    `;
}

/**
 * Create message element for chat display
 * @param {Object} message - Parsed message object
 * @returns {string} HTML string for message
 */
function createMessageElement(message) {
    // Render user messages with bubble
    if (message.type === 'user') {
        return `
            <div class="message user-message">
                <div class="message-content">${formatMessageContent(message.content, 'user')}</div>
                <div class="message-time">${formatTime(message.timestamp)}</div>
            </div>
        `;
    }

    // Render assistant messages without bubble
    return `
        <div class="message assistant-message">
            <div class="message-content">${formatMessageContent(message.content, 'assistant')}</div>
            <div class="message-time">${formatTime(message.timestamp)}</div>
        </div>
    `;
}



/**
 * Escape HTML characters
 * @param {string} text 
 * @returns {string} Escaped text
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
} 
/**
 * Dedicated conversation parser for extracting chat data
 * Handles the conversation_turns structure from the backend API
 */

/**
 * Extract conversation messages from the conversation_turns structure
 * @param {Object} conversationData - The conversation data from API
 * @returns {Array} Array of messages formatted for display
 */
function extractConversationMessages(conversationData) {
    console.log('Extracting conversation messages:', conversationData);
    
    if (!conversationData || !conversationData.conversation_turns) {
        console.log('No conversation turns found');
        return [];
    }

    const messages = [];
    const turns = conversationData.conversation_turns;

    turns.forEach(turn => {
        console.log('Processing turn:', turn.turn_id, turn.turn_number);
        
        // Add user message
        if (turn.user_message) {
            const userMessage = {
                id: turn.user_message.message_id,
                type: 'user',
                content: turn.user_message.content,
                timestamp: new Date(turn.user_message.timestamp),
                turnId: turn.turn_id,
                turnNumber: turn.turn_number,
                metadata: turn.user_message.metadata || {}
            };
            messages.push(userMessage);
            console.log('Added user message:', userMessage.content.substring(0, 50) + '...');
        }

        // Add assistant responses
        if (turn.assistant_responses && Array.isArray(turn.assistant_responses)) {
            turn.assistant_responses.forEach(response => {
                const assistantMessage = {
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
                    metadata: response.metadata || {}
                };
                messages.push(assistantMessage);
                console.log('Added assistant message:', assistantMessage.content.substring(0, 50) + '...');
            });
        }
    });

    // Sort messages by timestamp to ensure proper chronological order
    const sortedMessages = messages.sort((a, b) => a.timestamp - b.timestamp);
    console.log(`Extracted ${sortedMessages.length} messages total`);
    
    return sortedMessages;
}

/**
 * Validate conversation data structure
 * @param {Object} data - Raw conversation data from API
 * @returns {boolean} True if valid structure
 */
function validateConversationData(data) {
    if (!data) {
        console.warn('No conversation data provided');
        return false;
    }

    if (!data.conversation_history) {
        console.warn('No conversation_history in data');
        return false;
    }

    if (!data.conversation_history.conversation_turns) {
        console.warn('No conversation_turns in conversation_history');
        return false;
    }

    if (!Array.isArray(data.conversation_history.conversation_turns)) {
        console.warn('conversation_turns is not an array');
        return false;
    }

    return true;
}

/**
 * Extract session metadata for display
 * @param {Object} sessionData - Session data from API
 * @returns {Object} Formatted session metadata
 */
function extractSessionMetadata(sessionData) {
    return {
        id: sessionData.session_id,
        name: sessionData.name,
        status: sessionData.status,
        messageCount: sessionData.message_count,
        createdAt: new Date(sessionData.created_at),
        updatedAt: new Date(sessionData.updated_at),
        metadata: sessionData.metadata || {}
    };
}

/**
 * Debug function to log conversation structure
 * @param {Object} data - Raw API response
 */
function debugConversationStructure(data) {
    console.group('🔍 Conversation Structure Debug');
    console.log('Raw data keys:', Object.keys(data || {}));
    
    if (data?.conversation_history) {
        console.log('Conversation history keys:', Object.keys(data.conversation_history));
        
        if (data.conversation_history.conversation_turns) {
            console.log('Number of turns:', data.conversation_history.conversation_turns.length);
            
            data.conversation_history.conversation_turns.forEach((turn, index) => {
                console.log(`Turn ${index + 1}:`, {
                    turnId: turn.turn_id,
                    turnNumber: turn.turn_number,
                    hasUserMessage: !!turn.user_message,
                    assistantResponseCount: turn.assistant_responses?.length || 0
                });
            });
        }
    }
    console.groupEnd();
}

// Export for testing and debugging
window.conversationParser = {
    extractConversationMessages,
    validateConversationData,
    extractSessionMetadata,
    debugConversationStructure
}; 
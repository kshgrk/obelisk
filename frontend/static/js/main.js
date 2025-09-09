// Obelisk Chat Platform - Main Application Controller
// Handles session management, chat functionality, and real-time streaming

// Configuration
const API_CONFIG = {
    BASE_URL: 'http://localhost:8080',
    BACKEND_URL: 'http://localhost:8080',
    ENDPOINTS: {
        SESSIONS: '/api/sessions',
        CHAT: '/api/chat',
        EVENTS: '/api/events'
    }
};

// Application State
class AppState {
    constructor() {
        this.currentSessionId = null;
        this.sessions = [];
        this.isLoading = false;
        this.currentStreamingMessage = null;
        this.pagination = {
            page: 1,
            pageSize: 50,
            total: 0
        };
        this.aiConfig = {
            model: "deepseek/deepseek-chat-v3-0324:free",
            temperature: 1.0,
            max_tokens: 5000,
            streaming: true,
            show_tool_calls: true
        };
    }

    setCurrentSession(sessionId) {
        this.currentSessionId = sessionId;
        this.saveState();
    }

    setSessions(sessions, pagination = {}) {
        this.sessions = sessions;
        this.pagination = { ...this.pagination, ...pagination };
        this.saveState();
    }

    saveState() {
        try {
            localStorage.setItem('obelisk_state', JSON.stringify({
                version: '1.1', // Added version for config migration
                currentSessionId: this.currentSessionId,
                pagination: this.pagination,
                aiConfig: this.aiConfig
            }));
        } catch (error) {
            console.warn('Failed to save application state:', error);
        }
    }

    loadState() {
        try {
            const saved = localStorage.getItem('obelisk_state');
            if (saved) {
                const state = JSON.parse(saved);
                
                // Check version for config migration
                if (!state.version || state.version !== '1.1') {
                    console.log('Migrating config to new defaults (temperature 1.0, max_tokens 5000)');
                    // Reset to new defaults for config migration
                    this.aiConfig = {
                        model: "deepseek/deepseek-chat-v3-0324:free",
                        temperature: 1.0,
                        max_tokens: 5000,
                        streaming: true,
                        show_tool_calls: true
                    };
                } else {
                    // Load saved config only if version matches
                    if (state.aiConfig) {
                        this.aiConfig = { ...this.aiConfig, ...state.aiConfig };
                    }
                }
                
                // Always load session and pagination state
                this.currentSessionId = state.currentSessionId;
                this.pagination = { ...this.pagination, ...state.pagination };
            }
        } catch (error) {
            console.warn('Failed to load application state:', error);
        }
    }

    updateAiConfig(newConfig) {
        this.aiConfig = { ...this.aiConfig, ...newConfig };
        this.saveState();
    }

    getConfigOverride() {
        // Only return config if it differs from defaults
        const defaults = {
            model: "deepseek/deepseek-chat-v3-0324:free",
            temperature: 1.0,
            max_tokens: 5000
        };

        const override = {};
        if (this.aiConfig.model !== defaults.model) {
            override.model = this.aiConfig.model;
        }
        if (this.aiConfig.temperature !== defaults.temperature) {
            override.temperature = this.aiConfig.temperature;
        }
        if (this.aiConfig.max_tokens !== defaults.max_tokens) {
            override.max_tokens = this.aiConfig.max_tokens;
        }

        return Object.keys(override).length > 0 ? override : null;
    }
}

const appState = new AppState();

// Config Management
class ConfigManager {
    constructor() {
        this.modelOptions = [];
        this.allModels = [];
        this.filteredModels = [];
        this.initializeModal();
        this.loadModels();
    }

    initializeModal() {
        // Modal elements
        this.modal = document.getElementById('configModal');
        this.modelSelect = document.getElementById('modelSelect');
        this.temperatureSlider = document.getElementById('temperatureSlider');
        this.maxTokensInput = document.getElementById('maxTokensInput');

        // Model controls
        this.refreshModelsBtn = document.getElementById('refreshModelsBtn');
        this.modelSearch = document.getElementById('modelSearch');
        this.toolsOnlyFilter = document.getElementById('toolsOnlyFilter');

        // Value display elements
        this.temperatureValue = document.getElementById('temperatureValue');

        // Preview elements
        this.previewModel = document.getElementById('previewModel');
        this.previewTemperature = document.getElementById('previewTemperature');
        this.previewMaxTokens = document.getElementById('previewMaxTokens');

        // Bind events
        this.bindEvents();
        
        // Initialize values
        this.loadCurrentConfig();
    }

    bindEvents() {
        // Modal controls
        document.getElementById('configBtn').addEventListener('click', () => this.openModal());
        document.getElementById('closeConfigModal').addEventListener('click', () => this.closeModal());
        document.getElementById('cancelConfigBtn').addEventListener('click', () => this.closeModal());
        document.getElementById('saveConfigBtn').addEventListener('click', () => this.saveConfig());
        document.getElementById('resetConfigBtn').addEventListener('click', () => this.resetToDefaults());

        // Model controls
        this.refreshModelsBtn.addEventListener('click', () => this.refreshModels());
        this.modelSearch.addEventListener('input', () => this.filterModels());
        this.toolsOnlyFilter.addEventListener('change', () => this.filterModels());

        // Close modal on overlay click
        this.modal.addEventListener('click', (e) => {
            if (e.target === this.modal) {
                this.closeModal();
            }
        });

        // Input event listeners
        this.modelSelect.addEventListener('change', () => this.updatePreview());
        this.temperatureSlider.addEventListener('input', () => this.updateSliderValues());
        this.maxTokensInput.addEventListener('input', () => this.updatePreview());
    }

    openModal() {
        this.loadCurrentConfig();
        this.modal.style.display = 'flex';
        document.body.style.overflow = 'hidden';
    }

    closeModal() {
        this.modal.style.display = 'none';
        document.body.style.overflow = 'auto';
        this.loadCurrentConfig(); // Reset to current values
    }

    loadCurrentConfig() {
        const config = appState.aiConfig;
        
        // Set form values
        this.modelSelect.value = config.model;
        this.temperatureSlider.value = config.temperature;
        this.maxTokensInput.value = config.max_tokens;
        
        // Update displays
        this.updateSliderValues();
        this.updatePreview();
    }

    updateSliderValues() {
        this.temperatureValue.textContent = this.temperatureSlider.value;
        this.updatePreview();
    }

    updatePreview() {
        const selectedModel = this.modelOptions.find(opt => opt.value === this.modelSelect.value);
        this.previewModel.textContent = selectedModel ? selectedModel.label : this.modelSelect.value;
        this.previewTemperature.textContent = this.temperatureSlider.value;
        this.previewMaxTokens.textContent = this.maxTokensInput.value;
    }

    saveConfig() {
        const newConfig = {
            model: this.modelSelect.value,
            temperature: parseFloat(this.temperatureSlider.value),
            max_tokens: parseInt(this.maxTokensInput.value),
            streaming: true, // Keep current streaming setting
            show_tool_calls: true // Keep current tool calls setting
        };

        appState.updateAiConfig(newConfig);
        
        // Immediately update the session header to show the new config
        this.updateSessionHeaderWithNewConfig(newConfig);
        
        notifications.success('AI configuration updated successfully');
        this.closeModal();
    }

    updateSessionHeaderWithNewConfig(config) {
        // Update the session header immediately to show the new model
        if (appState.currentSessionId) {
            const modelOption = this.modelOptions.find(opt => opt.value === config.model);
            const modelDisplayName = modelOption ? modelOption.label : config.model;
            
            // Find and update the model display in the session metadata
            const sessionMetadata = document.getElementById('sessionMetadata');
            if (sessionMetadata) {
                // Look for existing model info and update it
                const statusIndicators = sessionMetadata.querySelectorAll('.status-indicator');
                let modelUpdated = false;
                
                statusIndicators.forEach(indicator => {
                    if (indicator.textContent.includes('Model:')) {
                        indicator.textContent = `Model: ${config.model}`;
                        modelUpdated = true;
                    }
                });
                
                // If no model indicator exists, add one
                if (!modelUpdated) {
                    const modelIndicator = document.createElement('span');
                    modelIndicator.className = 'status-indicator';
                    modelIndicator.textContent = `Model: ${config.model}`;
                    sessionMetadata.appendChild(modelIndicator);
                }
            }
        }
    }

    async loadModels() {
        try {
            const response = await fetch('/api/models');
            const data = await response.json();
            
            if (data.status === 'success') {
                this.allModels = data.models;
                this.filterModels();
            } else {
                // Fallback to default models if API fails
                this.allModels = [
                    { id: "deepseek/deepseek-chat-v3-0324:free", name: "DeepSeek Chat v3 (Default)", is_tool_call: true }
                ];
                this.filterModels();
            }
        } catch (error) {
            console.warn('Failed to load models:', error);
            // Fallback to default models
            this.allModels = [
                { id: "deepseek/deepseek-chat-v3-0324:free", name: "DeepSeek Chat v3 (Default)", is_tool_call: true }
            ];
            this.filterModels();
        }
    }

    async refreshModels() {
        try {
            this.refreshModelsBtn.classList.add('loading');
            this.refreshModelsBtn.disabled = true;
            
            const response = await fetch('/api/models/refresh', { method: 'POST' });
            const data = await response.json();
            
            if (data.status === 'success') {
                notifications.success(`Refreshed ${data.models_count} models (${data.tool_models_count} with tools)`);
                await this.loadModels();
            } else {
                notifications.error(`Failed to refresh models: ${data.error}`);
            }
        } catch (error) {
            console.error('Failed to refresh models:', error);
            notifications.error('Failed to refresh models');
        } finally {
            this.refreshModelsBtn.classList.remove('loading');
            this.refreshModelsBtn.disabled = false;
        }
    }

    filterModels() {
        const searchTerm = this.modelSearch.value.toLowerCase();
        const toolsOnly = this.toolsOnlyFilter.checked;
        
        this.filteredModels = this.allModels.filter(model => {
            const matchesSearch = model.name.toLowerCase().includes(searchTerm) || 
                                model.id.toLowerCase().includes(searchTerm);
            const matchesFilter = !toolsOnly || model.is_tool_call;
            
            return matchesSearch && matchesFilter;
        });
        
        this.renderModelOptions();
    }

    renderModelOptions() {
        this.modelSelect.innerHTML = '';
        
        if (this.filteredModels.length === 0) {
            const option = document.createElement('option');
            option.value = '';
            option.textContent = 'No models found';
            option.disabled = true;
            this.modelSelect.appendChild(option);
            return;
        }
        
        this.filteredModels.forEach(model => {
            const option = document.createElement('option');
            option.value = model.id;
            
            // Create text content with tool indicator and context length
            const toolIndicator = model.is_tool_call ? '🔧 ' : '';
            const contextLength = model.context_length ? this.formatContextLength(model.context_length) : '';
            
            if (contextLength) {
                // Create right-aligned context length with visual separation
                const baseName = `${toolIndicator}${model.name}`;
                const paddingLength = Math.max(2, 45 - baseName.length - contextLength.length);
                const padding = ' '.repeat(paddingLength);
                option.textContent = `${baseName}${padding}(${contextLength})`;
                option.setAttribute('data-has-context', 'true');
            } else {
                option.textContent = `${toolIndicator}${model.name}`;
                option.setAttribute('data-has-context', 'false');
            }
            
            this.modelSelect.appendChild(option);
        });
        
        // Restore current selection if it exists in filtered models
        const currentModel = appState.aiConfig.model;
        if (this.filteredModels.some(m => m.id === currentModel)) {
            this.modelSelect.value = currentModel;
        } else if (this.filteredModels.length > 0) {
            // Select first available model if current isn't in filtered list
            this.modelSelect.value = this.filteredModels[0].id;
        }
        
        this.updatePreview();
    }

    formatContextLength(contextLength) {
        if (!contextLength || contextLength === 0) return '';
        
        if (contextLength >= 1000000) {
            return `${Math.round(contextLength / 1000000)}M`;
        } else if (contextLength >= 1000) {
            return `${Math.round(contextLength / 1000)}k`;
        }
        return contextLength.toString();
    }

    resetToDefaults() {
        const defaults = {
            model: "deepseek/deepseek-chat-v3-0324:free",
            temperature: 1.0,
            max_tokens: 5000,
            streaming: true,
            show_tool_calls: true
        };

        this.modelSelect.value = defaults.model;
        this.temperatureSlider.value = defaults.temperature;
        this.maxTokensInput.value = defaults.max_tokens;
        
        this.updateSliderValues();
        this.updatePreview();
    }
}

// DOM Manager
class DOMManager {
    constructor() {
        this.elements = {};
        this.initializeElements();
    }

    initializeElements() {
        this.elements = {
            // Session management
            sessionList: document.getElementById('sessionList'),
            sessionSearch: document.getElementById('sessionSearch'),
            newSessionBtn: document.getElementById('newSessionBtn'),
            welcomeNewSessionBtn: document.getElementById('welcomeNewSessionBtn'),
            refreshSessionsBtn: document.getElementById('refreshSessionsBtn'),
            
            // Pagination
            pagination: document.getElementById('pagination'),
            paginationInfo: document.getElementById('paginationInfo'),
            prevPageBtn: document.getElementById('prevPageBtn'),
            nextPageBtn: document.getElementById('nextPageBtn'),
            
            // Chat interface
            sessionTitle: document.getElementById('sessionTitle'),
            sessionMetadata: document.getElementById('sessionMetadata'),
            chatMessages: document.getElementById('chatMessages'),
            welcomeScreen: document.getElementById('welcomeScreen'),
            
            // Input
            chatForm: document.getElementById('chatForm'),
            messageInput: document.getElementById('messageInput'),
            sendBtn: document.getElementById('sendBtn'),
            attachBtn: document.getElementById('attachBtn'),
            messageInfo: document.getElementById('messageInfo'),
            
            // UI controls
            exportBtn: document.getElementById('exportBtn'),
            settingsBtn: document.getElementById('settingsBtn'),
            configBtn: document.getElementById('configBtn'),
            loadingOverlay: document.getElementById('loadingOverlay'),
            notificationContainer: document.getElementById('notificationContainer'),
            
            // Config Modal
            configModal: document.getElementById('configModal'),
            modelSelect: document.getElementById('modelSelect'),
            temperatureSlider: document.getElementById('temperatureSlider'),
            maxTokensInput: document.getElementById('maxTokensInput'),
            temperatureValue: document.getElementById('temperatureValue'),
            previewModel: document.getElementById('previewModel'),
            previewTemperature: document.getElementById('previewTemperature'),
            previewMaxTokens: document.getElementById('previewMaxTokens'),
            closeConfigModal: document.getElementById('closeConfigModal'),
            cancelConfigBtn: document.getElementById('cancelConfigBtn'),
            saveConfigBtn: document.getElementById('saveConfigBtn'),
            resetConfigBtn: document.getElementById('resetConfigBtn')
        };
    }

    showElement(element, show = true) {
        if (element) {
            element.style.display = show ? '' : 'none';
        }
    }

    hideElement(element) {
        this.showElement(element, false);
    }

    enableElement(element, enabled = true) {
        if (element) {
            element.disabled = !enabled;
        }
    }

    setElementText(element, text) {
        if (element) {
            element.textContent = text;
        }
    }

    setElementHTML(element, html) {
        if (element) {
            element.innerHTML = html;
        }
    }
}

const dom = new DOMManager();

// Notification System
class NotificationManager {
    show(message, type = 'info', duration = 5000) {
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.innerHTML = `
            <div class="notification-content">
                <span class="notification-message">${message}</span>
                <button class="notification-close" onclick="this.parentElement.parentElement.remove()">×</button>
        </div>
    `;
    
        dom.elements.notificationContainer.appendChild(notification);

        // Auto-remove after duration
        if (duration > 0) {
            setTimeout(() => {
                if (notification.parentElement) {
                    notification.remove();
                }
            }, duration);
        }

        return notification;
    }

    error(message, duration = 7000) {
        return this.show(message, 'error', duration);
    }

    success(message, duration = 4000) {
        return this.show(message, 'success', duration);
    }

    warning(message, duration = 5000) {
        return this.show(message, 'warning', duration);
    }
}

const notifications = new NotificationManager();

// API Client
class APIClient {
    async request(endpoint, options = {}) {
        const url = `${API_CONFIG.BASE_URL}${endpoint}`;
        const config = {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        };

        try {
            const response = await fetch(url, config);
        
        if (!response.ok) {
                const error = await response.text();
                throw new Error(`HTTP ${response.status}: ${error}`);
        }
        
            // Handle different content types
        const contentType = response.headers.get('content-type');
            if (contentType?.includes('application/json')) {
                return await response.json();
            } else if (contentType?.includes('text/event-stream')) {
                return response; // Return response for streaming
        } else {
                return await response.text();
            }
    } catch (error) {
            console.error(`API request failed for ${endpoint}:`, error);
            throw error;
        }
    }

    async getSessions(page = 1, pageSize = 50) {
        const offset = (page - 1) * pageSize;
        return this.request(`${API_CONFIG.ENDPOINTS.SESSIONS}?limit=${pageSize}&offset=${offset}`);
    }

    async getSession(sessionId) {
        return this.request(`${API_CONFIG.ENDPOINTS.SESSIONS}/${sessionId}`);
    }

    async createSession(sessionData = {}) {
        return this.request(API_CONFIG.ENDPOINTS.SESSIONS, {
            method: 'POST',
            body: JSON.stringify(sessionData)
        });
    }

    async sendMessage(sessionId, message, streaming = true) {
        const requestData = {
            session_id: sessionId,
            message: message,
            stream: streaming
        };

        // Add config override if different from defaults
        const configOverride = appState.getConfigOverride();
        if (configOverride) {
            requestData.config_override = configOverride;
        }

        const response = await this.request(API_CONFIG.ENDPOINTS.CHAT, {
            method: 'POST',
            body: JSON.stringify(requestData)
        });

        return response;
    }

    async deleteSession(sessionId) {
        return this.request(`${API_CONFIG.ENDPOINTS.SESSIONS}/${sessionId}`, {
            method: 'DELETE'
        });
    }

    async updateSessionName(sessionId, name) {
        return this.request(`${API_CONFIG.ENDPOINTS.SESSIONS}/${sessionId}/name`, {
            method: 'PATCH',
            body: JSON.stringify({ name: name })
        });
    }
}

const apiClient = new APIClient();

// Session Manager
class SessionManager {
    async loadSessions(page = 1) {
        try {
            dom.showElement(dom.elements.loadingOverlay);
            
            const response = await apiClient.getSessions(page, appState.pagination.pageSize);
            
            // Parse SessionListResponse
            const sessions = response.sessions || [];
            const pagination = {
                page: response.page || 1,
                pageSize: response.page_size || 50,
                total: response.total || 0
            };

            appState.setSessions(sessions, pagination);
            this.renderSessions();
            this.updatePagination();

            // Load first session if none selected
            if (sessions.length > 0 && !appState.currentSessionId) {
                await this.loadSession(sessions[0].id);
            }

    } catch (error) {
            console.error('Failed to load sessions:', error);
            notifications.error(`Failed to load sessions: ${error.message}`);
            this.renderError('Failed to load sessions');
        } finally {
            dom.hideElement(dom.elements.loadingOverlay);
        }
    }

    renderSessions() {
        if (!dom.elements.sessionList) return;

        if (appState.sessions.length === 0) {
            dom.setElementHTML(dom.elements.sessionList, `
                <div class="no-sessions">
                    <p>No sessions found</p>
                    <button class="btn btn-primary" onclick="sessionManager.createSession()">
                        Create First Session
                    </button>
                </div>
            `);
            return;
        }

        const sessionsHTML = appState.sessions.map(session => this.createSessionElement(session)).join('');
        dom.setElementHTML(dom.elements.sessionList, sessionsHTML);

        // Add event listeners
        this.attachSessionEventListeners();
    }

    createSessionElement(session) {
        const isActive = session.id === appState.currentSessionId;
        const statusClass = session.status || 'active';
        const createdAt = session.created_at ? new Date(session.created_at).toLocaleDateString() : 'Unknown';
        
        // Extract additional info from session metadata
        const messageCount = session.message_count || session.metadata?.total_messages || 0;
        const turnCount = session.metadata?.total_turns || 0;
        
        return `
            <div class="session-item ${isActive ? 'active' : ''}" data-session-id="${session.id}">
                <div class="session-item-header">
                    <div class="session-item-title" title="${session.name || session.id}">
                        ${session.name || `Session ${session.id.substring(0, 8)}`}
        </div>
                    <div class="session-actions">
                        <span class="session-status ${statusClass}">${statusClass}</span>
                        <button class="session-delete-btn" title="Delete session" onclick="sessionManager.deleteSession('${session.id}', event)">
                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2m3 0v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6h14zM10 11v6M14 11v6"/>
                            </svg>
                        </button>
                    </div>
                </div>
                <div class="session-item-meta">
                    <span class="message-count">${messageCount} messages</span>
                    ${turnCount > 0 ? `<span class="turn-count">${turnCount} turns</span>` : ''}
                    <span class="session-date">${createdAt}</span>
                </div>
        </div>
    `;
    }

    attachSessionEventListeners() {
        const sessionItems = dom.elements.sessionList.querySelectorAll('.session-item');
        sessionItems.forEach(item => {
            item.addEventListener('click', async () => {
                const sessionId = item.dataset.sessionId;
                await this.loadSession(sessionId);
            });
        });
    }

    updatePagination() {
        if (!dom.elements.pagination) return;

        const { page, pageSize, total } = appState.pagination;
        const totalPages = Math.ceil(total / pageSize);

        if (totalPages <= 1) {
            dom.hideElement(dom.elements.pagination);
            return;
        }

        dom.showElement(dom.elements.pagination);
        dom.setElementText(dom.elements.paginationInfo, `Page ${page} of ${totalPages}`);
        
        dom.enableElement(dom.elements.prevPageBtn, page > 1);
        dom.enableElement(dom.elements.nextPageBtn, page < totalPages);
    }

    async loadSession(sessionId) {
        try {
            appState.setCurrentSession(sessionId);
            
            // Update UI immediately
            this.updateActiveSessionUI();
            dom.hideElement(dom.elements.welcomeScreen);
            
            // Show loading in chat area
            dom.setElementHTML(dom.elements.chatMessages, `
                <div class="loading-state">
                    <div class="spinner"></div>
                    <span>Loading conversation...</span>
                </div>
            `);

            const sessionData = await apiClient.getSession(sessionId);
            
            // Update session header
            this.updateSessionHeader(sessionData);
            
            // Render conversation history
            this.renderConversationHistory(sessionData.conversation_history);
            
            // Enable chat input
            this.enableChatInput();

    } catch (error) {
            console.error('Failed to load session:', error);
            notifications.error(`Failed to load session: ${error.message}`);
            this.renderError('Failed to load conversation');
        }
    }

    updateActiveSessionUI() {
        // Update session list active state
        const sessionItems = dom.elements.sessionList.querySelectorAll('.session-item');
        sessionItems.forEach(item => {
            const isActive = item.dataset.sessionId === appState.currentSessionId;
            item.classList.toggle('active', isActive);
        });
    }

    updateSessionHeader(sessionData) {
        const title = sessionData.name || `Session ${sessionData.session_id.substring(0, 8)}`;
        dom.setElementText(dom.elements.sessionTitle, title);

        // Extract data from the new session_data structure
        const sessionInfo = sessionData.session_data || {};
        const config = sessionInfo.config || {};
        const statistics = sessionInfo.statistics || {};
        const metadata = sessionInfo.metadata || {};

        // Format display values
        const model = config.model ? config.model.split('/').pop() : 'Unknown';
        const messageCount = sessionData.message_count || metadata.total_messages || 0;
        const totalTurns = metadata.total_turns || 0;
        const avgResponseTime = statistics.average_response_time_ms 
            ? `${(statistics.average_response_time_ms / 1000).toFixed(2)}s avg`
            : '';
        const tokenUsage = statistics.total_tokens_input || statistics.total_tokens_output
            ? `${statistics.total_tokens_input || 0}/${statistics.total_tokens_output || 0} tokens`
            : '';

        const metadataHTML = `
            <span class="status-indicator">${sessionData.status || 'active'}</span>
            <span class="session-stat">${messageCount} messages</span>
            <span class="session-stat">${totalTurns} turns</span>
            ${sessionData.created_at ? `<span class="session-stat">Created ${new Date(sessionData.created_at).toLocaleDateString()}</span>` : ''}
            <span class="session-stat">Model: ${model}</span>
            ${avgResponseTime ? `<span class="session-stat">${avgResponseTime}</span>` : ''}
            ${tokenUsage ? `<span class="session-stat">${tokenUsage}</span>` : ''}
        `;
        dom.setElementHTML(dom.elements.sessionMetadata, metadataHTML);
    }

    renderConversationHistory(conversationHistory) {
        if (!conversationHistory || !conversationHistory.conversation_turns) {
            dom.setElementHTML(dom.elements.chatMessages, `
                <div class="no-messages">
                    <p>No messages in this conversation yet.</p>
                    <p>Start by sending a message below!</p>
                </div>
            `);
        return;
    }
    
        const messages = this.extractMessages(conversationHistory.conversation_turns);
        const messagesHTML = messages.map(msg => this.createMessageElement(msg)).join('');
        dom.setElementHTML(dom.elements.chatMessages, messagesHTML);
        
        this.scrollToBottom();
    }

    extractMessages(turns) {
        const messages = [];
        
        turns.forEach(turn => {
            // Add user message
            if (turn.user_message) {
                messages.push({
                    id: turn.user_message.message_id,
                    role: 'user',
                    content: turn.user_message.content,
                    timestamp: turn.user_message.timestamp,
                    metadata: turn.user_message.metadata || {}
                });
            }

            // Add assistant responses
            if (turn.assistant_responses) {
                turn.assistant_responses.forEach(response => {
                    if (response.is_active !== false) { // Include if not explicitly false
                        messages.push({
                            id: response.message_id,
                            role: 'assistant',
                            content: response.final_content || response.content,
                            timestamp: response.timestamp,
                            metadata: response.metadata || {}
                        });
                    }
                });
            }
        });

        return messages;
    }

    createMessageElement(message) {
        const timestamp = message.timestamp ? new Date(message.timestamp).toLocaleTimeString() : '';
        const content = this.formatMessageContent(message.content, message.role);
        
        // For assistant messages, include model name if available
        let messageFooter = timestamp;
        if (message.role === 'assistant' && message.metadata && message.metadata.generation_config) {
            const model = message.metadata.generation_config.model;
            if (model) {
                // Extract just the model name part (e.g., "mistral-small-3.2-24b-instruct" from "mistralai/mistral-small-3.2-24b-instruct:free")
                const modelName = model.split('/').pop().split(':')[0];
                messageFooter = `${timestamp} • ${modelName}`;
            }
        }
        
        return `
            <div class="message ${message.role}-message" data-message-id="${message.id}">
                <div class="message-content">${content}</div>
                <div class="message-time">${messageFooter}</div>
            </div>
        `;
    }

    formatMessageContent(content, role) {
        if (!content) return '';

        if (role === 'assistant' && typeof marked !== 'undefined') {
            try {
                return marked.parse(content);
            } catch (error) {
                console.warn('Markdown parsing failed:', error);
                return this.escapeHtml(content).replace(/\n/g, '<br>');
            }
        }

        return this.escapeHtml(content).replace(/\n/g, '<br>');
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    renderError(message) {
        dom.setElementHTML(dom.elements.chatMessages, `
            <div class="error-state">
                <p class="error-message">${message}</p>
                <button class="btn btn-secondary" onclick="sessionManager.loadSession('${appState.currentSessionId}')">
                    Retry
                </button>
            </div>
        `);
    }

    enableChatInput() {
        dom.enableElement(dom.elements.messageInput);
        dom.enableElement(dom.elements.sendBtn);
        dom.enableElement(dom.elements.attachBtn);
        dom.elements.messageInput.placeholder = "Type your message...";
    }

    disableChatInput() {
        dom.enableElement(dom.elements.messageInput, false);
        dom.enableElement(dom.elements.sendBtn, false);
        dom.enableElement(dom.elements.attachBtn, false);
        dom.elements.messageInput.placeholder = "Select a session to start chatting...";
    }

    async createSession() {
        try {
            notifications.show('Creating new session...', 'info', 2000);
            
            const sessionData = {
                name: `Chat Session ${new Date().toLocaleString()}`
            };

            const newSession = await apiClient.createSession(sessionData);
            
            if (!newSession || !newSession.id) {
                throw new Error('Invalid session response from server');
            }
            
            // Reload sessions to include the new one
            await this.loadSessions();
            
            // Load the new session
            await this.loadSession(newSession.id);
            
            notifications.success('New session created successfully');
        
    } catch (error) {
            console.error('Failed to create session:', error);
            notifications.error(`Failed to create session: ${error.message}`);
        }
    }

    scrollToBottom() {
        if (dom.elements.chatMessages) {
            dom.elements.chatMessages.scrollTop = dom.elements.chatMessages.scrollHeight;
        }
    }

    async deleteSession(sessionId, event) {
        // Prevent the session click event from firing
        if (event) {
            event.stopPropagation();
        }

        // Confirm deletion
        const sessionName = appState.sessions.find(s => s.id === sessionId)?.name || sessionId.substring(0, 8);
        if (!confirm(`Are you sure you want to delete "${sessionName}"? This action cannot be undone.`)) {
            return;
        }

        try {
            // Call the API to delete the session
            await apiClient.deleteSession(sessionId);
            
            // Remove from local state
            appState.sessions = appState.sessions.filter(s => s.id !== sessionId);
            
            // If this was the current session, clear it
            if (appState.currentSessionId === sessionId) {
                appState.setCurrentSession(null);
                
                // Load another session if available, or show welcome screen
                if (appState.sessions.length > 0) {
                    await this.loadSession(appState.sessions[0].id);
                } else {
                    // Show welcome screen
                    dom.showElement(dom.elements.welcomeScreen);
                    dom.setElementHTML(dom.elements.chatMessages, '');
                    dom.setElementText(dom.elements.sessionTitle, 'No Session Selected');
                    dom.setElementHTML(dom.elements.sessionMetadata, '');
                    this.disableChatInput();
                }
            }
            
            // Re-render sessions list
            this.renderSessions();
            this.updatePagination();
            
            notifications.success(`Session "${sessionName}" deleted successfully`);
            
        } catch (error) {
            console.error('Failed to delete session:', error);
            notifications.error(`Failed to delete session: ${error.message}`);
        }
    }
}

const sessionManager = new SessionManager();

// Chat Manager
class ChatManager {
    async sendMessage(message) {
        if (!appState.currentSessionId || !message.trim()) {
        return;
    }
    
        try {
            // Add user message to UI immediately
            this.addUserMessage(message);
            
            // Clear input
            dom.elements.messageInput.value = '';
            this.autoResizeTextarea(dom.elements.messageInput);

            // Send message and handle streaming response
            const response = await apiClient.sendMessage(appState.currentSessionId, message, true);

            if (response.body) {
                await this.handleStreamingResponse(response);
            } else {
                // Handle non-streaming response
                this.addAssistantMessage(response.response || 'No response received');
            }

            // After successful message, refresh session data to update statistics
            await this.refreshSessionData();

        } catch (error) {
            console.error('Failed to send message:', error);
            notifications.error(`Failed to send message: ${error.message}`);
            this.addErrorMessage('Failed to send message. Please try again.');
        }
    }

    async refreshSessionData() {
        try {
            // Refresh current session data to update statistics
            const sessionData = await apiClient.getSession(appState.currentSessionId);
            sessionManager.updateSessionHeader(sessionData);
            
            // Update session name in local state if it changed
            const sessionInList = appState.sessions.find(s => s.id === appState.currentSessionId);
            if (sessionInList && sessionData.session_data?.metadata?.name) {
                const newName = sessionData.session_data.metadata.name;
                if (sessionInList.name !== newName) {
                    sessionInList.name = newName;
                    sessionManager.renderSessions(); // Re-render to show updated name
                    notifications.success(`Session renamed to "${newName}"`);
                    
                    // Only reload sessions if the message count has changed significantly
                    // This reduces unnecessary API calls while still keeping the UI updated
                    const currentMessageCount = sessionData.message_count || 0;
                    const localMessageCount = sessionInList.message_count || 0;
                    
                    if (Math.abs(currentMessageCount - localMessageCount) > 0) {
                        // Update local message count
                        sessionInList.message_count = currentMessageCount;
                        sessionManager.renderSessions(); // Re-render to show updated count
                    }
                    return; // Skip the sessions list reload since we updated locally
                }
            }
            
            // Only reload sessions list if session name didn't change (to update message count)
            await sessionManager.loadSessions(appState.pagination.page);
        } catch (error) {
            console.warn('Failed to refresh session data:', error);
        }
    }

    addUserMessage(content) {
        const message = {
            id: `user-${Date.now()}`,
            role: 'user',
            content: content,
            timestamp: new Date().toISOString()
        };

        this.addMessageToChat(message);
    }

    async handleStreamingResponse(response) {
        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        // Start assistant message
        const assistantMessage = {
            id: `assistant-${Date.now()}`,
            role: 'assistant',
            content: '',
            timestamp: new Date().toISOString(),
            isStreaming: true
        };

        this.addMessageToChat(assistantMessage);

        try {
            while (true) {
                const { done, value } = await reader.read();

                if (done) break;

                const chunk = decoder.decode(value);
                const lines = chunk.split('\n');

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        const data = line.slice(6);

                        if (data === '[DONE]') {
                            await this.completeStreamingMessage(assistantMessage.id);
                            return;
                        }

                        try {
                            const eventData = JSON.parse(data);
                            await this.handleStreamingEvent(assistantMessage.id, eventData);
                        } catch (error) {
                            console.warn('Failed to parse streaming data:', data);
                        }
                    }
                }
        }
    } catch (error) {
            console.error('Streaming error:', error);
            this.showStreamingError(assistantMessage.id, error.message);
        }
    }

    async handleStreamingEvent(messageId, eventData) {
        const messageElement = document.querySelector(`[data-message-id="${messageId}"]`);
        if (!messageElement) return;

        const contentElement = messageElement.querySelector('.message-content');
        if (!contentElement) return;

        // Handle different event types
        switch (eventData.event) {
            case 'RunStarted':
                // Initialize streaming for this message
                appState.currentStreamingMessage = '';
                contentElement.innerHTML = '<span class="streaming-cursor">▊</span>';
                break;
                
            case 'RunResponse':
            case 'content':
            case 'delta':
                const newContent = eventData.content || eventData.data?.content || '';
                if (newContent) {
                    appState.currentStreamingMessage = appState.currentStreamingMessage || '';
                    appState.currentStreamingMessage += newContent;
                    contentElement.innerHTML = this.formatMessageContent(appState.currentStreamingMessage, 'assistant') + 
                                             '<span class="streaming-cursor">▊</span>';
                    sessionManager.scrollToBottom();
                }
                break;
                
            case 'completed':
            case 'RunCompleted':
                await this.completeStreamingMessage(messageId);
                break;
                
            case 'error':
                this.showStreamingError(messageId, eventData.error || eventData.message || 'Unknown error');
                break;
                
            case 'keepalive':
                // Do nothing for keepalive events
                break;
                
            default:
                console.log('Unknown streaming event:', eventData.event, eventData);
        }
    }

    async completeStreamingMessage(messageId) {
        const messageElement = document.querySelector(`[data-message-id="${messageId}"]`);
        if (!messageElement) return;

        const contentElement = messageElement.querySelector('.message-content');
        const timeElement = messageElement.querySelector('.message-time');
        if (!contentElement) return;

        // Remove streaming cursor and finalize content
        contentElement.innerHTML = this.formatMessageContent(appState.currentStreamingMessage || '', 'assistant');
        messageElement.classList.remove('streaming');
        
        // Update the timestamp to include model information
        if (timeElement) {
            const timestamp = new Date().toLocaleTimeString();
            const model = appState.aiConfig.model;
            if (model) {
                // Extract just the model name part
                const modelName = model.split('/').pop().split(':')[0];
                timeElement.textContent = `${timestamp} • ${modelName}`;
            } else {
                timeElement.textContent = timestamp;
            }
        }
        
        appState.currentStreamingMessage = null;
        sessionManager.scrollToBottom();

        // Refresh session data to update statistics after streaming completes
        await this.refreshSessionData();
    }

    showStreamingError(messageId, errorMessage) {
        const messageElement = document.querySelector(`[data-message-id="${messageId}"]`);
        if (!messageElement) return;

        const contentElement = messageElement.querySelector('.message-content');
        if (!contentElement) return;

        contentElement.innerHTML = `<div class="error-message">Error: ${errorMessage}</div>`;
        messageElement.classList.remove('streaming');
        messageElement.classList.add('error');
        
        appState.currentStreamingMessage = null;
    }

    addAssistantMessage(content) {
        const message = {
            id: `assistant-${Date.now()}`,
            role: 'assistant',
            content: content,
            timestamp: new Date().toISOString()
        };

        this.addMessageToChat(message);
    }

    addErrorMessage(content) {
        const message = {
            id: `error-${Date.now()}`,
            role: 'assistant',
            content: `❌ ${content}`,
            timestamp: new Date().toISOString(),
            isError: true
        };

        this.addMessageToChat(message);
    }

    addMessageToChat(message) {
        // Hide welcome screen and no-messages
        dom.hideElement(dom.elements.welcomeScreen);
        const noMessages = dom.elements.chatMessages.querySelector('.no-messages');
        if (noMessages) dom.hideElement(noMessages);

        const messageHTML = sessionManager.createMessageElement(message);
        const messageElement = document.createElement('div');
        messageElement.innerHTML = messageHTML;
        
        const messageNode = messageElement.firstElementChild;
        if (message.isStreaming) {
            messageNode.classList.add('streaming');
        }
        if (message.isError) {
            messageNode.classList.add('error');
        }

        dom.elements.chatMessages.appendChild(messageNode);
        sessionManager.scrollToBottom();
    }

    formatMessageContent(content, role) {
        return sessionManager.formatMessageContent(content, role);
    }

    autoResizeTextarea(textarea) {
        textarea.style.height = 'auto';
        textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px';
    }
}

const chatManager = new ChatManager();

// Event Handlers
function setupEventHandlers() {
    // Session management
    dom.elements.newSessionBtn?.addEventListener('click', () => sessionManager.createSession());
    dom.elements.welcomeNewSessionBtn?.addEventListener('click', () => sessionManager.createSession());
    dom.elements.refreshSessionsBtn?.addEventListener('click', () => sessionManager.loadSessions());

    // Pagination
    dom.elements.prevPageBtn?.addEventListener('click', async () => {
        if (appState.pagination.page > 1) {
            await sessionManager.loadSessions(appState.pagination.page - 1);
        }
    });
    
    dom.elements.nextPageBtn?.addEventListener('click', async () => {
        const totalPages = Math.ceil(appState.pagination.total / appState.pagination.pageSize);
        if (appState.pagination.page < totalPages) {
            await sessionManager.loadSessions(appState.pagination.page + 1);
        }
    });

    // Search functionality
    let searchTimeout;
    dom.elements.sessionSearch?.addEventListener('input', (e) => {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => {
            searchSessions(e.target.value);
        }, 300);
    });

    // Chat form
    dom.elements.chatForm?.addEventListener('submit', async (e) => {
                e.preventDefault();
        const message = dom.elements.messageInput?.value.trim();
        if (message) {
            await chatManager.sendMessage(message);
        }
    });

    // Input auto-resize
    dom.elements.messageInput?.addEventListener('input', (e) => {
        chatManager.autoResizeTextarea(e.target);
    });

    // Keyboard shortcuts
    dom.elements.messageInput?.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            dom.elements.chatForm?.requestSubmit();
        }
    });

    // Export functionality
    dom.elements.exportBtn?.addEventListener('click', exportConversation);
    
    // Settings functionality  
    dom.elements.settingsBtn?.addEventListener('click', openSettings);
}

// Utility Functions
function searchSessions(query) {
    const filteredSessions = appState.sessions.filter(session => {
        const name = session.name || '';
        return name.toLowerCase().includes(query.toLowerCase());
    });

    // Re-render with filtered sessions
    const originalSessions = appState.sessions;
    appState.sessions = filteredSessions;
    sessionManager.renderSessions();
    appState.sessions = originalSessions;
}

async function exportConversation() {
    if (!appState.currentSessionId) {
        notifications.warning('No session selected for export');
        return;
    }

    try {
        const sessionData = await apiClient.getSession(appState.currentSessionId);
        const blob = new Blob([JSON.stringify(sessionData, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        
        const a = document.createElement('a');
        a.href = url;
        a.download = `obelisk-chat-${sessionData.session_id.substring(0, 8)}-${new Date().toISOString().split('T')[0]}.json`;
        a.click();
        
        URL.revokeObjectURL(url);
        notifications.success('Conversation exported successfully');
    } catch (error) {
        console.error('Export failed:', error);
        notifications.error('Failed to export conversation');
    }
}

function openSettings() {
    notifications.warning('Settings panel coming soon');
}

async function testBackendConnection() {
    try {
        const response = await fetch(`${API_CONFIG.BACKEND_URL}/health`);
        if (response.ok) {
            console.log('✅ Backend connection successful');
        } else {
            console.warn('⚠️ Backend health check failed');
        }
    } catch (error) {
        console.error('❌ Backend connection failed:', error);
        notifications.error('Backend connection failed. Some features may not work properly.');
    }
}

// Application Initialization
async function initializeApp() {
    console.log('Initializing Obelisk Chat Platform...');
    
    // Load saved state
    appState.loadState();
    
    // Setup event handlers
    setupEventHandlers();
    
    // Initialize config manager
    const configManager = new ConfigManager();
    
    // Initialize chat input state
    sessionManager.disableChatInput();
    
    // Test backend connection
    await testBackendConnection();
    
    // Load sessions
    await sessionManager.loadSessions(appState.pagination.page);
    
    console.log('✅ Obelisk Chat Platform initialized successfully');
}

// Start the application
document.addEventListener('DOMContentLoaded', initializeApp); 
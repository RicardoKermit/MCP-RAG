let isConnected = false;
let currentLanguage = 'pt';
let isGenerating = false;
let currentAbortController = null;
let currentTypewriterClear = null;

// Configurar marked para formatação
marked.setOptions({
    breaks: true,
    gfm: true
});

// Traduções
let translations = {};

// Auto-resize textarea
function autoResizeTextarea(textarea) {
    textarea.style.height = 'auto';
    textarea.style.height = Math.min(textarea.scrollHeight, 200) + 'px';
}

// Initialize textarea auto-resize
document.addEventListener('DOMContentLoaded', function() {
    const textarea = document.getElementById('messageInput');
    if (textarea) {
        textarea.addEventListener('input', function() {
            autoResizeTextarea(this);
        });
        
        // Initial resize
        autoResizeTextarea(textarea);
    }
    
    // Load initial language
    loadLanguage();
    
    // Set initial language selector
    const savedLanguage = localStorage.getItem('language') || 'pt';
    const languageSelect = document.getElementById('languageSelect');
    if (languageSelect) {
        languageSelect.value = savedLanguage;
    }
});

// Função updateStatus removida - agora o estado é controlado diretamente pelo botão

function showConnectionStatus(message, isError = false) {
    const statusDiv = document.getElementById('connectionStatus');
    statusDiv.innerHTML = `<div class="${isError ? 'error' : 'success'}">${message}</div>`;
    setTimeout(() => {
        statusDiv.innerHTML = '';
    }, 5000);
}

function showToolsInfo(tools) {
    const toolsInfo = document.getElementById('toolsInfo');
    const toolsList = document.getElementById('toolsList');
    
    if (tools && tools.length > 0) {
        toolsList.innerHTML = tools.map(tool => `<div class="tool-item">${tool}</div>`).join('');
        toolsInfo.style.display = 'block';
    } else {
        toolsInfo.style.display = 'none';
    }
}

function formatMessage(content) {
    // Converter markdown para HTML
    try {
        return marked.parse(content);
    } catch (e) {
        // Se falhar, retorna o conteúdo original
        return content.replace(/\n/g, '<br>');
    }
}

function addMessage(content, isUser = false, typewriter = false) {
    const messagesContainer = document.getElementById('chatMessages');
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${isUser ? 'user' : 'assistant'}`;
    
    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    
    if (isUser) {
        avatar.textContent = 'U';
    } else {
        avatar.innerHTML = `
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z" fill="currentColor"/>
            </svg>
        `;
    }
    
    const messageContent = document.createElement('div');
    messageContent.className = 'message-content';
    
    const messageText = document.createElement('div');
    messageText.className = 'message-text';
    
    messageContent.appendChild(messageText);
    messageDiv.appendChild(avatar);
    messageDiv.appendChild(messageContent);
    messagesContainer.appendChild(messageDiv);
    
    // Scroll to bottom
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
    
    if (typewriter && !isUser) {
        // Efeito de digitação para respostas do assistente
        currentTypewriterClear = typewriterEffect(messageText, content);
    } else {
        // Formatar o conteúdo se for do assistente
        if (isUser) {
            messageText.textContent = content;
        } else {
            messageText.innerHTML = formatMessage(content);
        }
    }
}

function typewriterEffect(element, text, speed = 15) {
    let i = 0;
    const originalText = text;
    let timeoutId = null;
    let isCancelled = false;
    
    function typeChar() {
        if (i < originalText.length && !isCancelled) {
            element.innerHTML = formatMessage(originalText.substring(0, i + 1));
            i++;
            timeoutId = setTimeout(typeChar, speed);
        } else if (isCancelled) {
            // If generation was cancelled, show the full text immediately
            element.innerHTML = formatMessage(originalText);
        }
    }
    
    typeChar();
    
    // Return a function to clear the timeout if needed
    return () => {
        isCancelled = true;
        if (timeoutId) {
            clearTimeout(timeoutId);
        }
    };
}

async function connectToServer() {
    const serverPath = document.getElementById('serverPath').value;
    if (!serverPath) {
        showConnectionStatus('Por favor, especifique o caminho do servidor.', true);
        return;
    }

    const connectButton = document.getElementById('connectButton');
    const btnText = connectButton.querySelector('.btn-text');
    
    // Show connecting state
    connectButton.classList.add('connecting');
    connectButton.disabled = true;
    btnText.textContent = translations.connecting || 'Conectando...';
    
    try {
        const response = await fetch('/connect', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ server_path: serverPath })
        });

        const data = await response.json();
        
        if (data.success) {
            // Show connected state
            connectButton.classList.remove('connecting');
            connectButton.classList.add('connected');
            btnText.textContent = translations.connected || 'Conectado';
            isConnected = true;
            showConnectionStatus(translations.connection_success || 'Conectado com sucesso ao servidor MCP!');
            showToolsInfo(data.tools);
            
            // Enable send button and input
            const sendButton = document.getElementById('sendButton');
            const messageInput = document.getElementById('messageInput');
            if (sendButton) {
                sendButton.disabled = false;
            }
            if (messageInput) {
                messageInput.disabled = false;
                messageInput.placeholder = translations.input_placeholder || 'Digite a sua pergunta...';
            }
        } else {
            // Reset to disconnected state
            connectButton.classList.remove('connecting', 'connected');
            btnText.textContent = translations.connect || 'Conectar ao servidor';
            isConnected = false;
            showConnectionStatus(`${translations.connection_error || 'Erro ao conectar'}: ${data.error}`, true);
            
            // Disable send button and input
            const sendButton = document.getElementById('sendButton');
            const messageInput = document.getElementById('messageInput');
            if (sendButton) {
                sendButton.disabled = true;
            }
            if (messageInput) {
                messageInput.disabled = true;
                messageInput.placeholder = translations.connect_first || 'Conecte-se primeiro ao servidor...';
            }
        }
    } catch (error) {
        // Reset to disconnected state
        connectButton.classList.remove('connecting', 'connected');
        btnText.textContent = translations.connect || 'Conectar ao servidor';
        isConnected = false;
        showConnectionStatus(`${translations.connection_error || 'Erro de rede'}: ${error.message}`, true);
    } finally {
        connectButton.disabled = false;
    }
}

async function sendMessage() {
    const input = document.getElementById('messageInput');
    const message = input.value.trim();
    
    if (!message || !isConnected || isGenerating) return;

    // Create new conversation if none exists
    if (!currentConversationId) {
        currentConversationId = createNewConversation();
    }

    // Adiciona mensagem do usuário
    addMessage(message, true);
    input.value = '';
    
    // Reset textarea height
    autoResizeTextarea(input);

    // Set generating state
    isGenerating = true;
    currentAbortController = new AbortController();

    // Show stop button
    const sendButton = document.getElementById('sendButton');
    const originalContent = sendButton.innerHTML;
    
    sendButton.disabled = false;
    sendButton.onclick = stopGeneration;
    sendButton.classList.add('stop-generating');
    sendButton.innerHTML = `
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M6 6h12v12H6z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
    `;

    try {
        const response = await fetch('/query', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ 
                query: message,
                language: currentLanguage || 'pt'  // Send current language
            }),
            signal: currentAbortController.signal
        });

        const data = await response.json();
        addMessage(data.response, false, true); // true para ativar efeito de digitação
        
        // Save conversation after successful response
        saveCurrentConversation();
    } catch (error) {
        if (error.name === 'AbortError') {
            const cancelMsg = translations.generation_cancelled || 'Geração cancelada pelo utilizador.';
            addMessage(cancelMsg, false, false);
        } else {
            const errorMsg = translations.error_processing || 'Erro ao processar a pergunta:';
            addMessage(`${errorMsg} ${error.message}`, false, false);
        }
    } finally {
        // Reset generating state
        isGenerating = false;
        currentAbortController = null;
        currentTypewriterClear = null;
        
        // Restore send button
        sendButton.disabled = !isConnected;
        sendButton.onclick = sendMessage;
        sendButton.classList.remove('stop-generating');
        sendButton.innerHTML = `
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
        `;
    }
}

// Stop generation function
function stopGeneration() {
    if (currentAbortController) {
        currentAbortController.abort();
    }
    
    // Clear any ongoing typing animation
    if (currentTypewriterClear) {
        currentTypewriterClear();
        currentTypewriterClear = null;
    }
}

function handleKeyPress(event) {
    if (event.key === 'Enter' && !event.shiftKey && isConnected && !isGenerating) {
        event.preventDefault();
        sendMessage();
    }
}

// Nova conversa
function newChat() {
    // Create a new conversation
    currentConversationId = createNewConversation();
    
    const messagesContainer = document.getElementById('chatMessages');
    const welcomeMessage = translations.new_chat_welcome || 'Nova conversa iniciada. Como posso ajudá-lo hoje?';
    messagesContainer.innerHTML = `
        <div class="message assistant">
            <div class="message-avatar">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z" fill="currentColor"/>
                </svg>
            </div>
            <div class="message-content">
                <div class="message-text">
                    ${welcomeMessage}
                </div>
            </div>
        </div>
    `;
}

// Limpar histórico
async function clearHistory() {
    try {
        const response = await fetch('/clear-history', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        });
        
        const data = await response.json();
        if (data.success) {
            const successMsg = translations.history_cleared || 'Histórico limpo com sucesso';
            showConnectionStatus(successMsg);
        } else {
            const errorMsg = translations.error_clearing_history || 'Erro ao limpar histórico:';
            showConnectionStatus(`${errorMsg} ${data.error}`, true);
        }
    } catch (error) {
        const errorMsg = translations.error_clearing_history || 'Erro ao limpar histórico:';
        showConnectionStatus(`${errorMsg} ${error.message}`, true);
    }
}

// Verificar status inicial
async function checkStatus() {
    try {
        const response = await fetch('/status');
        const data = await response.json();
        
        const connectButton = document.getElementById('connectButton');
        const btnText = connectButton.querySelector('.btn-text');
        
        if (data.connected) {
            // Show connected state
            connectButton.classList.remove('connecting');
            connectButton.classList.add('connected');
            btnText.textContent = translations.connected || 'Conectado';
            isConnected = true;
            showToolsInfo(data.tools);
            
            // Enable send button and input
            const sendButton = document.getElementById('sendButton');
            const messageInput = document.getElementById('messageInput');
            if (sendButton) {
                sendButton.disabled = false;
            }
            if (messageInput) {
                messageInput.disabled = false;
                messageInput.placeholder = translations.input_placeholder || 'Digite a sua pergunta...';
            }
        } else {
            // Show disconnected state
            connectButton.classList.remove('connecting', 'connected');
            btnText.textContent = translations.connect || 'Conectar ao servidor';
            isConnected = false;
            
            // Disable send button and input
            const sendButton = document.getElementById('sendButton');
            const messageInput = document.getElementById('messageInput');
            if (sendButton) {
                sendButton.disabled = true;
            }
            if (messageInput) {
                messageInput.disabled = true;
                messageInput.placeholder = translations.connect_first || 'Conecte-se primeiro ao servidor...';
            }
        }
        
        // Update model selector if available
        if (data.current_model) {
            const modelSelect = document.getElementById('modelSelect');
            const modelInfo = document.getElementById('modelInfo');
            
            if (modelSelect && modelInfo) {
                modelSelect.value = data.current_model;
                
                if (MODEL_INFO[data.current_model]) {
                    modelInfo.innerHTML = `<small>${MODEL_INFO[data.current_model].description}</small>`;
                }
                
                // Mostrar mensagem se o modelo foi sincronizado
                if (data.connected) {
                    showConnectionStatus(`Modelo sincronizado: ${MODEL_INFO[data.current_model].name}`);
                }
            }
        }
    } catch (error) {
        console.log('Erro ao verificar status:', error);
    }
}

// Dark mode functionality
function toggleDarkMode() {
    const html = document.documentElement;
    const toggle = document.getElementById('darkModeToggle');
    
    if (html.getAttribute('data-theme') === 'light') {
        html.removeAttribute('data-theme');
        toggle.innerHTML = `
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
        `;
        localStorage.setItem('theme', 'dark');
    } else {
        html.setAttribute('data-theme', 'light');
        toggle.innerHTML = `
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
        `;
        localStorage.setItem('theme', 'light');
    }
}

async function loadLanguage() {
    const savedLanguage = localStorage.getItem('language') || 'pt';
    currentLanguage = savedLanguage;
    
    try {
        const response = await fetch(`/translations/${currentLanguage}`);
        const data = await response.json();
        
        if (data.success) {
            translations = data.translations;
            updateInterfaceLanguage();
        }
    } catch (error) {
        console.error('Erro ao carregar traduções:', error);
    }
}

function updateInterfaceLanguage() {
    // Atualizar textos da interface
    if (translations.new_chat) {
        document.getElementById('newChatText').textContent = translations.new_chat;
    }
    if (translations.connection) {
        document.getElementById('connectionSectionTitle').textContent = translations.connection;
    }
    if (translations.gemini_model) {
        document.getElementById('modelSectionTitle').textContent = translations.gemini_model;
    }
    if (translations.language) {
        document.getElementById('languageSectionTitle').textContent = translations.language;
    }
    if (translations.tools) {
        document.getElementById('toolsSectionTitle').textContent = translations.tools;
    }
    if (translations.welcome_message) {
        document.getElementById('welcomeMessage').textContent = translations.welcome_message;
    }
    if (translations.input_placeholder) {
        const textarea = document.getElementById('messageInput');
        textarea.placeholder = translations.input_placeholder;
        textarea.setAttribute('data-placeholder', translations.input_placeholder);
    }
    if (translations.connect) {
        document.getElementById('connectBtnText').textContent = translations.connect;
    }
    if (translations.disconnected) {
        document.getElementById('statusText').textContent = translations.disconnected;
    }
}

async function changeLanguage() {
    const languageSelect = document.getElementById('languageSelect');
    const selectedLanguage = languageSelect.value;
    
    if (selectedLanguage !== currentLanguage) {
        currentLanguage = selectedLanguage;
        localStorage.setItem('language', currentLanguage);
        
        await loadLanguage();
    }
}

// Load theme preference
function loadThemePreference() {
    const theme = localStorage.getItem('theme');
    const html = document.documentElement;
    const toggle = document.getElementById('darkModeToggle');
    
    if (theme === 'light') {
        html.setAttribute('data-theme', 'light');
        toggle.innerHTML = `
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
        `;
    } else {
        html.removeAttribute('data-theme');
        toggle.innerHTML = `
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
        `;
    }
}

// Model information
const MODEL_INFO = {
    "gemini-1.5-flash": {
        name: "Gemini 1.5 Flash",
        description: "Modelo rápido e eficiente para tarefas gerais"
    },
    "gemini-1.5-pro": {
        name: "Gemini 1.5 Pro",
        description: "Modelo avançado para tarefas complexas"
    },
    "gemini-1.0-pro": {
        name: "Gemini 1.0 Pro",
        description: "Modelo estável e confiável"
    },
    "gemini-pro": {
        name: "Gemini Pro",
        description: "Modelo versátil para diversas aplicações"
    },
    "gemini-2.0-flash-lite": {
        name: "Gemini 2.0 Flash Lite",
        description: "Modelo ultra-rápido e leve para tarefas simples"
    },
    "gemini-2.0-flash": {
        name: "Gemini 2.0 Flash",
        description: "Modelo rápido da nova geração para tarefas gerais"
    },
    "gemini-2.5-flash-lite": {
        name: "Gemini 2.5 Flash Lite",
        description: "Versão lite do modelo mais recente, otimizada para velocidade"
    },
    "gemini-2.5-flash": {
        name: "Gemini 2.5 Flash",
        description: "Modelo mais recente e rápido para tarefas avançadas"
    },
    "gemini-2.5-pro": {
        name: "Gemini 2.5 Pro",
        description: "Modelo mais avançado da nova geração para tarefas complexas"
    }
};

// Change model function
async function changeModel() {
    const modelSelect = document.getElementById('modelSelect');
    const modelInfo = document.getElementById('modelInfo');
    const selectedModel = modelSelect.value;
    
    // Update model info
    if (MODEL_INFO[selectedModel]) {
        modelInfo.innerHTML = `<small>${MODEL_INFO[selectedModel].description}</small>`;
    }
    
    try {
        const response = await fetch('/set-model', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ model: selectedModel })
        });

        const data = await response.json();
        
        if (data.success) {
            showConnectionStatus(data.message + " (sincronizado com servidor)");
        } else {
            showConnectionStatus(`Erro ao alterar modelo: ${data.error}`, true);
        }
    } catch (error) {
        showConnectionStatus(`Erro de rede: ${error.message}`, true);
    }
}

// Load current model
async function loadCurrentModel() {
    try {
        const response = await fetch('/models');
        const data = await response.json();
        
        const modelSelect = document.getElementById('modelSelect');
        const modelInfo = document.getElementById('modelInfo');
        
        if (data.current_model) {
            modelSelect.value = data.current_model;
            
            if (MODEL_INFO[data.current_model]) {
                modelInfo.innerHTML = `<small>${MODEL_INFO[data.current_model].description}</small>`;
            }
        }
    } catch (error) {
        console.log('Erro ao carregar modelo atual:', error);
    }
}

// Initialize when page loads
document.addEventListener('DOMContentLoaded', function() {
    // Verificar status quando a página carrega
    checkStatus();
    
    // Load theme preference
    loadThemePreference();
    
    // Load current model
    loadCurrentModel();
    
    // Load conversations
    loadConversations();
    
    // Focus on input when page loads
    const messageInput = document.getElementById('messageInput');
    if (messageInput) {
        messageInput.focus();
    }
});

// Conversation management
let conversations = [];
let currentConversationId = null;

// Load conversations from localStorage
function loadConversations() {
    const saved = localStorage.getItem('conversations');
    if (saved) {
        conversations = JSON.parse(saved);
        renderConversations();
    }
}

// Save conversations to localStorage
function saveConversations() {
    localStorage.setItem('conversations', JSON.stringify(conversations));
}

// Create a new conversation
function createNewConversation() {
    const conversationId = Date.now().toString();
    const conversation = {
        id: conversationId,
        title: 'Nova conversa',
        date: new Date().toLocaleDateString(),
        messages: []
    };
    
    conversations.unshift(conversation);
    saveConversations();
    renderConversations();
    
    return conversationId;
}

// Render conversations list
function renderConversations() {
    const conversationsList = document.getElementById('conversationsList');
    if (!conversationsList) return;
    
    conversationsList.innerHTML = conversations.map(conversation => `
        <div class="conversation-item ${conversation.id === currentConversationId ? 'active' : ''}" 
             onclick="loadConversation('${conversation.id}')">
            <div class="conversation-info">
                <div class="conversation-title">${conversation.title}</div>
                <div class="conversation-date">${conversation.date}</div>
            </div>
            <button class="conversation-delete" onclick="deleteConversation('${conversation.id}', event)">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2m3 0v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6h14z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
            </button>
        </div>
    `).join('');
}

// Load a specific conversation
function loadConversation(conversationId) {
    const conversation = conversations.find(c => c.id === conversationId);
    if (!conversation) return;
    
    currentConversationId = conversationId;
    
    // Clear current messages
    const messagesContainer = document.getElementById('chatMessages');
    messagesContainer.innerHTML = '';
    
    // Load conversation messages
    conversation.messages.forEach(message => {
        addMessage(message.content, message.isUser, false);
    });
    
    // Update active conversation in list
    renderConversations();
}

// Delete a conversation
function deleteConversation(conversationId, event) {
    event.stopPropagation();
    
    if (confirm('Tem certeza que deseja apagar esta conversa?')) {
        conversations = conversations.filter(c => c.id !== conversationId);
        
        if (currentConversationId === conversationId) {
            currentConversationId = null;
            // Clear messages
            const messagesContainer = document.getElementById('chatMessages');
            messagesContainer.innerHTML = `
                <div class="message assistant">
                    <div class="message-avatar">
                        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z" fill="currentColor"/>
                        </svg>
                    </div>
                    <div class="message-content">
                        <div class="message-text" id="welcomeMessage">
                            Olá! Sou o seu assistente MCP. Conecte-se ao servidor para começar a fazer perguntas.
                        </div>
                    </div>
                </div>
            `;
        }
        
        saveConversations();
        renderConversations();
    }
}

// Save current conversation
function saveCurrentConversation() {
    if (!currentConversationId) {
        currentConversationId = createNewConversation();
    }
    
    const conversation = conversations.find(c => c.id === currentConversationId);
    if (!conversation) return;
    
    // Get all messages from the chat
    const messagesContainer = document.getElementById('chatMessages');
    const messageElements = messagesContainer.querySelectorAll('.message');
    
    conversation.messages = [];
    messageElements.forEach(element => {
        const isUser = element.classList.contains('user');
        const content = element.querySelector('.message-text').textContent;
        conversation.messages.push({
            content: content,
            isUser: isUser
        });
    });
    
    // Update title based on first user message
    if (conversation.messages.length > 0) {
        const firstUserMessage = conversation.messages.find(m => m.isUser);
        if (firstUserMessage) {
            conversation.title = firstUserMessage.content.substring(0, 30) + (firstUserMessage.content.length > 30 ? '...' : '');
        }
    }
    
    saveConversations();
    renderConversations();
}

// Mobile menu toggle
function toggleMobileMenu() {
    const sidebar = document.getElementById('sidebar');
    sidebar.classList.toggle('open');
} 
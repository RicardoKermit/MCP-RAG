let isConnected = false;
let currentLanguage = 'pt';

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

function updateStatus(connected, message) {
    const indicator = document.getElementById('statusIndicator');
    const statusText = document.getElementById('statusText');
    
    isConnected = connected;
    indicator.className = connected ? 'status-indicator connected' : 'status-indicator';
    statusText.textContent = message;
    
    document.getElementById('sendButton').disabled = !connected;
    document.getElementById('connectButton').disabled = connected;
}

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
        typewriterEffect(messageText, content);
    } else {
        // Formatar o conteúdo se for do assistente
        if (isUser) {
            messageText.textContent = content;
        } else {
            messageText.innerHTML = formatMessage(content);
        }
    }
}

function typewriterEffect(element, text, speed = 30) {
    let i = 0;
    const originalText = text;
    
    function typeChar() {
        if (i < originalText.length) {
            element.innerHTML = formatMessage(originalText.substring(0, i + 1));
            i++;
            setTimeout(typeChar, speed);
        }
    }
    
        typeChar();
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
            updateStatus(true, translations.connected || 'Conectado');
            showConnectionStatus(translations.connection_success || 'Conectado com sucesso ao servidor MCP!');
            showToolsInfo(data.tools);
        } else {
            // Reset to disconnected state
            connectButton.classList.remove('connecting', 'connected');
            btnText.textContent = translations.connect || 'Conectar';
            updateStatus(false, translations.connection_error || 'Erro de conexão');
            showConnectionStatus(`${translations.connection_error || 'Erro ao conectar'}: ${data.error}`, true);
        }
    } catch (error) {
        // Reset to disconnected state
        connectButton.classList.remove('connecting', 'connected');
        btnText.textContent = translations.connect || 'Conectar';
        updateStatus(false, translations.connection_error || 'Erro de conexão');
        showConnectionStatus(`${translations.connection_error || 'Erro de rede'}: ${error.message}`, true);
    } finally {
        connectButton.disabled = false;
    }
}

async function sendMessage() {
    const input = document.getElementById('messageInput');
    const message = input.value.trim();
    
    if (!message || !isConnected) return;

    // Adiciona mensagem do usuário
    addMessage(message, true);
    input.value = '';
    
    // Reset textarea height
    autoResizeTextarea(input);

    // Mostra loading no botão
    const sendButton = document.getElementById('sendButton');
    const originalContent = sendButton.innerHTML;
    
    sendButton.disabled = true;
    sendButton.innerHTML = `
        <div class="btn-loading" style="width: 16px; height: 16px; border: 2px solid transparent; border-top: 2px solid white; border-radius: 50%; animation: spin 1s linear infinite;"></div>
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
            })
        });

        const data = await response.json();
        addMessage(data.response, false, true); // true para ativar efeito de digitação
    } catch (error) {
        const errorMsg = translations.error_processing || 'Erro ao processar a pergunta:';
        addMessage(`${errorMsg} ${error.message}`);
    } finally {
        sendButton.disabled = false;
        sendButton.innerHTML = originalContent;
    }
}

function handleKeyPress(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
    }
}

// Nova conversa
function newChat() {
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
        if (data.connected) {
            updateStatus(true, translations.connected || 'Conectado');
            showToolsInfo(data.tools);
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
    
    // Focus on input when page loads
    const messageInput = document.getElementById('messageInput');
    if (messageInput) {
        messageInput.focus();
    }
}); 
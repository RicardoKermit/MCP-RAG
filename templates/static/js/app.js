let isConnected = false;

// Configurar marked para formatação
marked.setOptions({
    breaks: true,
    gfm: true
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
    toolsList.textContent = tools.join(', ');
    toolsInfo.style.display = 'block';
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

function addMessage(content, isUser = false) {
    const messagesContainer = document.getElementById('chatMessages');
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${isUser ? 'user' : 'assistant'}`;
    
    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    avatar.textContent = isUser ? 'U' : 'AI';
    
    const messageContent = document.createElement('div');
    messageContent.className = 'message-content';
    
    // Formatar o conteúdo se for do assistente
    if (isUser) {
        messageContent.textContent = content;
    } else {
        messageContent.innerHTML = formatMessage(content);
    }
    
    const time = document.createElement('div');
    time.className = 'message-time';
    time.textContent = new Date().toLocaleTimeString();
    
    messageContent.appendChild(time);
    messageDiv.appendChild(avatar);
    messageDiv.appendChild(messageContent);
    
    messagesContainer.appendChild(messageDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

async function connectToServer() {
    const serverPath = document.getElementById('serverPath').value;
    if (!serverPath) {
        showConnectionStatus('Por favor, especifique o caminho do servidor.', true);
        return;
    }

    const connectButton = document.getElementById('connectButton');
    connectButton.disabled = true;
    connectButton.textContent = 'Conectando...';

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
            updateStatus(true, 'Conectado');
            showConnectionStatus('Conectado com sucesso ao servidor MCP!');
            showToolsInfo(data.tools);
        } else {
            updateStatus(false, 'Erro de conexão');
            showConnectionStatus(`Erro ao conectar: ${data.error}`, true);
        }
    } catch (error) {
        updateStatus(false, 'Erro de conexão');
        showConnectionStatus(`Erro de rede: ${error.message}`, true);
    } finally {
        connectButton.disabled = false;
        connectButton.textContent = 'Conectar';
    }
}

async function sendMessage() {
    const input = document.getElementById('messageInput');
    const message = input.value.trim();
    
    if (!message || !isConnected) return;

    // Adiciona mensagem do usuário
    addMessage(message, true);
    input.value = '';

    // Mostra loading
    const sendButton = document.getElementById('sendButton');
    const sendButtonText = document.getElementById('sendButtonText');
    const sendButtonLoading = document.getElementById('sendButtonLoading');
    
    sendButton.disabled = true;
    sendButtonText.style.display = 'none';
    sendButtonLoading.style.display = 'inline-block';

    try {
        const response = await fetch('/query', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ query: message })
        });

        const data = await response.json();
        addMessage(data.response);
    } catch (error) {
        addMessage(`Erro ao processar a pergunta: ${error.message}`);
    } finally {
        sendButton.disabled = false;
        sendButtonText.style.display = 'inline';
        sendButtonLoading.style.display = 'none';
    }
}

function handleKeyPress(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
    }
}

// Verificar status inicial
async function checkStatus() {
    try {
        const response = await fetch('/status');
        const data = await response.json();
        if (data.connected) {
            updateStatus(true, 'Conectado');
            showToolsInfo(data.tools);
        }
    } catch (error) {
        console.log('Erro ao verificar status:', error);
    }
}

// Dark mode functionality
function toggleDarkMode() {
    const body = document.body;
    const toggle = document.getElementById('darkModeToggle');
    
    if (body.classList.contains('dark-mode')) {
        body.classList.remove('dark-mode');
        toggle.innerHTML = '🌙';
        localStorage.setItem('darkMode', 'false');
    } else {
        body.classList.add('dark-mode');
        toggle.innerHTML = '☀️';
        localStorage.setItem('darkMode', 'true');
    }
}

// Load dark mode preference
function loadDarkModePreference() {
    const darkMode = localStorage.getItem('darkMode');
    const toggle = document.getElementById('darkModeToggle');
    
    if (darkMode === 'true') {
        document.body.classList.add('dark-mode');
        toggle.innerHTML = '☀️';
    }
}

// Initialize when page loads
document.addEventListener('DOMContentLoaded', function() {
    // Verificar status quando a página carrega
    checkStatus();
    
    // Load preferences when page loads
    loadDarkModePreference();
}); 
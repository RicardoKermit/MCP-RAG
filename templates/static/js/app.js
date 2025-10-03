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

// Logout function
function logout() {
    showLogoutModal();
}

// Show logout modal
function showLogoutModal() {
    const modal = document.getElementById('logoutModal');
    modal.classList.add('show');
}

// Close logout modal
function closeLogoutModal() {
    const modal = document.getElementById('logoutModal');
    modal.classList.remove('show');
}

// Confirm logout
function confirmLogout() {
    window.location.href = '/logout';
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
    
    // Modal de ajuda - fechar ao clicar fora
    const helpModal = document.getElementById('helpModal');
    if (helpModal) {
        helpModal.addEventListener('click', function(e) {
            if (e.target === helpModal) {
                toggleHelpModal();
            }
        });
    }
    
    // Modal de logout - fechar ao clicar fora
    const logoutModal = document.getElementById('logoutModal');
    if (logoutModal) {
        logoutModal.addEventListener('click', function(e) {
            if (e.target === logoutModal) {
                closeLogoutModal();
            }
        });
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
    const toolsList = document.getElementById('toolsList');
    
    if (tools && tools.length > 0) {
        toolsList.innerHTML = tools.map(tool => `<div class="tool-item">${tool}</div>`).join('');
    }
}

function toggleHelpModal() {
    const modal = document.getElementById('helpModal');
    if (modal.classList.contains('show')) {
        modal.classList.remove('show');
    } else {
        modal.classList.add('show');
    }
}

async function changeLanguage() {
    const languageSelect = document.getElementById('languageSelect');
    const selectedLanguage = languageSelect.value;
    
    console.log('Mudando idioma de', currentLanguage, 'para', selectedLanguage);
    
    if (selectedLanguage !== currentLanguage) {
        currentLanguage = selectedLanguage;
        localStorage.setItem('language', currentLanguage);
        
        await loadLanguage();
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

async function addMessage(content, isUser = false, typewriter = false, skipSave = false) {
    const messagesContainer = document.getElementById('chatMessages');
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${isUser ? 'user' : 'assistant'}`;

    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';

    if (isUser) {
        avatar.textContent = 'U';
    } else {
        avatar.innerHTML = `
            <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
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

    // Scroll para o fim
    messagesContainer.scrollTop = messagesContainer.scrollHeight;

    if (typewriter && !isUser) {
        currentTypewriterClear = typewriterEffect(messageText, content);
    } else {
        if (isUser) {
            messageText.textContent = content;
        } else {
            messageText.innerHTML = formatMessage(content);
        }
    }

    // 🔄 Guardar no backend apenas se não for carregamento histórico
    if (!skipSave) {
        try {
            const res = await fetch(`/conversations/${currentConversationId}/messages`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    role: isUser ? "user" : "assistant",
                    content: content
                })
            });
            const data = await res.json();
            if (!data.success) {
                console.error("Erro ao guardar mensagem:", data.error);
            }
        } catch (err) {
            console.error("Erro de rede ao guardar mensagem:", err);
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
    
    console.log("message", message);
    
    if (!message || !isConnected || isGenerating) return;

    // Create new conversation if none exists
    if (!currentConversationId) {
        //currentConversationId = await createNewConversation("message");
        // --- Início da Modificação ---

        // 1. Define o comprimento máximo para o título
        let conversationTitle;

        // 2. Cria o título curto a partir da mensagem completa
        if (message.length > 20) {
            conversationTitle = message.slice(0, 20) + "...";
        } else {
            conversationTitle = message;
        }

        // 3. Usa o título curto para criar a conversa
        currentConversationId = await createNewConversation(conversationTitle);
        
        // --- Fim da Modificação ---
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
            <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M6 6h12v12H6z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
        `;

    let data = null;
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
        console.log("data", data);
        // 👉 Se vier um download_url, dispara o download
        if (data.download_url && typeof data.download_url === "string" && data.download_url.trim() !== "") {
            const url = window.location.origin + data.download_url; // 👈 constrói o URL completo
            console.log("Download URL:", url);
        
            const a = document.createElement('a');
            a.href = url;
            a.download = "";
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
        }
        

        addMessage(data.response, false, true); // true para ativar efeito de digitação

        
        
        // Save conversation after successful response
        //saveCurrentConversation();
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
            <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
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

async function newChat() {
    // Criar conversa na BD e esperar pelo UUID
    currentConversationId = await createNewConversation();

    const messagesContainer = document.getElementById('chatMessages');
    const welcomeMessage = 'Nova conversa iniciada. Como posso ajudá-lo hoje?';

    messagesContainer.innerHTML = `
        <div class="message assistant">
            <div class="message-avatar">
                <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z" fill="currentColor"/>
                </svg>
            </div>
            <div class="message-content">
                <div class="message-text">${welcomeMessage}</div>
            </div>
        </div>
    `;

    console.log("✅ currentConversationId resolvido:", currentConversationId);
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
    const logo = document.getElementById('appLogo');
    
    if (html.getAttribute('data-theme') === 'light') {
        html.removeAttribute('data-theme');
        toggle.innerHTML = `
            <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
        `;
        localStorage.setItem('theme', 'dark');

        // trocar para logotipo branco
        logo.src = "/static/images/icon_white.png";

    } else {
        html.setAttribute('data-theme', 'light');
        toggle.innerHTML = `
            <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
        `;
        localStorage.setItem('theme', 'light');

        // voltar ao logotipo normal
        logo.src = "/static/images/icon.png";
    }
}


async function loadLanguage() {
    const savedLanguage = localStorage.getItem('language') || 'pt';
    currentLanguage = savedLanguage;
    
    try {
        console.log('Carregando traduções para:', currentLanguage);
        const response = await fetch(`/translations/${currentLanguage}`);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        console.log('Resposta do servidor:', data);
        
        if (data.success) {
            translations = data.translations;
            console.log('Traduções carregadas:', Object.keys(translations));
            updateInterfaceLanguage();
        } else {
            console.error('Erro na resposta do servidor:', data.error);
        }
    } catch (error) {
        console.error('Erro ao carregar traduções:', error);
        // Fallback para traduções básicas
        translations = {
            new_chat: currentLanguage === 'pt' ? 'Nova conversa' : 'New chat',
            connection: currentLanguage === 'pt' ? '🔗 Conexão' : '🔗 Connection',
            gemini_model: currentLanguage === 'pt' ? '🤖 Modelo Gemini' : '🤖 Gemini Model',
            language: currentLanguage === 'pt' ? '🌐 Idioma' : '🌐 Language',
            welcome_message: currentLanguage === 'pt' ? 'Olá! Sou o seu assistente MCP. Conecte-se ao servidor para começar a fazer perguntas.' : 'Hello! I\'m your MCP assistant. Connect to the server to start asking questions.',
            input_placeholder: currentLanguage === 'pt' ? 'Digite a sua mensagem...' : 'Type your message...',
            connect: currentLanguage === 'pt' ? 'Conectar ao servidor' : 'Connect to server',
            disconnected: currentLanguage === 'pt' ? 'Desconectado' : 'Disconnected'
        };
        updateInterfaceLanguage();
    }
}

function updateInterfaceLanguage() {
    try {
        console.log('Atualizando interface para idioma:', currentLanguage);
        console.log('Traduções disponíveis:', Object.keys(translations));
        
    // Atualizar textos da interface
    if (translations.new_chat) {
            const newChatText = document.getElementById('newChatText');
            if (newChatText) newChatText.textContent = translations.new_chat;
    }
    if (translations.connection) {
            const connectionSection = document.getElementById('connectionSectionTitle');
            if (connectionSection) connectionSection.textContent = translations.connection;
    }
    if (translations.gemini_model) {
            const modelSection = document.getElementById('modelSectionTitle');
            if (modelSection) modelSection.textContent = translations.gemini_model;
    }
    if (translations.language) {
            const languageSection = document.getElementById('languageSectionTitle');
            if (languageSection) languageSection.textContent = translations.language;
    }
    if (translations.tools) {
            const toolsSection = document.getElementById('toolsSectionTitle');
            if (toolsSection) toolsSection.textContent = translations.tools;
    }
    if (translations.welcome_message) {
            const welcomeMessage = document.getElementById('welcomeMessage');
            if (welcomeMessage) welcomeMessage.textContent = translations.welcome_message;
    }
    if (translations.input_placeholder) {
        const textarea = document.getElementById('messageInput');
            if (textarea) {
        textarea.placeholder = translations.input_placeholder;
        textarea.setAttribute('data-placeholder', translations.input_placeholder);
            }
    }
    if (translations.connect) {
            const connectBtnText = document.getElementById('connectBtnText');
            if (connectBtnText) connectBtnText.textContent = translations.connect;
    }
    if (translations.disconnected) {
            const statusText = document.getElementById('statusText');
            if (statusText) statusText.textContent = translations.disconnected;
        }
        
        // Atualizar placeholders
        if (translations.server_path_placeholder) {
            const serverPath = document.getElementById('serverPath');
            if (serverPath) serverPath.placeholder = translations.server_path_placeholder;
        }
        
        if (translations.connect_first) {
            const messageInput = document.getElementById('messageInput');
            if (messageInput && !isConnected) {
                messageInput.placeholder = translations.connect_first;
            }
        }
        
        // Atualizar títulos dos botões
        if (translations.clear_history_title) {
            const clearHistoryBtn = document.querySelector('.clear-history-btn');
            if (clearHistoryBtn) clearHistoryBtn.title = translations.clear_history_title;
        }
        if (translations.logout_title) {
            const logoutBtn = document.querySelector('.logout-btn');
            if (logoutBtn) logoutBtn.title = translations.logout_title;
        }
        if (translations.menu_title) {
            const mobileMenuToggle = document.getElementById('mobileMenuToggle');
            if (mobileMenuToggle) mobileMenuToggle.title = translations.menu_title;
        }
        if (translations.help_title) {
            const helpToggle = document.getElementById('helpToggle');
            if (helpToggle) helpToggle.title = translations.help_title;
        }
        if (translations.statistics) {
            const statsToggle = document.getElementById('statsToggle');
            if (statsToggle) statsToggle.title = translations.statistics;
        }
        if (translations.dark_mode) {
            const darkModeToggle = document.getElementById('darkModeToggle');
            if (darkModeToggle) darkModeToggle.title = translations.dark_mode;
        }
        
        // Atualizar seções
        if (translations.conversations) {
            const conversationsSection = document.getElementById('conversationsSectionTitle');
            if (conversationsSection) conversationsSection.textContent = translations.conversations;
        }
        
        
        // Atualizar descrição do modelo atual
        updateModelDescription();
        
        // Atualizar footer
        if (translations.mcp_client_interface) {
            const footer = document.querySelector('.input-footer small');
            if (footer) footer.textContent = translations.mcp_client_interface;
        }
        
        // Atualizar modais
        updateModalTranslations();
        
        console.log('Interface atualizada com sucesso');
    } catch (error) {
        console.error('Erro ao atualizar interface:', error);
    }
}


function updateModalTranslations() {
    try {
        // Atualizar modal de ajuda
        if (translations.available_tools) {
            const helpModalTitle = document.querySelector('#helpModal h3');
            if (helpModalTitle) helpModalTitle.textContent = translations.available_tools;
        }
        
        // Atualizar modal de logout
        if (translations.logout_modal_title) {
            const logoutModalTitle = document.querySelector('#logoutModal h3');
            if (logoutModalTitle) logoutModalTitle.textContent = translations.logout_modal_title;
        }
        if (translations.logout_confirm_message) {
            const logoutMessage = document.querySelector('.logout-message');
            if (logoutMessage) logoutMessage.textContent = translations.logout_confirm_message;
        }
        if (translations.logout_redirect_message) {
            const logoutSubtitle = document.querySelector('.logout-subtitle');
            if (logoutSubtitle) logoutSubtitle.textContent = translations.logout_redirect_message;
        }
        if (translations.cancel) {
            const cancelBtn = document.querySelector('.logout-cancel-btn');
            if (cancelBtn) cancelBtn.textContent = translations.cancel;
        }
        if (translations.confirm_logout) {
            const confirmBtn = document.querySelector('.logout-confirm-btn');
            if (confirmBtn) confirmBtn.textContent = translations.confirm_logout;
        }
    } catch (error) {
        console.error('Erro ao atualizar traduções dos modais:', error);
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
            <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
        `;
    } else {
        html.removeAttribute('data-theme');
        toggle.innerHTML = `
            <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
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
    },
    // OpenAI
    "gpt-3.5-turbo": {
        name: "GPT-3.5 Turbo",
        description: "Modelo rápido e económico da OpenAI"
    },
    "gpt-4o": {
        name: "GPT-4o",
        description: "Modelo multimodal otimizado da OpenAI"
    },
    "gpt-4o-mini": {
        name: "GPT-4o Mini",
        description: "Versão mais leve e barata do GPT-4o"
    },
    "gpt-4.1": {
        name: "GPT-4.1",
        description: "Modelo avançado com contexto extenso"
    },

    // Ollama
    "llama3": {
        name: "LLaMA 3 (8B)",
        description: "Modelo base Meta LLaMA 3 com 8B parâmetros"
    },
    "llama3-70b": {
        name: "LLaMA 3 (70B)",
        description: "Modelo maior, melhor raciocínio mas pesado"
    },
    "mistral": {
        name: "Mistral 7B",
        description: "Modelo rápido e eficiente em máquinas locais"
    },
    "codellama": {
        name: "CodeLLaMA",
        description: "Modelo otimizado para programação e código"
    },
    "gemma": {
        name: "Gemma 7B",
        description: "Modelo Google leve para uso local"
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

// Load and change RAG backend
async function loadRagBackend() {
    try {
        const response = await fetch('/rag-backend');
        const data = await response.json();
        const select = document.getElementById('ragBackendSelect');
        
        if (data && data.response && select) {
            console.log("Value: ",select.value)
            console.log("data: ",data.response)
            select.value = data.response;
        }
    } catch (e) {
        console.log('Erro ao carregar backend RAG:', e);
    }
}

async function changeRagBackend() {
    const select = document.getElementById('ragBackendSelect');
    const backend = select.value;
    try {
        const response = await fetch('/set-rag-backend', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ backend })
        });
        const data = await response.json();

        let backendName;
        if (data.backend) {
            backendName = data.backend;
        } else if (data.message) {
            try {
                // tentar extrair JSON de dentro de message
                const innerJson = data.message.match(/\{.*\}/s);
                if (innerJson) {
                    const parsed = JSON.parse(innerJson[0]);
                    backendName = parsed.backend;
                }
            } catch (e) {
                console.error("Erro a parsear backend:", e);
            }
        }

        if (backendName) {
            showConnectionStatus(`Backend RAG alterado para: ${backendName}`);
        } else {
            showConnectionStatus(`Erro ao alterar backend RAG: ${data.error || 'desconhecido'}`, true);
        }
    } catch (e) {
        showConnectionStatus(`Erro de rede ao alterar backend RAG: ${e.message}`, true);
    }
}


// Function to check if user is authenticated
async function checkAuthentication() {
    try {
        const response = await fetch('/status');
        
        // If we get a 401 or 403, redirect to login
        if (response.status === 401 || response.status === 403) {
            window.location.href = '/login';
            return false;
        }
        
        // If we can't access the status endpoint, redirect to login
        if (!response.ok) {
            window.location.href = '/login';
            return false;
        }
        
        // If we get here, user is authenticated
        console.log('✅ Utilizador autenticado');
        return true;
        
    } catch (error) {
        console.error('❌ Erro ao verificar autenticação:', error);
        // If there's any error, redirect to login for safety
        window.location.href = '/login';
        return false;
    }
}

// Initialize when page loads
document.addEventListener('DOMContentLoaded', function() {
    // Check authentication first
    checkAuthentication().then(isAuthenticated => {
        if (isAuthenticated) {
            // Verificar status quando a página carrega
            checkStatus();
            
            // Load theme preference
            loadThemePreference();
            
            // Load current model
            loadCurrentModel();
            // Load RAG backend
            loadRagBackend();
            
            // Load conversations
            loadConversations();
            
            // Focus on input when page loads
            const messageInput = document.getElementById('messageInput');
            if (messageInput) {
                messageInput.focus();
            }
        }
    });
});

// Conversation management
let conversations = [];
let currentConversationId = null;

async function loadConversations() {
    try {
        const res = await fetch("/conversations");
        const data = await res.json();

        if (data.success) {
            // Guardar em memória (não é localStorage, apenas variável global)
            conversations = data.conversations || [];

            // Renderizar na UI
            renderConversations(conversations);
        } else {
            console.error("❌ Erro a carregar conversas:", data.error);
        }
    } catch (err) {
        console.error("❌ Erro de rede ao carregar conversas:", err);
    }
}


async function loadMessages(conversationId) {
    try {
        const res = await fetch(`/conversations/${conversationId}/messages`);
        const data = await res.json();

        if (data.success) {
            // Guardar conversa ativa globalmente
            currentConversationId = conversationId;

            // Limpar chat antes de desenhar
            const messagesContainer = document.getElementById('chatMessages');
            messagesContainer.innerHTML = '';

            // Renderizar mensagens desta conversa
            renderMessages(data.messages);
        } else {
            console.error("❌ Erro a carregar mensagens:", data.error);
        }
    } catch (err) {
        console.error("❌ Erro de rede ao carregar mensagens:", err);
    }
}

function renderMessages(messages) {
    const messagesContainer = document.getElementById('chatMessages');
    messagesContainer.innerHTML = '';

    messages.forEach(msg => {
        // 👉 skipSave = true para não gravar outra vez no backend
        addMessage(msg.content, msg.role === "user", false, true);
    });

    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}


// Save conversations to localStorage
function saveConversations() {
    localStorage.setItem('conversations', JSON.stringify(conversations));
}

async function createNewConversation(title = "Nova conversa") {
    try {
        const res = await fetch("/conversations", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ title })
        });
        const data = await res.json();

        if (data.success) {
            // ✅ recarregar conversas da BD em vez de manipular array local
            await loadConversations();
            return data.id;
        } else {
            console.error("❌ Erro ao criar conversa:", data.error);
            return null;
        }
    } catch (err) {
        console.error("❌ Erro de rede ao criar conversa:", err);
        return null;
    }
}



// Render conversations list
function renderConversations(conversations) {
    const conversationsList = document.getElementById('conversationsList');
    if (!conversationsList) return;

    conversationsList.innerHTML = conversations.map(conversation => {
        const title = conversation.title && conversation.title.trim() !== ""
            ? conversation.title
            : "Nova conversa";

        const date = conversation.updated_at
            ? new Date(conversation.updated_at).toLocaleString()
            : "";

        return `
            <div class="conversation-item ${conversation.id === currentConversationId ? 'active' : ''}" 
                 onclick="loadMessages('${conversation.id}')">
                <div class="conversation-info">
                    <div class="conversation-title">${title}</div>
                    <div class="conversation-date">${date}</div>
                </div>
                <button class="conversation-delete" onclick="deleteConversation('${conversation.id}', event)">
                    <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2m3 0v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6h14z" 
                              stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                    </svg>
                </button>
            </div>
        `;
    }).join('');
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

// Apagar conversa na BD
async function deleteConversation(conversationId, event) {
    event.stopPropagation();

    if (confirm('Tem certeza que deseja apagar esta conversa?')) {
        try {
            const res = await fetch(`/conversations/${conversationId}`, {
                method: "DELETE"
            });
            const data = await res.json();

            if (data.success) {
                // Se a conversa apagada era a atual, limpar o chat
                if (currentConversationId === conversationId) {
                    currentConversationId = null;
                    const messagesContainer = document.getElementById('chatMessages');
                    messagesContainer.innerHTML = `
                        <div class="message assistant">
                            <div class="message-avatar">
                                <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
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

                // Recarregar lista de conversas a partir da BD
                loadConversations();
            } else {
                console.error("Erro ao apagar conversa:", data.error);
            }
        } catch (err) {
            console.error("Erro de rede ao apagar conversa:", err);
        }
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

// Open statistics page
function openStatistics() {
    window.open('/stats/statistics-page-new', '_blank');
}

// Open statistics page
function openSettings() {
    /*window.open('/settings-page', '_blank');*/
    window.location.href="/settings-page"
}


// Função para atualizar a descrição do modelo atual com base no idioma
function updateModelDescription() {
    try {
        const modelSelect = document.getElementById('modelSelect');
        const modelInfo = document.getElementById('modelInfo');
        
        if (modelSelect && modelInfo) {
            const selectedModel = modelSelect.value;
            
            // Mapear modelos para chaves de tradução
            const modelTranslationKeys = {
                'gemini-1.5-flash-8b': 'model_description_fast',
                'gemini-2.0-flash-lite': 'model_description_ultra_fast',
                'gemini-2.5-flash-lite': 'model_description_optimized',
                'gemini-1.5-flash': 'model_description_fast',
                'gemini-2.0-flash': 'model_description_next_gen',
                'gemini-2.5-flash': 'model_description_latest',
                'gemini-2.0-pro': 'model_description_less_used',
                'gemini-1.5-pro': 'model_description_popular',
                'gemini-1.0-pro': 'model_description_first',
                'gemini-pro': 'model_description_base',
                'gemini-2.5-pro': 'model_description_top'
            };
            
            const translationKey = modelTranslationKeys[selectedModel];
            if (translationKey && translations[translationKey]) {
                modelInfo.innerHTML = `<small>${translations[translationKey]}</small>`;
            } else {
                // Fallback para descrição padrão
                const fallbackDescription = currentLanguage === 'pt' ? 
                    'Modelo rápido e eficiente para tarefas gerais' : 
                    'Fast and efficient model for general tasks';
                modelInfo.innerHTML = `<small>${fallbackDescription}</small>`;
            }
        }
    } catch (error) {
        console.error('Erro ao atualizar descrição do modelo:', error);
    }
}

async function loadSettings() {
    try {
      const modelResp = await fetch("/model"); // se já tiveres algo equivalente no client
      const modelData = await modelResp.json();
      if (modelData.success) {
        document.getElementById("modelSelect").value = modelData.model;
      }
  
      const ragResp = await fetch("/rag-backend"); // <-- usa o endpoint que já tens
      const ragData = await ragResp.json();
      if (ragData.success) {
        document.getElementById("ragBackendSelect").value = ragData.response;
      }
    } catch (e) {
      console.error("Erro a carregar settings:", e);
    }
}


function toggleSidebar() {
    document.getElementById("sidebar").classList.toggle("collapsed");
}

function addAssistantMessage(text, downloadUrl = null) {
  const chatMessages = document.getElementById("chatMessages");

  const msgDiv = document.createElement("div");
  msgDiv.className = "message assistant";

  const contentDiv = document.createElement("div");
  contentDiv.className = "message-content";

  const msgText = document.createElement("div");
  msgText.className = "message-text";
  msgText.innerText = text;

  contentDiv.appendChild(msgText);

  // 👉 Se houver link de download, adiciona ao chat
  if (downloadUrl) {
    const link = document.createElement("a");
    link.href = downloadUrl;
    link.innerText = "⬇️ Descarregar Quiz em GIFT";
    link.style.display = "block";
    link.style.marginTop = "8px";
    link.setAttribute("download", "");

    contentDiv.appendChild(link);
  }

  msgDiv.appendChild(contentDiv);
  chatMessages.appendChild(msgDiv);

  chatMessages.scrollTop = chatMessages.scrollHeight;
}

document.getElementById("pdfUpload").addEventListener("change", async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append("file", file);

    try {
        const resp = await fetch("/upload-temp", {
            method: "POST",
            body: formData
        });
        const data = await resp.json();

        if (data.success) {
            // Mostra ícone de PDF no chat
            addMessage(`📎 PDF carregado: ${data.filename}\n${data.message}`, false);
        } else {
            addMessage("❌ Erro ao carregar PDF: " + (data.error || "desconhecido"), false);
        }
    } catch (err) {
        addMessage("❌ Erro de rede ao carregar PDF", false);
    }
});

const fileInput = document.getElementById("fileInput");
const filePreview = document.getElementById("filePreview");
let selectedFiles = [];

fileInput.addEventListener("change", (e) => {
  for (let file of e.target.files) {
    if (file.type === "application/pdf") {
      selectedFiles.push(file);
      renderFileChips();
    }
  }
  fileInput.value = ""; // reset para permitir re-selecionar
});

function renderFileChips() {
  filePreview.innerHTML = "";
  selectedFiles.forEach((file, index) => {
    const chip = document.createElement("div");
    chip.classList.add("file-chip");
    chip.innerHTML = `
      <span>📄 ${file.name}</span>
      <button onclick="removeFile(${index})">❌</button>
    `;
    filePreview.appendChild(chip);
  });
}

function removeFile(index) {
  selectedFiles.splice(index, 1);
  renderFileChips();
}

  //window.onload = loadSettings;
  


# 🤖 MCP Client - Interface Web

Uma interface web moderna e elegante para o seu cliente MCP (Model Context Protocol) usando Flask e SocketIO.

## ✨ Características

- **Interface Moderna**: Design responsivo e elegante com gradientes e animações
- **Chat em Tempo Real**: Comunicação em tempo real com WebSocket
- **Conexão Dinâmica**: Conecte-se a diferentes servidores MCP
- **Indicador de Status**: Visualização clara do estado da conexão
- **Lista de Ferramentas**: Mostra as ferramentas disponíveis no servidor
- **Responsivo**: Funciona perfeitamente em desktop e mobile

## 🚀 Instalação

1. **Instalar dependências**:
   ```bash
   pip install -r requirements_web.txt
   ```

2. **Configurar variáveis de ambiente**:
   Crie um arquivo `.env` com:
   ```
   GOOGLE_API_KEY=sua_chave_api_do_google
   ```

## 🎯 Como Usar

1. **Iniciar a aplicação**:
   ```bash
   python app.py
   ```

2. **Aceder à interface**:
   Abra o navegador e vá para `http://localhost:5000`

3. **Conectar ao servidor**:
   - Digite o caminho para o seu servidor MCP (ex: `MCP_Server.py`)
   - Clique em "Conectar"
   - Aguarde a confirmação da conexão

4. **Fazer perguntas**:
   - Digite a sua pergunta no campo de texto
   - Pressione Enter ou clique em "Enviar"
   - Aguarde a resposta do assistente

## 🎨 Interface

### Elementos Principais

- **Header**: Título e indicador de status da conexão
- **Formulário de Conexão**: Campo para especificar o servidor MCP
- **Informação de Ferramentas**: Lista das ferramentas disponíveis
- **Chat**: Área de conversação com histórico de mensagens
- **Input**: Campo para digitar perguntas

### Estados Visuais

- **Desconectado**: Indicador vermelho, botão de envio desabilitado
- **Conectado**: Indicador verde, chat ativo
- **Loading**: Animação de carregamento durante processamento
- **Erro**: Mensagens de erro em vermelho
- **Sucesso**: Mensagens de sucesso em verde

## 🔧 Configuração Avançada

### Alterar Porta
Edite o arquivo `app.py` na linha final:
```python
socketio.run(app, debug=True, host='0.0.0.0', port=5000)
```

### Personalizar Design
Edite o CSS no arquivo `templates/index.html` para personalizar cores, fontes e layout.

### Adicionar Novas Funcionalidades
- Adicione novas rotas no `app.py`
- Crie novos endpoints para funcionalidades específicas
- Integre com outros serviços via API

## 🛠️ Estrutura do Projeto

```
rag/
├── app.py                 # Aplicação Flask principal
├── templates/
│   └── index.html        # Template HTML da interface
├── requirements_web.txt   # Dependências da aplicação web
├── MCP_Client.py         # Cliente MCP original (CLI)
├── MCP_Server.py         # Servidor MCP
└── README_Web.md         # Este arquivo
```

## 🔍 Troubleshooting

### Erro de Conexão
- Verifique se o servidor MCP está acessível
- Confirme que o caminho do servidor está correto
- Verifique se todas as dependências estão instaladas

### Erro de API Key
- Certifique-se de que a `GOOGLE_API_KEY` está definida no `.env`
- Verifique se a chave é válida

### Problemas de WebSocket
- Verifique se a porta 5000 está livre
- Confirme que o firewall não está bloqueando a conexão

## 🎯 Exemplos de Uso

### Perguntas Típicas
- "O que é realidade virtual?"
- "Explica o conceito de RAG"
- "Quais são as vantagens da IA generativa?"

### Integração com PDFs
O sistema pode processar perguntas sobre documentos PDF carregados no servidor MCP.

## 📱 Compatibilidade

- ✅ Chrome/Chromium
- ✅ Firefox
- ✅ Safari
- ✅ Edge
- ✅ Mobile browsers

## 🔒 Segurança

- A aplicação roda localmente por padrão
- Não exponha a aplicação publicamente sem configuração adequada
- Use HTTPS em produção
- Configure autenticação se necessário

## 📈 Próximos Passos

- [ ] Adicionar autenticação de utilizadores
- [ ] Implementar histórico de conversas
- [ ] Adicionar upload de ficheiros
- [ ] Criar API REST completa
- [ ] Adicionar temas personalizáveis
- [ ] Implementar cache de respostas

---

**Desenvolvido com ❤️ usando Flask e SocketIO** 
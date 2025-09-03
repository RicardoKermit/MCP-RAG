# 🚀 Guia de Migração do Sistema de Logs

## 📋 O que foi feito

Este script migrou o sistema de logs de SQLite para PostgreSQL:

✅ **Backup** do sistema antigo criado
✅ **Novo sistema de logs** PostgreSQL implementado
✅ **Arquivos atualizados** criados
✅ **Configuração de ambiente** criada

## 🔄 Próximos Passos

### 1. Revisar os arquivos novos
- `MCP_Client_new.py` - Cliente MCP com PostgreSQL
- `MCP_Server_new.py` - Servidor MCP com PostgreSQL
- `postgres_logger.py` - Sistema de logs PostgreSQL
- `.env` - Configuração de ambiente

### 2. Testar o novo sistema
```bash
# Testar conexão PostgreSQL
python postgres_logger.py

# Verificar se as tabelas existem
python show_tables.py
```

### 3. Substituir arquivos antigos
```bash
# Fazer backup dos originais
mv MCP_Client.py MCP_Client_old.py
mv MCP_Server.py MCP_Server_old.py

# Usar os novos
mv MCP_Client_new.py MCP_Client.py
mv MCP_Server_new.py MCP_Server.py
```

### 4. Reiniciar aplicação
```bash
# Parar aplicação atual
# Iniciar com novo sistema
python MCP_Client.py
```

## 🆕 Novas Funcionalidades

### Sistema de Logs PostgreSQL
- **Logs estruturados** em base de dados
- **Métricas de performance** em tempo real
- **Estatísticas avançadas** de utilização
- **Fallback automático** para ficheiros
- **Limpeza automática** de logs antigos

### Tipos de Operações Logadas
- `rag_query` - Consultas RAG
- `quiz_generation` - Geração de questionários
- `video_generation` - Geração de vídeos
- `user_login/logout` - Autenticação
- `file_upload/download` - Operações de ficheiros
- `system_maintenance` - Manutenção do sistema

### Métricas de Sistema
- CPU e memória
- Utilização de disco
- Conexões ativas
- Tempo de resposta
- Throughput

## 🔧 Configuração

### Variáveis de Ambiente (.env)
- `DB_HOST` - Host PostgreSQL
- `DB_PORT` - Porta PostgreSQL
- `DB_NAME` - Nome da base de dados
- `DB_USER` - Utilizador
- `DB_PASSWORD` - Password

### Conexão à Base de Dados
- **Host**: localhost (ou rag_postgres em Docker)
- **Porta**: 5432
- **Base de dados**: rag_system
- **Utilizador**: rag_user
- **Password**: rag_password_secure_2024

## 📊 Monitorização

### pgAdmin
- **URL**: http://localhost:8080
- **Email**: admin@example.com
- **Password**: admin_password_2024

### Consultas Úteis
```sql
-- Ver logs recentes
SELECT * FROM operation_logs ORDER BY created_at DESC LIMIT 10;

-- Estatísticas por tipo de operação
SELECT operation_type, COUNT(*) FROM operation_logs GROUP BY operation_type;

-- Performance do sistema
SELECT * FROM performance_stats ORDER BY created_at DESC LIMIT 20;
```

## 🚨 Troubleshooting

### Se PostgreSQL não conectar
1. Verificar se Docker está a correr
2. Verificar se containers estão ativos: `docker-compose ps`
3. Verificar logs: `docker-compose logs postgres`

### Se aplicação não iniciar
1. Verificar dependências: `pip install -r requirements_postgres.txt`
2. Verificar ficheiro .env
3. Verificar logs de erro

### Fallback para Ficheiros
Se PostgreSQL falhar, o sistema automaticamente:
- Regista erros em ficheiros de log
- Continua a funcionar
- Tenta reconectar na próxima operação

## 📞 Suporte

Para problemas ou dúvidas:
1. Verificar logs em `logs/migration_logging.log`
2. Verificar logs do PostgreSQL
3. Verificar ficheiros de fallback

---
**Migração concluída em**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

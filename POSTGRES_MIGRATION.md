# 🐘 Migração para PostgreSQL - RAG System

## 📋 Visão Geral

Este documento descreve a migração do sistema RAG de SQLite para PostgreSQL, incluindo:

- **Base de dados robusta** com suporte a múltiplos utilizadores
- **Sistema de roles e permissões** completo
- **Logs estruturados** para auditoria e análise
- **Escalabilidade** para produção
- **Backup e recuperação** automáticos

## 🚀 Início Rápido

### 1. Pré-requisitos

```bash
# Instalar Docker e Docker Compose
# Windows: Docker Desktop
# Linux: docker.io + docker-compose
# macOS: Docker Desktop

# Verificar instalação
docker --version
docker-compose --version
```

### 2. Iniciar PostgreSQL

```bash
# Dar permissões de execução
chmod +x start_postgres.sh

# Iniciar serviços
./start_postgres.sh
```

### 3. Instalar Dependências

```bash
pip install -r requirements_postgres.txt
```

### 4. Migrar Dados (Opcional)

```bash
python migrate_to_postgres.py
```

## 🏗️ Arquitetura da Base de Dados

### Tabelas Principais

| Tabela | Descrição | Chave |
|--------|-----------|-------|
| `users` | Utilizadores do sistema | UUID |
| `roles` | Roles e permissões | SERIAL |
| `user_roles` | Relação many-to-many | Composite |
| `user_sessions` | Sessões ativas | UUID |
| `operation_logs` | Logs de operações | UUID |
| `conversations` | Conversas de chat | UUID |
| `quiz_generations` | Questionários gerados | UUID |
| `video_generations` | Vídeos gerados | UUID |

### Estrutura de Roles

```sql
-- Roles padrão
admin      - Acesso total ao sistema
user       - Utilizador regular
moderator  - Moderador de conteúdo
analyst    - Analista de dados
```

## 🔧 Configuração

### Variáveis de Ambiente

Copiar `env.example` para `.env` e configurar:

```bash
# Base de dados
DB_HOST=localhost
DB_PORT=5432
DB_NAME=rag_system
DB_USER=rag_user
DB_PASSWORD=rag_password_secure_2024

# Segurança
SECRET_KEY=your-super-secret-key
JWT_SECRET_KEY=your-jwt-secret-key
```

### Docker Compose

```yaml
services:
  postgres:
    image: postgres:15-alpine
    ports:
      - "5432:5432"
    environment:
      POSTGRES_DB: rag_system
      POSTGRES_USER: rag_user
      POSTGRES_PASSWORD: rag_password_secure_2024
  
  pgadmin:
    image: dpage/pgadmin4:latest
    ports:
      - "8080:80"
    environment:
      PGADMIN_DEFAULT_EMAIL: admin@rag.local
      PGADMIN_DEFAULT_PASSWORD: admin_password_2024
```

## 📊 Acesso à Base de Dados

### pgAdmin (Interface Web)

- **URL**: http://localhost:8080
- **Email**: admin@rag.local
- **Password**: admin_password_2024

### Conexão Direta

```bash
# Via psql
psql -h localhost -U rag_user -d rag_system

# Via Python
import psycopg2
conn = psycopg2.connect(
    host="localhost",
    database="rag_system",
    user="rag_user",
    password="rag_password_secure_2024"
)
```

## 🔄 Migração de Dados

### Script Automático

```bash
python migrate_to_postgres.py
```

### Migração Manual

```sql
-- 1. Criar backup
-- 2. Exportar dados SQLite
-- 3. Importar para PostgreSQL
-- 4. Verificar integridade
```

## 📈 Vantagens da Migração

### Antes (SQLite)
- ❌ Base de dados local
- ❌ Sem controlo de concorrência
- ❌ Limitações de escalabilidade
- ❌ Sem sistema de roles
- ❌ Logs básicos

### Depois (PostgreSQL)
- ✅ Base de dados robusta
- ✅ Controlo de concorrência avançado
- ✅ Escalabilidade horizontal
- ✅ Sistema de roles completo
- ✅ Logs estruturados
- ✅ Backup automático
- ✅ Replicação
- ✅ Particionamento

## 🛠️ Manutenção

### Backup Automático

```bash
# Backup diário
docker exec rag_postgres pg_dump -U rag_user rag_system > backup_$(date +%Y%m%d).sql

# Restore
docker exec -i rag_postgres psql -U rag_user rag_system < backup_20241201.sql
```

### Monitorização

```sql
-- Verificar tamanho da base de dados
SELECT pg_size_pretty(pg_database_size('rag_system'));

-- Verificar conexões ativas
SELECT count(*) FROM pg_stat_activity;

-- Verificar performance
SELECT * FROM system_statistics ORDER BY date DESC LIMIT 10;
```

### Limpeza

```sql
-- Limpar sessões expiradas
SELECT clean_expired_sessions();

-- Limpar logs antigos (manter últimos 30 dias)
DELETE FROM operation_logs WHERE created_at < NOW() - INTERVAL '30 days';
```

## 🚨 Troubleshooting

### Problemas Comuns

1. **PostgreSQL não inicia**
   ```bash
   docker-compose logs postgres
   docker-compose down && docker-compose up -d
   ```

2. **Erro de conexão**
   ```bash
   # Verificar se o serviço está a correr
   docker-compose ps
   
   # Verificar logs
   docker-compose logs -f postgres
   ```

3. **Erro de permissões**
   ```bash
   # Verificar ownership dos volumes
   sudo chown -R 999:999 postgres_data/
   ```

### Logs e Debug

```bash
# Ver logs em tempo real
docker-compose logs -f

# Ver logs específicos
docker-compose logs postgres
docker-compose logs pgadmin

# Aceder ao container
docker-compose exec postgres bash
```

## 🔒 Segurança

### Boas Práticas

1. **Alterar passwords padrão**
2. **Usar HTTPS em produção**
3. **Implementar rate limiting**
4. **Auditar acessos**
5. **Backup encriptado**

### Firewall

```bash
# Permitir apenas localhost
sudo ufw allow from 127.0.0.1 to any port 5432
sudo ufw deny 5432
```

## 📚 Recursos Adicionais

### Documentação
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Docker Compose](https://docs.docker.com/compose/)
- [SQLAlchemy](https://docs.sqlalchemy.org/)

### Ferramentas
- [pgAdmin](https://www.pgadmin.org/)
- [DBeaver](https://dbeaver.io/)
- [TablePlus](https://tableplus.com/)

### Monitorização
- [pg_stat_statements](https://www.postgresql.org/docs/current/pgstatstatements.html)
- [pgBadger](https://pgbadger.darold.net/)
- [Prometheus + Grafana](https://prometheus.io/)

## 🤝 Suporte

### Comunidade
- [PostgreSQL Community](https://www.postgresql.org/community/)
- [Stack Overflow](https://stackoverflow.com/questions/tagged/postgresql)

### Issues
- Criar issue no repositório
- Incluir logs e configuração
- Descrever passos para reproduzir

---

**Nota**: Esta migração é uma atualização significativa. Teste sempre em ambiente de desenvolvimento antes de aplicar em produção.

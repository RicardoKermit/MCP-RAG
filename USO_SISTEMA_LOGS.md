# 🚀 Guia de Uso do Sistema de Logs PostgreSQL

## 📋 Visão Geral

O sistema de logs foi migrado com sucesso de SQLite para PostgreSQL, oferecendo:

- **Logs estruturados** em base de dados robusta
- **Métricas de performance** em tempo real
- **Estatísticas avançadas** de utilização
- **Fallback automático** para ficheiros
- **Limpeza automática** de logs antigos

## 🔧 Como Usar

### 1. **Logging de Operações**

```python
from postgres_logger import PostgresLogger, OperationType

# Inicializar logger
logger = PostgresLogger({
    'host': 'localhost',
    'port': 5432,
    'database': 'rag_system',
    'user': 'rag_user',
    'password': 'rag_password_secure_2024'
})

# Log de operação RAG
logger.log_operation(
    operation_type=OperationType.RAG_QUERY,
    user_id="user_uuid_here",  # ou None para operações sem utilizador
    details={"query": "pergunta do utilizador", "model": "gemini-1.5-flash"},
    duration_ms=1500,
    status="success"
)

# Log de geração de questionário
logger.log_operation(
    operation_type=OperationType.QUIZ_GENERATION,
    user_id="user_uuid_here",
    details={"topic": "História de Portugal", "num_questions": 10},
    duration_ms=3000
)

# Log de erro
logger.log_operation(
    operation_type=OperationType.RAG_QUERY,
    user_id="user_uuid_here",
    status="error",
    error_message="API key inválida",
    duration_ms=500
)
```

### 2. **Logging de Interações de Utilizador**

```python
# Log de login
logger.log_user_interaction(
    user_id="user_uuid_here",
    action="user_login",
    details={"ip_address": "192.168.1.1", "user_agent": "Mozilla/5.0..."}
)

# Log de ação específica
logger.log_user_interaction(
    user_id="user_uuid_here",
    action="file_upload",
    details={"filename": "documento.pdf", "size_mb": 2.5}
)
```

### 3. **Métricas de Sistema**

```python
# Log de métricas de performance
logger.log_performance_metrics({
    'cpu_percent': 45.2,
    'memory_percent': 67.8,
    'disk_usage_percent': 23.1
})

# Ou usar a função automática
logger.log_system_metrics()
```

### 4. **Estatísticas e Relatórios**

```python
# Obter estatísticas dos últimos 30 dias
stats = logger.get_statistics(days=30)

# Estatísticas dos últimos 7 dias
weekly_stats = logger.get_statistics(days=7)

# Estatísticas personalizadas
custom_stats = logger.get_statistics(days=90)
```

## 📊 Estrutura dos Dados

### Tabela `operation_logs`
```sql
CREATE TABLE operation_logs (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    operation_type VARCHAR(100),
    operation_details JSONB,
    status VARCHAR(50),
    error_message TEXT,
    duration_ms INTEGER,
    created_at TIMESTAMP WITH TIME ZONE,
    ip_address INET,
    user_agent TEXT
);
```

### Tabela `user_interactions`
```sql
CREATE TABLE user_interactions (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    action VARCHAR(100),
    details JSONB,
    created_at TIMESTAMP WITH TIME ZONE,
    session_id UUID REFERENCES user_sessions(id)
);
```

### Tabela `performance_stats`
```sql
CREATE TABLE performance_stats (
    id UUID PRIMARY KEY,
    metric_name VARCHAR(100),
    metric_value REAL,
    metric_unit VARCHAR(50),
    date DATE,
    created_at TIMESTAMP WITH TIME ZONE
);
```

## 🔍 Consultas Úteis

### Logs Recentes
```sql
-- Últimas 10 operações
SELECT 
    operation_type, 
    status, 
    duration_ms, 
    created_at 
FROM operation_logs 
ORDER BY created_at DESC 
LIMIT 10;

-- Operações por tipo
SELECT 
    operation_type, 
    COUNT(*) as total,
    COUNT(CASE WHEN status = 'success' THEN 1 END) as successful,
    COUNT(CASE WHEN status = 'error' THEN 1 END) as failed
FROM operation_logs 
GROUP BY operation_type;
```

### Performance do Sistema
```sql
-- Métricas de CPU e memória
SELECT 
    metric_name, 
    AVG(metric_value) as avg_value,
    MAX(metric_value) as max_value,
    MIN(metric_value) as min_value
FROM performance_stats 
WHERE metric_name IN ('cpu_percent', 'memory_percent')
GROUP BY metric_name;

-- Performance por dia
SELECT 
    date,
    AVG(metric_value) as avg_cpu
FROM performance_stats 
WHERE metric_name = 'cpu_percent'
GROUP BY date
ORDER BY date DESC;
```

### Estatísticas de Utilizadores
```sql
-- Utilizadores mais ativos
SELECT 
    u.username,
    COUNT(ui.id) as interactions,
    COUNT(ol.id) as operations
FROM users u
LEFT JOIN user_interactions ui ON u.id = ui.user_id
LEFT JOIN operation_logs ol ON u.id = ol.user_id
GROUP BY u.id, u.username
ORDER BY interactions DESC;
```

## 🚨 Tratamento de Erros

### Fallback Automático
Se PostgreSQL falhar, o sistema automaticamente:
- Regista erros em ficheiros de log
- Continua a funcionar
- Tenta reconectar na próxima operação

### Logs de Fallback
Os logs de fallback são guardados em:
- `logs/fallback_operation_YYYYMMDD.log`
- `logs/fallback_user_interaction_YYYYMMDD.log`
- `logs/fallback_performance_YYYYMMDD.log`

## 🧹 Manutenção

### Limpeza de Logs Antigos
```python
# Manter logs dos últimos 90 dias
logger.cleanup_old_logs(days_to_keep=90)

# Manter logs dos últimos 30 dias
logger.cleanup_old_logs(days_to_keep=30)
```

### Backup da Base de Dados
```bash
# Backup completo
docker-compose exec postgres pg_dump -U rag_user rag_system > backup_$(date +%Y%m%d).sql

# Backup apenas das tabelas de logs
docker-compose exec postgres pg_dump -U rag_user rag_system -t operation_logs -t user_interactions -t performance_stats > logs_backup_$(date +%Y%m%d).sql
```

## 📈 Monitorização

### pgAdmin
- **URL**: http://localhost:8080
- **Email**: admin@example.com
- **Password**: admin_password_2024

### Dashboards Recomendados
1. **Operações por Tipo** - Gráfico de barras
2. **Performance do Sistema** - Gráfico de linha temporal
3. **Utilizadores Ativos** - Gráfico de pizza
4. **Logs de Erro** - Tabela com filtros

## 🔐 Segurança

### Boas Práticas
- **Nunca** logar passwords ou dados sensíveis
- **Sempre** validar UUIDs antes de inserir
- **Usar** HTTPS em produção
- **Configurar** firewall para PostgreSQL

### Auditoria
```sql
-- Ver todas as operações de um utilizador
SELECT * FROM operation_logs 
WHERE user_id = 'user_uuid_here' 
ORDER BY created_at DESC;

-- Ver tentativas de login falhadas
SELECT * FROM user_interactions 
WHERE action = 'user_login' 
AND details->>'success' = 'false';
```

## 🚀 Próximos Passos

### Funcionalidades Futuras
1. **Alertas automáticos** para erros críticos
2. **Dashboards em tempo real** com WebSockets
3. **Exportação de relatórios** em PDF/Excel
4. **Integração com sistemas** de monitorização (Grafana, Prometheus)
5. **Machine Learning** para deteção de anomalias

### Otimizações
1. **Índices compostos** para consultas frequentes
2. **Particionamento** de tabelas por data
3. **Compressão** de dados antigos
4. **Cache Redis** para consultas frequentes

---

## 📞 Suporte

Para problemas ou dúvidas:
1. Verificar logs em `logs/postgres_logger_YYYYMMDD.log`
2. Verificar logs de fallback
3. Consultar base de dados diretamente
4. Verificar conectividade PostgreSQL

**Sistema configurado e testado em**: 2025-09-02

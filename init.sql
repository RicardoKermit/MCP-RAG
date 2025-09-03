-- =====================================================
-- RAG System Database Initialization Script
-- PostgreSQL 15+
-- =====================================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =====================================================
-- USERS AND ROLES
-- =====================================================

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE,
    full_name VARCHAR(255),
    role VARCHAR(50) NOT NULL DEFAULT 'user',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP WITH TIME ZONE,
    moodle_user_id INTEGER,
    preferences JSONB DEFAULT '{}'
);

-- Roles table
CREATE TABLE IF NOT EXISTS roles (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    description TEXT,
    permissions JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- User roles junction table (many-to-many)
CREATE TABLE IF NOT EXISTS user_roles (
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    role_id INTEGER REFERENCES roles(id) ON DELETE CASCADE,
    granted_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    granted_by UUID REFERENCES users(id),
    PRIMARY KEY (user_id, role_id)
);

-- =====================================================
-- SESSIONS AND AUTHENTICATION
-- =====================================================

-- User sessions
CREATE TABLE IF NOT EXISTS user_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    session_token VARCHAR(255) UNIQUE NOT NULL,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    is_active BOOLEAN DEFAULT TRUE
);

-- =====================================================
-- OPERATIONS AND LOGS
-- =====================================================

-- Operation logs
CREATE TABLE IF NOT EXISTS operation_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    operation_type VARCHAR(100) NOT NULL,
    operation_details JSONB,
    status VARCHAR(50) DEFAULT 'success',
    error_message TEXT,
    duration_ms INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    ip_address INET,
    user_agent TEXT
);

-- User interactions
CREATE TABLE IF NOT EXISTS user_interactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(100) NOT NULL,
    details JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    session_id UUID REFERENCES user_sessions(id) ON DELETE SET NULL
);

-- =====================================================
-- STATISTICS AND METRICS
-- =====================================================

-- Operation statistics
CREATE TABLE IF NOT EXISTS operation_stats (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    operation_type VARCHAR(100) NOT NULL,
    total_count INTEGER DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    avg_duration_ms REAL DEFAULT 0,
    min_duration_ms INTEGER,
    max_duration_ms INTEGER,
    date DATE DEFAULT CURRENT_DATE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Performance metrics
CREATE TABLE IF NOT EXISTS performance_stats (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    metric_name VARCHAR(100) NOT NULL,
    metric_value REAL NOT NULL,
    metric_unit VARCHAR(50),
    date DATE DEFAULT CURRENT_DATE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Usage statistics
CREATE TABLE IF NOT EXISTS usage_stats (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    date DATE DEFAULT CURRENT_DATE,
    total_connections INTEGER DEFAULT 0,
    total_queries INTEGER DEFAULT 0,
    total_quiz_generations INTEGER DEFAULT 0,
    total_video_generations INTEGER DEFAULT 0,
    total_duration_minutes INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- CONVERSATIONS AND CHAT
-- =====================================================

-- Conversations
CREATE TABLE IF NOT EXISTS conversations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(255),
    model_used VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_archived BOOLEAN DEFAULT FALSE
);

-- Conversation messages
CREATE TABLE IF NOT EXISTS conversation_messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL, -- 'user' or 'assistant'
    content TEXT NOT NULL,
    tokens_used INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- QUIZ AND VIDEO GENERATION
-- =====================================================

-- Quiz generations
CREATE TABLE IF NOT EXISTS quiz_generations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    topic VARCHAR(255) NOT NULL,
    question_type VARCHAR(50) NOT NULL,
    num_questions INTEGER NOT NULL,
    difficulty VARCHAR(20) NOT NULL,
    format VARCHAR(20) NOT NULL,
    content TEXT,
    status VARCHAR(20) DEFAULT 'success',
    error_message TEXT,
    duration_ms INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Video generations
CREATE TABLE IF NOT EXISTS video_generations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    prompt TEXT NOT NULL,
    duration_seconds INTEGER NOT NULL,
    aspect_ratio VARCHAR(20) NOT NULL,
    status VARCHAR(20) DEFAULT 'success',
    video_path VARCHAR(500),
    error_message TEXT,
    duration_ms INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- INDEXES FOR PERFORMANCE
-- =====================================================

-- Users indexes
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at);

-- Sessions indexes
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON user_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_token ON user_sessions(session_token);
CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON user_sessions(expires_at);

-- Logs indexes
CREATE INDEX IF NOT EXISTS idx_operation_logs_user_id ON operation_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_operation_logs_type ON operation_logs(operation_type);
CREATE INDEX IF NOT EXISTS idx_operation_logs_created_at ON operation_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_operation_logs_status ON operation_logs(status);

-- Statistics indexes
CREATE INDEX IF NOT EXISTS idx_operation_stats_type_date ON operation_stats(operation_type, date);
CREATE INDEX IF NOT EXISTS idx_usage_stats_user_date ON usage_stats(user_id, date);

-- Conversations indexes
CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations(user_id);
CREATE INDEX IF NOT EXISTS idx_conversations_created_at ON conversations(created_at);

-- Messages indexes
CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON conversation_messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_messages_created_at ON conversation_messages(created_at);

-- =====================================================
-- DEFAULT DATA
-- =====================================================

-- Insert default roles
INSERT INTO roles (name, description, permissions) VALUES
('admin', 'System Administrator', '{"all": true}'),
('user', 'Regular User', '{"read": true, "write": true, "delete_own": true}'),
('moderator', 'Content Moderator', '{"read": true, "write": true, "moderate": true}'),
('analyst', 'Data Analyst', '{"read": true, "analytics": true}')
ON CONFLICT (name) DO NOTHING;

-- Insert default admin user (password: admin123)
INSERT INTO users (username, email, full_name, role) VALUES
('admin', 'admin@rag.local', 'System Administrator', 'admin')
ON CONFLICT (username) DO NOTHING;

-- Grant admin role to admin user
INSERT INTO user_roles (user_id, role_id, granted_by)
SELECT u.id, r.id, u.id
FROM users u, roles r
WHERE u.username = 'admin' AND r.name = 'admin'
ON CONFLICT DO NOTHING;

-- =====================================================
-- FUNCTIONS AND TRIGGERS
-- =====================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers for updated_at
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_conversations_updated_at BEFORE UPDATE ON conversations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_usage_stats_updated_at BEFORE UPDATE ON usage_stats
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Function to clean old sessions
CREATE OR REPLACE FUNCTION clean_expired_sessions()
RETURNS void AS $$
BEGIN
    DELETE FROM user_sessions WHERE expires_at < CURRENT_TIMESTAMP;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- VIEWS FOR COMMON QUERIES
-- =====================================================

-- View for user statistics
CREATE OR REPLACE VIEW user_statistics AS
SELECT 
    u.id,
    u.username,
    u.full_name,
    u.role,
    u.created_at,
    u.last_login,
    COUNT(DISTINCT c.id) as total_conversations,
    COUNT(DISTINCT q.id) as total_quizzes,
    COUNT(DISTINCT v.id) as total_videos,
    COALESCE(us.total_queries, 0) as total_queries
FROM users u
LEFT JOIN conversations c ON u.id = c.user_id
LEFT JOIN quiz_generations q ON u.id = q.user_id
LEFT JOIN video_generations v ON u.id = v.user_id
LEFT JOIN usage_stats us ON u.id = us.user_id
GROUP BY u.id, u.username, u.full_name, u.role, u.created_at, u.last_login, us.total_queries;

-- View for system statistics
CREATE OR REPLACE VIEW system_statistics AS
SELECT 
    DATE(created_at) as date,
    COUNT(*) as total_operations,
    COUNT(CASE WHEN status = 'success' THEN 1 END) as successful_operations,
    COUNT(CASE WHEN status = 'error' THEN 1 END) as failed_operations,
    AVG(duration_ms) as avg_duration_ms
FROM operation_logs
GROUP BY DATE(created_at)
ORDER BY date DESC;

-- =====================================================
-- COMMENTS
-- =====================================================

COMMENT ON TABLE users IS 'System users with authentication and role information';
COMMENT ON TABLE roles IS 'User roles and permissions';
COMMENT ON TABLE operation_logs IS 'Detailed logs of all system operations';
COMMENT ON TABLE user_interactions IS 'User interaction tracking for analytics';
COMMENT ON TABLE conversations IS 'Chat conversations between users and AI';
COMMENT ON TABLE quiz_generations IS 'Generated quizzes and their metadata';
COMMENT ON TABLE video_generations IS 'AI-generated videos and their metadata';

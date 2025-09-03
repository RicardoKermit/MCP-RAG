#!/bin/bash

# =====================================================
# RAG System PostgreSQL Startup Script
# =====================================================

echo "🚀 Starting RAG System with PostgreSQL..."

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker first."
    exit 1
fi

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null; then
    echo "❌ docker-compose is not installed. Please install it first."
    exit 1
fi

# Create necessary directories
echo "📁 Creating necessary directories..."
mkdir -p backups
mkdir -p logs

# Start PostgreSQL and pgAdmin
echo "🐘 Starting PostgreSQL and pgAdmin..."
docker-compose up -d

# Wait for PostgreSQL to be ready
echo "⏳ Waiting for PostgreSQL to be ready..."
until docker-compose exec -T postgres pg_isready -U rag_user -d rag_system > /dev/null 2>&1; do
    echo "   Waiting for PostgreSQL..."
    sleep 2
done

echo "✅ PostgreSQL is ready!"

# Show connection information
echo ""
echo "📊 Database Information:"
echo "   Host: localhost"
echo "   Port: 5432"
echo "   Database: rag_system"
echo "   Username: rag_user"
echo "   Password: rag_password_secure_2024"
echo ""
echo "🌐 pgAdmin:"
echo "   URL: http://localhost:8080"
echo "   Email: admin@rag.local"
echo "   Password: admin_password_2024"
echo ""

# Check if migration is needed
if [ -f "statistics.db" ]; then
    echo "🔄 SQLite database detected. You can migrate to PostgreSQL using:"
    echo "   python migrate_to_postgres.py"
    echo ""
fi

echo "🎉 RAG System is ready!"
echo ""
echo "To stop the services:"
echo "   docker-compose down"
echo ""
echo "To view logs:"
echo "   docker-compose logs -f"

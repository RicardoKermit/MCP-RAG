#!/usr/bin/env python3
"""
Test script to verify PostgreSQL connection
"""

import psycopg2
from psycopg2.extras import RealDictCursor

def test_postgres_connection():
    """Test connection to PostgreSQL database"""
    
    # Database configuration
    db_config = {
        'host': 'localhost',
        'port': 5432,
        'database': 'rag_system',
        'user': 'rag_user',
        'password': 'rag_password_secure_2024'
    }
    
    try:
        print("🔗 Testing PostgreSQL connection...")
        
        # Connect to database
        conn = psycopg2.connect(**db_config)
        print("✅ Connected to PostgreSQL successfully!")
        
        # Create cursor
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Test basic query
        cursor.execute("SELECT version();")
        version = cursor.fetchone()
        print(f"📊 PostgreSQL Version: {version['version']}")
        
        # Test table count
        cursor.execute("SELECT COUNT(*) as table_count FROM information_schema.tables WHERE table_schema = 'public';")
        table_count = cursor.fetchone()
        print(f"📋 Tables created: {table_count['table_count']}")
        
        # List tables
        cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name;")
        tables = cursor.fetchall()
        print("\n📋 Available tables:")
        for table in tables:
            print(f"   - {table['table_name']}")
        
        # Test roles
        cursor.execute("SELECT name, description FROM roles ORDER BY name;")
        roles = cursor.fetchall()
        print("\n👥 Available roles:")
        for role in roles:
            print(f"   - {role['name']}: {role['description']}")
        
        # Test users
        cursor.execute("SELECT username, email, role FROM users ORDER BY username;")
        users = cursor.fetchall()
        print("\n👤 Available users:")
        for user in users:
            print(f"   - {user['username']} ({user['email']}) - Role: {user['role']}")
        
        # Close cursor and connection
        cursor.close()
        conn.close()
        print("\n✅ All tests passed! PostgreSQL is ready to use.")
        
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False
    
    return True

if __name__ == "__main__":
    test_postgres_connection()

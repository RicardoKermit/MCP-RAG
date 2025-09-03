#!/usr/bin/env python3
"""
Test script for the new PostgreSQL logging system
"""

import os
import sys
from pathlib import Path

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_postgres_logger():
    """Test PostgreSQL logger functionality"""
    try:
        from postgres_logger import PostgresLogger, OperationType
        print("PostgresLogger import successful")
        
        # Test logger initialization
        logger = PostgresLogger({
            'host': 'localhost',
            'port': 5432,
            'database': 'rag_system',
            'user': 'rag_user',
            'password': 'rag_password_secure_2024'
        })
        print("PostgresLogger initialization successful")
        
        # Test basic logging
        success = logger.log_operation(
            operation_type=OperationType.SYSTEM_MAINTENANCE,
            details={"test": "system test", "component": "postgres_logger"},
            duration_ms=100
        )
        print(f"Operation logging: {success}")
        
        # Test system metrics
        metrics_success = logger.log_system_metrics()
        print(f"System metrics logging: {metrics_success}")
        
        # Test statistics
        stats = logger.get_statistics(days=1)
        print(f"Statistics retrieval: {len(stats.get('recent_activity', []))} activities found")
        
        return True
        
    except Exception as e:
        print(f"PostgresLogger test failed: {e}")
        return False

def test_mcp_server_import():
    """Test MCP Server import"""
    try:
        # This will test if all imports work
        import MCP_Server_new
        print("MCP_Server_new import successful")
        return True
    except Exception as e:
        print(f"MCP_Server_new import failed: {e}")
        return False

def test_mcp_client_import():
    """Test MCP Client import"""
    try:
        # This will test if all imports work
        import MCP_Client_new
        print("MCP_Client_new import successful")
        return True
    except Exception as e:
        print(f"MCP_Client_new import failed: {e}")
        return False

def test_environment():
    """Test environment configuration"""
    try:
        # Load environment variables
        from dotenv import load_dotenv
        load_dotenv()
        
        # Check key variables
        google_api_key = os.getenv("GOOGLE_API_KEY")
        moodle_token = os.getenv("MOODLE_TOKEN")
        qdrant_host = os.getenv("QDRANT_HOST")
        
        print(f"Environment loaded:")
        print(f"   - GOOGLE_API_KEY: {'OK' if google_api_key else 'MISSING'}")
        print(f"   - MOODLE_TOKEN: {'OK' if moodle_token else 'MISSING'}")
        print(f"   - QDRANT_HOST: {'OK' if qdrant_host else 'MISSING'}")
        
        return all([google_api_key, moodle_token, qdrant_host])
        
    except Exception as e:
        print(f"Environment test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("🚀 Testing new PostgreSQL logging system...\n")
    
    tests = [
        ("PostgreSQL Logger", test_postgres_logger),
        ("MCP Server Import", test_mcp_server_import),
        ("MCP Client Import", test_mcp_client_import),
        ("Environment Configuration", test_environment)
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"🔍 Testing {test_name}...")
        try:
            result = test_func()
            results.append((test_name, result))
            print()
        except Exception as e:
            print(f"{test_name} test crashed: {e}")
            results.append((test_name, False))
            print()
    
    # Summary
    print("📊 Test Results:")
    print("=" * 50)
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"{test_name:25} {status}")
        if result:
            passed += 1
    
    print("=" * 50)
    print(f"Total: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! System is ready.")
        return True
    else:
        print("⚠️ Some tests failed. Check the errors above.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

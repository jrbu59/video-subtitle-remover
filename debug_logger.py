#!/usr/bin/env python3
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("🔍 Testing logger directly...")

try:
    from backend.api.utils.logger import APILogger
    print("✅ Successfully imported APILogger")
    
    # Test logging functions
    print("📝 Testing log_info...")
    APILogger.log_info("This is a test info message")
    
    print("📝 Testing log_warning...")
    APILogger.log_warning("This is a test warning message")
    
    print("📝 Testing log_error...")
    APILogger.log_error("This is a test error message")
    
    print("📝 Testing request/response logging...")
    APILogger.log_request("test123", "GET", "/api/health", "127.0.0.1")
    APILogger.log_response("test123", 200, 0.123)
    
    print("\n🔍 Checking log files...")
    
    for log_name in ["access.log", "application.log", "error.log"]:
        log_path = f"backend/api/logs/{log_name}"
        if os.path.exists(log_path):
            size = os.path.getsize(log_path)
            print(f"   {log_name}: {size} bytes")
        else:
            print(f"   {log_name}: NOT FOUND")
            
    print("\n✅ Logger test complete")
    
except Exception as e:
    print(f"❌ Error testing logger: {e}")
    import traceback
    traceback.print_exc()

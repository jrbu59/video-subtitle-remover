#!/usr/bin/env python3
"""
验证多区域修复是否生效
"""

import requests
import json

def test_multi_region_processing():
    """测试多区域处理"""
    print("🧪 验证多区域字幕处理修复...")
    
    # 健康检查
    try:
        response = requests.get("http://localhost:8002/api/health")
        if response.status_code != 200:
            print("❌ API服务异常")
            return
        print("✅ API服务正常")
    except:
        print("❌ 无法连接API服务")
        return
    
    # 模拟你的客户端调用
    test_file_path = "/tmp/verify_fix.mp4"
    with open(test_file_path, "wb") as f:
        f.write(b"test video for multi-region verification")
    
    try:
        files = {'file': ('verify_fix.mp4', open(test_file_path, 'rb'), 'video/mp4')}
        
        # 使用你实际的4个区域坐标
        subtitle_regions = [
            [108, 96, 972, 249],
            [108, 384, 972, 537], 
            [108, 1632, 972, 1785],
            [108, 1785, 972, 1938]
        ]
        
        data = {
            'algorithm': 'sttn',
            'subtitle_regions': json.dumps(subtitle_regions)
        }
        
        print(f"📤 发送请求：{len(subtitle_regions)}个字幕区域")
        for i, region in enumerate(subtitle_regions):
            print(f"   区域{i+1}: [{region[0]}, {region[1]}, {region[2]}, {region[3]}]")
        
        response = requests.post("http://localhost:8002/api/upload", files=files, data=data)
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 请求成功！任务ID: {result.get('task_id')}")
            
            # 检查任务状态
            task_id = result.get('task_id')
            if task_id:
                status_response = requests.get(f"http://localhost:8002/api/task/{task_id}")
                if status_response.status_code == 200:
                    task_info = status_response.json()
                    print(f"📋 任务状态: {task_info.get('status')}")
                    
        else:
            print(f"❌ 请求失败: {response.status_code}")
            print(f"响应: {response.text}")
            
    except Exception as e:
        print(f"❌ 测试失败: {e}")
    finally:
        import os
        if os.path.exists(test_file_path):
            os.remove(test_file_path)

def check_recent_logs():
    """检查最近的日志记录"""
    print("\n📋 检查最近的处理日志...")
    
    import os
    from datetime import datetime
    
    log_file = "backend/api/logs/application.log"
    if os.path.exists(log_file):
        with open(log_file, 'r') as f:
            lines = f.readlines()
        
        # 查找包含region相关的最新日志
        recent_lines = []
        for line in reversed(lines):
            if any(keyword in line.lower() for keyword in ['region', 'multi', 'subtitle']):
                recent_lines.append(line.strip())
                if len(recent_lines) >= 5:
                    break
        
        if recent_lines:
            print("🔍 最近的相关日志:")
            for line in reversed(recent_lines):
                print(f"   {line}")
        else:
            print("⚠️  未找到相关日志记录")
    else:
        print("❌ 日志文件不存在")

if __name__ == "__main__":
    print("=" * 50)
    print("🔧 多区域修复验证")
    print("=" * 50)
    
    test_multi_region_processing()
    check_recent_logs()
    
    print("\n" + "=" * 50)
    print("📋 验证要点:")
    print("✅ 如果看到 'Multi-region mode: 4 regions' - 修复生效")
    print("❌ 如果看到 'Sub area: ymin=96, ymax=1938' - 仍在使用旧版本")
    print("=" * 50)

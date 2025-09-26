# 🎯 客户端使用指南 - 多区域字幕处理

## ⚠️ 重要说明

**第二次运行没有去除字幕的原因**：使用了旧版本的代码或缓存。

从日志对比可以看出：
- **修复后**：`[Debug] Multi-region mode: 4 regions` ✅
- **旧版本**：`[Debug] Sub area: ymin=96, ymax=1938` ❌

## 🔧 确保使用修复版本

### 1. 确认API服务地址
```
修复后的API地址：http://localhost:8002
```

### 2. 验证API版本
```bash
curl http://localhost:8002/api/health
```

应该返回：
```json
{
  "status": "healthy",
  "version": "1.1.1"
}
```

### 3. 客户端调用示例

```python
import requests
import json

# API地址
API_URL = "http://localhost:8002"

# 你的4个字幕区域（保持不变）
subtitle_regions = [
    [108, 96, 972, 249],   # 区域1：上部字幕
    [108, 384, 972, 537],  # 区域2：中部字幕
    [108, 1632, 972, 1785], # 区域3：下部字幕1
    [108, 1785, 972, 1938]  # 区域4：下部字幕2
]

# 上传文件
files = {'file': ('video.mp4', open('video.mp4', 'rb'), 'video/mp4')}
data = {
    'algorithm': 'sttn',
    'subtitle_regions': json.dumps(subtitle_regions)
}

response = requests.post(f"{API_URL}/api/upload", files=files, data=data)
if response.status_code == 200:
    result = response.json()
    task_id = result['task_id']
    print(f"任务创建成功：{task_id}")
else:
    print(f"上传失败：{response.status_code}")
```

## 🔍 验证修复是否生效

### 预期的处理日志

**修复后（正确）**：
```
🔧 Initializing API loggers...
Processing 4 subtitle regions: [[108, 96, 972, 249], [108, 384, 972, 537], [108, 1632, 972, 1785], [108, 1785, 972, 1938]]
✅ Will use 4 independent subtitle regions for precise detection
   Region 1: ymin=96, ymax=249, xmin=108, xmax=972
   Region 2: ymin=384, ymax=537, xmin=108, xmax=972
   Region 3: ymin=1632, ymax=1785, xmin=108, xmax=972
   Region 4: ymin=1785, ymax=1938, xmin=108, xmax=972
[Debug] Multi-region mode: 4 regions
[Debug] Detected text: xmin=204, xmax=874, ymin=374, ymax=450
[Debug] Checking region 1: ymin=96, ymax=249, xmin=108, xmax=972
[Debug] Checking region 2: ymin=384, ymax=537, xmin=108, xmax=972
[Debug] ✅ Text matches region 2
```

**旧版本（错误）**：
```
[Debug] Sub area: ymin=96, ymax=1938, xmin=108, xmax=972
[Debug] Detected text: xmin=204, xmax=872, ymin=374, ymax=450
[Debug] Check: 108 <= 204 <= 872 <= 972 and 96 <= 374 <= 450 <= 1938
```

## 📋 处理效果对比

### 修复前（合并区域）
- **处理范围**：整个大矩形 (96→1938, 108→972)
- **结果**：所有文字都被去除 ❌

### 修复后（独立区域）
- **处理范围**：只处理4个精确区域内的文字
- **结果**：只去除真正的字幕，保留其他文字 ✅

## 🚀 重新测试步骤

1. **确认使用正确的API**：
   ```bash
   netstat -tulpn | grep 8002
   ```

2. **重新发送相同的请求**：
   - 使用相同的视频文件
   - 使用相同的4个区域坐标
   - 确保请求发送到 `http://localhost:8002`

3. **检查处理日志**：
   - 应该看到 `Multi-region mode: 4 regions`
   - 应该看到逐个区域的检查过程

4. **验证结果**：
   - 区域外的文字应该被保留
   - 只有区域内的字幕被去除

## 🔧 故障排除

### 如果仍然看到旧版本日志

1. **重启API服务**：
   ```bash
   pkill -f "python start_api.py"
   python start_api.py
   ```

2. **清除客户端缓存**：
   - 重启客户端程序
   - 确认API地址是 `localhost:8002`

3. **验证代码版本**：
   ```bash
   grep -n "Multi-region mode" backend/main.py
   ```
   应该能找到相关代码。

## 📞 支持信息

如果仍然遇到问题，请检查：
- [ ] API服务运行在8002端口
- [ ] 客户端请求发送到正确地址
- [ ] 处理日志显示多区域模式
- [ ] 没有使用缓存的旧请求

**修复已经完成**，关键是确保使用修复后的API服务！
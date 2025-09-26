# 多区域字幕处理修复说明

## 🔍 问题分析

**用户遇到的问题**：
- 客户端传入4个独立的字幕区域：`[[108, 96, 972, 249], [108, 384, 972, 537], [108, 1632, 972, 1785], [108, 1785, 972, 1938]]`
- 服务端将所有区域合并成一个大区域：`ymin=96, ymax=1938, xmin=108, xmax=972`
- 结果：整个视频中从上到下的所有文字都被处理了，不仅仅是字幕

## ✅ 解决方案

### 核心修改

1. **修改 `backend/api/services/video_service.py`**:
   - 不再将多个区域合并成一个大区域
   - 保持4个独立区域：`[(96, 249, 108, 972), (384, 537, 108, 972), ...]`
   - 传递区域列表而非单个区域

2. **修改 `backend/main.py`**:
   - 支持多区域模式检测
   - 检查文本是否在**任意一个**区域内（而非必须在合并的大区域内）
   - 保持向后兼容性（单区域模式仍然工作）

### 技术实现

**之前的逻辑**：
```python
# 合并所有区域成一个大矩形
min_y = min(area[0] for area in all_areas)  # 96
max_y = max(area[1] for area in all_areas)  # 1938
min_x = min(area[2] for area in all_areas)  # 108
max_x = max(area[3] for area in all_areas)  # 972
sub_area = (min_y, max_y, min_x, max_x)     # (96, 1938, 108, 972)
```

**修复后的逻辑**：
```python
# 保持多个独立区域
sub_area = [
    (96, 249, 108, 972),    # 区域1
    (384, 537, 108, 972),   # 区域2
    (1632, 1785, 108, 972), # 区域3
    (1785, 1938, 108, 972)  # 区域4
]

# 检查文本是否在任意一个区域内
for area in sub_area:
    if text_in_area(detected_text, area):
        # 这是字幕，需要处理
        break
```

## 🧪 测试验证

### 预期行为

现在当检测到文字时：

1. **如果文字在区域1** `[108, 96, 972, 249]` 内 → **处理**
2. **如果文字在区域2** `[108, 384, 972, 537]` 内 → **处理**
3. **如果文字在区域3** `[108, 1632, 972, 1785]` 内 → **处理**
4. **如果文字在区域4** `[108, 1785, 972, 1938]` 内 → **处理**
5. **如果文字在其他位置**（如区域之间的空隙）→ **忽略**

### 调试日志

修复后的系统会输出详细的调试信息：

```
[Debug] Multi-region mode: 4 regions
[Debug] Detected text: xmin=204, xmax=872, ymin=374, ymax=450
[Debug] Checking region 1: ymin=96, ymax=249, xmin=108, xmax=972
[Debug] Checking region 2: ymin=384, ymax=537, xmin=108, xmax=972
[Debug] ✅ Text matches region 2
```

## 📋 使用说明

### 客户端调用

保持原有的调用方式不变：

```python
subtitle_regions = [
    [108, 96, 972, 249],   # [x1, y1, x2, y2]
    [108, 384, 972, 537],
    [108, 1632, 972, 1785],
    [108, 1785, 972, 1938]
]

data = {
    'algorithm': 'sttn',
    'subtitle_regions': json.dumps(subtitle_regions)
}
```

### API响应

服务端日志将显示：

```
✅ Will use 4 independent subtitle regions for precise detection
   Region 1: ymin=96, ymax=249, xmin=108, xmax=972
   Region 2: ymin=384, ymax=537, xmin=108, xmax=972
   Region 3: ymin=1632, ymax=1785, xmin=108, xmax=972
   Region 4: ymin=1785, ymax=1938, xmin=108, xmax=972
```

## 🔧 兼容性

### 向后兼容

- **单区域**：仍然支持传统的单区域模式
- **多区域**：新增支持多个独立区域
- **无区域**：自动检测模式不受影响

### 坐标格式

- **输入格式**：`[[x1, y1, x2, y2], ...]`
- **内部格式**：`[(ymin, ymax, xmin, xmax), ...]`
- **自动转换**：系统自动处理坐标转换

## 🎯 预期效果

修复后，使用相同的4个字幕区域：

- ✅ **只处理指定区域内的字幕**
- ✅ **忽略区域外的文字内容**
- ✅ **保持中间部分的正常文字不变**
- ✅ **精确控制处理范围**

## 🚀 部署

修复已经应用到当前运行的API服务（端口8002）。

**重启服务**：
```bash
python start_api.py
```

**测试功能**：
```bash
python test_multi_region.py
```

---

**总结**：通过保持多个独立区域而非合并为单个大区域，现在可以精确控制字幕去除的范围，避免误处理区域外的正常文字内容。
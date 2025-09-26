# Gemini字幕检测重构说明

## 重构目标

将原本在客户端进行的Gemini字幕检测功能移到服务端，统一处理流程，避免客户端和服务端对字幕区域理解不一致的问题。

## 重构内容

### 1. 服务端新增功能

#### 1.1 Gemini组件
- `backend/api/gemini/token_manager.py`: 访问令牌管理器
- `backend/api/gemini/gemini_client.py`: Gemini API客户端，负责调用Google Vertex AI进行字幕检测

#### 1.2 新增API接口
- `/api/detect-subtitles`: 字幕检测接口
- `/api/subtitle-analysis/{task_id}`: 获取字幕分析结果接口

#### 1.3 服务集成
- 在视频处理服务中集成自动字幕检测功能
- 添加新的任务状态：`DETECTING`
- 更新任务模型，添加`auto_detect_subtitles`字段

### 2. 客户端简化

#### 2.1 移除本地Gemini检测逻辑
- 移除了`src/token_manager.py`和`src/gemini_client.py`等本地组件
- 简化了处理流程，客户端只需上传视频并等待服务端处理完成

#### 2.2 新的处理流程
1. 客户端上传视频文件到服务端
2. 服务端接收请求，如果指定了`auto_detect_subtitles=true`，则自动调用Gemini进行字幕检测
3. 服务端根据检测结果或用户提供的字幕区域进行字幕去除处理
4. 客户端轮询任务状态，处理完成后下载结果

## 使用方法

### 服务端启动
```bash
cd backend/api
python main.py
```

### 客户端使用
```bash
# 使用自动字幕检测
python simple_vsr_client.py video.mp4 --vsr-url http://localhost:8002

# 指定输出路径
python simple_vsr_client.py video.mp4 -o output.mp4 --vsr-url http://localhost:8002
```

## API接口说明

### 上传文件（支持自动字幕检测）
```http
POST /api/upload
Content-Type: multipart/form-data

file: <视频文件>
algorithm: sttn|lama|propainter (可选，默认sttn)
auto_detect_subtitles: true|false (可选，默认false)
```

### 开始处理
```http
POST /api/process
Content-Type: application/x-www-form-urlencoded

task_id: <任务ID>
start_immediately: true|false (可选，默认true)
auto_detect_subtitles: true|false (可选，默认false)
```

### 获取任务状态
```http
GET /api/task/{task_id}
```

### 下载结果
```http
GET /api/download/{task_id}
```

## 优势

1. **统一处理**: 服务端统一处理字幕检测和去除，避免理解不一致
2. **简化客户端**: 客户端无需处理复杂的Gemini API调用
3. **更好的错误处理**: 服务端可以更好地处理各种异常情况
4. **可扩展性**: 便于后续添加更多AI检测功能
5. **性能优化**: 服务端可以更好地管理资源和并发处理

## 注意事项

1. 需要配置正确的Gemini API令牌端点
2. 服务端需要网络访问权限以调用Google Vertex AI
3. 处理大视频文件时需要考虑内存和存储限制
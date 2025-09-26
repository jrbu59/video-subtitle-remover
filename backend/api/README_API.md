# Video Subtitle Remover API 服务文档

## 📚 目录

- [快速开始](#快速开始)
- [API概览](#api概览)
- [详细接口说明](#详细接口说明)
- [错误处理](#错误处理)
- [性能优化](#性能优化)
- [部署指南](#部署指南)

## 🚀 快速开始

### 1. 安装依赖

```bash
# 基础依赖
pip install -r requirements.txt

# API服务依赖
pip install -r requirements-api.txt
```

### 2. 启动服务

```bash
# 开发环境
cd backend/api
python main.py

# 生产环境
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 3. 访问文档

- **交互式文档**: http://localhost:8000/docs
- **详细文档**: http://localhost:8000/redoc
- **API Schema**: http://localhost:8000/openapi.json

## 📋 API概览

### 核心端点

| 方法 | 路径 | 描述 | 认证 |
|------|------|------|------|
| GET | `/` | 重定向到API文档 | 否 |
| GET | `/api/health` | 健康检查 | 否 |
| GET | `/api/algorithms` | 获取算法列表 | 否 |
| POST | `/api/upload` | 上传文件 | 否 |
| POST | `/api/process` | 开始处理 | 否 |
| GET | `/api/task/{task_id}` | 查询任务状态 | 否 |
| GET | `/api/download/{task_id}` | 下载结果 | 否 |
| GET | `/api/tasks` | 任务列表 | 否 |
| DELETE | `/api/task/{task_id}` | 删除任务 | 否 |
| POST | `/api/task/{task_id}/cancel` | 取消任务 | 否 |

### 管理端点

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/tasks/stats` | 任务统计 |
| POST | `/api/tasks/cleanup` | 清理过期任务 |
| GET | `/api/preview/{task_id}` | 获取处理预览 |

## 🔧 详细接口说明

### 1. 文件上传

**POST** `/api/upload`

上传视频或图片文件进行字幕去除处理。

**参数:**

| 参数 | 类型 | 必需 | 描述 |
|------|------|------|------|
| file | File | 是 | 视频或图片文件 |
| algorithm | string | 否 | 算法类型 (sttn/lama/propainter) |
| subtitle_regions | string | 否 | 字幕区域JSON数组 |
| config_override | string | 否 | 配置覆盖JSON对象 |

**请求示例:**

```bash
curl -X POST "http://localhost:8000/api/upload" \
  -F "file=@video.mp4" \
  -F "algorithm=sttn" \
  -F 'subtitle_regions=[[100,400,200,500]]' \
  -F 'config_override={"STTN_SKIP_DETECTION":true}'
```

**响应示例:**

```json
{
  "success": true,
  "message": "文件上传成功",
  "task_id": "123e4567-e89b-12d3-a456-426614174000",
  "file_info": {
    "filename": "video.mp4",
    "size": 10485760,
    "format": ".mp4",
    "duration": 120.5,
    "resolution": "1920x1080"
  }
}
```

### 2. 开始处理

**POST** `/api/process`

启动视频字幕去除处理任务。

**参数:**

| 参数 | 类型 | 必需 | 描述 |
|------|------|------|------|
| task_id | string | 是 | 任务ID |
| start_immediately | boolean | 否 | 是否立即开始 (默认true) |

**请求示例:**

```bash
curl -X POST "http://localhost:8000/api/process" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "task_id=123e4567-e89b-12d3-a456-426614174000"
```

### 3. 查询任务状态

**GET** `/api/task/{task_id}`

查询指定任务的详细状态和进度。

**响应示例:**

```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "processing",
  "progress": 45.5,
  "algorithm": "sttn",
  "original_filename": "video.mp4",
  "created_at": "2024-01-15T10:30:00",
  "started_at": "2024-01-15T10:31:00",
  "completed_at": null,
  "error_message": null,
  "file_size": 10485760,
  "duration": 120.5,
  "download_url": null
}
```

### 4. 下载结果

**GET** `/api/download/{task_id}`

下载处理完成的视频文件。

**请求示例:**

```bash
curl -O "http://localhost:8000/api/download/123e4567-e89b-12d3-a456-426614174000"
```

## 🎯 算法选择指南

### STTN算法
- **适用场景**: 真人视频、新闻类视频
- **优势**: 处理速度快，支持跳过检测
- **配置参数**:
  - `STTN_SKIP_DETECTION`: 跳过字幕检测
  - `STTN_NEIGHBOR_STRIDE`: 相邻帧步长 (默认5)
  - `STTN_REFERENCE_LENGTH`: 参考帧数量 (默认10)

### LAMA算法
- **适用场景**: 动画视频、静态图片
- **优势**: 修复质量高，适合静态内容
- **配置参数**:
  - `LAMA_SUPER_FAST`: 快速模式 (默认false)

### ProPainter算法
- **适用场景**: 高运动场景、体育视频
- **优势**: 处理效果最佳
- **配置参数**:
  - `PROPAINTER_MAX_LOAD_NUM`: 最大加载帧数 (默认70)

## ⚠️ 错误处理

### 常见错误码

| 状态码 | 错误类型 | 描述 | 解决方案 |
|--------|----------|------|----------|
| 400 | 参数错误 | 请求参数不正确 | 检查参数格式和类型 |
| 404 | 资源不存在 | 任务或文件不存在 | 确认task_id正确 |
| 413 | 文件过大 | 文件超过最大限制 | 压缩文件或分段处理 |
| 415 | 格式不支持 | 文件格式不受支持 | 转换为支持的格式 |
| 500 | 服务器错误 | 内部处理错误 | 查看服务器日志 |

### 错误响应格式

```json
{
  "success": false,
  "message": "错误描述",
  "error_code": "ERROR_CODE",
  "detail": "详细错误信息"
}
```

## 🚀 性能优化

### 1. 服务器配置

```bash
# 多进程部署
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4

# 自定义工作进程数（建议CPU核心数）
uvicorn main:app --workers $(nproc)
```

### 2. 资源限制

在 `config.py` 中调整以下参数：

```python
# 文件大小限制 (字节)
MAX_FILE_SIZE = 1024 * 1024 * 1024  # 1GB

# 文件保留时间 (小时)
FILE_RETENTION_HOURS = 24

# 并发处理任务数
MAX_CONCURRENT_TASKS = 4
```

### 3. 内存优化

```python
# STTN算法优化
STTN_MAX_LOAD_NUM = 30  # 减少显存占用
STTN_NEIGHBOR_STRIDE = 5  # 平衡效果和速度

# ProPainter算法优化
PROPAINTER_MAX_LOAD_NUM = 50  # 根据显存调整
```

## 🐳 部署指南

### Docker部署

```bash
# 构建镜像
docker build -f Dockerfile.api -t vsr-api .

# 运行容器
docker run -d \
  --name vsr-api \
  --gpus all \
  -p 8000:8000 \
  -v ./storage:/app/backend/api/storage \
  -e MAX_FILE_SIZE=2147483648 \
  vsr-api
```

### Docker Compose

```yaml
version: '3.8'
services:
  vsr-api:
    build:
      context: .
      dockerfile: Dockerfile.api
    ports:
      - "8000:8000"
    volumes:
      - ./storage:/app/backend/api/storage
    environment:
      - API_HOST=0.0.0.0
      - API_PORT=8000
      - MAX_FILE_SIZE=2147483648
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
```

### Nginx反向代理

```nginx
server {
    listen 80;
    server_name your-domain.com;

    client_max_body_size 2G;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # 增加超时时间
        proxy_read_timeout 3600;
        proxy_connect_timeout 3600;
        proxy_send_timeout 3600;
    }

    # 静态文件直接服务
    location /files/ {
        alias /path/to/storage/outputs/;
        expires 1d;
    }
}
```

### 系统服务

创建 systemd 服务文件 `/etc/systemd/system/vsr-api.service`:

```ini
[Unit]
Description=Video Subtitle Remover API
After=network.target

[Service]
Type=exec
User=www-data
Group=www-data
WorkingDirectory=/path/to/project
Environment=PATH=/path/to/venv/bin
ExecStart=/path/to/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启动服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable vsr-api
sudo systemctl start vsr-api
```

## 📊 监控和日志

### 健康检查

```bash
# 基础健康检查
curl http://localhost:8000/api/health

# 详细状态
curl http://localhost:8000/api/tasks/stats
```

### 日志配置

在 `main.py` 中添加日志配置：

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('api.log'),
        logging.StreamHandler()
    ]
)
```

### 监控指标

建议监控以下指标：
- API响应时间
- 并发任务数量
- 磁盘空间使用
- GPU/CPU利用率
- 内存使用情况

## 🔒 安全考虑

### 1. 文件验证

- 严格验证文件类型和大小
- 扫描恶意文件
- 限制上传频率

### 2. 访问控制

```python
# 添加API密钥认证
from fastapi import Header, HTTPException

async def verify_api_key(x_api_key: str = Header()):
    if x_api_key != "your-secret-key":
        raise HTTPException(status_code=401, detail="Invalid API Key")
```

### 3. 速率限制

```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.post("/api/upload")
@limiter.limit("5/minute")
async def upload_video(request: Request, ...):
    pass
```

## 📞 技术支持

如果遇到问题，请：

1. 查看API文档: http://localhost:8000/docs
2. 检查服务日志
3. 确认环境配置正确
4. 提交Issue到GitHub仓库
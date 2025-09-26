from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class TaskStatus(str, Enum):
    PENDING = "pending"
    DETECTING = "detecting"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class AlgorithmType(str, Enum):
    STTN = "sttn"
    LAMA = "lama"
    PROPAINTER = "propainter"


class TaskCreate(BaseModel):
    algorithm: Optional[AlgorithmType] = Field(default=AlgorithmType.STTN, description="选择的算法类型")
    subtitle_regions: Optional[list] = Field(default=None, description="指定字幕区域坐标 [[x1,y1,x2,y2], ...]")
    config_override: Optional[Dict[str, Any]] = Field(default=None, description="覆盖默认配置参数")
    auto_detect_subtitles: Optional[bool] = Field(default=False, description="是否自动检测字幕区域")


class Task(BaseModel):
    id: str = Field(..., description="任务唯一标识符")
    status: TaskStatus = Field(default=TaskStatus.PENDING, description="任务状态")
    progress: float = Field(default=0.0, ge=0.0, le=100.0, description="任务进度百分比")
    algorithm: AlgorithmType = Field(..., description="使用的算法")
    original_filename: str = Field(..., description="原始文件名")
    file_path: Optional[str] = Field(default=None, description="上传文件路径")
    output_path: Optional[str] = Field(default=None, description="输出文件路径")
    output_filename: Optional[str] = Field(default=None, description="输出文件名")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    started_at: Optional[datetime] = Field(default=None, description="开始处理时间")
    completed_at: Optional[datetime] = Field(default=None, description="完成时间")
    error_message: Optional[str] = Field(default=None, description="错误信息")
    subtitle_regions: Optional[list] = Field(default=None, description="字幕区域")
    config_override: Optional[Dict[str, Any]] = Field(default=None, description="配置覆盖")
    file_size: Optional[int] = Field(default=None, description="文件大小（字节）")
    duration: Optional[float] = Field(default=None, description="视频时长（秒）")
    auto_detect_subtitles: Optional[bool] = Field(default=False, description="是否自动检测字幕区域")


class TaskResponse(BaseModel):
    task_id: str = Field(..., description="任务ID")
    status: TaskStatus = Field(..., description="任务状态")
    message: str = Field(..., description="响应消息")


class TaskDetail(BaseModel):
    id: str = Field(..., description="任务ID")
    status: TaskStatus = Field(..., description="任务状态")
    progress: float = Field(..., description="进度百分比")
    algorithm: AlgorithmType = Field(..., description="算法类型")
    original_filename: str = Field(..., description="原始文件名")
    created_at: datetime = Field(..., description="创建时间")
    started_at: Optional[datetime] = Field(default=None, description="开始时间")
    completed_at: Optional[datetime] = Field(default=None, description="完成时间")
    error_message: Optional[str] = Field(default=None, description="错误信息")
    subtitle_regions: Optional[list] = Field(default=None, description="字幕区域")
    file_size: Optional[int] = Field(default=None, description="文件大小")
    duration: Optional[float] = Field(default=None, description="视频时长")
    download_url: Optional[str] = Field(default=None, description="下载链接")


class TaskList(BaseModel):
    tasks: list[TaskDetail] = Field(..., description="任务列表")
    total: int = Field(..., description="总数量")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页大小")
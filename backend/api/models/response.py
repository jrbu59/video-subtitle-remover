from typing import Optional, Any, Dict
from pydantic import BaseModel, Field


class APIResponse(BaseModel):
    success: bool = Field(..., description="请求是否成功")
    message: str = Field(..., description="响应消息")
    data: Optional[Any] = Field(default=None, description="响应数据")
    error_code: Optional[str] = Field(default=None, description="错误代码")


class ErrorResponse(BaseModel):
    success: bool = Field(default=False, description="请求失败")
    message: str = Field(..., description="错误消息")
    error_code: str = Field(..., description="错误代码")
    detail: Optional[str] = Field(default=None, description="详细错误信息")


class FileInfo(BaseModel):
    filename: str = Field(..., description="文件名")
    size: int = Field(..., description="文件大小（字节）")
    format: str = Field(..., description="文件格式")
    duration: Optional[float] = Field(default=None, description="视频时长（秒）")
    resolution: Optional[str] = Field(default=None, description="分辨率")


class UploadResponse(BaseModel):
    success: bool = Field(default=True, description="上传成功")
    message: str = Field(..., description="响应消息")
    task_id: str = Field(..., description="任务ID")
    file_info: FileInfo = Field(..., description="文件信息")


class DownloadInfo(BaseModel):
    filename: str = Field(..., description="文件名")
    size: int = Field(..., description="文件大小")
    url: str = Field(..., description="下载链接")
    expires_at: Optional[str] = Field(default=None, description="过期时间")


class StatusResponse(BaseModel):
    task_id: str = Field(..., description="任务ID")
    status: str = Field(..., description="任务状态")
    progress: float = Field(..., description="进度百分比")
    message: str = Field(..., description="状态消息")
    error_message: Optional[str] = Field(default=None, description="错误信息")
    result: Optional[DownloadInfo] = Field(default=None, description="处理结果")
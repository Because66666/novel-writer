# Trae Agent Flask API

这是一个基于 Flask 的 Web API，将 Trae Agent 的 CLI 功能转换为网络 API 接口。

## 功能特性

- **任务执行**: 通过 HTTP API 执行 Trae Agent 任务，支持多进程并发
- **流式输出**: 实时获取任务执行过程中的消息和状态
- **任务管理**: 列出、监控和停止正在运行的任务
- **配置管理**: 查看和管理 Trae Agent 配置
- **工具信息**: 获取可用工具列表
- **跨域支持**: 支持 CORS，可从前端应用调用

## 安装依赖

```bash
pip install -r requirements_api.txt
```

## 启动服务器

### 开发模式

```bash
python app.py
```

### 生产模式 (使用 Gunicorn)

```bash
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

### 生产模式 (使用 Waitress - Windows 推荐)

```bash
waitress-serve --host=0.0.0.0 --port=5000 app:app
```

## 环境变量配置

```bash
# 服务器配置
FLASK_HOST=0.0.0.0          # 默认: 0.0.0.0
FLASK_PORT=5000             # 默认: 5000
FLASK_DEBUG=false           # 默认: false

# Trae Agent 配置
TRAE_CONFIG_FILE=trae_config.yaml  # 默认配置文件路径
```

## API 端点

### 1. 健康检查

```http
GET /api/health
```

**响应示例:**
```json
{
  "status": "healthy",
  "message": "Trae Agent API is running"
}
```

### 2. 执行任务

```http
POST /api/run
Content-Type: application/json
```

**请求体:**
```json
{
  "task": "创建一个简单的 Python 脚本",
  "working_dir": "/path/to/project",
  "provider": "openai",
  "model": "gpt-4",
  "max_steps": 10,
  "must_patch": false,
  "agent_type": "trae_agent",
  "config_file": "trae_config.yaml",
  "trajectory_file": "trajectory.json",
  "patch_path": "/path/to/patch"
}
```

**响应示例:**
```json
{
  "status": "success",
  "message": "Task started successfully",
  "task_id": "uuid-string"
}
```

**注意**: 任务现在以异步方式执行，返回任务ID用于后续跟踪。

### 3. 显示配置

```http
GET /api/config?config_file=trae_config.yaml&provider=openai&model=gpt-4
```

**响应示例:**
```json
{
  "status": "success",
  "config": {
    "config_file": "trae_config.yaml",
    "config_exists": true,
    "general_settings": {
      "default_provider": "openai",
      "max_steps": 20
    },
    "provider_settings": {
      "provider": "openai",
      "model": "gpt-4",
      "base_url": "https://api.openai.com/v1",
      "api_version": "v1",
      "api_key_set": true,
      "max_tokens": 4096,
      "temperature": 0.7,
      "top_p": 1.0
    }
  }
}
```

### 4. 显示可用工具

```http
GET /api/tools
```

**响应示例:**
```json
{
  "status": "success",
  "tools": [
    {
      "name": "bash_tool",
      "description": "Execute bash commands"
    },
    {
      "name": "edit_tool",
      "description": "Edit files"
    }
  ],
  "total_tools": 2
}
```

### 5. 列出活跃任务

```http
GET /api/tasks
```

**响应示例:**
```json
{
  "status": "success",
  "active_tasks": [
    {
      "task_id": "uuid-string-1",
      "status": "running",
      "start_time": 1640995200.0,
      "duration": 120.5
    },
    {
      "task_id": "uuid-string-2",
      "status": "completed",
      "start_time": 1640995100.0,
      "duration": 180.2
    }
  ],
  "total_tasks": 2
}
```

### 6. 流式获取任务消息

```http
GET /api/tasks/<task_id>/stream
```

**响应**: Server-Sent Events (SSE) 流

**消息格式:**
```
data: {"type": "start", "task_id": "uuid", "message": "开始执行任务: ...", "timestamp": 1640995200.0}

data: {"type": "complete", "task_id": "uuid", "result": "...", "message": "任务执行完成", "timestamp": 1640995300.0}

data: {"type": "end", "task_id": "uuid", "timestamp": 1640995300.0}
```

**消息类型:**
- `start`: 任务开始
- `complete`: 任务完成
- `error`: 任务出错
- `end`: 流结束

### 7. 获取任务状态

```http
GET /api/tasks/<task_id>/status
```

**响应示例:**
```json
{
  "status": "success",
  "task_id": "uuid-string",
  "task_status": "running",
  "start_time": 1640995200.0,
  "duration": 120.5,
  "messages": [
    {
      "type": "start",
      "task_id": "uuid-string",
      "message": "开始执行任务: ...",
      "timestamp": 1640995200.0
    }
  ]
}
```

### 8. 停止任务

```http
POST /api/tasks/<task_id>/stop
```

**响应示例:**
```json
{
  "status": "success",
  "message": "Task stopped successfully"
}
```

## 错误处理

所有 API 端点都会返回统一的错误格式:

```json
{
  "status": "error",
  "error": "错误描述",
  "traceback": "详细错误堆栈 (仅在调试模式下)"
}
```

常见的 HTTP 状态码:
- `200`: 成功
- `400`: 请求参数错误
- `404`: 端点不存在或资源未找到
- `500`: 服务器内部错误

## 使用示例

### Python 客户端示例

```python
import requests
import json

# 基础 URL
base_url = "http://localhost:5000/api"

# 1. 健康检查
response = requests.get(f"{base_url}/health")
print(response.json())

# 2. 执行任务
task_data = {
    "task": "创建一个 Hello World Python 脚本",
    "working_dir": "/tmp/test_project",
    "provider": "openai",
    "model": "gpt-4"
}

response = requests.post(f"{base_url}/run", json=task_data)
task_info = response.json()
task_id = task_info["task_id"]
print(f"任务已启动，ID: {task_id}")

# 3. 流式获取任务消息
import sseclient  # pip install sseclient-py

stream_url = f"{base_url}/tasks/{task_id}/stream"
response = requests.get(stream_url, stream=True)
client = sseclient.SSEClient(response)

for event in client.events():
    message = json.loads(event.data)
    print(f"[{message['type']}] {message.get('message', '')}")
    if message['type'] == 'end':
        break

# 3. 获取任务状态
response = requests.get(f"{base_url}/tasks/{task_id}/status")
status_info = response.json()
print(f"任务状态: {status_info['task_status']}")
print(f"消息数量: {len(status_info['messages'])}")

# 4. 停止任务（如果需要）
if status_info['task_status'] == 'running':
    response = requests.post(f"{base_url}/tasks/{task_id}/stop")
    print(response.json())
```

### JavaScript/Node.js 客户端示例

```javascript
const axios = require('axios');

const baseURL = 'http://localhost:5000/api';

// 执行任务并监听流式输出
async function runTaskWithStream() {
  try {
    // 启动任务
    const response = await axios.post(`${baseURL}/run`, {
      task: '创建一个简单的 Node.js 应用',
      working_dir: '/tmp/node_project',
      provider: 'openai',
      model: 'gpt-4'
    });
    
    const taskId = response.data.task_id;
    console.log('任务已启动，ID:', taskId);
    
    // 监听流式输出
    const EventSource = require('eventsource');
    const eventSource = new EventSource(`${baseURL}/tasks/${taskId}/stream`);
    
    eventSource.onmessage = function(event) {
      const message = JSON.parse(event.data);
      console.log(`[${message.type}] ${message.message || ''}`);
      
      if (message.type === 'end') {
        eventSource.close();
      }
    };
    
    eventSource.onerror = function(error) {
      console.error('流式连接错误:', error);
      eventSource.close();
    };
    
  } catch (error) {
    console.error('错误:', error.response.data);
  }
}

runTaskWithStream();
```

### cURL 示例

```bash
# 健康检查
curl -X GET http://localhost:5000/api/health

# 执行任务
curl -X POST http://localhost:5000/api/run \
  -H "Content-Type: application/json" \
  -d '{
    "task": "创建一个简单的 Python 脚本",
    "working_dir": "/tmp/test",
    "provider": "openai",
    "model": "gpt-4"
  }'

# 流式获取任务消息（假设任务ID为 abc-123）
curl -N http://localhost:5000/api/tasks/abc-123/stream

# 获取任务状态
curl -X GET http://localhost:5000/api/tasks/abc-123/status

# 停止任务
curl -X POST http://localhost:5000/api/tasks/abc-123/stop

# 显示配置
curl -X GET "http://localhost:5000/api/config?config_file=trae_config.yaml"

# 显示工具
curl -X GET http://localhost:5000/api/tools

# 列出活跃任务
curl -X GET http://localhost:5000/api/tasks
```

## 注意事项

1. **配置文件**: 确保 `trae_config.yaml` 或 `trae_config.json` 文件存在并正确配置
2. **工作目录**: 工作目录必须是绝对路径
3. **多进程执行**: 任务在独立进程中执行，支持并发处理多个任务
4. **流式输出**: 使用 Server-Sent Events (SSE) 实现实时消息推送
5. **任务管理**: 任务信息保存在内存中，服务器重启后会丢失
6. **进程管理**: 任务进程会在完成后自动清理，也可以手动停止
7. **安全性**: 在生产环境中，建议添加认证和授权机制
8. **并发**: 支持多个并发任务，建议根据系统资源调整并发数量

## 部署建议

### Docker 部署

创建 `Dockerfile`:

```dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY requirements_api.txt .
RUN pip install -r requirements_api.txt

COPY . .

EXPOSE 5000

CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "app:app"]
```

构建和运行:

```bash
docker build -t trae-agent-api .
docker run -p 5000:5000 -v $(pwd)/trae_config.yaml:/app/trae_config.yaml trae-agent-api
```

### Nginx 反向代理

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location /api/ {
        proxy_pass http://localhost:5000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

这个 Flask API 提供了完整的 Trae Agent 任务执行功能的网络接口，支持异步任务处理、实时流式输出和任务管理，可以轻松集成到现有的 Web 应用或微服务架构中。
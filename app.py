# Copyright (c) 2025 ByteDance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

"""Flask Web API for Trae Agent."""

import asyncio
import os
import traceback
from pathlib import Path
from typing import Dict, Any, Optional
import multiprocessing
import queue
import threading
import time
import uuid

from flask import Flask, request, jsonify, Response, stream_with_context
from flask_cors import CORS
from dotenv import load_dotenv
import json

from trae_agent.agent import Agent
from trae_agent.utils.config import Config, TraeAgentConfig

# Load environment variables
_ = load_dotenv()

app = Flask(__name__)
CORS(app)  # 允许跨域请求

# 全局变量存储活跃的任务进程
active_tasks: Dict[str, Dict[str, Any]] = {}  # 存储任务进程和消息队列


def resolve_config_file(config_file: str) -> str:
    """
    Resolve config file with backward compatibility.
    First tries the specified file, then falls back to JSON if YAML doesn't exist.
    """
    if config_file.endswith(".yaml") or config_file.endswith(".yml"):
        yaml_path = Path(config_file)
        json_path = Path(config_file.replace(".yaml", ".json").replace(".yml", ".json"))
        if yaml_path.exists():
            return str(yaml_path)
        elif json_path.exists():
            return str(json_path)
        else:
            raise FileNotFoundError(f"Config file not found: {config_file}")
    else:
        return config_file


def create_agent_config(data: Dict[str, Any]) -> Config:
    """创建代理配置"""
    config_file = data.get('config_file', 'trae_config.yaml')
    config_file = resolve_config_file(config_file)
    
    config = Config.create(
        config_file=config_file,
    ).resolve_config_values(
        provider=data.get('provider'),
        model=data.get('model'),
        model_base_url=data.get('model_base_url'),
        api_key=data.get('api_key'),
        max_steps=data.get('max_steps'),
    )
    
    return config


def run_agent_task(task_id: str, task: str, config_data: Dict[str, Any], task_args: Dict[str, Any], message_queue: multiprocessing.Queue):
    """在独立进程中运行代理任务"""
    try:
        # 在子进程中创建配置对象
        config = create_agent_config(config_data)
        
        # 创建代理（不使用控制台）
        agent = Agent(
            agent_type='trae_agent',
            config=config,
            trajectory_file=None,
            cli_console=None,
            docker_config=None,
            docker_keep=False,
        )
        
        # 发送开始消息
        message_queue.put({
            'type': 'start',
            'task_id': task_id,
            'message': f'开始执行任务: {task}',
            'timestamp': time.time()
        })
        
        # 执行任务
        result = asyncio.run(agent.run(task, task_args))
        
        
        # 发送完成消息
        message_queue.put({
            'type': 'complete',
            'task_id': task_id,
            'message': '任务执行完成',
            'timestamp': time.time()
        })
        
    except Exception as e:
        # 发送错误消息
        message_queue.put({
            'type': 'error',
            'task_id': task_id,
            'error': str(e),
            'traceback': traceback.format_exc(),
            'timestamp': time.time()
        })
    finally:
        # 发送结束消息
        message_queue.put({
            'type': 'end',
            'task_id': task_id,
            'timestamp': time.time()
        })


@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查端点"""
    return jsonify({"status": "healthy", "message": "Trae Agent API is running"})


@app.route('/api/run', methods=['POST'])
def run_task():
    """执行任务的API端点"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
        
        # 获取任务内容
        task = data.get('task')
        file_path = data.get('file_path')
        
        if file_path:
            if task:
                return jsonify({"error": "Cannot use both task and file_path"}), 400
            try:
                task = Path(file_path).read_text()
            except FileNotFoundError:
                return jsonify({"error": f"File not found: {file_path}"}), 400
        elif not task:
            return jsonify({"error": "Must provide either task or file_path"}), 400
        
        # 处理工作目录
        dir_param = data.get('working_dir')
        working_dir = os.path.join(os.getcwd(), dir_param) if dir_param else os.getcwd()
        try:
            Path(working_dir).mkdir(parents=True, exist_ok=True)
            working_dir = os.path.abspath(working_dir)
        except Exception as e:
            return jsonify({"error": f"Error with working directory: {e}"}), 400
        
        # 确保工作目录是绝对路径
        if not Path(working_dir).is_absolute():
            return jsonify({"error": "Working directory must be an absolute path"}), 400
        
        # 生成任务ID
        task_id = str(uuid.uuid4())
        
        # 创建消息队列
        message_queue = multiprocessing.Queue()
        
        # 准备配置数据以便传递给子进程
        config_data = data
        
        # 准备任务参数
        task_args = {
            "project_path": working_dir,
            "issue": task,
            "must_patch": "true" if data.get('must_patch', False) else "false",
            "patch_path": data.get('patch_path'),
        }
        
        # 启动任务进程
        process = multiprocessing.Process(
            target=run_agent_task,
            args=(task_id, task, config_data, task_args, message_queue)
        )
        process.start()
        
        # 存储任务信息
        active_tasks[task_id] = {
            'process': process,
            'queue': message_queue,
            'start_time': time.time(),
            'status': 'running'
        }
        
        return jsonify({
            "status": "success",
            "message": "Task started successfully",
            "task_id": task_id
        })
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@app.route('/api/config', methods=['GET'])
def show_config():
    """显示配置信息"""
    try:
        # 从查询参数获取配置选项
        config_file = request.args.get('config_file', 'trae_config.yaml')
        provider = request.args.get('provider')
        model = request.args.get('model')
        model_base_url = request.args.get('model_base_url')
        api_key = request.args.get('api_key')
        max_steps = request.args.get('max_steps', type=int)
        
        # 解析配置文件
        config_file = resolve_config_file(config_file)
        
        config_path = Path(config_file)
        config_exists = config_path.exists()
        
        if config_exists:
            config = Config.create(
                config_file=config_file,
            ).resolve_config_values(
                provider=provider,
                model=model,
                model_base_url=model_base_url,
                api_key=api_key,
                max_steps=max_steps,
            )
            
            if not config.trae_agent:
                return jsonify({"error": "trae_agent configuration is required"}), 400
            
            trae_agent_config = config.trae_agent
            provider_config = trae_agent_config.model.model_provider
            
            # 构建配置信息
            config_info = {
                "config_file": config_file,
                "config_exists": True,
                "general_settings": {
                    "default_provider": provider_config.provider,
                    "max_steps": trae_agent_config.max_steps
                },
                "provider_settings": {
                    "provider": provider_config.provider,
                    "model": trae_agent_config.model.model,
                    "base_url": provider_config.base_url,
                    "api_version": provider_config.api_version,
                    "api_key_set": bool(provider_config.api_key),
                    "max_tokens": trae_agent_config.model.max_tokens,
                    "temperature": trae_agent_config.model.temperature,
                    "top_p": trae_agent_config.model.top_p
                }
            }
            
            # 添加特定于Anthropic的配置
            if provider_config.provider == "anthropic":
                config_info["provider_settings"]["top_k"] = trae_agent_config.model.top_k
            
            return jsonify({
                "status": "success",
                "config": config_info
            })
        else:
            return jsonify({
                "status": "warning",
                "message": f"No configuration file found at: {config_file}",
                "config": {
                    "config_file": config_file,
                    "config_exists": False,
                    "note": "Using default settings and environment variables"
                }
            })
            
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@app.route('/api/tools', methods=['GET'])
def show_tools():
    """显示可用工具"""
    try:
        from trae_agent.tools import tools_registry
        
        tools_info = []
        
        for tool_name in tools_registry:
            try:
                tool = tools_registry[tool_name]()
                tools_info.append({
                    "name": tool.name,
                    "description": tool.description
                })
            except Exception as e:
                tools_info.append({
                    "name": tool_name,
                    "description": f"Error loading: {e}",
                    "error": True
                })
        
        return jsonify({
            "status": "success",
            "tools": tools_info,
            "total_tools": len(tools_info)
        })
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500





@app.route('/api/tasks', methods=['GET'])
def list_active_tasks():
    """列出活跃的任务"""
    try:
        tasks = []
        for task_id, task_info in active_tasks.items():
            # 检查进程状态
            process = task_info['process']
            if process.is_alive():
                status = 'running'
            else:
                status = 'completed'
                task_info['status'] = status
            
            tasks.append({
                "task_id": task_id,
                "status": status,
                "start_time": task_info['start_time'],
                "duration": time.time() - task_info['start_time']
            })
        
        return jsonify({
            "status": "success",
            "active_tasks": tasks,
            "total_tasks": len(tasks)
        })
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


@app.route('/api/tasks/<task_id>/stream', methods=['GET'])
def stream_task_messages(task_id: str):
    """流式获取任务消息"""
    if task_id not in active_tasks:
        return jsonify({"error": "Task not found"}), 404
    
    def generate():
        task_info = active_tasks[task_id]
        message_queue = task_info['queue']
        
        while True:
            try:
                # 非阻塞获取消息
                message = message_queue.get_nowait()
                
                # 确保消息可以JSON序列化
                try:
                    serialized_message = json.dumps(message)
                    yield f"data: {serialized_message}\n\n"
                except (TypeError, ValueError) as e:
                    # 如果消息无法序列化，发送错误消息
                    error_message = {
                        'type': 'error',
                        'message': f'Message serialization error: {str(e)}',
                        'original_message': str(message),
                        'timestamp': time.time()
                    }
                    yield f"data: {json.dumps(error_message)}\n\n"
                
                # 如果收到结束消息，停止流式传输
                if message.get('type') == 'end':
                    break
                    
            except queue.Empty:
                # 检查进程是否还在运行
                if not task_info['process'].is_alive():
                    # 进程已结束，发送最后的消息
                    yield f"data: {{\"type\": \"end\", \"task_id\": \"{task_id}\", \"timestamp\": {time.time()}}}\n\n"
                    break
                time.sleep(0.1)  # 短暂等待
    
    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'Access-Control-Allow-Origin': '*'
        }
    )


@app.route('/api/tasks/<task_id>/status', methods=['GET'])
def get_task_status(task_id: str):
    """获取任务状态"""
    if task_id not in active_tasks:
        return jsonify({"error": "Task not found"}), 404
    
    try:
        task_info = active_tasks[task_id]
        process = task_info['process']
        
        # 检查进程状态
        if process.is_alive():
            status = 'running'
        else:
            status = 'completed'
            task_info['status'] = status
        
        # 获取所有可用的消息
        messages = []
        while True:
            try:
                message = task_info['queue'].get_nowait()
                # 确保消息可以JSON序列化
                try:
                    json.dumps(message)
                    messages.append(message)
                except (TypeError, ValueError) as e:
                    # 如果消息无法序列化，转换为字符串
                    messages.append({
                        'type': 'error',
                        'message': f'Message serialization error: {str(e)}',
                        'original_message': str(message),
                        'timestamp': time.time()
                    })
            except queue.Empty:
                break
        
        return jsonify({
            "status": "success",
            "task_id": task_id,
            "task_status": status,
            "start_time": task_info['start_time'],
            "duration": time.time() - task_info['start_time'],
            "messages": messages
        })
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


@app.route('/api/tasks/<task_id>/stop', methods=['POST'])
def stop_task(task_id: str):
    """停止任务"""
    if task_id not in active_tasks:
        return jsonify({"error": "Task not found"}), 404
    
    try:
        task_info = active_tasks[task_id]
        process = task_info['process']
        
        if process.is_alive():
            process.terminate()
            process.join(timeout=5)  # 等待5秒
            
            if process.is_alive():
                process.kill()  # 强制终止
                process.join()
        
        # 清理任务信息
        del active_tasks[task_id]
        
        return jsonify({
            "status": "success",
            "message": "Task stopped successfully"
        })
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


@app.errorhandler(404)
def not_found(error):
    """404错误处理"""
    return jsonify({
        "status": "error",
        "error": "Endpoint not found",
        "message": "The requested API endpoint does not exist"
    }), 404


@app.errorhandler(500)
def internal_error(error):
    """500错误处理"""
    return jsonify({
        "status": "error",
        "error": "Internal server error",
        "message": "An unexpected error occurred"
    }), 500


if __name__ == '__main__':
    # 从环境变量获取配置
    host = os.getenv('FLASK_HOST', '0.0.0.0')
    port = int(os.getenv('FLASK_PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    debug = True
    print(f"Starting Trae Agent API server on {host}:{port}")
    print(f"Debug mode: {debug}")
    print("\nAvailable endpoints:")
    print("  GET  /api/health - Health check")
    print("  POST /api/run - Execute a task")
    print("  GET  /api/config - Show configuration")
    print("  GET  /api/tools - Show available tools")
    print("  GET  /api/tasks - List active tasks")
    print("  GET  /api/tasks/<task_id>/stream - Stream task messages")
    print("  GET  /api/tasks/<task_id>/status - Get task status")
    print("  POST /api/tasks/<task_id>/stop - Stop task")
    
    app.run(host=host, port=port, debug=debug)
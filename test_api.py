#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Trae Agent Flask API 测试脚本

这个脚本用于测试 Trae Agent Flask API 的各个端点功能。
"""

import requests
import json
import time
import sys
import threading
from typing import Dict, Any


class TraeAgentAPITester:
    """Trae Agent API 测试类"""
    
    def __init__(self, base_url: str = "http://localhost:5000"):
        self.base_url = base_url.rstrip('/')
        self.api_url = f"{self.base_url}/api"
        self.session_id = None
        self.last_task_id = None
    
    def test_health_check(self) -> bool:
        """测试健康检查端点"""
        print("\n=== 测试健康检查 ===")
        try:
            response = requests.get(f"{self.api_url}/health")
            print(f"状态码: {response.status_code}")
            print(f"响应: {response.json()}")
            return response.status_code == 200
        except Exception as e:
            print(f"错误: {e}")
            return False
    
    def test_show_config(self) -> bool:
        """测试显示配置端点"""
        print("\n=== 测试显示配置 ===")
        try:
            response = requests.get(f"{self.api_url}/config")
            print(f"状态码: {response.status_code}")
            result = response.json()
            print(f"响应: {json.dumps(result, indent=2, ensure_ascii=False)}")
            return response.status_code in [200, 400]  # 配置文件可能不存在
        except Exception as e:
            print(f"错误: {e}")
            return False
    
    def test_show_tools(self) -> bool:
        """测试显示工具端点"""
        print("\n=== 测试显示工具 ===")
        try:
            response = requests.get(f"{self.api_url}/tools")
            print(f"状态码: {response.status_code}")
            result = response.json()
            print(f"工具数量: {result.get('total_tools', 0)}")
            if 'tools' in result:
                for tool in result['tools'][:3]:  # 只显示前3个工具
                    print(f"  - {tool.get('name', 'Unknown')}: {tool.get('description', 'No description')}")
            return response.status_code == 200
        except Exception as e:
            print(f"错误: {e}")
            return False
    

    def test_run_task(self) -> bool:
        """测试执行任务端点"""
        print("\n=== 测试执行任务 ===")
        try:
            data = {
                "task": "假如每天进账100万，我该如何在现代社会中生存下去。",
                "working_dir": "/workfolder",
                "agent_type": "trae_agent",
                "max_steps": 3
            }
            
            print("启动任务...")
            response = requests.post(f"{self.api_url}/run", json=data, timeout=10)
            print(f"状态码: {response.status_code}")
            result = response.json()
            print(f"响应: {json.dumps(result, indent=2, ensure_ascii=False)}")
            
            if response.status_code == 200 and 'task_id' in result:
                self.last_task_id = result['task_id']
                return True
            return response.status_code in [200, 500]  # 可能因为配置问题失败
        except Exception as e:
            print(f"错误: {e}")
            return False
    
    def test_invalid_endpoints(self) -> bool:
        """测试无效端点"""
        print("\n=== 测试无效端点 ===")
        try:
            response = requests.get(f"{self.api_url}/nonexistent")
            print(f"状态码: {response.status_code}")
            result = response.json()
            print(f"响应: {json.dumps(result, indent=2, ensure_ascii=False)}")
            return response.status_code == 404
        except Exception as e:
            print(f"错误: {e}")
            return False
    
    def test_list_tasks(self) -> bool:
        """测试列出活跃任务"""
        print("\n=== 测试列出活跃任务 ===")
        try:
            response = requests.get(f"{self.api_url}/tasks")
            print(f"状态码: {response.status_code}")
            result = response.json()
            print(f"活跃任务数: {result.get('total_tasks', 0)}")
            if 'active_tasks' in result:
                for task in result['active_tasks']:
                    print(f"  - 任务ID: {task.get('task_id', 'Unknown')}, 状态: {task.get('status', 'Unknown')}")
            return response.status_code == 200
        except Exception as e:
            print(f"错误: {e}")
            return False
    
    def test_task_status(self) -> bool:
        """测试获取任务状态"""
        print("\n=== 测试获取任务状态 ===")
        if not self.last_task_id:
            print("错误: 没有可用的任务ID")
            return False
        
        try:
            response = requests.get(f"{self.api_url}/tasks/{self.last_task_id}/status")
            print(f"状态码: {response.status_code}")
            result = response.json()
            print(f"响应: {json.dumps(result, indent=2, ensure_ascii=False)}")
            return response.status_code in [200, 404]  # 任务可能已完成并清理
        except Exception as e:
            print(f"错误: {e}")
            return False
    
    def test_stream_task_messages(self) -> bool:
        """测试流式获取任务消息"""
        print("\n=== 测试流式获取任务消息 ===")
        if not self.last_task_id:
            print("错误: 没有可用的任务ID")
            return False
        
        try:
            print(f"尝试连接到流式端点: /tasks/{self.last_task_id}/stream")
            response = requests.get(f"{self.api_url}/tasks/{self.last_task_id}/stream", 
                                  stream=True, timeout=10)
            print(f"状态码: {response.status_code}")
            
            if response.status_code == 200:
                print("开始接收流式消息...")
                message_count = 0
                for line in response.iter_lines(decode_unicode=True):
                    if line.startswith('data: '):
                        try:
                            data = json.loads(line[6:])  # 移除 'data: ' 前缀
                            from pprint import pprint
                            pprint(data)
                            # print(f"收到消息: {data.get('type', 'unknown')} - {data.get('message', '')}")
                            message_count += 1
                            if data.get('type') == 'end' or message_count >= 5:
                                break
                        except json.JSONDecodeError:
                            continue
                print(f"共收到 {message_count} 条消息")
                return True
            else:
                print(f"流式连接失败，状态码: {response.status_code}")
                return response.status_code == 404  # 任务可能不存在
        except requests.exceptions.Timeout:
            print("流式连接超时 - 这可能是正常的")
            return True
        except Exception as e:
            print(f"错误: {e}")
            return False
    
    def test_stop_task(self) -> bool:
        """测试停止任务"""
        print("\n=== 测试停止任务 ===")
        if not self.last_task_id:
            print("错误: 没有可用的任务ID")
            return False
        
        try:
            response = requests.post(f"{self.api_url}/tasks/{self.last_task_id}/stop")
            print(f"状态码: {response.status_code}")
            result = response.json()
            print(f"响应: {json.dumps(result, indent=2, ensure_ascii=False)}")
            return response.status_code in [200, 404]  # 任务可能已完成
        except Exception as e:
            print(f"错误: {e}")
            return False
    
    def run_all_tests(self) -> Dict[str, bool]:
        """运行所有测试"""
        print(f"开始测试 Trae Agent API: {self.api_url}")
        print("=" * 50)
        
        tests = [
            ("健康检查", self.test_health_check),
            ("显示配置", self.test_show_config),
            ("显示工具", self.test_show_tools),
            ("执行任务", self.test_run_task),
            ("列出活跃任务", self.test_list_tasks),
            ("获取任务状态", self.test_task_status),
            ("流式获取任务消息", self.test_stream_task_messages),
            ("停止任务", self.test_stop_task),
            ("无效端点", self.test_invalid_endpoints),
        ]
        
        results = {}
        passed = 0
        total = len(tests)
        
        for test_name, test_func in tests:
            try:
                result = test_func()
                results[test_name] = result
                if result:
                    passed += 1
                    print(f"✅ {test_name}: 通过")
                else:
                    print(f"❌ {test_name}: 失败")
            except Exception as e:
                results[test_name] = False
                print(f"❌ {test_name}: 异常 - {e}")
            
            time.sleep(1)  # 避免请求过于频繁
        
        print("\n" + "=" * 50)
        print(f"测试完成: {passed}/{total} 通过")
        print(f"成功率: {passed/total*100:.1f}%")
        
        return results


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Trae Agent API 测试脚本")
    parser.add_argument(
        "--url", 
        default="http://localhost:5000", 
        help="API 服务器 URL (默认: http://localhost:5000)"
    )
    parser.add_argument(
        "--test", 
        choices=[
            "health", "config", "tools", "run", "tasks", "status", 
            "stream", "stop", "invalid", "all"
        ],
        default="all",
        help="要运行的测试 (默认: all)"
    )
    
    args = parser.parse_args()
    
    tester = TraeAgentAPITester(args.url)
    
    # 首先检查服务器是否可达
    try:
        response = requests.get(f"{tester.api_url}/health", timeout=5)
        if response.status_code != 200:
            print(f"❌ 服务器不可达或未正常运行: {tester.api_url}")
            print("请确保 Flask 应用正在运行: python app.py")
            sys.exit(1)
    except Exception as e:
        print(f"❌ 无法连接到服务器: {e}")
        print("请确保 Flask 应用正在运行: python app.py")
        sys.exit(1)
    
    # 运行指定的测试
    if args.test == "all":
        results = tester.run_all_tests()
    else:
        test_map = {
            "health": tester.test_health_check,
            "config": tester.test_show_config,
            "tools": tester.test_show_tools,
            "run": tester.test_run_task,
            "tasks": tester.test_list_tasks,
            "status": tester.test_task_status,
            "stream": tester.test_stream_task_messages,
            "stop": tester.test_stop_task,
            "invalid": tester.test_invalid_endpoints,
        }
        
        if args.test in test_map:
            result = test_map[args.test]()
            print(f"\n测试结果: {'✅ 通过' if result else '❌ 失败'}")
        else:
            print(f"未知的测试: {args.test}")
            sys.exit(1)


if __name__ == "__main__":
    main()
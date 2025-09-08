#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Trae Agent Flask API 启动脚本

这个脚本提供了一个简单的方式来启动 Trae Agent Flask API 服务器，
包括开发模式和生产模式的选项。
"""

import os
import sys
import argparse
import subprocess
from pathlib import Path


def check_dependencies():
    """检查必要的依赖是否已安装"""
    required_packages = ['flask', 'flask_cors', 'requests']
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print(f"❌ 缺少必要的依赖包: {', '.join(missing_packages)}")
        print("请运行以下命令安装依赖:")
        print(f"pip install {' '.join(missing_packages)}")
        print("或者:")
        print("pip install -r requirements_api.txt")
        return False
    
    return True


def check_config_file(config_file):
    """检查配置文件是否存在"""
    config_path = Path(config_file)
    
    # 检查 YAML 配置文件
    if config_file.endswith('.yaml') or config_file.endswith('.yml'):
        yaml_path = config_path
        json_path = Path(config_file.replace('.yaml', '.json').replace('.yml', '.json'))
        
        if yaml_path.exists():
            print(f"✅ 找到配置文件: {yaml_path}")
            return True
        elif json_path.exists():
            print(f"✅ 找到配置文件: {json_path}")
            return True
        else:
            print(f"⚠️  配置文件不存在: {config_file}")
            print("API 将使用默认设置和环境变量")
            return False
    else:
        if config_path.exists():
            print(f"✅ 找到配置文件: {config_path}")
            return True
        else:
            print(f"⚠️  配置文件不存在: {config_file}")
            print("API 将使用默认设置和环境变量")
            return False


def start_development_server(host, port, debug, config_file):
    """启动开发服务器"""
    print("🚀 启动开发服务器...")
    print(f"   主机: {host}")
    print(f"   端口: {port}")
    print(f"   调试模式: {debug}")
    print(f"   配置文件: {config_file}")
    print()
    
    # 设置环境变量
    env = os.environ.copy()
    env['FLASK_HOST'] = host
    env['FLASK_PORT'] = str(port)
    env['FLASK_DEBUG'] = str(debug).lower()
    env['TRAE_CONFIG_FILE'] = config_file
    
    try:
        # 直接运行 app.py
        subprocess.run([sys.executable, 'app.py'], env=env, check=True)
    except KeyboardInterrupt:
        print("\n👋 服务器已停止")
    except subprocess.CalledProcessError as e:
        print(f"❌ 启动失败: {e}")
        sys.exit(1)


def start_production_server(host, port, workers, server_type, config_file):
    """启动生产服务器"""
    print(f"🚀 启动生产服务器 ({server_type})...")
    print(f"   主机: {host}")
    print(f"   端口: {port}")
    print(f"   工作进程: {workers}")
    print(f"   配置文件: {config_file}")
    print()
    
    # 设置环境变量
    env = os.environ.copy()
    env['TRAE_CONFIG_FILE'] = config_file
    
    try:
        if server_type == 'gunicorn':
            # 检查 gunicorn 是否可用
            try:
                subprocess.run(['gunicorn', '--version'], 
                             capture_output=True, check=True)
            except (subprocess.CalledProcessError, FileNotFoundError):
                print("❌ gunicorn 未安装，请运行: pip install gunicorn")
                sys.exit(1)
            
            cmd = [
                'gunicorn',
                '-w', str(workers),
                '-b', f'{host}:{port}',
                '--timeout', '300',
                '--keep-alive', '2',
                'app:app'
            ]
            
        elif server_type == 'waitress':
            # 检查 waitress 是否可用
            try:
                subprocess.run(['waitress-serve', '--help'], 
                             capture_output=True, check=True)
            except (subprocess.CalledProcessError, FileNotFoundError):
                print("❌ waitress 未安装，请运行: pip install waitress")
                sys.exit(1)
            
            cmd = [
                'waitress-serve',
                f'--host={host}',
                f'--port={port}',
                f'--threads={workers}',
                'app:app'
            ]
        
        print(f"执行命令: {' '.join(cmd)}")
        subprocess.run(cmd, env=env, check=True)
        
    except KeyboardInterrupt:
        print("\n👋 服务器已停止")
    except subprocess.CalledProcessError as e:
        print(f"❌ 启动失败: {e}")
        sys.exit(1)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="Trae Agent Flask API 启动脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  开发模式:
    python start_api.py --dev
    python start_api.py --dev --host 0.0.0.0 --port 8080 --debug
  
  生产模式:
    python start_api.py --prod
    python start_api.py --prod --server gunicorn --workers 4
    python start_api.py --prod --server waitress --host 0.0.0.0
"""
    )
    
    # 模式选择
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument(
        '--dev', '--development',
        action='store_true',
        help='启动开发服务器'
    )
    mode_group.add_argument(
        '--prod', '--production',
        action='store_true',
        help='启动生产服务器'
    )
    
    # 服务器配置
    parser.add_argument(
        '--host',
        default='0.0.0.0',
        help='服务器主机地址 (默认: 0.0.0.0)'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=5000,
        help='服务器端口 (默认: 5000)'
    )
    
    # 开发模式选项
    parser.add_argument(
        '--debug',
        action='store_true',
        help='启用调试模式 (仅开发模式)'
    )
    
    # 生产模式选项
    parser.add_argument(
        '--server',
        choices=['gunicorn', 'waitress'],
        default='waitress' if sys.platform == 'win32' else 'gunicorn',
        help='生产服务器类型 (默认: Windows用waitress, 其他用gunicorn)'
    )
    parser.add_argument(
        '--workers',
        type=int,
        default=4,
        help='工作进程/线程数 (默认: 4)'
    )
    
    # 配置文件
    parser.add_argument(
        '--config',
        default='trae_config.yaml',
        help='配置文件路径 (默认: trae_config.yaml)'
    )
    
    # 检查选项
    parser.add_argument(
        '--check-only',
        action='store_true',
        help='只检查依赖和配置，不启动服务器'
    )
    
    args = parser.parse_args()
    
    print("🔧 Trae Agent Flask API 启动器")
    print("=" * 40)
    
    # 检查依赖
    print("📦 检查依赖...")
    if not check_dependencies():
        sys.exit(1)
    print("✅ 依赖检查通过")
    
    # 检查配置文件
    print("⚙️  检查配置文件...")
    check_config_file(args.config)
    
    # 检查 app.py 是否存在
    if not Path('app.py').exists():
        print("❌ app.py 文件不存在")
        sys.exit(1)
    
    print("✅ 环境检查完成")
    
    if args.check_only:
        print("\n✅ 检查完成，环境配置正常")
        return
    
    print()
    
    # 启动服务器
    if args.dev:
        start_development_server(
            host=args.host,
            port=args.port,
            debug=args.debug,
            config_file=args.config
        )
    else:
        start_production_server(
            host=args.host,
            port=args.port,
            workers=args.workers,
            server_type=args.server,
            config_file=args.config
        )


if __name__ == '__main__':
    main()
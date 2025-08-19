#!/usr/bin/env python3
"""
Valkey连接测试脚本

验证Valkey服务是否正常运行并可以连接
Valkey是Redis的开源分支，使用相同的协议和客户端
"""

import redis  # Valkey使用Redis协议，可以使用redis-py客户端
import sys
import os

def test_valkey_connection():
    """测试Valkey连接"""
    print("🔧 测试Valkey连接...")
    print("📝 注意: Valkey使用Redis协议，使用redis-py客户端连接")
    
    # 测试配置
    valkey_configs = [
        {
            'name': 'Default Valkey',
            'url': 'redis://localhost:6379/0',
            'host': 'localhost',
            'port': 6379,
            'db': 0
        },
        {
            'name': 'Rate Limit Valkey',
            'url': 'redis://localhost:6379/1',
            'host': 'localhost',
            'port': 6379,
            'db': 1
        }
    ]
    
    success_count = 0
    
    for config in valkey_configs:
        try:
            print(f"\n📡 测试 {config['name']}...")
            
            # 方法1：使用URL连接
            try:
                r = redis.from_url(config['url'])
                response = r.ping()
                if response:
                    print(f"  ✅ URL连接成功: {config['url']}")
                    success_count += 1
                else:
                    print(f"  ❌ URL连接失败: 无响应")
            except Exception as e:
                print(f"  ❌ URL连接失败: {e}")
                
                # 方法2：使用主机端口连接
                try:
                    r = redis.Redis(
                        host=config['host'],
                        port=config['port'],
                        db=config['db'],
                        decode_responses=True
                    )
                    response = r.ping()
                    if response:
                        print(f"  ✅ 主机连接成功: {config['host']}:{config['port']}/{config['db']}")
                        success_count += 1
                    else:
                        print(f"  ❌ 主机连接失败: 无响应")
                except Exception as e2:
                    print(f"  ❌ 主机连接失败: {e2}")
            
            # 测试基本操作
            try:
                r.set('valkey_test_key', 'valkey_test_value', ex=10)  # 10秒过期
                value = r.get('valkey_test_key')
                if value == 'valkey_test_value' or value == b'valkey_test_value':
                    print(f"  ✅ 读写测试成功")
                else:
                    print(f"  ⚠️  读写测试异常: 期望 'valkey_test_value', 得到 '{value}'")
                
                # 清理测试数据
                r.delete('valkey_test_key')
                
            except Exception as e:
                print(f"  ❌ 读写测试失败: {e}")
                
        except Exception as e:
            print(f"  ❌ 连接测试异常: {e}")
    
    # [Deprecated 20250819] 测试函数不应返回非 None，避免 PytestReturnNotNoneWarning
    # return success_count


def test_valkey_info():
    """获取Valkey服务信息"""
    print("\n📊 获取Valkey服务信息...")
    
    try:
        r = redis.Redis(host='localhost', port=6379, db=0)
        info = r.info()
        
        # 检查是否是Valkey
        server_info = info.get('redis_version', 'Unknown')
        if 'valkey' in server_info.lower():
            print(f"  ✅ 检测到Valkey服务器")
        else:
            print(f"  ℹ️  服务器类型: {server_info} (可能是Redis兼容服务)")
        
        print(f"  服务器版本: {server_info}")
        print(f"  运行模式: {info.get('redis_mode', 'Unknown')}")
        print(f"  已用内存: {info.get('used_memory_human', 'Unknown')}")
        print(f"  连接数: {info.get('connected_clients', 'Unknown')}")
        print(f"  运行时间: {info.get('uptime_in_seconds', 0)} 秒")
        
        # 显示一些Valkey特有信息（如果有）
        if 'valkey_version' in info:
            print(f"  Valkey版本: {info['valkey_version']}")
        
        # [Deprecated 20250819] 测试函数不应返回非 None
        # return True
        
    except Exception as e:
        print(f"  ❌ 获取Valkey信息失败: {e}")
        # [Deprecated 20250819]
        # return False


def test_flask_limiter_storage():
    """测试Flask-Limiter存储"""
    print("\n🚦 测试Flask-Limiter与Valkey存储...")
    
    try:
        from flask_limiter.storage import RedisStorage
        
        # Flask-Limiter的RedisStorage可以直接用于Valkey
        storage = RedisStorage('redis://localhost:6379/1')
        
        # 测试存储操作
        test_key = 'test_valkey_limiter_key'
        storage.incr(test_key, 1, 60)  # 增加计数，60秒过期
        
        count = storage.get(test_key)
        if count and int(count) > 0:
            print(f"  ✅ Flask-Limiter Valkey存储测试成功: 计数 = {count}")
            
            # 清理测试数据
            storage.clear(test_key)
            # [Deprecated 20250819]
            # return True
        else:
            print(f"  ❌ Flask-Limiter Valkey存储测试失败: 计数 = {count}")
            # [Deprecated 20250819]
            # return False
            
    except ImportError:
        print("  ⚠️  Flask-Limiter未安装，跳过存储测试")
        # [Deprecated 20250819] 测试函数不应返回非 None
        # return True
    except Exception as e:
        print(f"  ❌ Flask-Limiter Valkey存储测试异常: {e}")
        # [Deprecated 20250819]
        # return False


def check_valkey_service():
    """检查Valkey服务状态"""
    print("\n🔍 检查Valkey服务状态...")
    
    import subprocess
    
    # 检查Valkey进程
    try:
        if os.name == 'nt':  # Windows
            result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq valkey-server.exe'], 
                                  capture_output=True, text=True)
            if 'valkey-server.exe' in result.stdout:
                print("  ✅ Valkey服务正在运行 (Windows)")
                # [Deprecated 20250819]
                # return True
            else:
                # 检查是否有Redis进程（可能是兼容模式）
                result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq redis-server.exe'], 
                                      capture_output=True, text=True)
                if 'redis-server.exe' in result.stdout:
                    print("  ⚠️  检测到Redis进程，可能兼容Valkey协议")
                    # [Deprecated 20250819]
                    # return True
                else:
                    print("  ❌ Valkey服务未运行 (Windows)")
                    # [Deprecated 20250819]
                    # return False
        else:  # Linux/macOS
            # 首先检查valkey-server
            result = subprocess.run(['pgrep', '-f', 'valkey-server'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                print("  ✅ Valkey服务正在运行 (Linux/macOS)")
                # [Deprecated 20250819]
                # return True
            else:
                # 检查redis-server（可能是兼容模式）
                result = subprocess.run(['pgrep', '-f', 'redis-server'], 
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    print("  ⚠️  检测到Redis进程，可能兼容Valkey协议")
                    # [Deprecated 20250819]
                    # return True
                else:
                    print("  ❌ Valkey服务未运行 (Linux/macOS)")
                    # [Deprecated 20250819]
                    # return False
                
    except Exception as e:
        print(f"  ⚠️  无法检查服务状态: {e}")
        # [Deprecated 20250819]
        # return False


def test_valkey_cli():
    """测试Valkey CLI工具"""
    print("\n🔧 测试Valkey CLI工具...")
    
    import subprocess
    
    # 测试valkey-cli
    try:
        result = subprocess.run(['valkey-cli', 'ping'], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0 and 'PONG' in result.stdout:
            print("  ✅ valkey-cli 连接成功")
            # [Deprecated 20250819]
            # return True
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    
    # 如果valkey-cli不可用，尝试redis-cli
    try:
        result = subprocess.run(['redis-cli', 'ping'], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0 and 'PONG' in result.stdout:
            print("  ✅ redis-cli 连接成功 (兼容Valkey)")
            # [Deprecated 20250819]
            # return True
        else:
            print("  ❌ CLI工具连接失败")
            # [Deprecated 20250819]
            # return False
    except (subprocess.TimeoutExpired, FileNotFoundError):
        print("  ❌ 未找到CLI工具 (valkey-cli 或 redis-cli)")
        # [Deprecated 20250819]
        # return False

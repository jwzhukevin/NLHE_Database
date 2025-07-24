#!/usr/bin/env python3
"""
Redis连接测试脚本

验证Redis服务是否正常运行并可以连接
"""

import redis
import sys
import os

def test_redis_connection():
    """测试Redis连接"""
    print("🔧 测试Redis连接...")
    
    # 测试配置
    redis_configs = [
        {
            'name': 'Default Redis',
            'url': 'redis://localhost:6379/0',
            'host': 'localhost',
            'port': 6379,
            'db': 0
        },
        {
            'name': 'Rate Limit Redis',
            'url': 'redis://localhost:6379/1',
            'host': 'localhost',
            'port': 6379,
            'db': 1
        }
    ]
    
    success_count = 0
    
    for config in redis_configs:
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
                r.set('test_key', 'test_value', ex=10)  # 10秒过期
                value = r.get('test_key')
                if value == 'test_value' or value == b'test_value':
                    print(f"  ✅ 读写测试成功")
                else:
                    print(f"  ⚠️  读写测试异常: 期望 'test_value', 得到 '{value}'")
                
                # 清理测试数据
                r.delete('test_key')
                
            except Exception as e:
                print(f"  ❌ 读写测试失败: {e}")
                
        except Exception as e:
            print(f"  ❌ 连接测试异常: {e}")
    
    return success_count

def test_redis_info():
    """获取Redis服务信息"""
    print("\n📊 获取Redis服务信息...")
    
    try:
        r = redis.Redis(host='localhost', port=6379, db=0)
        info = r.info()
        
        print(f"  Redis版本: {info.get('redis_version', 'Unknown')}")
        print(f"  运行模式: {info.get('redis_mode', 'Unknown')}")
        print(f"  已用内存: {info.get('used_memory_human', 'Unknown')}")
        print(f"  连接数: {info.get('connected_clients', 'Unknown')}")
        print(f"  运行时间: {info.get('uptime_in_seconds', 0)} 秒")
        
        return True
        
    except Exception as e:
        print(f"  ❌ 获取Redis信息失败: {e}")
        return False

def test_flask_limiter_storage():
    """测试Flask-Limiter存储"""
    print("\n🚦 测试Flask-Limiter存储...")
    
    try:
        from flask_limiter.storage import RedisStorage
        
        storage = RedisStorage('redis://localhost:6379/1')
        
        # 测试存储操作
        test_key = 'test_limiter_key'
        storage.incr(test_key, 1, 60)  # 增加计数，60秒过期
        
        count = storage.get(test_key)
        if count and int(count) > 0:
            print(f"  ✅ Flask-Limiter存储测试成功: 计数 = {count}")
            
            # 清理测试数据
            storage.clear(test_key)
            return True
        else:
            print(f"  ❌ Flask-Limiter存储测试失败: 计数 = {count}")
            return False
            
    except ImportError:
        print("  ⚠️  Flask-Limiter未安装，跳过存储测试")
        return True
    except Exception as e:
        print(f"  ❌ Flask-Limiter存储测试异常: {e}")
        return False

def check_redis_service():
    """检查Redis服务状态"""
    print("\n🔍 检查Redis服务状态...")
    
    import subprocess
    
    # 检查Redis进程
    try:
        if os.name == 'nt':  # Windows
            result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq redis-server.exe'], 
                                  capture_output=True, text=True)
            if 'redis-server.exe' in result.stdout:
                print("  ✅ Redis服务正在运行 (Windows)")
                return True
            else:
                print("  ❌ Redis服务未运行 (Windows)")
                return False
        else:  # Linux/macOS
            result = subprocess.run(['pgrep', '-f', 'redis-server'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                print("  ✅ Redis服务正在运行 (Linux/macOS)")
                return True
            else:
                print("  ❌ Redis服务未运行 (Linux/macOS)")
                return False
                
    except Exception as e:
        print(f"  ⚠️  无法检查服务状态: {e}")
        return False

def main():
    """主函数"""
    print("🎯 Redis配置验证测试")
    print("=" * 60)
    
    # 检查Redis模块
    try:
        import redis
        print(f"✅ Redis Python客户端已安装: 版本 {redis.__version__}")
    except ImportError:
        print("❌ Redis Python客户端未安装")
        print("请运行: pip install redis")
        return 1
    
    # 运行所有测试
    tests = [
        ("Redis服务状态", check_redis_service),
        ("Redis连接测试", test_redis_connection),
        ("Redis服务信息", test_redis_info),
        ("Flask-Limiter存储", test_flask_limiter_storage),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name}测试异常: {e}")
            results.append((test_name, False))
    
    # 显示结果
    print("\n" + "=" * 60)
    print("🎉 测试完成！")
    print("\n📋 测试结果:")
    
    passed = 0
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"  {test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n📊 总计: {passed}/{len(results)} 个测试通过")
    
    if passed >= 2:  # 至少连接测试要通过
        print("\n🎉 Redis配置成功！")
        print("\n💡 下一步:")
        print("  1. 重启Flask应用")
        print("  2. 检查日志中的 'Rate limiting enabled with Redis storage'")
        print("  3. 不再看到内存存储警告")
        return 0
    else:
        print(f"\n⚠️  Redis配置有问题，请检查:")
        print("  1. Redis服务是否启动")
        print("  2. 端口6379是否可访问")
        print("  3. 防火墙设置")
        return 1

if __name__ == "__main__":
    exit(main())

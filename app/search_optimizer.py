# search_optimizer.py
# 搜索性能优化模块
# 包括缓存管理、查询优化和性能监控

import hashlib
import json
import time
from functools import wraps
from typing import Dict, List, Any, Optional
from flask import current_app, request
from sqlalchemy import text
from . import db
from .models import Material

class SearchCache:
    """
    搜索结果缓存管理器
    
    功能:
    1. 缓存搜索结果以提高响应速度
    2. 智能缓存失效策略
    3. 内存使用优化
    """
    
    def __init__(self):
        self.cache = {}
        self.cache_stats = {
            'hits': 0,
            'misses': 0,
            'total_requests': 0
        }
        self.max_cache_size = 1000  # 最大缓存条目数
        self.cache_ttl = 300  # 缓存生存时间（秒）
    
    def _generate_cache_key(self, search_params: Dict, user_context: str = None) -> str:
        """生成搜索参数的缓存键，包含用户上下文"""
        # 添加用户上下文到缓存键中
        cache_data = {
            'search_params': search_params,
            'user_context': user_context or 'anonymous'
        }
        # 排序参数以确保一致性
        sorted_data = json.dumps(cache_data, sort_keys=True)
        return hashlib.md5(sorted_data.encode()).hexdigest()
    
    def get(self, search_params: Dict, user_context: str = None) -> Optional[Dict]:
        """从缓存获取搜索结果"""
        self.cache_stats['total_requests'] += 1

        cache_key = self._generate_cache_key(search_params, user_context)

        if cache_key in self.cache:
            cached_item = self.cache[cache_key]

            # 检查是否过期
            if time.time() - cached_item['timestamp'] < self.cache_ttl:
                self.cache_stats['hits'] += 1
                return cached_item['data']
            else:
                # 删除过期项
                del self.cache[cache_key]

        self.cache_stats['misses'] += 1
        return None

    def set(self, search_params: Dict, result_data: Dict, user_context: str = None):
        """将搜索结果存入缓存"""
        cache_key = self._generate_cache_key(search_params, user_context)

        # 如果缓存已满，删除最旧的项
        if len(self.cache) >= self.max_cache_size:
            oldest_key = min(self.cache.keys(),
                           key=lambda k: self.cache[k]['timestamp'])
            del self.cache[oldest_key]

        self.cache[cache_key] = {
            'data': result_data,
            'timestamp': time.time()
        }
    
    def clear(self):
        """清空缓存"""
        self.cache.clear()
        self.cache_stats = {
            'hits': 0,
            'misses': 0,
            'total_requests': 0
        }
    
    def get_stats(self) -> Dict:
        """获取缓存统计信息"""
        total = self.cache_stats['total_requests']
        if total > 0:
            hit_rate = self.cache_stats['hits'] / total * 100
        else:
            hit_rate = 0
        
        return {
            'hit_rate': round(hit_rate, 2),
            'cache_size': len(self.cache),
            'max_size': self.max_cache_size,
            **self.cache_stats
        }

# 全局缓存实例
search_cache = SearchCache()

class QueryOptimizer:
    """
    查询优化器
    
    功能:
    1. 优化数据库查询
    2. 批量操作优化
    3. 查询性能监控
    """
    
    @staticmethod
    def optimize_material_search(search_params: Dict) -> Dict:
        """
        优化材料搜索查询
        
        返回优化后的查询结果和性能统计
        """
        start_time = time.time()
        
        # 构建优化的查询
        query = Material.query
        filters = []
        
        # 文本搜索优化：使用索引友好的查询
        if search_params.get('q'):
            search_term = search_params['q']
            # 优先使用精确匹配，然后是前缀匹配，最后是模糊匹配
            filters.append(
                db.or_(
                    Material.name == search_term,  # 精确匹配（最快）
                    Material.name.like(f'{search_term}%'),  # 前缀匹配（较快）
                    Material.mp_id == search_term,  # MP ID精确匹配
                    Material.name.ilike(f'%{search_term}%')  # 模糊匹配（较慢）
                )
            )
        
        # 状态过滤（使用索引）
        if search_params.get('status'):
            filters.append(Material.status == search_params['status'])
        
        # 材料类型过滤（使用索引）
        if search_params.get('materials_type'):
            filters.append(Material.materials_type == search_params['materials_type'])
        
        # 数值范围过滤（优化版本）
        numeric_filters = QueryOptimizer._build_numeric_filters(search_params)
        filters.extend(numeric_filters)
        
        # 应用所有过滤条件
        if filters:
            query = query.filter(db.and_(*filters))
        
        # 执行查询并计算性能
        total_count = query.count()
        execution_time = time.time() - start_time
        
        return {
            'query': query,
            'total_count': total_count,
            'execution_time': execution_time,
            'filters_applied': len(filters)
        }
    
    @staticmethod
    def _build_numeric_filters(search_params: Dict) -> List:
        """构建数值范围过滤条件"""
        filters = []
        
        # 费米能级范围
        if search_params.get('fermi_level_min'):
            try:
                min_val = float(search_params['fermi_level_min'])
                filters.append(Material.fermi_level >= min_val)
            except (ValueError, TypeError):
                pass
        
        if search_params.get('fermi_level_max'):
            try:
                max_val = float(search_params['fermi_level_max'])
                filters.append(Material.fermi_level <= max_val)
            except (ValueError, TypeError):
                pass
        
        # Shift Current范围
        if search_params.get('max_sc_min'):
            try:
                min_val = float(search_params['max_sc_min'])
                filters.append(Material.max_sc >= min_val)
            except (ValueError, TypeError):
                pass

        if search_params.get('max_sc_max'):
            try:
                max_val = float(search_params['max_sc_max'])
                filters.append(Material.max_sc <= max_val)
            except (ValueError, TypeError):
                pass

        # Band Gap范围
        if search_params.get('band_gap_min'):
            try:
                min_val = float(search_params['band_gap_min'])
                filters.append(Material.band_gap >= min_val)
            except (ValueError, TypeError):
                pass

        if search_params.get('band_gap_max'):
            try:
                max_val = float(search_params['band_gap_max'])
                filters.append(Material.band_gap <= max_val)
            except (ValueError, TypeError):
                pass

        return filters
    
    @staticmethod
    def create_database_indexes():
        """创建数据库索引以提高查询性能"""
        try:
            with db.engine.begin() as conn:
                # 检查并创建索引
                indexes_to_create = [
                    # 基本搜索索引
                    "CREATE INDEX IF NOT EXISTS idx_material_name ON material (name)",
                    "CREATE INDEX IF NOT EXISTS idx_material_mp_id ON material (mp_id)",
                    "CREATE INDEX IF NOT EXISTS idx_material_status ON material (status)",
                    "CREATE INDEX IF NOT EXISTS idx_material_metal_type ON material (metal_type)",
                    
                    # 数值范围搜索索引
                    "CREATE INDEX IF NOT EXISTS idx_material_fermi_level ON material (fermi_level)",
                    "CREATE INDEX IF NOT EXISTS idx_material_max_sc ON material (max_sc)",
                    "CREATE INDEX IF NOT EXISTS idx_material_band_gap ON material (band_gap)",
                    "CREATE INDEX IF NOT EXISTS idx_material_sg_num ON material (sg_num)",
                    
                    # 复合索引
                    "CREATE INDEX IF NOT EXISTS idx_material_search_combo ON material (name, status, metal_type)",
                    "CREATE INDEX IF NOT EXISTS idx_material_properties ON material (fermi_level, max_sc)",
                ]
                
                for index_sql in indexes_to_create:
                    try:
                        conn.execute(text(index_sql))
                        current_app.logger.info(f"Created index: {index_sql}")
                    except Exception as e:
                        current_app.logger.warning(f"Index creation failed: {index_sql}, Error: {e}")
                
                current_app.logger.info("Database indexes creation completed")
                
        except Exception as e:
            current_app.logger.error(f"Failed to create database indexes: {e}")

def performance_monitor(func):
    """
    性能监控装饰器
    
    监控函数执行时间和资源使用
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        
        try:
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            
            # 记录性能日志
            current_app.logger.info(
                f"Function {func.__name__} executed in {execution_time:.3f}s"
            )
            
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time
            current_app.logger.error(
                f"Function {func.__name__} failed after {execution_time:.3f}s: {e}"
            )
            raise
    
    return wrapper

def cached_search(cache_enabled=True):
    """
    搜索结果缓存装饰器

    使用用户感知的缓存，避免不同用户看到错误的登录状态
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not cache_enabled:
                return func(*args, **kwargs)

            # 生成用户上下文标识
            from flask_login import current_user
            if current_user.is_authenticated:
                user_context = f"user_{current_user.get_id()}_{current_user.role}"
            else:
                user_context = "anonymous"

            # 从请求参数生成缓存键（包含用户上下文）
            search_params = dict(request.args)

            # 尝试从缓存获取结果
            cached_result = search_cache.get(search_params, user_context)
            if cached_result:
                current_app.logger.info(f"Search result served from cache for {user_context}")
                return cached_result

            # 执行搜索并缓存结果
            result = func(*args, **kwargs)

            # 只缓存成功的结果
            if result and not isinstance(result, tuple):  # 不是错误响应
                search_cache.set(search_params, result, user_context)
                current_app.logger.info(f"Search result cached for {user_context}")

            return result

        return wrapper
    return decorator

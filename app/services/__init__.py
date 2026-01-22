# -*- coding: utf-8 -*-
"""
服务层模块
包含业务逻辑服务：能带分析、化学式解析、搜索优化等
"""

from .band_analyzer import band_analyzer, BandAnalysisConfig
from .chemical_parser import chemical_parser
from .search_optimizer import (
    search_cache, 
    QueryOptimizer, 
    performance_monitor, 
    cached_search,
    register_material_cache_invalidation,
    get_search_cache_stats
)
from .font_manager import FontManager
from .embedded_font import EmbeddedFont
from .captcha_logger import CaptchaLogger
from .csv_config import get_csv_path

__all__ = [
    'band_analyzer',
    'BandAnalysisConfig',
    'chemical_parser',
    'search_cache',
    'QueryOptimizer',
    'performance_monitor',
    'cached_search',
    'register_material_cache_invalidation',
    'get_search_cache_stats',
    'FontManager',
    'EmbeddedFont',
    'CaptchaLogger',
    'get_csv_path',
]

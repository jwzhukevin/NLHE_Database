#!/usr/bin/env python3
"""
能带分析器 - 合并版本

用于分析材料的能带结构，计算带隙和确定材料类型
专门用于材料导入时的自动分析，只输出带隙和材料类型
合并了原 band_analyzer.py、band_config.py、band_gap_calculator.py 的功能

主要功能：
1. 从 band.dat 文件分析能带数据
2. 计算材料带隙
3. 确定材料类型（metal/semimetal/semiconductor/insulator）
4. 生成简化的 band.json 文件
5. 支持批量处理和进度显示
"""

import os
import json
import numpy as np
from flask import current_app
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
import logging


class BandAnalysisConfig:
    """能带分析配置类 - 统一参数定义"""
    
    # 费米能级相关参数
    DEFAULT_FERMI_LEVEL = 0.0  # 默认费米能级
    FERMI_TOLERANCE = 0.1      # 费米能级容差
    
    # 材料分类阈值 (eV)
    METAL_THRESHOLD = 0.0           # 金属：带隙 = 0
    SEMIMETAL_THRESHOLD = 0.1       # 半金属：0 < 带隙 <= 0.1
    SEMICONDUCTOR_THRESHOLD = 3.0   # 半导体：0.1 < 带隙 <= 3.0
    # 绝缘体：带隙 > 3.0
    
    # 数值计算精度
    ENERGY_PRECISION = 1e-6
    
    @classmethod
    def classify_material(cls, band_gap: float) -> str:
        """根据带隙值分类材料类型"""
        if band_gap is None or band_gap < 0:
            return "unknown"
        elif band_gap <= cls.METAL_THRESHOLD:
            return "metal"
        elif band_gap <= cls.SEMIMETAL_THRESHOLD:
            return "semimetal"
        elif band_gap <= cls.SEMICONDUCTOR_THRESHOLD:
            return "semiconductor"
        else:
            return "insulator"


class BandAnalyzer:
    """能带分析器类 - 简化版本，只计算带隙和材料类型"""
    
    def __init__(self):
        self.config = BandAnalysisConfig()
        self.fermi_tolerance = self.config.FERMI_TOLERANCE
        self.logger = logging.getLogger(__name__)
    
    def analyze_material(self, material_path: str) -> Dict[str, Union[float, str]]:
        """
        分析单个材料的能带数据
        
        Args:
            material_path: 材料数据目录路径
            
        Returns:
            包含 band_gap 和 materials_type 的字典
        """
        try:
            # 查找能带数据文件
            band_file = self._find_band_file(material_path)
            if not band_file:
                self.logger.warning(f"No band data file found in {material_path}")
                return self._get_default_result()
            
            # 解析能带数据
            band_data = self._parse_band_file(band_file)
            if not band_data:
                self.logger.warning(f"Failed to parse band data from {band_file}")
                return self._get_default_result()
            
            # 计算带隙
            band_gap = self._calculate_band_gap(band_data)
            
            # 确定材料类型
            materials_type = self.config.classify_material(band_gap)
            
            result = {
                'band_gap': band_gap,
                'materials_type': materials_type
            }
            
            # 保存结果到 band.json
            self._save_band_json(material_path, result)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error analyzing material {material_path}: {e}")
            return self._get_default_result()
    
    def _find_band_file(self, material_path: str) -> Optional[str]:
        """查找能带数据文件"""
        possible_files = ['band.dat', 'EIGENVAL', 'eigenvalues.dat']
        
        for filename in possible_files:
            filepath = os.path.join(material_path, filename)
            if os.path.exists(filepath):
                return filepath
        
        return None
    
    def _parse_band_file(self, band_file: str) -> Optional[Dict]:
        """解析能带数据文件"""
        try:
            if band_file.endswith('band.dat'):
                return self._parse_band_dat(band_file)
            elif 'EIGENVAL' in band_file:
                return self._parse_eigenval(band_file)
            else:
                return self._parse_generic_band_file(band_file)
        except Exception as e:
            self.logger.error(f"Error parsing band file {band_file}: {e}")
            return None
    
    def _parse_band_dat(self, filepath: str) -> Optional[Dict]:
        """解析 band.dat 格式文件"""
        try:
            with open(filepath, 'r') as f:
                lines = f.readlines()
            
            eigenvalues = []
            current_kpoint = []
            
            for line in lines:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                try:
                    # 尝试解析能量值
                    values = [float(x) for x in line.split()]
                    if len(values) >= 2:  # k点坐标 + 能量值
                        current_kpoint.extend(values[1:])  # 跳过k点坐标
                    elif len(values) == 1:  # 只有能量值
                        current_kpoint.append(values[0])
                    
                    # 检查是否是新的k点（通过空行或特定标记）
                    if len(current_kpoint) > 0:
                        eigenvalues.append(current_kpoint[:])
                        current_kpoint = []
                        
                except ValueError:
                    continue
            
            if current_kpoint:
                eigenvalues.append(current_kpoint)
            
            return {
                'eigenvalues': eigenvalues,
                'fermi_level': 0.0  # 默认费米能级
            }
            
        except Exception as e:
            self.logger.error(f"Error parsing band.dat file: {e}")
            return None
    
    def _parse_eigenval(self, filepath: str) -> Optional[Dict]:
        """解析 VASP EIGENVAL 格式文件"""
        try:
            with open(filepath, 'r') as f:
                lines = f.readlines()
            
            # 跳过头部信息
            eigenvalues = []
            i = 0
            while i < len(lines):
                line = lines[i].strip()
                if not line:
                    i += 1
                    continue
                
                try:
                    # 查找能量数据
                    values = [float(x) for x in line.split()]
                    if len(values) >= 1:
                        eigenvalues.append(values)
                except ValueError:
                    pass
                
                i += 1
            
            return {
                'eigenvalues': eigenvalues,
                'fermi_level': 0.0
            }
            
        except Exception as e:
            self.logger.error(f"Error parsing EIGENVAL file: {e}")
            return None
    
    def _parse_generic_band_file(self, filepath: str) -> Optional[Dict]:
        """解析通用能带数据文件"""
        try:
            data = np.loadtxt(filepath)
            if data.ndim == 1:
                eigenvalues = [data.tolist()]
            else:
                eigenvalues = data.tolist()
            
            return {
                'eigenvalues': eigenvalues,
                'fermi_level': 0.0
            }
            
        except Exception as e:
            self.logger.error(f"Error parsing generic band file: {e}")
            return None
    
    def _calculate_band_gap(self, band_data: Dict) -> Optional[float]:
        """计算带隙"""
        try:
            eigenvalues = band_data['eigenvalues']
            fermi_level = band_data.get('fermi_level', 0.0)
            
            # 收集所有本征值
            all_eigenvalues = []
            for kpoint_eigenvals in eigenvalues:
                if isinstance(kpoint_eigenvals, list):
                    for eigenval in kpoint_eigenvals:
                        all_eigenvalues.append(eigenval - fermi_level)
                else:
                    all_eigenvalues.append(kpoint_eigenvals - fermi_level)
            
            if not all_eigenvalues:
                return None
            
            all_eigenvalues = np.array(all_eigenvalues)
            
            # 找到价带顶 (VBM) 和导带底 (CBM)
            occupied_states = all_eigenvalues[all_eigenvalues <= -self.fermi_tolerance]
            unoccupied_states = all_eigenvalues[all_eigenvalues > self.fermi_tolerance]
            
            if len(occupied_states) == 0 or len(unoccupied_states) == 0:
                # 可能是金属
                return 0.0
            
            vbm = np.max(occupied_states)
            cbm = np.min(unoccupied_states)
            
            band_gap = cbm - vbm
            
            # 确保带隙为正值
            return max(0.0, band_gap)
            
        except Exception as e:
            self.logger.error(f"Error calculating band gap: {e}")
            return None
    
    def _save_band_json(self, material_path: str, result: Dict):
        """保存分析结果到 band.json"""
        try:
            band_json_path = os.path.join(material_path, 'band.json')
            with open(band_json_path, 'w') as f:
                json.dump(result, f, indent=2)
            
            self.logger.debug(f"Saved band analysis to {band_json_path}")
            
        except Exception as e:
            self.logger.error(f"Error saving band.json: {e}")
    
    def _get_default_result(self) -> Dict[str, Union[float, str]]:
        """获取默认结果（分析失败时使用）"""
        return {
            'band_gap': None,
            'materials_type': 'unknown'
        }
    
    def batch_analyze(self, materials_paths: List[str], 
                     progress_callback=None) -> Dict[str, Dict]:
        """
        批量分析材料
        
        Args:
            materials_paths: 材料路径列表
            progress_callback: 进度回调函数
            
        Returns:
            分析结果字典
        """
        results = {}
        total = len(materials_paths)
        
        for i, material_path in enumerate(materials_paths):
            try:
                result = self.analyze_material(material_path)
                results[material_path] = result
                
                if progress_callback:
                    progress_callback(i + 1, total, material_path)
                    
            except Exception as e:
                self.logger.error(f"Error in batch analysis for {material_path}: {e}")
                results[material_path] = self._get_default_result()
        
        return results


# 全局实例
band_analyzer = BandAnalyzer()


def analyze_material_bands(material_path: str) -> Dict[str, Union[float, str]]:
    """
    分析单个材料的能带数据（便捷函数）
    
    Args:
        material_path: 材料数据目录路径
        
    Returns:
        包含 band_gap 和 materials_type 的字典
    """
    return band_analyzer.analyze_material(material_path)


def batch_analyze_materials(materials_paths: List[str], 
                          progress_callback=None) -> Dict[str, Dict]:
    """
    批量分析材料能带数据（便捷函数）
    
    Args:
        materials_paths: 材料路径列表
        progress_callback: 进度回调函数
        
    Returns:
        分析结果字典
    """
    return band_analyzer.batch_analyze(materials_paths, progress_callback)

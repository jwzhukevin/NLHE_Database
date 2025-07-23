# band_gap_calculator.py
# Band Gap计算服务类
# 集成到应用内部，提供自动计算和缓存功能

import os
from typing import Optional, Dict, List, Tuple
from flask import current_app
from . import db
from .models import Material

class BandGapCalculator:
    """
    Band Gap计算器类
    
    功能:
    1. 从能带数据文件计算Band Gap
    2. 自动缓存计算结果到数据库
    3. 提供批量计算和单个计算接口
    4. 集成到应用生命周期中
    """
    
    def __init__(self):
        self.tolerance = 0.1  # 费米能级容差
        self.fermi_level = 0.0  # 默认费米能级
    
    def parse_band_data(self, file_path: str) -> Optional[Dict]:
        """解析能带数据文件"""
        try:
            if not os.path.exists(file_path):
                current_app.logger.warning(f"Band data file not found: {file_path}")
                return None
                
            with open(file_path, 'r') as f:
                lines = f.readlines()
            
            if len(lines) < 3:
                current_app.logger.warning(f"Invalid band data file format: {file_path}")
                return None
                
            # 解析高对称点信息
            k_labels = lines[0].strip().split()
            k_positions = list(map(float, lines[1].strip().split()))
            
            # 解析能带数据
            bands = []
            kpoints = []
            
            for i in range(2, len(lines)):
                line = lines[i].strip()
                if not line:
                    continue
                    
                values = list(map(float, line.split()))
                if len(values) < 2:
                    continue
                    
                kpoints.append(values[0])
                
                # 初始化能带数组
                if not bands:
                    num_bands = len(values) - 1
                    bands = [[] for _ in range(num_bands)]
                
                # 添加能带数据
                for j in range(1, len(values)):
                    if j-1 < len(bands):
                        bands[j-1].append(values[j])
            
            return {
                'kpoints': kpoints, 
                'bands': bands,
                'k_labels': k_labels,
                'k_positions': k_positions
            }
            
        except Exception as e:
            current_app.logger.error(f"Error parsing band data file {file_path}: {e}")
            return None
    
    def analyze_band_structure(self, bands: List[List[float]]) -> Optional[Dict]:
        """分析能带结构，计算Band Gap"""
        if not bands:
            return None
        
        # 分离价带和导带
        valence_bands = []
        conduction_bands = []
        
        for band_index, band in enumerate(bands):
            if not band:
                continue
                
            max_energy = max(band)
            min_energy = min(band)
            
            if max_energy < self.fermi_level - self.tolerance:
                # 价带
                valence_bands.append({'index': band_index, 'energies': band})
            elif min_energy > self.fermi_level + self.tolerance:
                # 导带
                conduction_bands.append({'index': band_index, 'energies': band})
        
        # 计算带隙
        if len(valence_bands) > 0 and len(conduction_bands) > 0:
            # 找到价带顶 (VBM)
            vbm_value = float('-inf')
            for band in valence_bands:
                for energy in band['energies']:
                    if energy > vbm_value:
                        vbm_value = energy
            
            # 找到导带底 (CBM)
            cbm_value = float('inf')
            for band in conduction_bands:
                for energy in band['energies']:
                    if energy < cbm_value:
                        cbm_value = energy
            
            band_gap = cbm_value - vbm_value
            
            # 判断材料类型
            if band_gap > 3.0:
                material_type = "Insulator"
            elif band_gap > 0.1:
                material_type = "Semiconductor"
            else:
                material_type = "Metal"
                
            return {
                'band_gap': band_gap,
                'vbm_energy': vbm_value,
                'cbm_energy': cbm_value,
                'material_type': material_type,
                'num_valence_bands': len(valence_bands),
                'num_conduction_bands': len(conduction_bands)
            }
        else:
            # 金属或无法确定带隙
            return {
                'band_gap': 0.0,
                'vbm_energy': None,
                'cbm_energy': None,
                'material_type': "Metal",
                'num_valence_bands': len(valence_bands),
                'num_conduction_bands': len(conduction_bands)
            }
    
    def get_band_file_path(self, material: Material) -> str:
        """获取材料的能带数据文件路径"""
        if not material.formatted_id:
            return None
            
        # 转换格式化ID到实际文件夹名称
        if material.formatted_id.startswith('IMR-'):
            folder_name = f"IMR-{int(material.formatted_id.split('-')[1])}"
        else:
            folder_name = material.formatted_id
        
        return f"app/static/materials/{folder_name}/band/band.dat"
    
    def calculate_band_gap(self, material: Material, force_recalculate: bool = False) -> Optional[float]:
        """
        计算单个材料的Band Gap
        
        Args:
            material: 材料对象
            force_recalculate: 是否强制重新计算（忽略缓存）
            
        Returns:
            Band Gap值，如果计算失败返回None
        """
        # 如果已有缓存值且不强制重新计算，直接返回
        if not force_recalculate and material.band_gap is not None:
            current_app.logger.info(f"Using cached band gap for {material.formatted_id}: {material.band_gap}")
            return material.band_gap
        
        # 获取能带数据文件路径
        band_file = self.get_band_file_path(material)
        if not band_file:
            current_app.logger.warning(f"Cannot determine band file path for {material.formatted_id}")
            return None
        
        # 解析能带数据
        band_data = self.parse_band_data(band_file)
        if not band_data or not band_data['bands']:
            current_app.logger.warning(f"Failed to parse band data for {material.formatted_id}")
            return None
        
        # 分析能带结构
        analysis = self.analyze_band_structure(band_data['bands'])
        if not analysis:
            current_app.logger.warning(f"Failed to analyze band structure for {material.formatted_id}")
            return None
        
        band_gap = analysis['band_gap']
        
        # 保存到数据库
        try:
            material.band_gap = band_gap
            db.session.commit()
            
            current_app.logger.info(
                f"Calculated and saved band gap for {material.formatted_id}: "
                f"{band_gap:.4f} eV ({analysis['material_type']})"
            )
            
            return band_gap
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Failed to save band gap for {material.formatted_id}: {e}")
            return None
    
    def calculate_all_band_gaps(self, force_recalculate: bool = False) -> Dict[str, int]:
        """
        批量计算所有材料的Band Gap
        
        Args:
            force_recalculate: 是否强制重新计算所有材料
            
        Returns:
            统计信息字典
        """
        materials = Material.query.all()
        stats = {
            'total': len(materials),
            'calculated': 0,
            'cached': 0,
            'failed': 0
        }
        
        current_app.logger.info(f"Starting batch band gap calculation for {stats['total']} materials")
        
        for material in materials:
            try:
                if not force_recalculate and material.band_gap is not None:
                    stats['cached'] += 1
                    continue
                
                result = self.calculate_band_gap(material, force_recalculate)
                if result is not None:
                    stats['calculated'] += 1
                else:
                    stats['failed'] += 1
                    
            except Exception as e:
                current_app.logger.error(f"Error calculating band gap for {material.formatted_id}: {e}")
                stats['failed'] += 1
        
        current_app.logger.info(
            f"Batch calculation completed: {stats['calculated']} calculated, "
            f"{stats['cached']} cached, {stats['failed']} failed"
        )
        
        return stats

# 创建全局计算器实例
band_gap_calculator = BandGapCalculator()

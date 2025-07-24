#!/usr/bin/env python3
"""
能带数据分析器

从band.dat文件中分析并提取：
1. Band Gap (带隙值)
2. Materials Type (材料类型：metal, semiconductor, insulator, semimetal)

生成band.json文件保存分析结果
"""

import os
import json
import numpy as np
from flask import current_app

class BandAnalyzer:
    """能带数据分析器"""
    
    def __init__(self):
        self.band_gap_threshold = {
            'metal': 0.0,           # 带隙 = 0，金属
            'semimetal': 0.1,       # 带隙 0-0.1 eV，半金属
            'semiconductor': 3.0,   # 带隙 0.1-3.0 eV，半导体
            'insulator': float('inf')  # 带隙 > 3.0 eV，绝缘体
        }
    
    def analyze_band_file(self, band_file_path):
        """
        分析band.dat文件
        
        参数:
            band_file_path: band.dat文件的完整路径
            
        返回:
            dict: 包含band_gap和materials_type的字典
        """
        try:
            if not os.path.exists(band_file_path):
                current_app.logger.error(f"Band file not found: {band_file_path}")
                return None
            
            # 读取能带数据
            band_data = self._read_band_data(band_file_path)
            if band_data is None:
                return None
            
            # 计算带隙
            band_gap = self._calculate_band_gap(band_data)
            
            # 确定材料类型
            materials_type = self._determine_materials_type(band_gap)
            
            result = {
                'band_gap': round(band_gap, 6),
                'materials_type': materials_type,
                'analysis_info': {
                    'total_kpoints': len(band_data['kpoints']),
                    'total_bands': len(band_data['eigenvalues'][0]) if band_data['eigenvalues'] else 0,
                    'fermi_level': band_data.get('fermi_level', 0.0)
                }
            }
            
            current_app.logger.info(f"Band analysis completed: {result}")
            return result
            
        except Exception as e:
            current_app.logger.error(f"Error analyzing band file {band_file_path}: {str(e)}")
            return None
    
    def _read_band_data(self, band_file_path):
        """读取band.dat文件数据"""
        try:
            with open(band_file_path, 'r') as f:
                lines = f.readlines()

            if not lines:
                return None

            # 解析能带数据格式
            # 第1行：k点路径标签 (如 'Γ X M R X|M')
            # 第2行：k点坐标
            # 第3行开始：每行第一个值是k点索引，后面是所有能级值

            if len(lines) < 3:
                current_app.logger.error("Band file has insufficient lines")
                return None

            # 跳过第一行的k点标签
            # 第二行是k点坐标
            kpoint_line = lines[1].strip()
            kpoint_coords = [float(x) for x in kpoint_line.split()]

            # 从第三行开始读取能级数据
            eigenvalues = []

            for i, line in enumerate(lines[2:], start=2):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue

                parts = line.split()
                if len(parts) < 2:  # 至少需要k点索引 + 1个能级
                    continue

                # 第一个值是k点索引，跳过
                # 剩余的值是能级值
                eigenvals = [float(x) for x in parts[1:]]
                eigenvalues.append(eigenvals)

            # 生成k点列表（简化处理，使用索引作为k点坐标）
            kpoints = []
            for i in range(len(eigenvalues)):
                if i < len(kpoint_coords):
                    # 使用实际的k点坐标
                    kpoints.append([kpoint_coords[i], 0.0, 0.0])
                else:
                    # 如果k点坐标不够，使用索引
                    kpoints.append([float(i), 0.0, 0.0])

            current_app.logger.info(f"Read band data: {len(kpoints)} k-points, {len(eigenvalues[0]) if eigenvalues else 0} bands")

            return {
                'kpoints': kpoints,
                'eigenvalues': eigenvalues,
                'fermi_level': 0.0  # 默认费米能级为0
            }

        except Exception as e:
            current_app.logger.error(f"Error reading band data: {str(e)}")
            return None
    
    def _calculate_band_gap(self, band_data):
        """计算带隙"""
        try:
            eigenvalues = band_data['eigenvalues']
            fermi_level = band_data.get('fermi_level', 0.0)
            
            if not eigenvalues:
                return 0.0
            
            # 将所有能级相对于费米能级进行调整
            all_eigenvalues = []
            for kpoint_eigenvals in eigenvalues:
                for eigenval in kpoint_eigenvals:
                    all_eigenvalues.append(eigenval - fermi_level)
            
            all_eigenvalues = np.array(all_eigenvalues)
            
            # 找到价带顶 (VBM) 和导带底 (CBM)
            occupied_states = all_eigenvalues[all_eigenvalues <= 0]  # 费米能级以下
            unoccupied_states = all_eigenvalues[all_eigenvalues > 0]  # 费米能级以上
            
            if len(occupied_states) == 0 or len(unoccupied_states) == 0:
                # 如果没有明确的价带或导带分离，可能是金属
                return 0.0
            
            vbm = np.max(occupied_states)  # 价带顶
            cbm = np.min(unoccupied_states)  # 导带底
            
            band_gap = cbm - vbm
            
            # 确保带隙为正值
            return max(0.0, band_gap)
            
        except Exception as e:
            current_app.logger.error(f"Error calculating band gap: {str(e)}")
            return 0.0
    
    def _determine_materials_type(self, band_gap):
        """根据带隙确定材料类型"""
        if band_gap <= self.band_gap_threshold['metal']:
            return 'metal'
        elif band_gap <= self.band_gap_threshold['semimetal']:
            return 'semimetal'
        elif band_gap <= self.band_gap_threshold['semiconductor']:
            return 'semiconductor'
        else:
            return 'insulator'
    
    def save_analysis_to_json(self, analysis_result, json_file_path):
        """将分析结果保存到band.json文件"""
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(json_file_path), exist_ok=True)
            
            # 添加时间戳
            analysis_result['analyzed_at'] = __import__('datetime').datetime.now().isoformat()
            
            # 保存到JSON文件
            with open(json_file_path, 'w', encoding='utf-8') as f:
                json.dump(analysis_result, f, indent=2, ensure_ascii=False)
            
            current_app.logger.info(f"Band analysis saved to: {json_file_path}")
            return True
            
        except Exception as e:
            current_app.logger.error(f"Error saving analysis to {json_file_path}: {str(e)}")
            return False
    
    def analyze_material_band(self, material_id):
        """
        分析指定材料的能带数据
        
        参数:
            material_id: 材料ID
            
        返回:
            dict: 分析结果，如果失败返回None
        """
        try:
            # 构建文件路径
            material_dir = f"app/static/materials/IMR-{material_id}"
            band_file = os.path.join(material_dir, "band", "band.dat")
            json_file = os.path.join(material_dir, "band", "band.json")
            
            # 分析能带数据
            analysis_result = self.analyze_band_file(band_file)
            if analysis_result is None:
                return None
            
            # 保存分析结果
            if self.save_analysis_to_json(analysis_result, json_file):
                return analysis_result
            else:
                return None
                
        except Exception as e:
            current_app.logger.error(f"Error analyzing material {material_id}: {str(e)}")
            return None

# 全局分析器实例
band_analyzer = BandAnalyzer()

#!/usr/bin/env python3
"""
ICM文件管理系统
管理相机校色文件，提供品牌-型号-场景三级选择结构
"""

import os
import sys
import re
from typing import Dict, List, Optional, Tuple
from PIL import ImageCms
import threading
import time


class ICMManager:
    """ICM文件管理器"""

    def __init__(self, icm_directory: str = "DSLR"):
        """
        初始化ICM管理器

        Args:
            icm_directory: ICM文件目录路径
        """
        self.icm_directory = self._get_icm_directory(icm_directory)
        self.icm_cache = {}  # 文件名 -> ICC Profile缓存
        self.brand_model_scene_map = {}  # 品牌 -> 型号 -> 场景 -> ICM文件
        self.brands = []  # 可用品牌列表
        self.models = {}  # 品牌 -> 型号列表
        self.scenes = {}  # (品牌, 型号) -> 场景列表
        self._lock = threading.Lock()
        self._scanned = False

        # 预定义场景列表
        self.all_scenes = [
            "Generic", "Flat", "Landscape", "Monochrome",
            "Neutral", "Portrait", "Standard", "Vivid",
            "ProStandard", "Apple", "Daylight", "Flash",
            "Sunset", "Tungsten"
        ]

        # 如果目录存在，立即扫描
        if os.path.exists(self.icm_directory):
            self.refresh_icm_database()

    def _get_icm_directory(self, default_dir: str) -> str:
        """
        获取ICM文件目录路径，支持打包后的环境

        Args:
            default_dir: 默认目录名

        Returns:
            ICM文件目录的实际路径
        """
        # 首先检查是否在打包环境中运行
        if hasattr(sys, '_MEIPASS'):
            # PyInstaller打包环境
            base_path = sys._MEIPASS
            icm_path = os.path.join(base_path, default_dir)
            if os.path.exists(icm_path):
                return icm_path

        # 检查当前目录
        if os.path.exists(default_dir):
            return default_dir

        # 检查脚本所在目录
        script_dir = os.path.dirname(os.path.abspath(__file__))
        icm_path = os.path.join(script_dir, default_dir)
        if os.path.exists(icm_path):
            return icm_path

        # 检查工作目录
        current_dir = os.getcwd()
        icm_path = os.path.join(current_dir, default_dir)
        if os.path.exists(icm_path):
            return icm_path

        # 最后返回默认路径，即使不存在
        return default_dir

    def _parse_icm_filename(self, filename: str) -> Optional[Tuple[str, str, str]]:
        """
        解析ICM文件名，提取品牌、型号、场景信息

        Args:
            filename: ICM文件名 (如 "CanonEOSR5-Generic.icm")

        Returns:
            (品牌, 型号, 场景) 或 None
        """
        # 移除.icm扩展名
        basename = os.path.splitext(filename)[0]

        # 匹配模式：品牌型号-场景
        # 常见品牌模式
        brand_patterns = [
            r'^(Canon)(.+?)-(.+?)$',  # Canon模式
            r'^(Nikon)(.+?)-(.+?)$',  # Nikon模式
            r'^(Sony)(.+?)-(.+?)$',   # Sony模式
            r'^(Fujifilm)(.+?)-(.+?)$', # Fujifilm模式
            r'^(Olympus)(.+?)-(.+?)$', # Olympus模式
            r'^(Panasonic)(.+?)-(.+?)$', # Panasonic模式
            r'^(Leica)(.+?)-(.+?)$',   # Leica模式
            r'^(Pentax)(.+?)-(.+?)$',  # Pentax模式
            r'^(Samsung)(.+?)-(.+?)$', # Samsung模式
            r'^(Apple)(.+?)-(.+?)$',   # Apple模式
        ]

        for pattern in brand_patterns:
            match = re.match(pattern, basename, re.IGNORECASE)
            if match:
                brand, model, scene = match.groups()
                # 标准化品牌名
                brand = brand.title()
                # 清理型号名
                model = self._clean_model_name(model)
                # 标准化场景名
                scene = self._clean_scene_name(scene)
                return brand, model, scene

        # 特殊处理：文件系统相关的配置文件
        if basename.startswith('FileSystem'):
            return 'FileSystem', basename.replace('FileSystem', ''), 'neutral'

        return None

    def _clean_model_name(self, model: str) -> str:
        """清理型号名称"""
        # 移除多余的空格和特殊字符
        model = re.sub(r'\s+', '', model)
        model = re.sub(r'[-_]+', ' ', model)
        return model.strip()

    def _clean_scene_name(self, scene: str) -> str:
        """清理场景名称"""
        # 移除版本信息
        scene = re.sub(r'\s+V\d+$', '', scene)
        # 标准化场景名称
        scene_mapping = {
            'neutral': 'Neutral',
            'standard': 'Standard',
            'vivid': 'Vivid',
            'portrait': 'Portrait',
            'landscape': 'Landscape',
            'monochrome': 'Monochrome',
            'flat': 'Flat',
            'generic': 'Generic',
            'prostandard': 'ProStandard',
            'apple': 'Apple',
            'daylight': 'Daylight',
            'flash': 'Flash',
            'sunset': 'Sunset',
            'tungsten': 'Tungsten'
        }

        scene_lower = scene.lower().strip()
        return scene_mapping.get(scene_lower, scene.title())

    def scan_icm_files(self) -> Dict[str, Dict[str, List[str]]]:
        """
        扫描ICM文件并建立品牌-型号-场景映射

        Returns:
            品牌字典结构
        """
        print(f"正在扫描ICM文件目录: {self.icm_directory}")

        if not os.path.exists(self.icm_directory):
            print(f"警告: ICM目录不存在: {self.icm_directory}")
            return {}

        with self._lock:
            # 清空现有数据
            self.brand_model_scene_map.clear()
            self.brands.clear()
            self.models.clear()
            self.scenes.clear()
            self.icm_cache.clear()

            scanned_count = 0

            # 扫描目录中的所有.icm文件
            for filename in os.listdir(self.icm_directory):
                if filename.lower().endswith('.icm'):
                    parsed = self._parse_icm_filename(filename)
                    if parsed:
                        brand, model, scene = parsed

                        # 添加到品牌-型号-场景映射
                        if brand not in self.brand_model_scene_map:
                            self.brand_model_scene_map[brand] = {}
                        if model not in self.brand_model_scene_map[brand]:
                            self.brand_model_scene_map[brand][model] = []

                        # 避免重复场景
                        if scene not in self.brand_model_scene_map[brand][model]:
                            self.brand_model_scene_map[brand][model].append(scene)

                        scanned_count += 1

            # 构建快速查找列表
            self.brands = sorted(self.brand_model_scene_map.keys())

            for brand, models_dict in self.brand_model_scene_map.items():
                self.models[brand] = sorted(models_dict.keys())
                for model, scenes_list in models_dict.items():
                    key = (brand, model)
                    if key not in self.scenes:
                        self.scenes[key] = []
                    # 合并场景列表并去重
                    for scene in scenes_list:
                        if scene not in self.scenes[key]:
                            self.scenes[key].append(scene)
                    self.scenes[key] = sorted(self.scenes[key])

            self._scanned = True
            print(f"ICM文件扫描完成，共处理 {scanned_count} 个文件")
            print(f"发现品牌: {len(self.brands)}, 型号: {sum(len(models) for models in self.models.values())}")

            return self.brand_model_scene_map

    def get_available_brands(self) -> List[str]:
        """
        获取所有可用品牌列表

        Returns:
            品牌列表
        """
        if not self._scanned:
            self.scan_icm_files()
        return self.brands.copy()

    def get_available_models(self, brand: str) -> List[str]:
        """
        获取指定品牌的型号列表

        Args:
            brand: 相机品牌

        Returns:
            型号列表
        """
        if not self._scanned:
            self.scan_icm_files()
        return self.models.get(brand, []).copy()

    def get_available_scenes(self, brand: str, model: str) -> List[str]:
        """
        获取指定品牌型号的可用场景列表

        Args:
            brand: 相机品牌
            model: 相机型号

        Returns:
            场景列表
        """
        if not self._scanned:
            self.scan_icm_files()
        key = (brand, model)
        return self.scenes.get(key, []).copy()

    def get_icm_file(self, brand: str, model: str, scene: str) -> Optional[str]:
        """
        获取指定的ICM文件路径

        Args:
            brand: 相机品牌
            model: 相机型号
            scene: 校色场景

        Returns:
            ICM文件完整路径，如果不存在返回None
        """
        if not self._scanned:
            self.scan_icm_files()

        if brand not in self.brand_model_scene_map:
            return None
        if model not in self.brand_model_scene_map[brand]:
            return None
        if scene not in self.brand_model_scene_map[brand][model]:
            return None

        # 构建文件名
        # 特殊处理FileSystem
        if brand == 'FileSystem':
            filename = f"FileSystem{model}-{scene}.icm"
        else:
            # 去掉型号中的空格，匹配文件名格式
            clean_model = model.replace(' ', '')
            filename = f"{brand}{clean_model}-{scene}.icm"

        icm_path = os.path.join(self.icm_directory, filename)
        if os.path.exists(icm_path):
            return icm_path

        # 尝试一些常见的变体
        variants = [
            f"{brand}{model}-{scene}.icm",  # 保留空格
            f"{brand}{model.lower()}-{scene}.icm",  # 小写型号
            f"{brand}{clean_model}-{scene}.icm",  # 无空格
        ]

        for variant in variants:
            test_path = os.path.join(self.icm_directory, variant)
            if os.path.exists(test_path):
                return test_path

        # 如果是在打包环境中，尝试在所有可能的路径中查找
        if hasattr(sys, '_MEIPASS'):
            base_path = sys._MEIPASS
            for variant in [filename] + variants:
                test_path = os.path.join(base_path, "DSLR", variant)
                if os.path.exists(test_path):
                    return test_path

        return None

    def load_icc_profile(self, icm_path: str) -> Optional[ImageCms.ImageCmsProfile]:
        """
        加载ICC配置文件

        Args:
            icm_path: ICM文件路径

        Returns:
            ICC Profile对象，失败返回None
        """
        if not os.path.exists(icm_path):
            return None

        # 检查缓存
        if icm_path in self.icm_cache:
            return self.icm_cache[icm_path]

        try:
            profile = ImageCms.ImageCmsProfile(icm_path)

            # 缓存配置文件（限制缓存大小）
            with self._lock:
                if len(self.icm_cache) > 100:  # 限制缓存数量
                    # 移除最旧的缓存项
                    oldest_key = next(iter(self.icm_cache))
                    del self.icm_cache[oldest_key]

                self.icm_cache[icm_path] = profile

            return profile
        except Exception as e:
            print(f"警告: 加载ICM文件失败 {icm_path}: {str(e)}")
            return None

    def refresh_icm_database(self):
        """刷新ICM文件数据库"""
        print("正在刷新ICM文件数据库...")
        self.scan_icm_files()

    def get_statistics(self) -> Dict[str, int]:
        """
        获取ICM文件统计信息

        Returns:
            统计信息字典
        """
        if not self._scanned:
            self.scan_icm_files()

        total_models = sum(len(models) for models in self.models.values())
        total_scenes = sum(len(scenes) for scenes in self.scenes.values())

        return {
            'brands': len(self.brands),
            'models': total_models,
            'scenes': total_scenes,
            'icm_files': sum(
                len(scenes)
                for brand_dict in self.brand_model_scene_map.values()
                for scenes in brand_dict.values()
            )
        }


# 全局ICM管理器实例
_icm_manager = None

def get_icm_manager() -> ICMManager:
    """获取全局ICM管理器实例"""
    global _icm_manager
    if _icm_manager is None:
        _icm_manager = ICMManager()
    return _icm_manager


if __name__ == "__main__":
    # 测试代码
    manager = ICMManager()

    print("=== ICM文件管理器测试 ===")

    # 显示统计信息
    stats = manager.get_statistics()
    print(f"统计信息: {stats}")

    # 显示品牌列表
    brands = manager.get_available_brands()
    print(f"可用品牌 ({len(brands)}): {brands[:10]}...")  # 显示前10个

    # 显示每个品牌的型号数量
    for brand in brands[:5]:  # 前5个品牌
        models = manager.get_available_models(brand)
        print(f"{brand}: {len(models)} 个型号")
        if models:
            print(f"  示例型号: {models[:3]}")  # 显示前3个型号

            # 显示第一个型号的场景
            scenes = manager.get_available_scenes(brand, models[0])
            print(f"  {models[0]} 场景: {scenes}")

    # 测试文件查找
    test_brand = "Canon"
    if test_brand in brands:
        models = manager.get_available_models(test_brand)
        if models:
            test_model = models[0]
            scenes = manager.get_available_scenes(test_brand, test_model)
            if scenes:
                test_scene = scenes[0]
                icm_path = manager.get_icm_file(test_brand, test_model, test_scene)
                print(f"\n测试查找: {test_brand} {test_model} {test_scene}")
                print(f"ICM文件路径: {icm_path}")

                # 测试加载ICC配置
                if icm_path:
                    profile = manager.load_icc_profile(icm_path)
                    if profile:
                        print(f"ICC配置加载成功: {os.path.basename(icm_path)}")
                    else:
                        print("ICC配置加载失败")
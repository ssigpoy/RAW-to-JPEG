#!/usr/bin/env python3
"""
相机型号识别系统
从RAW文件中提取相机品牌和型号信息
"""

import os
import re
from typing import Optional, Tuple, Dict
import rawpy


class CameraDetector:
    """相机型号检测器"""

    def __init__(self):
        """初始化相机检测器"""
        # 品牌映射表 - 标准化品牌名称
        self.brand_mapping = {
            'Canon': 'Canon',
            'NIKON': 'Nikon',
            'NIKON CORPORATION': 'Nikon',
            'Sony': 'Sony',
            'SONY': 'Sony',
            'Fujifilm': 'Fujifilm',
            'FUJIFILM': 'Fujifilm',
            'Olympus': 'Olympus',
            'OLYMPUS IMAGING CORP.': 'Olympus',
            'Panasonic': 'Panasonic',
            'Panasonic Corporation': 'Panasonic',
            'LEICA': 'Leica',
            'Leica': 'Leica',
            'Leica Camera AG': 'Leica',
            'Pentax': 'Pentax',
            'PENTAX': 'Pentax',
            'RICOH IMAGING COMPANY, LTD.': 'Pentax',
            'Samsung': 'Samsung',
            'SAMSUNG': 'Samsung',
            'Apple': 'Apple',
            'Hasselblad': 'Hasselblad',
            'Phase One': 'PhaseOne',
            'Mamiya': 'Mamiya',
            'Leaf': 'Leaf',
            'Contax': 'Contax',
            'Kodak': 'Kodak',
        }

        # 型号清理规则
        self.model_cleanup_rules = [
            # 移除公司名称
            (r'\b(Canon|NIKON|SONY|Fujifilm|FUJIFILM|Olympus|Panasonic|Leica|Pentax|Samsung|Apple)\s+', ''),
            # 移除常见前缀
            (r'^(EOS|DSC|ILCE|DMC|GR|K-|X-T|GFX|Hasselblad|Phase\s+One)\s*', ''),
            # 清理多余空格和符号
            (r'\s+', ' '),
            (r'[()]', ''),
            (r'\s*-\s*', ' '),
        ]

        # 品牌前缀模式 - 用于从型号中识别品牌
        self.brand_prefix_patterns = {
            'Canon': [r'^EOS', r'^PowerShot', r'^IXUS'],
            'Nikon': [r'^D\d+', r'^Z\d+', r'^COOLPIX'],
            'Sony': [r'^ILCE-', r'^ILCA-', r'^DSC', r'^α'],
            'Fujifilm': [r'^X-', r'^GFX', r'^FinePix'],
            'Olympus': [r'^E-', r'^STYLUS', r'^TOUGH'],
            'Panasonic': [r'^DMC-', r'^LUMIX'],
            'Leica': [r'^M\d+', r'^SL\d+', r'^Q\d+', r'^CL'],
            'Pentax': [r'^K-\d+', r'^KP', r'^645D', r'^645Z'],
            'Samsung': [r'^NX\d+', r'^Galaxy'],
            'Apple': [r'^iPhone', r'^iPad'],
        }

    def extract_camera_info(self, raw_path: str) -> Optional[Dict[str, str]]:
        """
        从RAW文件中提取相机信息

        Args:
            raw_path: RAW文件路径

        Returns:
            包含相机信息的字典，失败返回None
        """
        if not os.path.exists(raw_path):
            return None

        try:
            with rawpy.imread(raw_path) as raw:
                # 从RAW元数据获取相机信息
                metadata = getattr(raw, 'raw_metadata', {})

                # 尝试不同的元数据字段
                camera_make = (
                    metadata.get('camera_make') or
                    metadata.get('Make') or
                    metadata.get('make') or
                    ''
                )

                camera_model = (
                    metadata.get('camera_model') or
                    metadata.get('Model') or
                    metadata.get('model') or
                    ''
                )

                # 如果没有从raw_metadata获取到，尝试其他属性
                if not camera_make or not camera_model:
                    # 尝试从其他属性获取
                    if hasattr(raw, 'color_desc') and raw.color_desc:
                        # 某些情况下可以从color_desc推断
                        pass

                return {
                    'make': camera_make.strip(),
                    'model': camera_model.strip(),
                }

        except Exception as e:
            print(f"警告: 读取RAW元数据失败 {raw_path}: {str(e)}")
            return None

    def normalize_camera_model(self, make: str, model: str) -> Tuple[str, str]:
        """
        标准化相机品牌和型号名称用于ICM匹配

        Args:
            make: 相机制造商
            model: 相机型号

        Returns:
            (标准化品牌, 标准化型号)
        """
        # 标准化品牌
        brand = self._normalize_brand(make)

        # 如果无法确定品牌，尝试从型号推断
        if brand == 'Unknown':
            brand = self._infer_brand_from_model(model)

        # 标准化型号
        normalized_model = self._normalize_model(model, brand)

        return brand, normalized_model

    def _normalize_brand(self, make: str) -> str:
        """标准化相机品牌"""
        if not make:
            return 'Unknown'

        make_clean = make.strip()

        # 直接匹配
        if make_clean in self.brand_mapping:
            return self.brand_mapping[make_clean]

        # 模糊匹配
        make_lower = make_clean.lower()
        for mapped_make, standard_name in self.brand_mapping.items():
            if mapped_make.lower() in make_lower or make_lower in mapped_make.lower():
                return standard_name

        return 'Unknown'

    def _infer_brand_from_model(self, model: str) -> str:
        """从型号推断相机品牌"""
        if not model:
            return 'Unknown'

        model_clean = model.strip()

        for brand, patterns in self.brand_prefix_patterns.items():
            for pattern in patterns:
                if re.search(pattern, model_clean, re.IGNORECASE):
                    return brand

        return 'Unknown'

    def _normalize_model(self, model: str, brand: str) -> str:
        """标准化相机型号"""
        if not model:
            return 'Unknown'

        # 基础清理
        model_clean = model.strip()

        # 应用清理规则
        for pattern, replacement in self.model_cleanup_rules:
            model_clean = re.sub(pattern, replacement, model_clean, flags=re.IGNORECASE)

        # 品牌特定清理
        model_clean = self._brand_specific_model_cleanup(model_clean, brand)

        # 最终清理
        model_clean = re.sub(r'\s+', ' ', model_clean).strip()

        # 确保型号不为空
        if not model_clean:
            return 'Unknown'

        return model_clean

    def _brand_specific_model_cleanup(self, model: str, brand: str) -> str:
        """品牌特定的型号清理"""
        if brand == 'Canon':
            # Canon特殊处理
            model = re.sub(r'Canon\s*', '', model, flags=re.IGNORECASE)
            model = re.sub(r'^EOS\s+', 'EOS', model, flags=re.IGNORECASE)
            # 处理Rebel系列
            model = re.sub(r'Rebel\s+([A-Z]\d+)', r'EOS \1', model, flags=re.IGNORECASE)

        elif brand == 'Nikon':
            # Nikon特殊处理
            model = re.sub(r'Nikon\s*', '', model, flags=re.IGNORECASE)
            # 标准化D系列
            model = re.sub(r'^D(\d+)', r'D\1', model, flags=re.IGNORECASE)
            # 标准化Z系列
            model = re.sub(r'^Z\s*(\d+)', r'Z\1', model, flags=re.IGNORECASE)

        elif brand == 'Sony':
            # Sony特殊处理
            model = re.sub(r'Sony\s*', '', model, flags=re.IGNORECASE)
            # 标准化ILCE系列
            model = re.sub(r'^ILCE[-\s]*(\d+)', r'α\1', model, flags=re.IGNORECASE)
            model = re.sub(r'^α\s*(\d+)', r'α\1', model, flags=re.IGNORECASE)

        elif brand == 'Fujifilm':
            # Fujifilm特殊处理
            model = re.sub(r'Fujifilm\s*', '', model, flags=re.IGNORECASE)
            # 标准化X系列
            model = re.sub(r'^X[-\s]*(\w+)', r'X-\1', model, flags=re.IGNORECASE)
            # 标准化GFX系列
            model = re.sub(r'^GFX\s*(\w+)', r'GFX\1', model, flags=re.IGNORECASE)

        elif brand == 'Olympus':
            # Olympus特殊处理
            model = re.sub(r'Olympus\s*', '', model, flags=re.IGNORECASE)

        elif brand == 'Panasonic':
            # Panasonic特殊处理
            model = re.sub(r'Panasonic\s*', '', model, flags=re.IGNORECASE)
            # 标准化DMC系列
            model = re.sub(r'^DMC[-\s]*(\w+)', r'DMC-\1', model, flags=re.IGNORECASE)

        return model

    def detect_camera_from_raw(self, raw_path: str) -> Optional[Tuple[str, str]]:
        """
        从RAW文件检测相机品牌和型号

        Args:
            raw_path: RAW文件路径

        Returns:
            (品牌, 型号) 或 None
        """
        camera_info = self.extract_camera_info(raw_path)
        if not camera_info:
            return None

        make = camera_info.get('make', '')
        model = camera_info.get('model', '')

        if not make and not model:
            return None

        brand, normalized_model = self.normalize_camera_model(make, model)

        if brand != 'Unknown' and normalized_model != 'Unknown':
            return brand, normalized_model

        return None

    def get_supported_file_extensions(self) -> list:
        """获取支持的RAW文件扩展名"""
        return [
            '.arw',   # Sony
            '.cr2', '.cr3',  # Canon
            '.dng',   # Adobe DNG
            '.nef',   # Nikon
            '.raw',   # Generic
            '.orf',   # Olympus
            '.rw2',   # Panasonic
            '.pef',   # Pentax
            '.srw',   # Samsung
            '.mos',   # Leica
            '.mrw',   # Minolta
            '.erf',   # Epson
            '.k25', '.kc2', '.kdc',  # Kodak
            '.raf',   # Fujifilm
            '.3fr',   # Hasselblad
            '.fff',   # Hasselblad
            '.iiq',   # Phase One
            '.mos',   # Leaf
            '.crw',   # Canon old format
            '.bay',   # Casio
            '.bmq',   # Nokia
            '.cap',   # Phase One
            '.cine',  # Imacon
            '.cs1',   # Captureshop
            '.dc2',   # Sinar
            '.dcr',   # Kodak
            '.dcs',   # Kodak
            '.drf',   # Kodak
            '.dsc',   # Konica Minolta
            '.exr',   # OpenEXR
            '.fff',   # Hasselblad
            '.ia',    # Imacon
            '.jpg',   # JPEG (for testing)
            '.jpeg',  # JPEG (for testing)
            '.tif', '.tiff',  # TIFF
        ]

    def is_raw_file(self, file_path: str) -> bool:
        """检查文件是否为RAW格式"""
        ext = os.path.splitext(file_path)[1].lower()
        return ext in self.get_supported_file_extensions()


# 全局相机检测器实例
_camera_detector = None

def get_camera_detector() -> CameraDetector:
    """获取全局相机检测器实例"""
    global _camera_detector
    if _camera_detector is None:
        _camera_detector = CameraDetector()
    return _camera_detector


if __name__ == "__main__":
    # 测试代码
    detector = CameraDetector()

    print("=== 相机检测器测试 ===")

    # 测试标准化功能
    test_cases = [
        ('Canon', 'Canon EOS R5'),
        ('NIKON CORPORATION', 'NIKON Z9'),
        ('SONY', 'ILCE-7RM4'),
        ('FUJIFILM', 'GFX100S'),
        ('OLYMPUS IMAGING CORP.', 'E-M1 Mark III'),
        ('Apple', 'iPhone 13 Pro'),
        ('', 'EOS R6'),  # 只有型号
        ('Canon', ''),   # 只有品牌
        ('', ''),        # 都为空
    ]

    print("测试型号标准化:")
    for make, model in test_cases:
        brand, normalized_model = detector.normalize_camera_model(make, model)
        print(f"输入: {make!r} + {model!r}")
        print(f"输出: {brand!r} + {normalized_model!r}")
        print("---")

    # 显示支持的文件格式
    print(f"支持的文件格式 ({len(detector.get_supported_file_extensions())}):")
    formats = detector.get_supported_file_extensions()
    print(", ".join(formats[:15]) + "...")  # 显示前15个

    # 如果当前目录有RAW文件，可以测试检测
    print("\n如需测试实际RAW文件检测，请提供RAW文件路径")
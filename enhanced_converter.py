#!/usr/bin/env python3
"""
增强RAW转换引擎
优化转换性能、错误处理和内存管理
"""

import os
import rawpy
import imageio
import threading
import time
import psutil
from typing import List, Dict, Optional, Tuple, Callable
from dataclasses import dataclass
from pathlib import Path
import concurrent.futures
from enum import Enum
from PIL import Image, ImageCms
import numpy

# 导入ICM管理器和相机检测器
try:
    from icm_manager import get_icm_manager
    from camera_detector import get_camera_detector
    ICM_AVAILABLE = True
except ImportError:
    ICM_AVAILABLE = False
    print("警告: ICM功能模块未找到，校色功能将被禁用")

# 支持的RAW格式
SUPPORTED_FORMATS = {
    '.arw': 'Sony',
    '.cr2': 'Canon',
    '.cr3': 'Canon',
    '.dng': 'Adobe DNG',
    '.nef': 'Nikon',
    '.raw': 'Generic',
    '.orf': 'Olympus',
    '.rw2': 'Panasonic',
    '.pef': 'Pentax',
    '.srw': 'Samsung',
    '.mos': 'Leica'
}

class ConversionStatus(Enum):
    """转换状态枚举"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

@dataclass
class ConversionConfig:
    """转换配置类"""
    jpeg_quality: int = 95
    use_camera_wb: bool = True
    use_auto_wb: bool = False
    output_bps: int = 8
    bright: float = 1.0
    no_auto_bright: bool = False
    half_size: bool = False
    exp_shift: float = 0.0
    exp_preserve_highlights: bool = True
    four_color_rgb: bool = False
    max_threads: Optional[int] = None  # None表示自动检测

    # ICM校色相关配置
    enable_icm_correction: bool = True  # 启用ICM校色
    icm_brand: str = ""             # 品牌选择
    icm_model: str = ""             # 型号选择
    icm_scene: str = "Generic"     # 校色场景
    manual_icm_path: Optional[str] = None  # 手动指定的ICM文件路径
    strict_icm: bool = True        # 严格模式：校色失败则中断
    auto_detect_camera: bool = True  # 自动检测相机型号

@dataclass
class ConversionResult:
    """转换结果类"""
    input_path: str
    output_path: str
    status: ConversionStatus
    start_time: float
    end_time: float
    file_size_input: int
    file_size_output: int
    error_message: str = ""
    processing_time: float = 0.0

    # ICM校色相关信息
    camera_brand: str = ""
    camera_model: str = ""
    icm_applied: bool = False
    icm_file: str = ""

class ConversionMetrics:
    """转换性能指标"""
    def __init__(self):
        self.total_files = 0
        self.completed_files = 0
        self.failed_files = 0
        self.skipped_files = 0
        self.total_size_input = 0
        self.total_size_output = 0
        self.total_processing_time = 0.0
        self.average_processing_time = 0.0
        self.conversion_rate = 0.0  # MB/s
        self.start_time = 0.0
        self.end_time = 0.0

    def start_timing(self):
        """开始计时"""
        self.start_time = time.time()

    def end_timing(self):
        """结束计时"""
        self.end_time = time.time()

    def add_result(self, result: ConversionResult):
        """添加转换结果"""
        self.total_files += 1

        if result.status == ConversionStatus.COMPLETED:
            self.completed_files += 1
            self.total_size_input += result.file_size_input
            self.total_size_output += result.file_size_output
            self.total_processing_time += result.processing_time
        elif result.status == ConversionStatus.FAILED:
            self.failed_files += 1
        elif result.status == ConversionStatus.SKIPPED:
            self.skipped_files += 1

    def calculate_metrics(self):
        """计算性能指标"""
        if self.completed_files > 0:
            self.average_processing_time = self.total_processing_time / self.completed_files

            total_mb = self.total_size_input / (1024 * 1024)
            if total_mb > 0 and self.total_processing_time > 0:
                self.conversion_rate = total_mb / self.total_processing_time

    def get_summary(self) -> Dict:
        """获取指标摘要"""
        return {
            'total_files': self.total_files,
            'completed': self.completed_files,
            'failed': self.failed_files,
            'skipped': self.skipped_files,
            'success_rate': (self.completed_files / self.total_files * 100) if self.total_files > 0 else 0,
            'total_time': self.end_time - self.start_time,
            'avg_time_per_file': self.average_processing_time,
            'conversion_rate_mbps': self.conversion_rate,
            'size_compression': (1 - self.total_size_output / self.total_size_input * 100) if self.total_size_input > 0 else 0
        }

class EnhancedRAWConverter:
    """增强RAW转换器"""

    def __init__(self, config: Optional[ConversionConfig] = None):
        self.config = config or ConversionConfig()
        self.metrics = ConversionMetrics()
        self.is_converting = False
        self.progress_callback: Optional[Callable] = None
        self.status_callback: Optional[Callable] = None

        # 系统资源检测
        self.max_threads = self._detect_optimal_threads()
        self.memory_limit = self._detect_memory_limit()

        # ICM校色组件初始化
        self.icm_manager = None
        self.camera_detector = None
        if ICM_AVAILABLE and self.config.enable_icm_correction:
            try:
                self.icm_manager = get_icm_manager()
                self.camera_detector = get_camera_detector()
            except Exception as e:
                print(f"警告: ICM组件初始化失败: {str(e)}")
                self.config.enable_icm_correction = False

    def _detect_optimal_threads(self) -> int:
        """检测最优线程数"""
        cpu_count = os.cpu_count() or 1
        memory_gb = psutil.virtual_memory().total / (1024**3)

        # 基于CPU核心数和内存限制确定线程数
        if self.config.max_threads:
            return min(self.config.max_threads, cpu_count)

        # RAW处理比较消耗内存，限制线程数
        optimal_threads = min(cpu_count, max(1, int(memory_gb / 2)))
        return min(optimal_threads, 4)  # 最多4个线程

    def _detect_memory_limit(self) -> int:
        """检测内存限制(MB)"""
        total_memory = psutil.virtual_memory().total
        available_memory = psutil.virtual_memory().available

        # 使用70%的可用内存作为限制
        return int(available_memory * 0.7 / (1024 * 1024))

    def set_progress_callback(self, callback: Callable[[int, int], None]):
        """设置进度回调函数"""
        self.progress_callback = callback

    def set_status_callback(self, callback: Callable[[str], None]):
        """设置状态回调函数"""
        self.status_callback = callback

    def scan_raw_files(self, input_path: str, recursive: bool = True) -> List[str]:
        """扫描RAW文件"""
        raw_files = []

        try:
            if recursive:
                for root, dirs, files in os.walk(input_path):
                    for file in files:
                        if self._is_raw_file(file):
                            raw_files.append(os.path.join(root, file))
            else:
                for file in os.listdir(input_path):
                    if self._is_raw_file(file):
                        raw_files.append(os.path.join(input_path, file))

        except Exception as e:
            raise Exception(f"扫描文件失败: {str(e)}")

        return sorted(raw_files)

    def _is_raw_file(self, filename: str) -> bool:
        """检查是否为RAW文件"""
        ext = Path(filename).suffix.lower()
        return ext in SUPPORTED_FORMATS

    def prepare_output_path(self, input_path: str, output_dir: str) -> str:
        """准备输出文件路径"""
        # 保持相对路径结构
        relative_path = os.path.relpath(input_path, os.path.dirname(input_path))
        name_without_ext = os.path.splitext(relative_path)[0]

        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)

        return os.path.join(output_dir, f"{name_without_ext}.jpg")

    def convert_single_file(self, input_path: str, output_path: str) -> ConversionResult:
        """转换单个文件"""
        start_time = time.time()
        file_size_input = os.path.getsize(input_path) if os.path.exists(input_path) else 0

        # 初始化结果变量
        camera_brand = ""
        camera_model = ""
        icm_applied = False
        icm_file = ""

        try:
            # 检查输出目录
            output_dir = os.path.dirname(output_path)
            os.makedirs(output_dir, exist_ok=True)

            # 检查输出文件是否已存在
            if os.path.exists(output_path):
                return ConversionResult(
                    input_path=input_path,
                    output_path=output_path,
                    status=ConversionStatus.SKIPPED,
                    start_time=start_time,
                    end_time=time.time(),
                    file_size_input=file_size_input,
                    file_size_output=0,
                    error_message="输出文件已存在"
                )

            # 相机检测
            if self.config.auto_detect_camera and self.camera_detector:
                camera_brand, camera_model = self.detect_camera_from_file(input_path)

            # 确定ICM文件
            if self.config.enable_icm_correction:
                icm_file = self.determine_icm_file(input_path, camera_brand, camera_model)

            # 执行转换
            self._convert_with_rawpy(input_path, output_path, camera_brand, camera_model)

            # 标记ICM应用状态
            icm_applied = self.config.enable_icm_correction and bool(icm_file)

            end_time = time.time()
            file_size_output = os.path.getsize(output_path) if os.path.exists(output_path) else 0

            return ConversionResult(
                input_path=input_path,
                output_path=output_path,
                status=ConversionStatus.COMPLETED,
                start_time=start_time,
                end_time=end_time,
                file_size_input=file_size_input,
                file_size_output=file_size_output,
                processing_time=end_time - start_time,
                camera_brand=camera_brand,
                camera_model=camera_model,
                icm_applied=icm_applied,
                icm_file=icm_file
            )

        except Exception as e:
            end_time = time.time()
            return ConversionResult(
                input_path=input_path,
                output_path=output_path,
                status=ConversionStatus.FAILED,
                start_time=start_time,
                end_time=end_time,
                file_size_input=file_size_input,
                file_size_output=0,
                error_message=str(e),
                processing_time=end_time - start_time,
                camera_brand=camera_brand,
                camera_model=camera_model,
                icm_applied=icm_applied,
                icm_file=icm_file
            )

    def _convert_with_rawpy(self, input_path: str, output_path: str,
                        detected_brand: str = "", detected_model: str = ""):
        """使用rawpy进行转换"""
        try:
            with rawpy.imread(input_path) as raw:
                # 优化的处理参数
                rgb = raw.postprocess(
                    use_camera_wb=self.config.use_camera_wb,
                    use_auto_wb=self.config.use_auto_wb,
                    output_bps=self.config.output_bps,
                    bright=self.config.bright,
                    no_auto_bright=self.config.no_auto_bright,
                    half_size=self.config.half_size,
                    exp_shift=self.config.exp_shift,
                    exp_preserve_highlights=self.config.exp_preserve_highlights,
                    four_color_rgb=self.config.four_color_rgb,
                )

            # 应用ICM校色
            if self.config.enable_icm_correction:
                rgb = self.apply_icm_correction(input_path, rgb, detected_brand, detected_model)

            # 保存JPEG
            imageio.imwrite(output_path, rgb, quality=self.config.jpeg_quality)

        except Exception as e:
            # 重新抛出转换错误
            raise Exception(f"RAW转换失败: {str(e)}")

    def convert_batch(self, input_files: List[str], output_dir: str,
                     max_workers: Optional[int] = None) -> List[ConversionResult]:
        """批量转换文件"""
        if not input_files:
            return []

        self.is_converting = True
        self.metrics = ConversionMetrics()
        self.metrics.start_timing()

        # 准备输出路径
        file_pairs = []
        for input_file in input_files:
            output_path = self.prepare_output_path(input_file, output_dir)
            file_pairs.append((input_file, output_path))

        # 确定工作线程数
        workers = max_workers or self.max_threads

        results = []

        try:
            if len(file_pairs) == 1:
                # 单文件直接转换
                result = self.convert_single_file(file_pairs[0][0], file_pairs[0][1])
                results = [result]
            else:
                # 多文件并行转换
                results = self._convert_parallel(file_pairs, workers)

        except Exception as e:
            if self.status_callback:
                self.status_callback(f"批量转换失败: {str(e)}")
            raise
        finally:
            self.is_converting = False
            self.metrics.end_timing()

            # 更新指标
            for result in results:
                self.metrics.add_result(result)
            self.metrics.calculate_metrics()

        return results

    def _convert_parallel(self, file_pairs: List[Tuple[str, str]],
                         max_workers: int) -> List[ConversionResult]:
        """并行转换文件"""
        results = [None] * len(file_pairs)
        completed_count = 0

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            future_to_index = {
                executor.submit(self.convert_single_file, input_path, output_path): i
                for i, (input_path, output_path) in enumerate(file_pairs)
            }

            # 等待任务完成
            for future in concurrent.futures.as_completed(future_to_index):
                if not self.is_converting:
                    # 取消剩余任务
                    for f in future_to_index:
                        f.cancel()
                    break

                index = future_to_index[future]
                try:
                    result = future.result()
                    results[index] = result
                    completed_count += 1

                    # 更新进度
                    if self.progress_callback:
                        self.progress_callback(completed_count, len(file_pairs))

                    # 更新状态
                    if self.status_callback:
                        filename = os.path.basename(result.input_path)
                        if result.status == ConversionStatus.COMPLETED:
                            self.status_callback(f"已完成: {filename}")
                        elif result.status == ConversionStatus.FAILED:
                            self.status_callback(f"失败: {filename} - {result.error_message}")
                        elif result.status == ConversionStatus.SKIPPED:
                            self.status_callback(f"跳过: {filename}")

                except Exception as e:
                    # 创建失败结果
                    input_path, output_path = file_pairs[index]
                    results[index] = ConversionResult(
                        input_path=input_path,
                        output_path=output_path,
                        status=ConversionStatus.FAILED,
                        start_time=time.time(),
                        end_time=time.time(),
                        file_size_input=0,
                        file_size_output=0,
                        error_message=str(e)
                    )

        return results

    def stop_conversion(self):
        """停止转换"""
        self.is_converting = False

    def get_metrics(self) -> Dict:
        """获取转换指标"""
        return self.metrics.get_summary()

    def estimate_conversion_time(self, files: List[str]) -> Tuple[float, float]:
        """估算转换时间和内存需求"""
        if not files:
            return 0.0, 0.0

        total_size = 0
        sample_count = min(5, len(files))  # 采样5个文件

        # 估算文件大小
        for file_path in files[:sample_count]:
            if os.path.exists(file_path):
                total_size += os.path.getsize(file_path)

        avg_size = total_size / sample_count if sample_count > 0 else 0
        estimated_total_size = avg_size * len(files)

        # 估算时间 (基于经验值: 约每MB需要0.5-2秒)
        size_mb = estimated_total_size / (1024 * 1024)
        estimated_time = size_mb * 1.0  # 1秒每MB的平均估算

        # 估算内存需求 (考虑并行处理)
        estimated_memory = (estimated_total_size * 3) / (1024 * 1024)  # 3倍文件大小作为缓存
        estimated_memory = min(estimated_memory, self.memory_limit)

        return estimated_time, estimated_memory

    def validate_environment(self) -> Dict[str, bool]:
        """验证转换环境"""
        validation = {
            'rawpy_available': False,
            'imageio_available': False,
            'memory_sufficient': False,
            'disk_space_sufficient': False,
            'icm_available': False,
            'pil_cms_available': False
        }

        try:
            import rawpy
            validation['rawpy_available'] = True
        except ImportError:
            pass

        try:
            import imageio
            validation['imageio_available'] = True
        except ImportError:
            pass

        # 检查PIL ImageCms
        try:
            from PIL import ImageCms
            validation['pil_cms_available'] = True
        except ImportError:
            pass

        validation['icm_available'] = ICM_AVAILABLE and self.icm_manager is not None

        # 内存检查
        memory_gb = psutil.virtual_memory().total / (1024**3)
        validation['memory_sufficient'] = memory_gb >= 2  # 至少2GB内存

        # 磁盘空间检查 (临时目录)
        try:
            temp_usage = psutil.disk_usage('/tmp' if os.name != 'nt' else os.environ.get('TEMP', 'C:\\'))
            validation['disk_space_sufficient'] = temp_usage.free > (1024**3)  # 至少1GB空闲
        except:
            pass

        return validation

    def detect_camera_from_file(self, raw_path: str) -> Tuple[str, str]:
        """
        从RAW文件检测相机品牌和型号

        Args:
            raw_path: RAW文件路径

        Returns:
            (品牌, 型号)
        """
        if not self.camera_detector:
            return "", ""

        try:
            result = self.camera_detector.detect_camera_from_raw(raw_path)
            return result if result else ("", "")
        except Exception as e:
            print(f"相机检测失败 {raw_path}: {str(e)}")
            return "", ""

    def determine_icm_file(self, raw_path: str, detected_brand: str = "", detected_model: str = "") -> Optional[str]:
        """
        确定要使用的ICM文件

        Args:
            raw_path: RAW文件路径
            detected_brand: 已检测的品牌
            detected_model: 已检测的型号

        Returns:
            ICM文件路径或None
        """
        if not self.icm_manager:
            return None

        # 手动指定的ICM文件优先
        if self.config.manual_icm_path and os.path.exists(self.config.manual_icm_path):
            return self.config.manual_icm_path

        # 使用配置中的品牌型号
        brand = self.config.icm_brand or detected_brand
        model = self.config.icm_model or detected_model
        scene = self.config.icm_scene

        if not brand or not model:
            return None

        # 从ICM管理器获取文件
        return self.icm_manager.get_icm_file(brand, model, scene)

    def apply_icm_correction(self, input_path: str, rgb_array: numpy.ndarray,
                           detected_brand: str = "", detected_model: str = "") -> numpy.ndarray:
        """
        应用ICM校色到RGB数组

        Args:
            input_path: 输入文件路径
            rgb_array: RGB数组
            detected_brand: 已检测的品牌
            detected_model: 已检测的型号

        Returns:
            校色后的RGB数组

        Raises:
            Exception: 校色失败时抛出异常
        """
        if not self.config.enable_icm_correction:
            return rgb_array

        # 确定ICM文件
        icm_path = self.determine_icm_file(input_path, detected_brand, detected_model)
        if not icm_path:
            error_msg = f"找不到ICM文件: {detected_brand} {detected_model} {self.config.icm_scene}"
            if self.config.strict_icm:
                raise Exception(error_msg)
            else:
                print(f"警告: {error_msg}，跳过校色")
                return rgb_array

        try:
            # 加载ICC配置文件
            if not self.icm_manager:
                raise Exception("ICM管理器未初始化")

            icc_profile = self.icm_manager.load_icc_profile(icm_path)
            if not icc_profile:
                raise Exception(f"加载ICM文件失败: {icm_path}")

            # 转换为PIL图像进行校色
            pil_image = Image.fromarray(rgb_array)

            # 获取sRGB配置文件作为输出配置
            try:
                # 尝试使用系统sRGB配置
                srgb_profile = ImageCms.createProfile("sRGB")
            except:
                # 如果失败，使用默认配置
                srgb_profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("RGB"))

            # 应用校色转换
            converted_image = ImageCms.profileToProfile(
                pil_image,
                icc_profile,
                srgb_profile,
                outputMode='RGB',
                inPlace=False
            )

            return numpy.array(converted_image)

        except Exception as e:
            error_msg = f"ICM校色失败: {str(e)}"
            if self.config.strict_icm:
                raise Exception(error_msg)
            else:
                print(f"警告: {error_msg}，使用原始图像")
                return rgb_array

# 便利函数
def create_default_converter() -> EnhancedRAWConverter:
    """创建默认配置的转换器"""
    config = ConversionConfig(
        jpeg_quality=95,
        use_camera_wb=True,
        output_bps=8,
        exp_preserve_highlights=True,
        max_threads=None,  # 自动检测
        enable_icm_correction=True,  # 启用ICM校色
        auto_detect_camera=True,     # 自动检测相机
        strict_icm=True             # 严格模式
    )
    return EnhancedRAWConverter(config)

def create_fast_converter() -> EnhancedRAWConverter:
    """创建快速转换配置"""
    config = ConversionConfig(
        jpeg_quality=85,  # 较低质量但更快
        use_camera_wb=False,  # 跳过白平衡计算
        use_auto_wb=True,  # 使用自动白平衡
        output_bps=8,
        half_size=True,  # 半尺寸输出
        no_auto_bright=True,  # 跳过自动亮度调整
        exp_preserve_highlights=False,
        max_threads=4,  # 使用更多线程
        enable_icm_correction=False,  # 快速模式禁用ICM
        auto_detect_camera=False
    )
    return EnhancedRAWConverter(config)

def create_high_quality_converter() -> EnhancedRAWConverter:
    """创建高质量转换配置"""
    config = ConversionConfig(
        jpeg_quality=98,
        use_camera_wb=True,
        use_auto_wb=False,
        output_bps=8,
        bright=1.0,
        no_auto_bright=False,
        half_size=False,  # 全分辨率
        exp_preserve_highlights=True,
        max_threads=1,  # 单线程确保质量
        enable_icm_correction=True,  # 高质量模式启用ICM
        auto_detect_camera=True,
        strict_icm=True,            # 严格模式确保质量
        icm_scene="ProStandard"     # 使用专业标准场景
    )
    return EnhancedRAWConverter(config)

def create_icm_converter(brand: str = "", model: str = "", scene: str = "Generic") -> EnhancedRAWConverter:
    """创建指定ICM配置的转换器"""
    config = ConversionConfig(
        jpeg_quality=95,
        use_camera_wb=True,
        output_bps=8,
        exp_preserve_highlights=True,
        max_threads=None,
        enable_icm_correction=True,
        auto_detect_camera=True,
        strict_icm=True,
        icm_brand=brand,
        icm_model=model,
        icm_scene=scene
    )
    return EnhancedRAWConverter(config)
#!/usr/bin/env python3
"""
现代化RAW to JPEG转换器
浅色简约界面设计，重点优化转换性能和用户体验
"""

import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
import os
import threading
import queue
import time
from typing import List, Optional, Callable
from dataclasses import dataclass
from pathlib import Path

# 导入增强转换器和ICM组件
try:
    from enhanced_converter import EnhancedRAWConverter, ConversionConfig
    from icm_manager import get_icm_manager
    from camera_detector import get_camera_detector
    ICM_AVAILABLE = True
except ImportError:
    ICM_AVAILABLE = False
    print("警告: ICM功能模块未找到，校色功能将被禁用")

# 设置CustomTkinter为浅色主题
ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

# 支持的RAW格式
SUPPORTED_FORMATS = ['.arw', '.cr2', '.cr3', '.dng', '.nef', '.raw', '.orf', '.rw2', '.pef', '.srw', '.mos']

# 浅色现代化配色方案
COLORS = {
    'primary': '#2196F3',
    'secondary': '#1976D2',
    'accent': '#FF6B35',
    'surface': '#FFFFFF',
    'surface_variant': '#F5F5F5',
    'background': '#FAFAFA',
    'error': '#F44336',
    'success': '#4CAF50',
    'warning': '#FF9800',
    'outline': '#E0E0E0',
    'text_primary': '#212121',
    'text_secondary': '#757575'
}

@dataclass
class ConversionTask:
    """转换任务数据类"""
    input_path: str
    output_path: str
    status: str = "pending"  # pending, processing, completed, failed
    progress: float = 0.0
    error_message: str = ""
    file_size: int = 0

    # ICM校色相关信息
    camera_brand: str = ""
    camera_model: str = ""
    icm_applied: bool = False
    icm_file: str = ""

class ModernConverter:
    """现代化RAW转JPEG转换器主类"""

    def __init__(self):
        # 创建主窗口
        self.root = ctk.CTk()
        self.root.title("RAW to JPEG 现代化转换器")
        self.root.geometry("1200x800")  # 调整窗口大小以适应文件列表
        self.root.resizable(True, True)

        # 设置窗口图标和样式
        self.setup_window_style()

        # 状态变量
        self.input_folder = tk.StringVar(value="")
        self.output_folder = tk.StringVar(value="")
        self.jpeg_quality = tk.IntVar(value=95)
        self.is_converting = False
        self.conversion_thread = None

        # ICM校色状态变量
        self.enable_icm = tk.BooleanVar(value=True if ICM_AVAILABLE else False)
        self.icm_brand = tk.StringVar(value="")
        self.icm_model = tk.StringVar(value="")
        self.icm_scene = tk.StringVar(value="Generic")
        self.auto_detect_camera = tk.BooleanVar(value=True)

        # ICM搜索和筛选变量
        self.icm_search_enabled = tk.BooleanVar(value=False)  # 搜索功能默认关闭
        self.brand_search_var = tk.StringVar(value="")
        self.model_search_var = tk.StringVar(value="")

        # ICM数据缓存
        self.all_brands = []
        self.all_models = {}
        self.filtered_brands = []
        self.filtered_models = {}

        # ICM组件
        self.icm_manager = None
        self.camera_detector = None

        # 任务管理
        self.conversion_queue = queue.Queue()
        self.conversion_tasks: List[ConversionTask] = []

        # 初始化ICM组件
        if ICM_AVAILABLE:
            self.init_icm_components()

        # 创建UI
        self.create_widgets()

        # 启动队列处理
        self.process_queue()

    def init_icm_components(self):
        """初始化ICM组件"""
        try:
            self.icm_manager = get_icm_manager()
            self.camera_detector = get_camera_detector()
            print("ICM组件初始化成功")
        except Exception as e:
            print(f"ICM组件初始化失败: {str(e)}")
            self.enable_icm.set(False)

    def setup_window_style(self):
        """设置窗口样式"""
        # 设置窗口背景色
        self.root.configure(fg_color=COLORS['background'])

    def create_widgets(self):
        """创建所有UI组件"""
        # 主容器
        main_container = ctk.CTkFrame(self.root, corner_radius=15, fg_color=COLORS['surface'])
        main_container.pack(fill="both", expand=True, padx=20, pady=20)

        # 标题区域
        self.create_header(main_container)

        # 文件选择区域
        self.create_file_selection(main_container)

        # 设置区域
        self.create_settings(main_container)

        # 控制按钮区域
        self.create_controls(main_container)

        # 进度显示区域
        self.create_progress_section(main_container)

        # 文件列表区域
        self.create_file_list(main_container)

    def create_header(self, parent):
        """创建标题区域"""
        header_frame = ctk.CTkFrame(parent, corner_radius=10, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 20))

        # 标题
        title_label = ctk.CTkLabel(
            header_frame,
            text="🖼️ RAW to JPEG 转换器",
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color=COLORS['text_primary']
        )
        title_label.pack(anchor="w", pady=(10, 5))

        # 副标题
        subtitle_label = ctk.CTkLabel(
            header_frame,
            text="高性能RAW图像批量转换工具 - 支持主流相机RAW格式",
            font=ctk.CTkFont(size=14),
            text_color=COLORS['text_secondary']
        )
        subtitle_label.pack(anchor="w", pady=(0, 10))

    def create_file_selection(self, parent):
        """创建文件选择区域"""
        selection_frame = ctk.CTkFrame(parent, corner_radius=12, fg_color=COLORS['surface_variant'])
        selection_frame.pack(fill="x", pady=(0, 20))

        # 输入文件夹选择
        input_frame = ctk.CTkFrame(selection_frame, fg_color="transparent")
        input_frame.pack(fill="x", padx=20, pady=(15, 10))

        input_label = ctk.CTkLabel(
            input_frame,
            text="📁 输入文件夹:",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=COLORS['text_primary'],
            width=120
        )
        input_label.pack(side="left", padx=(0, 10))

        self.input_entry = ctk.CTkEntry(
            input_frame,
            textvariable=self.input_folder,
            placeholder_text="选择包含RAW文件的文件夹...",
            font=ctk.CTkFont(size=14),
            height=40
        )
        self.input_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))

        input_browse_btn = ctk.CTkButton(
            input_frame,
            text="浏览",
            command=self.browse_input_folder,
            width=80,
            height=40,
            fg_color=COLORS['primary'],
            hover_color=COLORS['secondary']
        )
        input_browse_btn.pack(side="right")

        # 输出文件夹选择
        output_frame = ctk.CTkFrame(selection_frame, fg_color="transparent")
        output_frame.pack(fill="x", padx=20, pady=(10, 15))

        output_label = ctk.CTkLabel(
            output_frame,
            text="📁 输出文件夹:",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=COLORS['text_primary'],
            width=120
        )
        output_label.pack(side="left", padx=(0, 10))

        self.output_entry = ctk.CTkEntry(
            output_frame,
            textvariable=self.output_folder,
            placeholder_text="选择输出JPEG文件的文件夹...",
            font=ctk.CTkFont(size=14),
            height=40
        )
        self.output_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))

        output_browse_btn = ctk.CTkButton(
            output_frame,
            text="浏览",
            command=self.browse_output_folder,
            width=80,
            height=40,
            fg_color=COLORS['primary'],
            hover_color=COLORS['secondary']
        )
        output_browse_btn.pack(side="right")

    def create_settings(self, parent):
        """创建设置区域"""
        settings_frame = ctk.CTkFrame(parent, corner_radius=12, fg_color=COLORS['surface_variant'])
        settings_frame.pack(fill="x", pady=(0, 20))

        # JPEG质量设置
        quality_frame = ctk.CTkFrame(settings_frame, fg_color="transparent")
        quality_frame.pack(fill="x", padx=20, pady=15)

        quality_label = ctk.CTkLabel(
            quality_frame,
            text="🎯 JPEG质量:",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=COLORS['text_primary'],
            width=120
        )
        quality_label.pack(side="left", padx=(0, 15))

        # 质量滑块
        self.quality_slider = ctk.CTkSlider(
            quality_frame,
            from_=60,
            to=100,
            number_of_steps=40,
            variable=self.jpeg_quality,
            width=200,
            height=20,
            progress_color=COLORS['primary']
        )
        self.quality_slider.pack(side="left", padx=(0, 15))

        self.quality_label = ctk.CTkLabel(
            quality_frame,
            text=f"{self.jpeg_quality.get()}%",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLORS['primary'],
            width=40
        )
        self.quality_label.pack(side="left")

        # 绑定质量滑块变化事件
        self.quality_slider.configure(command=self.update_quality_label)

        # ICM校色设置 (仅在ICM可用时显示)
        if ICM_AVAILABLE:
            self.create_icm_settings(settings_frame)

        # 支持格式说明
        format_info = ctk.CTkLabel(
            settings_frame,
            text=f"支持格式: {', '.join([fmt.upper() for fmt in SUPPORTED_FORMATS])}",
            font=ctk.CTkFont(size=12),
            text_color=COLORS['text_secondary']
        )
        format_info.pack(padx=20, pady=(0, 15))

    def create_icm_settings(self, parent):
        """创建ICM校色设置区域"""
        icm_frame = ctk.CTkFrame(parent, corner_radius=12, fg_color=COLORS['surface_variant'])
        icm_frame.pack(fill="x", pady=(10, 0))

        # 标题
        title_label = ctk.CTkLabel(
            icm_frame,
            text="🎨 相机校色设置 (ICM)",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=COLORS['text_primary']
        )
        title_label.pack(anchor="w", padx=20, pady=(15, 10))

        # 启用ICM校色选项
        enable_frame = ctk.CTkFrame(icm_frame, fg_color="transparent")
        enable_frame.pack(fill="x", padx=20, pady=(0, 10))

        enable_cb = ctk.CTkCheckBox(
            enable_frame,
            text="启用相机校色 (提升色彩准确性)",
            variable=self.enable_icm,
            command=self.on_icm_toggled,
            font=ctk.CTkFont(size=14),
            text_color=COLORS['text_primary']
        )
        enable_cb.pack(side="left")

        # 自动检测相机选项
        auto_detect_cb = ctk.CTkCheckBox(
            enable_frame,
            text="自动检测相机型号",
            variable=self.auto_detect_camera,
            command=self.on_auto_detect_toggled,
            font=ctk.CTkFont(size=14),
            text_color=COLORS['text_primary']
        )
        auto_detect_cb.pack(side="left", padx=(20, 0))

        # 搜索功能开关
        search_cb = ctk.CTkCheckBox(
            enable_frame,
            text="启用搜索筛选",
            variable=self.icm_search_enabled,
            command=self.on_search_toggled,
            font=ctk.CTkFont(size=14),
            text_color=COLORS['text_primary']
        )
        search_cb.pack(side="left", padx=(20, 0))

        # 手动选择区域 (使用滚动框架)
        self.manual_selection_frame = ctk.CTkFrame(icm_frame, fg_color="transparent")
        self.manual_selection_frame.pack(fill="x", padx=20, pady=(10, 15))

        # 创建可滚动的容器
        self.scrollable_frame = ctk.CTkScrollableFrame(
            self.manual_selection_frame,
            height=250,  # 限制高度
            fg_color="transparent"
        )
        self.scrollable_frame.pack(fill="both", expand=True)

        # 搜索区域
        self.search_frame = ctk.CTkFrame(self.scrollable_frame, fg_color="transparent")
        self.search_frame.pack(fill="x", pady=(0, 10))

        # 品牌搜索
        brand_search_frame = ctk.CTkFrame(self.search_frame, fg_color="transparent")
        brand_search_frame.pack(fill="x", pady=(0, 5))

        brand_search_label = ctk.CTkLabel(brand_search_frame, text="品牌搜索:", width=80, font=ctk.CTkFont(size=12))
        brand_search_label.pack(side="left")

        self.brand_search_entry = ctk.CTkEntry(
            brand_search_frame,
            textvariable=self.brand_search_var,
            placeholder_text="输入品牌名称搜索...",
            width=200,
            height=28
        )
        self.brand_search_entry.pack(side="left", padx=(10, 10))
        self.brand_search_entry.bind("<KeyRelease>", self.on_brand_search_changed)

        # 型号搜索
        model_search_frame = ctk.CTkFrame(self.search_frame, fg_color="transparent")
        model_search_frame.pack(fill="x")

        model_search_label = ctk.CTkLabel(model_search_frame, text="型号搜索:", width=80, font=ctk.CTkFont(size=12))
        model_search_label.pack(side="left")

        self.model_search_entry = ctk.CTkEntry(
            model_search_frame,
            textvariable=self.model_search_var,
            placeholder_text="输入型号名称搜索...",
            width=200,
            height=28
        )
        self.model_search_entry.pack(side="left", padx=(10, 10))
        self.model_search_entry.bind("<KeyRelease>", self.on_model_search_changed)

        # 选择区域
        self.selection_frame = ctk.CTkFrame(self.scrollable_frame, fg_color="transparent")
        self.selection_frame.pack(fill="both", expand=True)

        # 第一行：品牌和场景选择
        first_row = ctk.CTkFrame(self.selection_frame, fg_color="transparent")
        first_row.pack(fill="x", pady=(0, 10))

        # 品牌选择 (使用Combobox替代OptionMenu以支持滚动)
        brand_label = ctk.CTkLabel(first_row, text="品牌:", width=60, font=ctk.CTkFont(size=14))
        brand_label.pack(side="left")

        self.brand_combobox = ctk.CTkComboBox(
            first_row,
            values=["请先扫描ICM文件"],
            variable=self.icm_brand,
            command=self.on_brand_selected,
            width=150,
            height=28
        )
        self.brand_combobox.pack(side="left", padx=(10, 20))

        # 场景选择
        scene_label = ctk.CTkLabel(first_row, text="场景:", width=60, font=ctk.CTkFont(size=14))
        scene_label.pack(side="left")

        self.scene_menu = ctk.CTkOptionMenu(
            first_row,
            values=["Generic", "Flat", "Landscape", "Monochrome",
                   "Neutral", "Portrait", "Standard", "Vivid", "ProStandard"],
            variable=self.icm_scene,
            width=120,
            height=32
        )
        self.scene_menu.pack(side="left", padx=(10, 0))

        # 第二行：型号选择和刷新按钮
        second_row = ctk.CTkFrame(self.selection_frame, fg_color="transparent")
        second_row.pack(fill="x", pady=(10, 0))

        # 型号选择 (使用Combobox)
        model_label = ctk.CTkLabel(second_row, text="型号:", width=60, font=ctk.CTkFont(size=14))
        model_label.pack(side="left")

        self.model_combobox = ctk.CTkComboBox(
            second_row,
            values=["请先选择品牌"],
            variable=self.icm_model,
            command=self.on_model_selected,
            width=300,  # 加宽以显示完整型号名称
            height=28
        )
        self.model_combobox.pack(side="left", padx=(10, 20))

        # 刷新按钮
        refresh_btn = ctk.CTkButton(
            second_row,
            text="刷新ICM列表",
            command=self.refresh_icm_list,
            width=120,
            height=32,
            fg_color=COLORS['primary'],
            hover_color=COLORS['secondary']
        )
        refresh_btn.pack(side="right")

        # 初始状态
        self.on_icm_toggled()
        self.on_search_toggled()

        # 异步刷新ICM列表
        self.root.after(100, self.async_refresh_icm_list)

        # 状态显示
        self.icm_status_label = ctk.CTkLabel(
            icm_frame,
            text="正在扫描ICM文件...",
            font=ctk.CTkFont(size=12),
            text_color=COLORS['text_secondary']
        )
        self.icm_status_label.pack(anchor="w", padx=20, pady=(0, 15))

    def on_icm_toggled(self):
        """ICM校色开关状态改变"""
        enabled = self.enable_icm.get()
        state = "normal" if enabled else "disabled"

        # 更新手动选择控件状态
        if not self.auto_detect_camera.get():
            self.update_manual_selection_state(state)

        # 如果启用，立即刷新ICM列表
        if enabled:
            self.async_refresh_icm_list()

    def on_auto_detect_toggled(self):
        """自动检测开关状态改变"""
        auto_enabled = self.auto_detect_camera.get()
        icm_enabled = self.enable_icm.get()

        if icm_enabled:
            if auto_enabled:
                # 自动检测模式，禁用手动选择
                self.update_manual_selection_state("disabled")
            else:
                # 手动选择模式，启用手动选择
                self.update_manual_selection_state("normal")

    def on_search_toggled(self):
        """搜索功能开关状态改变"""
        search_enabled = self.icm_search_enabled.get()

        if hasattr(self, 'search_frame'):
            if search_enabled:
                self.search_frame.pack(fill="x", pady=(0, 10))
            else:
                self.search_frame.pack_forget()

    def on_brand_search_changed(self, event=None):
        """品牌搜索内容改变"""
        if not self.icm_search_enabled.get() or not hasattr(self, 'all_brands'):
            return

        search_text = self.brand_search_var.get().lower()
        if search_text:
            self.filtered_brands = [brand for brand in self.all_brands if search_text in brand.lower()]
        else:
            self.filtered_brands = self.all_brands.copy()

        # 更新combobox
        self.brand_combobox.configure(values=self.filtered_brands)

        # 如果当前选择不在筛选结果中，清空选择
        current_brand = self.icm_brand.get()
        if current_brand and current_brand not in self.filtered_brands:
            self.icm_brand.set("")
            self.update_model_list("")  # 清空型号列表

    def on_model_search_changed(self, event=None):
        """型号搜索内容改变"""
        if not self.icm_search_enabled.get() or not hasattr(self, 'all_models'):
            return

        current_brand = self.icm_brand.get()
        search_text = self.model_search_var.get().lower()

        if current_brand and current_brand in self.all_models:
            all_brand_models = self.all_models[current_brand]
            if search_text:
                self.filtered_models[current_brand] = [model for model in all_brand_models
                                                    if search_text in model.lower()]
            else:
                self.filtered_models[current_brand] = all_brand_models.copy()
        else:
            self.filtered_models = {}

        # 更新combobox
        if current_brand in self.filtered_models:
            self.model_combobox.configure(values=self.filtered_models[current_brand])
        else:
            self.model_combobox.configure(values=[])

        # 如果当前选择不在筛选结果中，清空选择
        current_model = self.icm_model.get()
        if current_model and current_brand in self.filtered_models:
            if current_model not in self.filtered_models[current_brand]:
                self.icm_model.set("")

    def update_manual_selection_state(self, state):
        """更新手动选择控件状态"""
        self.brand_combobox.configure(state=state)
        self.model_combobox.configure(state=state)
        self.scene_menu.configure(state=state)

        # 同时更新搜索控件状态
        if hasattr(self, 'brand_search_entry'):
            self.brand_search_entry.configure(state=state)
        if hasattr(self, 'model_search_entry'):
            self.model_search_entry.configure(state=state)

    def on_brand_selected(self, brand):
        """品牌选择变化"""
        if not brand or brand == "请先扫描ICM文件":
            return

        # 清空型号搜索
        self.model_search_var.set("")
        # 更新型号列表
        self.update_model_list(brand)

    def on_model_selected(self, model):
        """型号选择变化"""
        # 这里可以添加型号选择后的处理逻辑
        # 比如显示该型号支持的ICM场景等
        pass

    def update_model_list(self, brand):
        """更新型号列表"""
        if not self.icm_manager:
            return

        try:
            # 如果启用了搜索，使用筛选后的数据
            if self.icm_search_enabled.get() and brand in self.filtered_models:
                models = self.filtered_models[brand]
            else:
                models = self.icm_manager.get_available_models(brand)

            if models:
                self.model_combobox.configure(values=models)
                # 优先选择第一个型号
                if models and (not self.icm_model.get() or self.icm_model.get() not in models):
                    self.icm_model.set(models[0])
            else:
                self.model_combobox.configure(values=["该品牌暂无型号"])
                self.icm_model.set("")
        except Exception as e:
            print(f"更新型号列表失败: {str(e)}")
            self.model_combobox.configure(values=["加载失败"])
            self.icm_model.set("")

    def async_refresh_icm_list(self):
        """异步刷新ICM文件列表"""
        def refresh_worker():
            try:
                if self.icm_manager:
                    self.icm_manager.refresh_icm_database()
                    # 在主线程中更新UI
                    self.root.after(0, self.update_icm_ui)
            except Exception as e:
                print(f"刷新ICM列表失败: {str(e)}")
                self.root.after(0, lambda: self.icm_status_label.configure(
                    text=f"ICM扫描失败: {str(e)}"
                ))

        # 在后台线程中执行
        threading.Thread(target=refresh_worker, daemon=True).start()

    def refresh_icm_list(self):
        """刷新ICM文件列表"""
        self.icm_status_label.configure(text="正在扫描ICM文件...")
        self.async_refresh_icm_list()

    def update_icm_ui(self):
        """更新ICM相关UI"""
        if not self.icm_manager:
            self.icm_status_label.configure(text="ICM管理器未初始化")
            return

        try:
            # 获取统计信息
            stats = self.icm_manager.get_statistics()
            self.icm_status_label.configure(
                text=f"已发现 {stats['brands']} 个品牌，{stats['models']} 个型号，{stats['icm_files']} 个ICM文件"
            )

            # 获取并缓存所有数据
            self.all_brands = self.icm_manager.get_available_brands()
            self.all_models = {}
            for brand in self.all_brands:
                self.all_models[brand] = self.icm_manager.get_available_models(brand)

            # 初始化筛选数据
            self.filtered_brands = self.all_brands.copy()
            self.filtered_models = self.all_models.copy()

            # 更新品牌combobox
            if self.all_brands:
                self.brand_combobox.configure(values=self.filtered_brands)
                if not self.icm_brand.get() or self.icm_brand.get() not in self.filtered_brands:
                    self.icm_brand.set(self.filtered_brands[0])
                    self.update_model_list(self.filtered_brands[0])
            else:
                self.brand_combobox.configure(values=["未找到ICM文件"])
                self.icm_brand.set("")

        except Exception as e:
            self.icm_status_label.configure(text=f"UI更新失败: {str(e)}")

    def create_controls(self, parent):
        """创建控制按钮区域"""
        controls_frame = ctk.CTkFrame(parent, corner_radius=12, fg_color=COLORS['surface_variant'])
        controls_frame.pack(fill="x", pady=(0, 20))

        # 按钮容器
        button_frame = ctk.CTkFrame(controls_frame, fg_color="transparent")
        button_frame.pack(pady=20)

        # 开始转换按钮
        self.start_btn = ctk.CTkButton(
            button_frame,
            text="🚀 开始转换",
            command=self.start_conversion,
            width=150,
            height=45,
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color=COLORS['success'],
            hover_color="#45a049"
        )
        self.start_btn.pack(side="left", padx=(0, 10))

        # 停止转换按钮
        self.stop_btn = ctk.CTkButton(
            button_frame,
            text="🛑 停止",
            command=self.stop_conversion,
            width=120,
            height=45,
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color=COLORS['error'],
            hover_color="#d32f2f",
            state="disabled"
        )
        self.stop_btn.pack(side="left", padx=(0, 10))

        # 清除列表按钮
        clear_btn = ctk.CTkButton(
            button_frame,
            text="🗑️ 清除列表",
            command=self.clear_file_list,
            width=120,
            height=45,
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color=COLORS['warning'],
            hover_color="#f57c00"
        )
        clear_btn.pack(side="left")

    def create_progress_section(self, parent):
        """创建进度显示区域"""
        progress_frame = ctk.CTkFrame(parent, corner_radius=12, fg_color=COLORS['surface_variant'])
        progress_frame.pack(fill="x", pady=(0, 20))

        # 进度条容器
        progress_container = ctk.CTkFrame(progress_frame, fg_color="transparent")
        progress_container.pack(fill="x", padx=20, pady=15)

        # 进度条
        self.progress_bar = ctk.CTkProgressBar(
            progress_container,
            height=25,
            corner_radius=12,
            progress_color=COLORS['primary']
        )
        self.progress_bar.pack(fill="x", pady=(0, 10))
        self.progress_bar.set(0)

        # 进度信息
        progress_info = ctk.CTkFrame(progress_container, fg_color="transparent")
        progress_info.pack(fill="x")

        self.progress_label = ctk.CTkLabel(
            progress_info,
            text="准备就绪",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLORS['text_primary']
        )
        self.progress_label.pack(side="left")

        self.progress_count = ctk.CTkLabel(
            progress_info,
            text="0/0 文件",
            font=ctk.CTkFont(size=14),
            text_color=COLORS['text_secondary']
        )
        self.progress_count.pack(side="right")

    def create_file_list(self, parent):
        """创建文件列表区域"""
        list_frame = ctk.CTkFrame(parent, corner_radius=12, fg_color=COLORS['surface_variant'])
        list_frame.pack(fill="both", expand=True, pady=(0, 0))

        # 列表标题
        list_header = ctk.CTkFrame(list_frame, corner_radius=10, fg_color=COLORS['primary'])
        list_header.pack(fill="x", padx=1, pady=(1, 10))

        header_label = ctk.CTkLabel(
            list_header,
            text="📋 文件列表",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="white",
            height=30
        )
        header_label.pack(pady=10)

        # 文件列表容器（滚动区域）
        self.file_list_frame = ctk.CTkScrollableFrame(
            list_frame,
            height=300,  # 增加文件列表高度
            corner_radius=8,
            fg_color=COLORS['surface']
        )
        self.file_list_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # 空状态提示
        self.empty_label = ctk.CTkLabel(
            self.file_list_frame,
            text="暂无文件\n请选择输入文件夹后点击开始转换",
            font=ctk.CTkFont(size=14),
            text_color=COLORS['text_secondary']
        )
        self.empty_label.pack(expand=True)

    def update_quality_label(self, value):
        """更新质量标签"""
        self.quality_label.configure(text=f"{int(value)}%")

    def browse_input_folder(self):
        """浏览输入文件夹"""
        folder = filedialog.askdirectory(title="选择包含RAW文件的文件夹")
        if folder:
            self.input_folder.set(folder)
            # 自动设置输出文件夹
            if not self.output_folder.get():
                output_folder = os.path.join(folder, "JPEG")
                self.output_folder.set(output_folder)

    def browse_output_folder(self):
        """浏览输出文件夹"""
        folder = filedialog.askdirectory(title="选择输出文件夹")
        if folder:
            self.output_folder.set(folder)

    def scan_raw_files(self) -> List[str]:
        """扫描输入文件夹中的RAW文件"""
        input_folder = self.input_folder.get()
        if not input_folder or not os.path.exists(input_folder):
            return []

        raw_files = []
        try:
            for root, dirs, files in os.walk(input_folder):
                for file in files:
                    if any(file.lower().endswith(ext) for ext in SUPPORTED_FORMATS):
                        raw_files.append(os.path.join(root, file))
        except Exception as e:
            messagebox.showerror("错误", f"扫描文件夹时出错: {str(e)}")
            return []

        return sorted(raw_files)

    def create_file_task(self, raw_file: str) -> ConversionTask:
        """创建转换任务"""
        # 生成输出文件路径
        relative_path = os.path.relpath(raw_file, self.input_folder.get())
        name_without_ext = os.path.splitext(relative_path)[0]
        output_path = os.path.join(self.output_folder.get(), f"{name_without_ext}.jpg")

        # 确保输出目录存在
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        return ConversionTask(
            input_path=raw_file,
            output_path=output_path,
            file_size=os.path.getsize(raw_file) if os.path.exists(raw_file) else 0
        )

    def start_conversion(self):
        """开始转换"""
        # 验证输入
        if not self.input_folder.get():
            messagebox.showwarning("警告", "请选择输入文件夹")
            return

        if not self.output_folder.get():
            messagebox.showwarning("警告", "请选择输出文件夹")
            return

        # 扫描文件
        raw_files = self.scan_raw_files()
        if not raw_files:
            messagebox.showwarning("警告", "在输入文件夹中未找到RAW文件")
            return

        # 创建转换任务
        self.conversion_tasks = [self.create_file_task(f) for f in raw_files]

        # 更新UI状态
        self.is_converting = True
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.progress_bar.set(0)
        self.progress_label.configure(text="准备转换...")

        # 更新文件列表显示
        self.update_file_list_display()

        # 启动转换线程
        self.conversion_thread = threading.Thread(target=self.conversion_worker, daemon=True)
        self.conversion_thread.start()

    def stop_conversion(self):
        """停止转换"""
        self.is_converting = False
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.progress_label.configure(text="转换已停止")

    def conversion_worker(self):
        """转换工作线程"""
        # 创建转换器配置
        config = ConversionConfig(
            jpeg_quality=self.jpeg_quality.get(),
            use_camera_wb=True,
            use_auto_wb=False,
            output_bps=8,
            bright=1.0,
            no_auto_bright=False,
            half_size=False,
            exp_preserve_highlights=True,
            four_color_rgb=False,
            max_threads=None,
            # ICM配置
            enable_icm_correction=self.enable_icm.get(),
            icm_brand=self.icm_brand.get(),
            icm_model=self.icm_model.get(),
            icm_scene=self.icm_scene.get(),
            manual_icm_path=None,
            strict_icm=True,
            auto_detect_camera=self.auto_detect_camera.get()
        )

        # 创建增强转换器
        converter = EnhancedRAWConverter(config)

        # 准备文件列表
        input_files = [task.input_path for task in self.conversion_tasks]
        output_dir = self.output_folder.get()

        # 设置进度回调
        def progress_callback(completed, total):
            if self.is_converting:
                progress_percent = completed / total if total > 0 else 0
                completed_count = completed

                # 更新任务状态
                for i in range(min(completed, len(self.conversion_tasks))):
                    task = self.conversion_tasks[i]
                    if task.status != "completed":
                        task.status = "completed"
                        task.progress = 100.0

                self.conversion_queue.put(("progress", {
                    "percent": progress_percent,
                    "completed": completed_count,
                    "total": total,
                    "current_file": "处理中..." if completed < total else "转换完成"
                }))

        # 设置状态回调
        def status_callback(message):
            if self.is_converting:
                self.conversion_queue.put(("status", message))

        converter.set_progress_callback(progress_callback)
        converter.set_status_callback(status_callback)

        try:
            # 执行批量转换
            results = converter.convert_batch(input_files, output_dir)

            # 更新任务结果
            completed_count = 0
            for i, result in enumerate(results):
                if i < len(self.conversion_tasks):
                    task = self.conversion_tasks[i]

                    # 更新任务信息
                    task.status = "completed" if result.status.value == "completed" else "failed"
                    task.progress = 100.0 if result.status.value == "completed" else 0.0
                    task.error_message = result.error_message
                    task.camera_brand = result.camera_brand
                    task.camera_model = result.camera_model
                    task.icm_applied = result.icm_applied
                    task.icm_file = result.icm_file

                    if result.status.value == "completed":
                        completed_count += 1

                    # 更新任务显示
                    self.conversion_queue.put(("update_task", task))

            # 转换完成
            total_files = len(self.conversion_tasks)
            failed_count = total_files - completed_count
            self.conversion_queue.put(("completed", {
                "total": total_files,
                "completed": completed_count,
                "failed": failed_count
            }))

        except Exception as e:
            # 转换失败
            error_msg = str(e)
            for task in self.conversion_tasks:
                if task.status == "processing":
                    task.status = "failed"
                    task.error_message = error_msg
                    self.conversion_queue.put(("update_task", task))

            self.conversion_queue.put(("error", {
                "file": "批量转换",
                "error": error_msg
            }))

    def process_queue(self):
        """处理队列消息"""
        try:
            while True:
                try:
                    # 非阻塞获取消息
                    msg_type, data = self.conversion_queue.get_nowait()

                    if msg_type == "progress":
                        self.update_progress(data)
                    elif msg_type == "error":
                        self.show_error(data)
                    elif msg_type == "update_task":
                        self.update_task_display(data)
                    elif msg_type == "completed":
                        self.conversion_completed(data)

                except queue.Empty:
                    break
        finally:
            # 继续处理队列
            self.root.after(100, self.process_queue)

    def update_progress(self, data):
        """更新进度显示"""
        self.progress_bar.set(data["percent"])
        self.progress_label.configure(text=f"正在转换: {data['current_file']}")
        self.progress_count.configure(text=f"{data['completed']}/{data['total']} 文件")

    def show_error(self, data):
        """显示错误信息"""
        print(f"错误: {data['file']} - {data['error']}")

    def update_task_display(self, task: ConversionTask):
        """更新任务显示"""
        pass  # 在文件列表中更新显示

    def conversion_completed(self, data):
        """转换完成"""
        self.is_converting = False
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")

        if data["failed"] == 0:
            self.progress_label.configure(text="✅ 转换完成")
            messagebox.showinfo("完成", f"成功转换 {data['completed']} 个文件")
        else:
            self.progress_label.configure(text=f"⚠️ 转换完成 ({data['failed']} 个失败)")
            messagebox.showwarning("完成",
                f"转换完成: {data['completed']} 成功, {data['failed']} 失败")

    def update_file_list_display(self):
        """更新文件列表显示"""
        # 清除空状态提示
        if hasattr(self, 'empty_label'):
            self.empty_label.pack_forget()

        # 清除现有显示
        for widget in self.file_list_frame.winfo_children():
            widget.destroy()

        # 显示文件任务
        for task in self.conversion_tasks:
            self.create_file_task_widget(task)

    def create_file_task_widget(self, task: ConversionTask):
        """创建文件任务显示组件"""
        task_frame = ctk.CTkFrame(self.file_list_frame, corner_radius=8, fg_color=COLORS['surface'])
        task_frame.pack(fill="x", pady=2)

        # 文件信息
        info_frame = ctk.CTkFrame(task_frame, fg_color="transparent")
        info_frame.pack(fill="x", padx=10, pady=6)

        # 第一行：文件名和状态
        first_row = ctk.CTkFrame(info_frame, fg_color="transparent")
        first_row.pack(fill="x")

        # 文件名
        filename = os.path.basename(task.input_path)
        name_label = ctk.CTkLabel(
            first_row,
            text=filename,
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLORS['text_primary'],
            anchor="w"
        )
        name_label.pack(side="left", fill="x", expand=True)

        # 状态标签
        status_color = {
            "pending": COLORS['text_secondary'],
            "processing": COLORS['primary'],
            "completed": COLORS['success'],
            "failed": COLORS['error']
        }.get(task.status, COLORS['text_secondary'])

        status_text = {
            "pending": "等待中",
            "processing": "转换中...",
            "completed": "✅ 完成",
            "failed": "❌ 失败"
        }.get(task.status, "未知")

        status_label = ctk.CTkLabel(
            first_row,
            text=status_text,
            font=ctk.CTkFont(size=11),
            text_color=status_color,
            width=80
        )
        status_label.pack(side="right", padx=(10, 0))

        # 第二行：ICM信息（如果有）
        if ICM_AVAILABLE and (task.camera_brand or task.icm_applied):
            second_row = ctk.CTkFrame(info_frame, fg_color="transparent")
            second_row.pack(fill="x", pady=(2, 0))

            # 相机信息
            if task.camera_brand and task.camera_model:
                camera_info = f"📷 {task.camera_brand} {task.camera_model}"
                camera_label = ctk.CTkLabel(
                    second_row,
                    text=camera_info,
                    font=ctk.CTkFont(size=10),
                    text_color=COLORS['text_secondary'],
                    anchor="w"
                )
                camera_label.pack(side="left")

            # ICM校色信息
            if task.icm_applied:
                icm_info = "🎨 ICM校色已应用"
                if task.icm_file:
                    icm_filename = os.path.basename(task.icm_file)
                    icm_info += f" ({icm_filename})"

                icm_label = ctk.CTkLabel(
                    second_row,
                    text=icm_info,
                    font=ctk.CTkFont(size=10),
                    text_color=COLORS['primary'],
                    anchor="w"
                )
                icm_label.pack(side="right", padx=(10, 0))

        # 错误信息（如果有）
        if task.error_message:
            error_row = ctk.CTkFrame(info_frame, fg_color="transparent")
            error_row.pack(fill="x", pady=(2, 0))

            error_label = ctk.CTkLabel(
                error_row,
                text=f"⚠️ {task.error_message}",
                font=ctk.CTkFont(size=10),
                text_color=COLORS['error'],
                anchor="w"
            )
            error_label.pack(fill="x")

    def clear_file_list(self):
        """清除文件列表"""
        self.conversion_tasks = []

        # 清除显示
        for widget in self.file_list_frame.winfo_children():
            widget.destroy()

        # 显示空状态提示
        self.empty_label = ctk.CTkLabel(
            self.file_list_frame,
            text="暂无文件\n请选择输入文件夹后点击开始转换",
            font=ctk.CTkFont(size=14),
            text_color=COLORS['text_secondary']
        )
        self.empty_label.pack(expand=True)

        # 重置进度
        self.progress_bar.set(0)
        self.progress_label.configure(text="准备就绪")
        self.progress_count.configure(text="0/0 文件")

    def run(self):
        """运行应用"""
        self.root.mainloop()

if __name__ == "__main__":
    app = ModernConverter()
    app.run()
#!/usr/bin/env python3
"""
RAW to JPEG 转换器构建脚本
构建可执行文件
"""

import os
import sys
import subprocess

def main():
    print("Building RAW to JPEG Converter...")

    # 构建命令
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name=RAW_to_JPEG_Converter",
        "--onefile",
        "--windowed",
        "--clean",
        "--noconfirm",
        "--collect-all", "customtkinter",
        "--collect-all", "rawpy",
        "--collect-all", "imageio",
        "--collect-all", "PIL",
        "--hidden-import", "psutil",
        "--hidden-import", "PIL.ImageCms",
        "--hidden-import", "icm_manager",
        "--hidden-import", "camera_detector",
        "--hidden-import", "enhanced_converter",
        "--add-data=DSLR;DSLR",  # 包含ICM文件目录
        "modern_converter.py"
    ]

    try:
        result = subprocess.run(cmd, check=True)
        print("Build successful!")
        print("Executable: dist/RAW_to_JPEG_Converter.exe")
        return 0
    except subprocess.CalledProcessError as e:
        print(f"Build failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
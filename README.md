# RAW to JPEG Converter

一个功能强大的RAW图像转JPEG工具，包含命令行脚本和现代化的图形界面。

## 功能特性

- 🖼️ **多格式支持**: 支持 ARW, CR2, CR3, DNG, NEF, RAW, ORF, RW2, PEF, SRW, MOS 等主流RAW格式
- 🎨 **现代化GUI**: 使用 CustomTkinter 构建的美观界面，支持深色/浅色主题
- 📁 **批量转换**: 支持文件夹递归扫描和批量转换
- ⚙️ **质量控制**: 可调节JPEG输出质量(1-100)
- 📊 **实时进度**: 显示转换进度条和详细状态信息
- 📝 **详细日志**: 彩色编码的转换日志，成功/错误信息一目了然
- 🛑 **中断控制**: 支持用户中断转换过程
- 🔧 **自定义输出**: 可自定义输出文件夹或使用默认设置

## 界面预览

![GUI界面预览](gui_preview.png)

## 安装说明

### 方法一：自动安装依赖
```bash
git clone https://github.com/your-username/raw-to-jpeg-converter.git
cd raw-to-jpeg-converter
python install_dependencies.py
```

### 方法二：手动安装依赖
```bash
pip install customtkinter rawpy imageio Pillow
```

## 使用方法

### GUI版本（推荐）
```bash
python gui_converter.py
```

GUI界面使用说明：
1. 选择包含RAW图像的输入文件夹
2. 选择或确认JPEG图像的输出文件夹
3. 调整JPEG质量滑块（默认95%）
4. 点击"Convert Images"开始转换
5. 查看转换进度和日志信息

### 命令行版本
```bash
python "raw to jpeg.py"
```
需要修改脚本中的 `raw_folder` 变量为您的RAW图像文件夹路径。

## 依赖包

- **customtkinter**: 现代化的Tkinter界面库，提供美观的GUI组件
- **rawpy**: RAW图像文件读取和处理
- **imageio**: 图像格式转换和保存
- **Pillow**: 图像处理和PIL兼容性

## 支持的RAW格式

| 格式 | 相机制造商 |
|------|------------|
| ARW  | Sony |
| CR2/CR3 | Canon |
| DNG  | Adobe通用格式 |
| NEF  | Nikon |
| RAW  | 通用RAW格式 |
| ORF  | Olympus |
| RW2  | Panasonic |
| PEF  | Pentax |
| SRW  | Samsung |
| MOS  | Leica |

## 项目结构

```
RAW-to-JPEG/
├── gui_converter.py          # GUI版本主程序
├── raw to jpeg.py           # 命令行版本
├── install_dependencies.py   # 依赖安装脚本
└── README.md                # 项目说明文档
```

## 系统要求

- Python 3.7+
- Windows / macOS / Linux

## 常见问题

### Q: 安装依赖时出现错误
A: 尝试使用以下命令：
```bash
pip install --upgrade pip
pip install customtkinter rawpy imageio Pillow
```

### Q: 无法识别某些RAW格式
A: 请确保您的RAW格式在支持列表中，或者尝试更新rawpy库：
```bash
pip install --upgrade rawpy
```

### Q: 转换速度较慢
A: RAW转JPEG是一个计算密集的过程，转换速度取决于：
- 图像分辨率
- 电脑性能
- RAW格式的复杂度

## 贡献

欢迎贡献代码！您可以：
- 提交Bug报告
- 请求新功能
- 提交Pull Request
- 改进文档

## 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 致谢

- [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) - 现代化的Tkinter替代品
- [rawpy](https://github.com/letmaik/rawpy) - RAW图像处理库
- [imageio](https://github.com/imageio/imageio) - 图像I/O库

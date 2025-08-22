import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTextEdit, QLabel, QLineEdit, QGroupBox, QGridLayout,
    QComboBox, QCheckBox, QFileDialog
)
from PyQt5.QtCore import Qt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.font_manager as fm


class GM8050ControlAppUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        """初始化用户界面"""
        self.setWindowTitle('GM8050 光谱解调仪控制软件')
        self.setGeometry(100, 100, 1200, 900)

        # 创建主控件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # 串口控制区域
        com_group = QGroupBox("串口设置")
        com_layout = QGridLayout()

        self.port_combo = QComboBox()
        self.refresh_btn = QPushButton("刷新串口")
        self.baudrate_edit = QLineEdit("115200")
        self.connect_btn = QPushButton("连接设备")
        self.disconnect_btn = QPushButton("断开连接")
        self.disconnect_btn.setEnabled(False)

        com_layout.addWidget(QLabel("串口号:"), 0, 0)
        com_layout.addWidget(self.port_combo, 0, 1)
        com_layout.addWidget(self.refresh_btn, 0, 2)
        com_layout.addWidget(QLabel("波特率:"), 1, 0)
        com_layout.addWidget(self.baudrate_edit, 1, 1)
        com_layout.addWidget(self.connect_btn, 0, 3)
        com_layout.addWidget(self.disconnect_btn, 1, 3)

        com_group.setLayout(com_layout)
        main_layout.addWidget(com_group)

        # 激光控制区域
        laser_group = QGroupBox("激光控制")
        laser_layout = QHBoxLayout()

        self.laser_on_btn = QPushButton("开启激光")
        self.laser_off_btn = QPushButton("关闭激光")
        self.laser_status_label = QLabel("状态: 未知")

        laser_layout.addWidget(self.laser_on_btn)
        laser_layout.addWidget(self.laser_off_btn)
        laser_layout.addStretch()
        laser_layout.addWidget(self.laser_status_label)

        laser_group.setLayout(laser_layout)
        main_layout.addWidget(laser_group)

        # 解调控制区域
        demod_group = QGroupBox("解调控制")
        demod_layout = QVBoxLayout()

        row1_layout = QHBoxLayout()
        self.start_demod_btn = QPushButton("启动解调")
        self.stop_demod_btn = QPushButton("停止解调")
        self.read_spectrum_btn = QPushButton("读取光谱数据")
        self.save_data_btn = QPushButton("保存光谱数据")


        # 新增实时绘图按钮
        row2_layout = QHBoxLayout()
        self.start_realtime_btn = QPushButton("开始实时绘图")
        self.stop_realtime_btn = QPushButton("停止实时绘图")
        self.save_realtime_btn = QPushButton("保存实时数据")
        self.stop_realtime_btn.setEnabled(False)
        self.save_realtime_btn.setEnabled(False)

        row3_layout = QHBoxLayout()
        self.interval_label = QLabel("更新时间间隔(秒):")
        self.interval_edit = QLineEdit("1.0")
        self.interval_edit.setFixedWidth(50)
        self.save_realtime_check = QCheckBox("自动保存实时数据")

        row1_layout.addWidget(self.start_demod_btn)
        row1_layout.addWidget(self.stop_demod_btn)
        row2_layout.addWidget(self.read_spectrum_btn)
        row2_layout.addWidget(self.save_data_btn)
        row2_layout.addWidget(self.start_realtime_btn)
        row2_layout.addWidget(self.stop_realtime_btn)
        row2_layout.addWidget(self.save_realtime_btn)
        row3_layout.addWidget(self.interval_label)
        row3_layout.addWidget(self.interval_edit)
        row3_layout.addStretch()
        row3_layout.addWidget(self.save_realtime_check)

        demod_layout.addLayout(row1_layout)
        demod_layout.addLayout(row2_layout)
        demod_layout.addLayout(row3_layout)
        demod_group.setLayout(demod_layout)
        main_layout.addWidget(demod_group)

        # 光谱参数设置
        spectrum_group = QGroupBox("光谱扫描参数")
        spectrum_layout = QHBoxLayout()

        self.start_wl_edit = QLineEdit("1527.0")
        self.stop_wl_edit = QLineEdit("1568.0")
        self.step_edit = QLineEdit("0.02")

        spectrum_layout.addWidget(QLabel("起始波长(nm):"))
        spectrum_layout.addWidget(self.start_wl_edit)
        spectrum_layout.addWidget(QLabel("终止波长(nm):"))
        spectrum_layout.addWidget(self.stop_wl_edit)
        spectrum_layout.addWidget(QLabel("步长(nm):"))
        spectrum_layout.addWidget(self.step_edit)

        spectrum_group.setLayout(spectrum_layout)
        main_layout.addWidget(spectrum_group)

        # 通道选择区域
        channel_group = QGroupBox("通道选择")
        channel_layout = QHBoxLayout()

        self.ch1_check = QCheckBox("通道 1")
        self.ch2_check = QCheckBox("通道 2")
        self.ch3_check = QCheckBox("通道 3")
        self.ch4_check = QCheckBox("通道 4")

        # 默认全选
        self.ch1_check.setChecked(True)
        self.ch2_check.setChecked(True)
        self.ch3_check.setChecked(True)
        self.ch4_check.setChecked(True)

        channel_layout.addWidget(self.ch1_check)
        channel_layout.addWidget(self.ch2_check)
        channel_layout.addWidget(self.ch3_check)
        channel_layout.addWidget(self.ch4_check)
        channel_layout.addStretch()

        channel_group.setLayout(channel_layout)
        main_layout.addWidget(channel_group)

        # 绘图区域
        plot_group = QGroupBox("数据可视化")
        plot_layout = QVBoxLayout()

        # 创建图形和画布
        self.fig = Figure(figsize=(10, 8))
        self.canvas = FigureCanvas(self.fig)

        # 设置中文字体
        font_path = fm.findfont(fm.FontProperties(family='SimHei'))
        self.fig.suptitle('光谱数据', fontproperties=fm.FontProperties(fname=font_path))

        self.ax = self.fig.add_subplot(111)
        self.ax.set_xlabel('波长 (nm)', fontproperties=fm.FontProperties(fname=font_path))
        self.ax.set_ylabel('幅值', fontproperties=fm.FontProperties(fname=font_path))
        self.ax.grid(True)

        # 添加图例
        self.ax.legend(['通道 1', '通道 2', '通道 3', '通道 4'],
                       prop=fm.FontProperties(fname=font_path))

        plot_layout.addWidget(self.canvas)

        plot_group.setLayout(plot_layout)
        main_layout.addWidget(plot_group, 4)  # 分配更多空间给绘图区域

        # 数据显示区域
        data_group = QGroupBox("数据输出")
        data_layout = QVBoxLayout()

        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.clear_btn = QPushButton("清空输出")

        data_layout.addWidget(self.output_text)
        data_layout.addWidget(self.clear_btn)

        data_group.setLayout(data_layout)
        main_layout.addWidget(data_group, 1)  # 分配较少空间给输出区域

        # 状态栏
        self.statusBar().showMessage("就绪")
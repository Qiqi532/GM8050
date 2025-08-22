import time
import os
import serial.tools.list_ports
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTextEdit, QLabel, QLineEdit, QGroupBox, QGridLayout,
    QComboBox, QCheckBox, QSizePolicy, QFileDialog
)
import matplotlib.font_manager as fm
from matplotlib.ticker import FormatStrFormatter

from ui import GM8050ControlAppUI
from basic import GM8050Reader


class GM8050ControlApp(GM8050ControlAppUI):
    def __init__(self):
        super().__init__()
        self.reader = None
        self.refresh_ports()  # 初始刷新串口列表
        # 添加实时绘图定时器
        self.realtime_timer = QTimer()
        self.realtime_timer.timeout.connect(self.update_realtime_plot)
        # 实时数据结构
        self.realtime_wavelengths = None  # 存储波长数据
        self.realtime_data = {  # 存储各通道数据
            0: [],  # 通道1
            1: [],  # 通道2
            2: [],  # 通道3
            3: []  # 通道4
        }
        self.realtime_timestamps = []
        # 连接信号
        self.refresh_btn.clicked.connect(self.refresh_ports)
        self.connect_btn.clicked.connect(self.connect_device)
        self.disconnect_btn.clicked.connect(self.disconnect_device)
        self.laser_on_btn.clicked.connect(self.laser_on)
        self.laser_off_btn.clicked.connect(self.laser_off)
        self.start_demod_btn.clicked.connect(self.start_demodulation)
        self.stop_demod_btn.clicked.connect(self.stop_demodulation)
        self.read_spectrum_btn.clicked.connect(self.read_spectrum_data)
        self.clear_btn.clicked.connect(self.clear_output)
        self.save_data_btn.clicked.connect(self.save_spectrum_data)
        self.start_realtime_btn.clicked.connect(self.start_realtime_plotting)
        self.stop_realtime_btn.clicked.connect(self.stop_realtime_plotting)
        self.save_realtime_btn.clicked.connect(self.save_realtime_data)

        # 禁用所有功能按钮直到连接设备
        self.set_controls_enabled(False)

    def refresh_ports(self):
        """刷新可用串口列表"""
        self.port_combo.clear()
        ports = serial.tools.list_ports.comports()
        for port in ports:
            self.port_combo.addItem(port.device)
        if ports:
            self.log_message(f"找到 {len(ports)} 个可用串口")
        else:
            self.log_message("未找到可用串口")

    def set_controls_enabled(self, enabled):
        """启用或禁用功能按钮"""
        self.laser_on_btn.setEnabled(enabled)
        self.laser_off_btn.setEnabled(enabled)
        self.start_demod_btn.setEnabled(enabled)
        self.stop_demod_btn.setEnabled(enabled)
        self.read_spectrum_btn.setEnabled(enabled)
        self.save_data_btn.setEnabled(enabled)
        self.ch1_check.setEnabled(enabled)
        self.ch2_check.setEnabled(enabled)
        self.ch3_check.setEnabled(enabled)
        self.ch4_check.setEnabled(enabled)
        self.start_realtime_btn.setEnabled(enabled)
        self.stop_realtime_btn.setEnabled(enabled and self.realtime_timer.isActive())
        self.save_realtime_btn.setEnabled(enabled and self.realtime_data_count > 0)

    def log_message(self, message):
        """在输出区域记录消息"""
        self.output_text.append(message)
        self.output_text.ensureCursorVisible()
        # 更新状态栏
        self.statusBar().showMessage(message)

    def clear_output(self):
        """清空输出区域"""
        self.output_text.clear()
        self.statusBar().showMessage("输出已清空")

    def connect_device(self):
        """连接设备"""
        try:
            port = self.port_combo.currentText()
            if not port:
                self.log_message("错误: 请选择串口")
                return

            baudrate = int(self.baudrate_edit.text().strip())

            self.log_message(f"正在连接串口 {port}，波特率 {baudrate}...")
            QApplication.processEvents()  # 更新UI

            self.reader = GM8050Reader(port, baudrate)
            self.log_message("设备连接成功!")

            # 更新UI状态
            self.connect_btn.setEnabled(False)
            self.disconnect_btn.setEnabled(True)
            self.set_controls_enabled(True)
            self.laser_status_label.setText("状态: 未知 (请点击激光按钮)")

        except Exception as e:
            self.log_message(f"连接失败: {str(e)}")

    def disconnect_device(self):
        """断开设备连接"""
        if self.realtime_timer.isActive():
            self.realtime_timer.stop()

        if self.reader:
            try:
                self.reader.close()
                self.log_message("设备已断开连接")
            except:
                pass
            finally:
                self.reader = None

        # 更新UI状态
        self.connect_btn.setEnabled(True)
        self.disconnect_btn.setEnabled(False)
        self.set_controls_enabled(False)
        self.laser_status_label.setText("状态: 未连接")

    def laser_on(self):
        """开启激光"""
        if not self.reader:
            self.log_message("错误: 设备未连接")
            return

        try:
            # 构建激光开启命令
            address = "01"  # 固定地址01
            function = "06"  # 功能码06H - 写寄存器
            register = self.reader.LASER_CTRL_REG  # 0200H - 激光控制寄存器
            data = "0001"  # 开启激光

            # 发送命令
            self.log_message("发送激光开启命令...")
            success = self.reader.send_command(address, function, register + data)

            if success:
                self.log_message("激光开启命令发送成功!")
                self.laser_status_label.setText("状态: 已开启")
                # 读取状态确认
                self.check_laser_status()
            else:
                self.log_message("激光开启命令发送失败!")

        except Exception as e:
            self.log_message(f"开启激光失败: {str(e)}")

    def laser_off(self):
        """关闭激光"""
        if not self.reader:
            self.log_message("错误: 设备未连接")
            return

        try:
            # 构建激光关闭命令
            address = "01"  # 固定地址01
            function = "06"  # 功能码06H - 写寄存器
            register = self.reader.LASER_CTRL_REG  # 0200H - 激光控制寄存器
            data = "0000"  # 关闭激光

            # 发送命令
            self.log_message("发送激光关闭命令...")
            success = self.reader.send_command(address, function, register + data)

            if success:
                self.log_message("激光关闭命令发送成功!")
                self.laser_status_label.setText("状态: 已关闭")
                # 读取状态确认
                self.check_laser_status()
            else:
                self.log_message("激光关闭命令发送失败!")

        except Exception as e:
            self.log_message(f"关闭激光失败: {str(e)}")

    def check_laser_status(self):
        """检查激光状态 (可选)"""
        try:
            # 构建状态读取命令
            address = "01"  # 固定地址01
            function = "03"  # 功能码03H - 读寄存器
            register = self.reader.LASER_CTRL_REG  # 0200H - 激光控制寄存器
            count = "0001"  # 读取1个寄存器

            # 发送命令
            self.log_message("读取激光状态...")
            success = self.reader.send_command(address, function, register + count)

            if success:
                # 期待响应: 5字节头 + 2字节数据
                resp_status = self.reader.read_response(7, 1.0)
                if resp_status == "成功" and len(self.reader.byte_array) >= 7:
                    # 解析状态值 (第5-6字节)
                    status_value = (self.reader.byte_array[4] << 8) | self.reader.byte_array[5]
                    status = "开启" if status_value == 1 else "关闭"
                    self.log_message(f"激光状态: {status}")
                    self.laser_status_label.setText(f"状态: {status} (已确认)")
                else:
                    self.log_message("激光状态读取失败!")
            else:
                self.log_message("激光状态读取命令发送失败!")

        except Exception as e:
            self.log_message(f"读取激光状态失败: {str(e)}")

    def start_demodulation(self):
        """启动解调过程"""
        try:
            # 检查激光状态
            if "关闭" in self.laser_status_label.text():
                self.log_message("警告: 激光器可能未开启，解调可能失败!")

            self.log_message("启动解调过程...")
            # 根据VB示例，启动解调顺序
            self.reader.send_command("01", "06", "02010001")  # 启动通道1-8
            self.log_message("解调已成功启动")
        except Exception as e:
            self.log_message(f"启动解调失败: {str(e)}")

    def stop_demodulation(self):
        """停止解调过程"""
        try:
            self.log_message("停止解调过程...")
            self.reader.send_command("01", "06", "02010000")  # 停止解调
            self.log_message("解调已成功停止")
        except Exception as e:
            self.log_message(f"停止解调失败: {str(e)}")


    def start_spectrum_scan(self):
        """启动光谱扫描"""
        try:
            # 检查激光状态
            if "关闭" in self.laser_status_label.text():
                self.log_message("警告: 激光器可能未开启，扫描可能失败!")

            self.log_message("启动光谱扫描...")
            self.reader.send_command("01", "06", "02020001")  # 启动一次扫描
            self.log_message("光谱扫描已启动，等待1秒...")
        except Exception as e:
            self.log_message(f"启动光谱扫描失败: {str(e)}")

    def read_spectrum_data(self):
        """读取光谱数据"""
        try:
            # 启动扫描
            self.log_message("启动光谱扫描...")
            self.reader.send_command("01", "06", "02020001")
            time.sleep(0.9)

            # 读取设备内置光谱数据
            wavelengths, spectrum = self.reader.read_spectrum()
            if not wavelengths or not any(spectrum):
                self.log_message("错误: 未获取到光谱数据")
                return [], []

            # 获取用户设置
            try:
                user_start = float(self.start_wl_edit.text())
                user_stop = float(self.stop_wl_edit.text())
                user_step = float(self.step_edit.text())
            except ValueError:
                self.log_message("错误: 无效的波长设置")
                return [], []

            # 获取设备步长
            device_step = wavelengths[1] - wavelengths[0] if len(wavelengths) > 1 else 0

            # 验证用户步长是设备步长的整数倍
            if device_step > 0:
                step_ratio = user_step / device_step
                if abs(step_ratio - round(step_ratio)) > 0.01:
                    adjusted_step = device_step * max(1, round(step_ratio))
                    self.log_message(
                        f"警告: 用户步长({user_step})不是设备步长({device_step:.4f})的整数倍，已自动调整为{adjusted_step:.4f}")
                    user_step = adjusted_step
                    self.step_edit.setText(f"{user_step:.4f}")

            # 筛选数据点
            filtered_wavelengths = []
            filtered_spectrum = [[] for _ in range(4)]

            # 计算步长倍数
            step_multiplier = max(1, round(user_step / device_step)) if device_step > 0 else 1

            for i, wl in enumerate(wavelengths):
                # 检查波长是否在用户设定范围内
                if wl < user_start or wl > user_stop:
                    continue

                # 按步长倍数采样
                if i % step_multiplier == 0:
                    filtered_wavelengths.append(wl)
                    for ch in range(4):
                        if i < len(spectrum[ch]):
                            filtered_spectrum[ch].append(spectrum[ch][i])
                        else:
                            filtered_spectrum[ch].append(0)

            if not filtered_wavelengths:
                self.log_message("错误: 没有在设定波长范围内的数据")
                return [], []

            # 保存并绘图
            self.last_wavelengths = filtered_wavelengths
            self.last_spectrum = filtered_spectrum
            self.plot_spectrum(filtered_wavelengths, filtered_spectrum)

            self.log_message(f"成功获取光谱数据: {len(filtered_wavelengths)}个点")

            # +++ 新增：计算并显示中心波长 +++
            self.calculate_center_wavelengths(filtered_wavelengths, filtered_spectrum)

            return filtered_wavelengths, filtered_spectrum
        except Exception as e:
            self.log_message(f"读取失败: {str(e)}")
            return [], []

    def plot_spectrum(self, wavelengths, spectrum):
        """绘制光谱数据"""
        # 清除之前的图形
        self.ax.clear()

        # 设置中文字体
        font_path = fm.findfont(fm.FontProperties(family='SimHei'))
        font_prop = fm.FontProperties(fname=font_path)

        # 设置标题和坐标轴标签
        self.ax.set_title('光谱扫描结果', fontproperties=font_prop)
        self.ax.set_xlabel('波长 (nm)', fontproperties=font_prop)
        self.ax.set_ylabel('幅值', fontproperties=font_prop)
        self.ax.grid(True)

        # 定义不同通道的颜色
        colors = ['b', 'g', 'r', 'c']
        labels = ['通道 1', '通道 2', '通道 3', '通道 4']

        # 根据复选框状态绘制数据
        for i in range(min(4, len(spectrum))):
            if i == 0 and self.ch1_check.isChecked():
                self.ax.plot(wavelengths, spectrum[i], colors[i], label=labels[i])
            elif i == 1 and self.ch2_check.isChecked():
                self.ax.plot(wavelengths, spectrum[i], colors[i], label=labels[i])
            elif i == 2 and self.ch3_check.isChecked():
                self.ax.plot(wavelengths, spectrum[i], colors[i], label=labels[i])
            elif i == 3 and self.ch4_check.isChecked():
                self.ax.plot(wavelengths, spectrum[i], colors[i], label=labels[i])

        # 添加图例
        self.ax.legend(prop=font_prop)

        # 自动调整坐标轴范围
        self.ax.relim()
        self.ax.autoscale_view()

        # 添加鼠标悬停事件
        self.canvas.mpl_connect('motion_notify_event', lambda event: self.on_mouse_move(event, wavelengths, spectrum))

        # 重绘画布
        self.canvas.draw()

        self.log_message("光谱数据绘制完成")

    def calculate_center_wavelengths(self, wavelengths, spectrum):
        """计算各通道的中心波长（取幅值高于阈值点的加权平均值）"""
        # 幅值阈值（可调整）
        THRESHOLD_RATIO = 100

        # 存储各通道的中心波长
        center_wavelengths = []

        # 遍历每个通道
        for ch in range(4):
            # 只处理被选中的通道
            if ((ch == 0 and self.ch1_check.isChecked()) or
                    (ch == 1 and self.ch2_check.isChecked()) or
                    (ch == 2 and self.ch3_check.isChecked()) or
                    (ch == 3 and self.ch4_check.isChecked())):

                # 获取当前通道数据
                ch_data = spectrum[ch]
                if not ch_data:
                    continue

                # 找到峰值点索引和最大幅值
                max_value = max(ch_data)
                max_idx = ch_data.index(max_value)

                # 计算阈值
                threshold = THRESHOLD_RATIO * max_value

                # 收集高于阈值的点
                high_value_points = []
                for i, value in enumerate(ch_data):
                    if value >= threshold:
                        # 存储波长和对应的幅值
                        high_value_points.append((wavelengths[i], value))

                # 如果没有符合条件的点，使用峰值点
                if not high_value_points:
                    center_wl = wavelengths[max_idx]
                    center_wavelengths.append((ch, center_wl))
                    continue

                # 计算加权平均中心波长
                total_weight = 0.0
                weighted_sum = 0.0

                for wl, value in high_value_points:
                    # 使用幅值的平方作为权重（更强调高幅值点）
                    weight = value ** 2
                    weighted_sum += wl * weight
                    total_weight += weight

                # 计算中心波长
                center_wl = weighted_sum / total_weight if total_weight > 0 else wavelengths[max_idx]
                center_wavelengths.append((ch, center_wl))

        # 显示结果
        if center_wavelengths:
            message = "中心波长: "
            for ch, wl in center_wavelengths:
                message += f"CH{ch + 1}: {wl:.4f}nm; "
            self.log_message(message)
        else:
            self.log_message("未找到有效的中心波长数据")

    def on_mouse_move(self, event, wavelengths, spectrum):
        """鼠标移动时显示当前点的数据"""
        if not event.inaxes:
            return

        # 获取鼠标位置
        x = event.xdata
        y = event.ydata

        # 找到最近的波长点
        if wavelengths:
            idx = min(range(len(wavelengths)), key=lambda i: abs(wavelengths[i] - x))
            wl = wavelengths[idx]

            # 获取所有通道在该波长的幅值
            values = []
            for i in range(4):
                if idx < len(spectrum[i]):
                    values.append(f"{spectrum[i][idx]}")
                else:
                    values.append("N/A")

            # 更新状态栏
            self.statusBar().showMessage(
                f"波长: {wl:.4f}nm, "
                f"通道1: {values[0]}, "
                f"通道2: {values[1]}, "
                f"通道3: {values[2]}, "
                f"通道4: {values[3]}"
            )

    def save_spectrum_data(self):
        """保存光谱数据到CSV文件"""
        try:
            # 检查是否有可用数据
            if not hasattr(self, 'last_wavelengths') or not hasattr(self, 'last_spectrum'):
                self.log_message("错误: 没有可用的光谱数据")
                return

            wavelengths = self.last_wavelengths
            spectrum = self.last_spectrum

            # 检查数据有效性
            if not wavelengths or not any(spectrum):
                self.log_message("错误: 数据为空")
                return

            # 弹出文件保存对话框
            file_path, _ = QFileDialog.getSaveFileName(
                self, "保存光谱数据", "", "CSV文件 (*.csv);;所有文件 (*)"
            )

            if not file_path:
                return  # 用户取消

            # 确保文件扩展名正确
            if not file_path.lower().endswith('.csv'):
                file_path += '.csv'

            # 写入CSV文件
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                # 写入表头
                f.write("波长(nm)")
                for i in range(4):
                    if (i == 0 and self.ch1_check.isChecked()) or \
                            (i == 1 and self.ch2_check.isChecked()) or \
                            (i == 2 and self.ch3_check.isChecked()) or \
                            (i == 3 and self.ch4_check.isChecked()):
                        f.write(f",通道{i + 1}")
                f.write("\n")

                # 写入数据
                for i in range(len(wavelengths)):
                    f.write(f"{wavelengths[i]:.4f}")
                    for ch in range(4):
                        if (ch == 0 and self.ch1_check.isChecked()) or \
                                (ch == 1 and self.ch2_check.isChecked()) or \
                                (ch == 2 and self.ch3_check.isChecked()) or \
                                (ch == 3 and self.ch4_check.isChecked()):
                            if i < len(spectrum[ch]):
                                f.write(f",{spectrum[ch][i]}")
                            else:
                                f.write(",")  # 空值
                    f.write("\n")

            self.log_message(f"光谱数据已保存到: {file_path}")

        except Exception as e:
            self.log_message(f"保存数据失败: {str(e)}")
            import traceback
            self.log_message(traceback.format_exc())

    def start_realtime_plotting(self):
        """开始实时绘图"""
        try:
            # 获取更新间隔
            interval = float(self.interval_edit.text().strip())
            if interval < 1.0:
                interval = 1.0
                self.interval_edit.setText("1.0")

            # 重置实时数据结构
            self.realtime_wavelengths = None
            self.realtime_data = {0: [], 1: [], 2: [], 3: []}
            self.realtime_timestamps = []
            self.last_update_time = 0  # 添加最后更新时间记录

            # 设置定时器
            self.realtime_timer.start(int(interval * 1000))
            self.log_message(f"开始实时绘图，间隔 {interval} 秒")

            # 更新按钮状态
            self.start_realtime_btn.setEnabled(False)
            self.stop_realtime_btn.setEnabled(True)
            self.save_realtime_btn.setEnabled(False)

        except ValueError:
            self.log_message("错误: 更新间隔必须是数字")

    def stop_realtime_plotting(self):
        """停止实时绘图"""
        self.realtime_timer.stop()
        self.log_message("已停止实时绘图")
        self.start_realtime_btn.setEnabled(True)
        self.stop_realtime_btn.setEnabled(False)

        # 如果有数据，则允许保存
        if any(len(data) > 0 for data in self.realtime_data.values()):
            self.save_realtime_btn.setEnabled(True)

    def update_realtime_plot(self):
        """更新实时光谱图"""
        if not self.reader:
            self.stop_realtime_plotting()
            return

        # 检查是否达到间隔时间
        current_time = time.time()
        if current_time - self.last_update_time < 1.0:  # 确保至少1秒间隔
            return

        try:
            # 记录开始时间
            start_time = time.time()

            # 读取光谱数据
            wavelengths, spectrum = self.read_spectrum_data()
            if wavelengths and any(spectrum):
                current_time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

                # 更新数据结构
                if self.realtime_wavelengths is None:
                    self.realtime_wavelengths = wavelengths

                # 存储各通道数据
                for ch in range(4):
                    if ((ch == 0 and self.ch1_check.isChecked()) or
                            (ch == 1 and self.ch2_check.isChecked()) or
                            (ch == 2 and self.ch3_check.isChecked()) or
                            (ch == 3 and self.ch4_check.isChecked())):
                        self.realtime_data[ch].append(spectrum[ch])

                # 存储时间戳
                self.realtime_timestamps.append(current_time_str)

                # 更新图表
                self.plot_spectrum(wavelengths, spectrum)
                self.statusBar().showMessage(
                    f"最后更新时间: {current_time_str} (数据组数: {len(self.realtime_timestamps)})")

                # 更新最后更新时间
                self.last_update_time = time.time()

                # 计算实际耗时并记录
                elapsed = time.time() - start_time
                self.log_message(f"数据采集耗时: {elapsed:.2f}秒")

        except Exception as e:
            self.log_message(f"实时更新失败: {str(e)}")

    def save_realtime_data(self):
        """保存实时数据到文件（每个通道单独保存）"""
        if not any(len(data) > 0 for data in self.realtime_data.values()):
            self.log_message("没有可保存的实时数据")
            return

        try:
            # 获取保存文件夹
            folder_path = QFileDialog.getExistingDirectory(self, "选择保存实时数据的文件夹")
            if not folder_path:
                return

            # 获取当前时间作为文件名前缀
            timestamp = time.strftime("%Y%m%d_%H%M%S", time.localtime())

            # 检查是否有波长数据
            if self.realtime_wavelengths is None or len(self.realtime_wavelengths) == 0:
                self.log_message("错误: 没有可用的波长数据")
                return

            # 保存每个通道的数据
            for ch in range(4):
                # 只保存用户选择的通道
                if ((ch == 0 and self.ch1_check.isChecked()) or
                    (ch == 1 and self.ch2_check.isChecked()) or
                    (ch == 2 and self.ch3_check.isChecked()) or
                    (ch == 3 and self.ch4_check.isChecked())) and \
                        len(self.realtime_data[ch]) > 0:

                    # 创建通道文件名
                    filename = f"channel_{ch + 1}_{timestamp}.csv"
                    file_path = os.path.join(folder_path, filename)

                    # 写入数据
                    with open(file_path, 'w', encoding='utf-8-sig') as f:
                        # 写入表头
                        f.write("波长(nm)")
                        for ts in self.realtime_timestamps:
                            f.write(f",{ts}")
                        f.write("\n")

                        # 写入数据行 - 按波长点组织
                        for i, wl in enumerate(self.realtime_wavelengths):
                            f.write(f"{wl:.4f}")
                            # 遍历所有时间点
                            for j in range(len(self.realtime_timestamps)):
                                # 确保索引在范围内
                                if j < len(self.realtime_data[ch]) and i < len(self.realtime_data[ch][j]):
                                    f.write(f",{self.realtime_data[ch][j][i]}")
                                else:
                                    f.write(",0")  # 缺失数据用0填充
                            f.write("\n")

                    self.log_message(f"通道 {ch + 1} 数据已保存至: {file_path}")

            self.log_message("所有通道数据保存完成")

            # 更新状态栏显示保存信息
            self.statusBar().showMessage(f"实时数据已保存到: {folder_path}")

        except Exception as e:
            self.log_message(f"保存实时数据失败: {str(e)}")

    def closeEvent(self, event):
        """窗口关闭时确保断开连接"""
        if self.reader:
            self.disconnect_device()
        event.accept()


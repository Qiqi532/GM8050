import serial
import time
import struct
from typing import List, Optional


class GM8050Reader:
    # 寄存器地址常量 (十六进制)
    LASER_CTRL_REG = "0200"
    DEMOD_CTRL_REG = "0201"
    SINGLE_SCAN_REG = "0202"
    CENTER_WL_FLOAT_BASE = "0300"  # 浮点数中心波长基地址
    SPECTRUM_BASE = "2000"  # 光谱数据基地址

    def __init__(self, port: str, baudrate: int = 115200, timeout: float = 1):
        """初始化串口连接"""
        self.ser = serial.Serial(
            port=port,
            baudrate=baudrate,  # 协议指定115200波特率
            bytesize=8,
            parity=serial.PARITY_NONE,
            stopbits=1,
            timeout=timeout
        )
        self.byte_array = bytearray()
        self.NUM_CHANNELS = 4  # 实际通道数设为4

    def convert_bytes_to_float(self, byte_array):
        """将4字节大端序数据转换为浮点数"""
        return struct.unpack('>f', byte_array)[0]

    def convert_bytes_to_uint16(self, byte_array):
        """将2字节数据转换为UINT16"""
        return (byte_array[0] << 8) | byte_array[1]

    @staticmethod
    def calc_crc16(data: bytes) -> int:
        """计算Modbus CRC16校验码 (符合协议规范)"""
        crc = 0xFFFF
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 0x0001:
                    crc >>= 1
                    crc ^= 0xA001
                else:
                    crc >>= 1
        return crc

    def build_command(self, address: str, function: str, data: str = "") -> bytes:
        """构建完整Modbus命令（带CRC校验）"""
        cmd_hex = address + function + data
        cmd_bytes = bytes.fromhex(cmd_hex)
        crc = self.calc_crc16(cmd_bytes)
        return cmd_bytes + bytes([crc & 0xFF, (crc >> 8) & 0xFF])

    def send_command(self, address: str, function: str, data: str = "") -> bool:
        """发送Modbus命令"""
        try:
            cmd = self.build_command(address, function, data)
            self.ser.write(cmd)
            return True
        except Exception as e:
            print(f"发送错误: {e}")
            return False

    def read_response(self, expected_len: int, timeout: float = 1.0) -> str:
        """读取并解析响应，优化超时处理"""
        self.ser.reset_input_buffer()
        self.byte_array = bytearray()
        start_time = time.time()
        last_data_time = start_time  # 记录最后一次收到数据的时间
        min_data_length = 5  # 最小有效数据长度

        while (time.time() - start_time) < timeout:
            if self.ser.in_waiting:
                self.byte_array.extend(self.ser.read(self.ser.in_waiting))
                last_data_time = time.time()  # 更新最后收到数据的时间

                # 检查基本错误
                if len(self.byte_array) >= 3:
                    if self.byte_array[1] & 0x80:  # 异常响应
                        if len(self.byte_array) >= 5:
                            error_code = self.byte_array[2]
                            if error_code == 1:
                                return "非法功能码"
                            elif error_code == 2:
                                return "非法数据地址"
                            elif error_code == 3:
                                return "非法数据值"
                            else:
                                return f"未知错误码: {error_code}"

                # 检查是否收到足够数据
                if len(self.byte_array) >= expected_len:
                    return "成功"

            # 快速判断：如果已经等待超过0.1秒且没有新数据，并且已有数据长度不足，则认为无数据
            if (time.time() - last_data_time > 0.1) and len(self.byte_array) < min_data_length:
                return "无数据"

        return "响应超时"

    def start_demodulation(self):
        """启动解调过程（符合协议启动顺序）"""
        # 由于只有4个通道，我们只需要启动地址01（通道1-8）即可
        self.send_command("01", "06", f"{self.DEMOD_CTRL_REG}0001")
        time.sleep(1)  # 等待扫描完成

    def read_center_wavelengths(self, address: str) -> List[float]:
        """读取单个通道的中心波长（浮点数）"""
        # 使用功能码14H读取浮点数中心波长
        cmd_data = f"03000200"  # 起始地址0300H，数量0200H(512个寄存器)
        results = []

        if not self.send_command(address, "14", cmd_data):
            return results

        # 期待响应: 4字节头 + 1024字节数据
        resp_status = self.read_response(4 + 1024, 20)
        if resp_status != "成功":
            print(f"读取中心波长失败: {resp_status}")
            return []

        # 解析数据 (跳过4字节头)
        data = self.byte_array[4:4 + 1024]

        # 解析32个浮点数波长
        for i in range(32):
            idx = i * 4
            # 大端序浮点数转换
            value = struct.unpack('>f', data[idx:idx + 4])[0]
            if value > 0:  # 过滤无效数据
                results.append(value)

        return results

    def start_spectrum_scan(self):
        """启动单次光谱扫描"""
        self.send_command("01", "06", f"{self.SINGLE_SCAN_REG}0001")
        time.sleep(1)  # 等待扫描完成

    def read_scan_parameters(self) -> tuple:
        """读取设备内置的扫描参数（起点、终点、步长）"""
        try:
            # 读取扫描起点 (1005H)
            if not self.send_command("01", "03", "10050001"):
                print("读取扫描起点失败")
                return (0, 0, 0)
            resp_status = self.read_response(7, 1.0)
            if resp_status != "成功" or len(self.byte_array) < 7:
                print(f"扫描起点响应失败: {resp_status}")
                return (0, 0, 0)
            start_reg = (self.byte_array[3] << 8) | self.byte_array[4]

            # 读取扫描终点 (1006H)
            if not self.send_command("01", "03", "10060001"):
                print("读取扫描终点失败")
                return (0, 0, 0)
            resp_status = self.read_response(7, 1.0)
            if resp_status != "成功" or len(self.byte_array) < 7:
                print(f"扫描终点响应失败: {resp_status}")
                return (0, 0, 0)
            stop_reg = (self.byte_array[3] << 8) | self.byte_array[4]

            # 读取扫描步长 (1007H)
            if not self.send_command("01", "03", "10070001"):
                print("读取扫描步长失败")
                return (0, 0, 0)
            resp_status = self.read_response(7, 1.0)
            if resp_status != "成功" or len(self.byte_array) < 7:
                print(f"扫描步长响应失败: {resp_status}")
                return (0, 0, 0)
            step_reg = (self.byte_array[3] << 8) | self.byte_array[4]

            # 转换为实际波长值 (根据协议 7000=1527nm, 48000=1568nm)
            start_wl = 1520 + start_reg / 1000.0
            stop_wl = 1520 + stop_reg / 1000.0
            step_wl = step_reg / 1000.0

            print(f"扫描参数: 起点={start_wl:.4f}nm, 终点={stop_wl:.4f}nm, 步长={step_wl:.4f}nm")
            return (start_wl, stop_wl, step_wl)
        except Exception as e:
            print(f"读取扫描参数失败: {e}")
            return (0, 0, 0)

    def read_spectrum(self) -> tuple:
        """读取光谱数据（使用设备内置参数）"""
        try:
            # 获取设备内置扫描参数
            start_wl, stop_wl, step_wl = self.read_scan_parameters()
            if step_wl <= 0:
                print("无效的扫描步长")
                return [], []

            # 计算数据点数 (协议规定每个通道2051个点)
            num_points = 2051

            # 通道基地址映射
            channel_base_addrs = {
                0: 0x2000,  # 通道1
                1: 0x3000,  # 通道2
                2: 0x4000,  # 通道3
                3: 0x5000  # 通道4
            }

            # 生成波长数组
            wavelengths = [start_wl + i * step_wl for i in range(num_points)]

            # 读取每个通道的光谱数据
            spectrum = []
            for ch_idx in range(4):
                base_addr = channel_base_addrs[ch_idx]
                cmd_start = f"{base_addr:04X}"
                cmd_count = f"{num_points:04X}"
                cmd = f"0114{cmd_start}{cmd_count}"

                if not self.send_command(cmd[:2], cmd[2:4], cmd[4:]):
                    print(f"通道{ch_idx + 1}光谱读取命令发送失败")
                    spectrum.append([])
                    continue

                # 预期响应长度：地址(1)+功能码(1)+字节数(2)+数据(2*num_points)
                expected_length = 4 + 2 * num_points
                resp_status = self.read_response(expected_length, timeout=1.0)
                if resp_status != "成功":
                    print(f"通道{ch_idx + 1}光谱读取失败: {resp_status}")
                    spectrum.append([])
                    continue

                # 解析数据
                data_bytes = self.byte_array[4:4 + 2 * num_points]
                channel_data = []
                for i in range(num_points):
                    idx = i * 2
                    if idx + 1 < len(data_bytes):
                        value = (data_bytes[idx] << 8) | data_bytes[idx + 1]
                        channel_data.append(value)
                    else:
                        channel_data.append(0)
                spectrum.append(channel_data)
                print(f"通道{ch_idx + 1}读取成功，获取{len(channel_data)}个数据点")

            return wavelengths, spectrum
        except Exception as e:
            print(f"读取光谱数据失败: {e}")
            return [], []


    def stop_demodulation(self):
        """停止解调"""
        # 只需要停止地址01（通道1-8）即可
        self.send_command("01", "06", f"{self.DEMOD_CTRL_REG}0000")
        time.sleep(0.5)

    def close(self):
        """关闭连接"""
        if self.ser.is_open:
            self.ser.close()
# coding:utf-8
import sys
import time
import serial
import serial.tools.list_ports
from serial import Serial, SerialException
from PyQt5.QtGui import QFont, QKeyEvent, QTextCursor
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal, QObject
from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QStackedWidget,
    QLabel,
    QAction,
    QFileDialog,
    QFontDialog,
)

from qfluentwidgets import (
    FluentIcon as FIF,
    SegmentedWidget,
    InfoBar,
    InfoBarPosition,
    BodyLabel,
    ComboBox,
    PlainTextEdit,
    DropDownPushButton,
    RoundMenu,
    PushButton,
    ToggleButton,
    SpinBox,
    CheckBox,
    CompactSpinBox,
    RadioButton,
    setTheme,
    Theme,
    setThemeColor,
    TogglePushButton,
    StrongBodyLabel,
)

import os
import sys
config_path = os.path.join(os.path.dirname(__file__), '..', 'settings')
if config_path not in sys.path:
    sys.path.insert(0, config_path)
from config import cfg


class PortComboBox(ComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._port_data = []

    def addPortItems(self, port_infos):
        self._port_data = port_infos
        self.clear()
        for port_info in port_infos:
            port_name = port_info.split(" : ")[0] if " : " in port_info else port_info
            self.addItem(port_name)

    def getPortData(self, index):
        if 0 <= index < len(self._port_data):
            return self._port_data[index]
        return ""

    def currentPortData(self):
        return self.getPortData(self.currentIndex())

    def setCurrentPortByDevice(self, device):
        for i, port_info in enumerate(self._port_data):
            if port_info.startswith(device):
                self.setCurrentIndex(i)
                return True
        return False

    def showPopup(self):
        for i in range(self.count()):
            port_data = self.getPortData(i)
            self.setItemText(i, port_data)
        super().showPopup()

    def hidePopup(self):
        index = self.currentIndex()
        port_data = self.getPortData(index)
        port_name = port_data.split(" : ")[0] if " : " in port_data else port_data
        super().hidePopup()
        self.setItemText(index, port_name)
        self.setCurrentText(port_name)


class TerminalTextEdit(PlainTextEdit):
    send_data = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._terminal_mode = False
        self._setup_font()
        self._setup_document()

    def _setup_font(self):
        font = QFont("FiraMono Nerd Font", 10)
        font.setStyleHint(QFont.Monospace)
        self.setFont(font)

    def _setup_document(self):
        doc = self.document()
        doc.setDocumentMargin(2)

    def set_terminal_mode(self, enabled):
        self._terminal_mode = enabled
        if enabled:
            cursor = self.textCursor()
            cursor.movePosition(cursor.End)
            self.setTextCursor(cursor)

    def paintEvent(self, event):
        super().paintEvent(event)
        if hasattr(self, '_theme'):
            if self._theme == Theme.DARK:
                self.setStyleSheet("background-color: #1e1e1e; color: #ffffff;")
            else:
                self.setStyleSheet("background-color: #ffffff; color: #000000;")

    def set_theme(self, theme):
        self._theme = theme
        self.paintEvent(None)

    def keyPressEvent(self, event: QKeyEvent):
        if self._terminal_mode:
            if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
                self.send_data.emit("\r")
                return
            elif event.key() == Qt.Key_Backspace:
                self.send_data.emit("\x7f")
                return
            elif event.key() == Qt.Key_Delete:
                self.send_data.emit("\x1b[3~")
                return
            elif event.key() == Qt.Key_Left:
                self.send_data.emit("\x1b[D")
                return
            elif event.key() == Qt.Key_Right:
                self.send_data.emit("\x1b[C")
                return
            elif event.key() == Qt.Key_Home:
                self.send_data.emit("\x1b[H")
                return
            elif event.key() == Qt.Key_End:
                self.send_data.emit("\x1b[F")
                return
            elif event.key() == Qt.Key_Up:
                self.send_data.emit("\x1b[A")
                return
            elif event.key() == Qt.Key_Down:
                self.send_data.emit("\x1b[B")
                return
            text = event.text()
            if text:
                self.send_data.emit(text)
                return
        super().keyPressEvent(event)


class Serial_Data_Reader_Thread(QThread):
    data_received = pyqtSignal(str)
    hex_data_received = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, serial_port):
        super().__init__()
        self.serial_port = serial_port
        self.running = True
        self._text_buffer = ""
        self._hex_buffer = ""
        self._buffer_timer = QTimer()
        self._buffer_timer.timeout.connect(self._flush_buffer)
        self._buffer_timer.start(50)
        print("Serial_Data_Reader_Thread 初始化完成")

    def _flush_buffer(self):
        if self._text_buffer:
            self.data_received.emit(self._text_buffer)
            self._text_buffer = ""
        if self._hex_buffer:
            self.hex_data_received.emit(self._hex_buffer)
            self._hex_buffer = ""

    def run(self):
        print("Serial_Data_Reader_Thread 开始运行")
        while self.running:
            if self.serial_port is None or not self.serial_port.isOpen():
                print("串口未打开或已关闭，停止读取数据")
                break
            try:
                if self.serial_port.in_waiting > 0:
                    data = self.serial_port.read(self.serial_port.in_waiting)
                    decoded_text = data.decode('utf-8', errors='replace')
                    decoded_text = decoded_text.replace('\r\n', '\n').replace('\r', '\n')
                    self._text_buffer += decoded_text
                    hex_data = data.hex()
                    if hex_data:
                        formatted_hex = " ".join(
                            [hex_data[i : i + 2] for i in range(0, len(hex_data), 2)]
                        )
                        self._hex_buffer += formatted_hex + " "

            except SerialException as e:
                print(f"读取数据失败: {e}")
                self.error_occurred.emit(f"读取数据失败: {e}")
                break
            except Exception as e:
                print(f"未知错误: {e}")
                self.error_occurred.emit(f"未知错误: {e}")
                break

            self.msleep(10)

        self._flush_buffer()
        print("Serial_Data_Reader_Thread 结束运行")

    def stop(self):
        self.running = False
        self._buffer_timer.stop()
        if self.serial_port is not None:
            self.serial_port.close()
            self.serial_port = None
        self.wait()  # 等待线程结束


class Serial_Tools_Widget(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("serial_setting_widget")
        self.resize(1000, 700)
        self.pivot = SegmentedWidget(self)
        self.stackedWidget = QStackedWidget(self)
        self.Main_hLayout = QHBoxLayout(self)
        self.serial_setting_vBoxLayout = QVBoxLayout()
        self.serial_setting = QWidget()
        self.more_setting = QWidget()
        self.add_sub_interface(self.serial_setting, "serial_setting", "串口设置")
        self.add_sub_interface(self.more_setting, "more_setting", "更多设置")

        self.serial_setting_vBoxLayout.addWidget(self.pivot)
        self.serial_setting_vBoxLayout.addWidget(self.stackedWidget)
        self.serial_setting_vBoxLayout.addStretch(1)
        self.Main_hLayout.addLayout(self.serial_setting_vBoxLayout)
        self.init_receive_bar_ui()
        self.stackedWidget.setCurrentWidget(self.serial_setting)
        self.pivot.setCurrentItem("serial_setting")
        self.pivot.currentItemChanged.connect(self._on_pivot_changed)
        self.init_serial_setting_ui()
        self.init_more_setting_ui()

        self.serial_poll_timer = QTimer(self)
        self.serial_poll_timer.timeout.connect(self.check_serial_ports)
        self.serial_poll_timer.start(200)

        self.current_ports = []
        self._is_first_load = True
        self.parity_mapping = {
            "无": "N",
            "偶": "E",
            "奇": "O",
            "标记": "M",
            "空格": "S",
        }
        self.serial_port = None
        self.serial_text_buffer = bytearray()
        self.serial_hex_buffer = bytearray()
        
        self._load_config()
        self._update_left_panel_width()

    def _on_pivot_changed(self, key):
        self.stackedWidget.setCurrentWidget(self.findChild(QWidget, key))
        self._update_left_panel_width()

    def _update_left_panel_width(self):
        current_widget = self.stackedWidget.currentWidget()
        if current_widget == self.serial_setting:
            self.stackedWidget.setFixedWidth(185)
        else:
            self.stackedWidget.setFixedWidth(260)

    def init_receive_bar_ui(self):
        self.receive_bar_vBoxLayout = QVBoxLayout()

        self.reception_area_text_hLayout = QHBoxLayout()

        self.reception_area_text = TerminalTextEdit()
        self.reception_area_text_hLayout.addWidget(self.reception_area_text)
        self.receive_bar_vBoxLayout.addLayout(self.reception_area_text_hLayout)
        self.reception_area_text.setReadOnly(False)
        self.reception_area_text.set_terminal_mode(True)
        self.reception_area_text.send_data.connect(self.send_terminal_data)
        self._text_cleared = False
        self._hex_cleared = False
        self.reception_area_Hex_text = PlainTextEdit()
        font = QFont("Consolas", 9)
        font.setStyleHint(QFont.Monospace)
        self.reception_area_Hex_text.setFont(font)
        self.reception_area_text_hLayout.addWidget(self.reception_area_Hex_text)
        self.reception_area_Hex_text.setReadOnly(True)
        self.reception_area_Hex_text.hide()

        self.receive_bar_button_hLayout = QHBoxLayout()

        self.textMode_checkBox = CheckBox("文本模式", self)
        self.textMode_checkBox.setChecked(True)
        self.HexMode_checkBox = CheckBox("Hex模式", self)
        self.receive_bar_button_hLayout.addWidget(self.textMode_checkBox)
        self.receive_bar_button_hLayout.addWidget(self.HexMode_checkBox)
        self.textMode_checkBox.stateChanged.connect(self.update_checkBox_state)
        self.HexMode_checkBox.stateChanged.connect(self.update_checkBox_state)

        self.timestamp_checkBox = CheckBox("时间戳", self)
        self.timestamp_checkBox.setChecked(False)
        self.receive_bar_button_hLayout.addWidget(self.timestamp_checkBox)

        self.receive_bar_edit_togglebutton = ToggleButton("终端模式", self)
        self.receive_bar_edit_togglebutton.setIcon(FIF.COMMAND_PROMPT)
        self.receive_bar_edit_togglebutton.setMaximumWidth(120)
        self.receive_bar_edit_togglebutton.setChecked(True)
        self.receive_bar_edit_togglebutton.toggled.connect(
            self.onToggle_receive_bar_edit_togglebutton
        )
        self.receive_bar_button_hLayout.addWidget(self.receive_bar_edit_togglebutton)

        self.receive_bar_clear_button = DropDownPushButton(
            FIF.DELETE, "清空接收区", self
        )
        self.menu = RoundMenu(parent=self)
        clear_text_action = QAction("清空文本区")
        clear_Hex_action = QAction("清空Hex区")
        clear_receive_action = QAction("清空接收区")
        clear_text_action.triggered.connect(self.on_text_clicked)
        clear_Hex_action.triggered.connect(self.on_Hex_clicked)
        clear_receive_action.triggered.connect(self.on_receive_clicked)
        self.menu.addAction(clear_text_action)
        self.menu.addAction(clear_Hex_action)
        self.menu.addAction(clear_receive_action)
        self.receive_bar_clear_button.setMenu(self.menu)
        # self.receive_bar_clear_button.setMaximumWidth(120)
        self.receive_bar_button_hLayout.addWidget(self.receive_bar_clear_button)

        self.reception_area_fontsize_spinBox = SpinBox()
        self.reception_area_fontsize_spinBox.setRange(4, 100)
        self.reception_area_fontsize_spinBox.setValue(10)
        self.reception_area_fontsize_spinBox.valueChanged.connect(
            self.change_reception_area_fontsize
        )
        self.receive_bar_button_hLayout.addWidget(self.reception_area_fontsize_spinBox)

        self.export_button = PushButton(FIF.SAVE, "导出TXT", self)
        self.export_button.setMaximumWidth(100)
        self.export_button.clicked.connect(self.on_export_clicked)
        self.receive_bar_button_hLayout.addWidget(self.export_button)

        self.receive_bar_button_hLayout.addStretch(1)

        self.receive_bar_vBoxLayout.addLayout(self.receive_bar_button_hLayout)
        self.receive_bar_vBoxLayout.setSpacing(10)
        self.receive_bar_vBoxLayout.setContentsMargins(0, 0, 0, 9)
        self.Main_hLayout.addLayout(self.receive_bar_vBoxLayout, 1)

    def init_serial_setting_ui(self):
        main_serial_setting_layout = QVBoxLayout()
        # Port selection
        port_label = BodyLabel("端口号:")
        self.port_combo = PortComboBox()
        self.port_combo.setObjectName("port_combo")
        self.port_combo.addPortItems(self.get_serial_ports())
        self.port_combo.currentIndexChanged.connect(
            lambda index: self.on_combobox_changed(self.port_combo, "端口号")
        )

        port_hlayout = QHBoxLayout()
        port_hlayout.addWidget(port_label)
        port_hlayout.addStretch(1)
        port_hlayout.addWidget(self.port_combo)
        self.port_combo.setMinimumWidth(96)
        main_serial_setting_layout.addLayout(port_hlayout)

        # Baudrate selection
        baudrate_label = BodyLabel("波特率:")
        self.baudrate_combo = ComboBox()
        self.baudrate_combo.setObjectName("baudrate_combo")
        baudrates = [
            "2400",
            "4800",
            "9600",
            "19200",
            "38400",
            "57600",
            "115200",
            "230400",
            "460800",
            "576000",
            "921600",
            "1152000",
        ]
        self.baudrate_combo.addItems(baudrates)
        self.baudrate_combo.setCurrentIndex(6)
        self.baudrate_combo.currentTextChanged.connect(
            lambda text: self.on_combobox_changed(self.baudrate_combo, "波特率")
        )

        baudrate_hlayout = QHBoxLayout()
        baudrate_hlayout.addWidget(baudrate_label)
        baudrate_hlayout.addStretch(1)
        baudrate_hlayout.addWidget(self.baudrate_combo)
        self.baudrate_combo.setMinimumWidth(96)
        main_serial_setting_layout.addLayout(baudrate_hlayout)

        # Data bits selection
        databit_label = BodyLabel("数据位:")
        self.databit_combo = ComboBox()
        self.databit_combo.setObjectName("databit_combo")
        databits = ["5", "6", "7", "8"]
        self.databit_combo.addItems(databits)
        self.databit_combo.setCurrentIndex(3)
        self.databit_combo.currentTextChanged.connect(
            lambda text: self.on_combobox_changed(self.databit_combo, "数据位")
        )

        databit_hlayout = QHBoxLayout()
        databit_hlayout.addWidget(databit_label)
        databit_hlayout.addStretch(1)
        databit_hlayout.addWidget(self.databit_combo)
        self.databit_combo.setMinimumWidth(96)
        main_serial_setting_layout.addLayout(databit_hlayout)

        # Stop bits selection
        stopbit_label = BodyLabel("停止位:")
        self.stopbit_combo = ComboBox()
        self.stopbit_combo.setObjectName("stopbit_combo")
        stopbits = ["1", "1.5", "2"]
        self.stopbit_combo.addItems(stopbits)
        self.stopbit_combo.currentTextChanged.connect(
            lambda text: self.on_combobox_changed(self.stopbit_combo, "停止位")
        )

        stopbit_hlayout = QHBoxLayout()
        stopbit_hlayout.addWidget(stopbit_label)
        stopbit_hlayout.addStretch(1)
        stopbit_hlayout.addWidget(self.stopbit_combo)
        self.stopbit_combo.setMinimumWidth(96)
        main_serial_setting_layout.addLayout(stopbit_hlayout)

        # Parity selection
        parity_label = BodyLabel("奇偶校验:")
        self.parity_combo = ComboBox()
        self.parity_combo.setObjectName("parity_combo")
        parities = ["无", "偶校验", "奇校验", "标记", "空格"]
        self.parity_combo.addItems(parities)
        self.parity_combo.currentTextChanged.connect(
            lambda text: self.on_combobox_changed(self.parity_combo, "奇偶校验")
        )

        parity_hlayout = QHBoxLayout()
        parity_hlayout.addWidget(parity_label)
        parity_hlayout.addStretch(1)
        parity_hlayout.addWidget(self.parity_combo)
        self.parity_combo.setMinimumWidth(96)
        main_serial_setting_layout.addLayout(parity_hlayout)

        dtr_rts_hlayout = QHBoxLayout()
        self.dtr_switch = TogglePushButton("DTR", self)
        self.dtr_switch.setChecked(cfg.get(cfg.serialDtrState))
        self.dtr_switch.toggled.connect(self.on_dtr_changed)
        dtr_rts_hlayout.addWidget(self.dtr_switch)

        self.rts_switch = TogglePushButton("RTS", self)
        self.rts_switch.setChecked(cfg.get(cfg.serialRtsState))
        self.rts_switch.toggled.connect(self.on_rts_changed)
        dtr_rts_hlayout.addWidget(self.rts_switch)
        main_serial_setting_layout.addLayout(dtr_rts_hlayout)

        self.serial_start_pushbutton = ToggleButton(FIF.PLAY_SOLID, "开始监视", self)
        self.serial_start_pushbutton.toggled.connect(
            self.onToggle_serial_start_pushbutton
        )
        serial_port_start_hlayout = QHBoxLayout()
        serial_port_start_hlayout.addWidget(self.serial_start_pushbutton)
        main_serial_setting_layout.addLayout(serial_port_start_hlayout)
        main_serial_setting_layout.setSpacing(12)
        self.serial_setting.setLayout(main_serial_setting_layout)

    def init_more_setting_ui(self):
        more_setting_layout = QVBoxLayout()
        
        font_group_label = StrongBodyLabel("字体设置")
        more_setting_layout.addWidget(font_group_label)
        
        font_hlayout = QHBoxLayout()
        self.font_display_label = BodyLabel(cfg.get(cfg.serialFontFamily))
        self.font_display_label.setMinimumWidth(150)
        self.font_select_button = PushButton(FIF.FONT, "选择字体", self)
        self.font_select_button.clicked.connect(self.on_font_select_clicked)
        font_hlayout.addStretch(1)
        font_hlayout.addWidget(self.font_display_label)
        font_hlayout.addWidget(self.font_select_button)
        font_hlayout.addStretch(1)
        more_setting_layout.addLayout(font_hlayout)
        
        more_setting_layout.addStretch(1)
        self.more_setting.setLayout(more_setting_layout)

    def _load_config(self):
        font = cfg.serialFont
        self.reception_area_text.setFont(font)
        self.reception_area_Hex_text.setFont(font)
        self.reception_area_fontsize_spinBox.setValue(cfg.get(cfg.serialFontSize))

    def on_dtr_changed(self, checked):
        cfg.set(cfg.serialDtrState, checked)
        if self.serial_port is not None and self.serial_port.is_open:
            self.serial_port.dtr = checked
        state = "开启" if checked else "关闭"
        self.show_success_info_bar("DTR状态：", f"已{state}", 1000)

    def on_rts_changed(self, checked):
        cfg.set(cfg.serialRtsState, checked)
        if self.serial_port is not None and self.serial_port.is_open:
            self.serial_port.rts = checked
        state = "开启" if checked else "关闭"
        self.show_success_info_bar("RTS状态：", f"已{state}", 1000)

    def on_font_select_clicked(self):
        font, ok = QFontDialog.getFont(cfg.serialFont, self, "选择串口文本字体")
        if ok:
            cfg.serialFont = font
            self.font_display_label.setText(font.family())
            self.reception_area_text.setFont(font)
            self.reception_area_Hex_text.setFont(font)
            self.reception_area_fontsize_spinBox.setValue(font.pointSize())
            self.show_success_info_bar("字体设置：", f"已设置为 {font.family()}", 1000)

    def update_checkBox_state(self, state=None):
        # 当前被触发的复选框
        sender = self.sender()
        # 如果发送者是文本模式复选框并且没有被选中，则选中Hex模式复选框
        if sender == self.textMode_checkBox and not self.textMode_checkBox.isChecked():
            self.HexMode_checkBox.setChecked(True)
            self.reception_area_Hex_text.show()
            self.reception_area_text.hide()
        # 如果发送者是Hex模式复选框并且没有被选中，则选中文本模式复选框
        elif sender == self.HexMode_checkBox and not self.HexMode_checkBox.isChecked():
            self.textMode_checkBox.setChecked(True)
            self.reception_area_text.show()
            self.reception_area_Hex_text.hide()
        else:
            self.reception_area_text.show()
            self.reception_area_Hex_text.show()

    def change_reception_area_fontsize(self, value):
        font = cfg.serialFont
        font.setPointSize(value)
        cfg.serialFont = font
        self.reception_area_text.setFont(font)
        self.reception_area_Hex_text.setFont(font)

    def onToggle_receive_bar_edit_togglebutton(self, checked):
        if checked:
            self.reception_area_text.setReadOnly(False)
            self.reception_area_Hex_text.setReadOnly(False)
            self.reception_area_text.set_terminal_mode(True)
            self.receive_bar_edit_togglebutton.setText("关闭终端")
            self.receive_bar_edit_togglebutton.setIcon(FIF.CLOSE)
            self.show_success_info_bar("终端模式：", "已开启，可交互发送数据", 1000)
        else:
            self.reception_area_text.setReadOnly(True)
            self.reception_area_Hex_text.setReadOnly(True)
            self.reception_area_text.set_terminal_mode(False)
            self.receive_bar_edit_togglebutton.setText("终端模式")
            self.receive_bar_edit_togglebutton.setIcon(FIF.COMMAND_PROMPT)
            self.show_success_info_bar("终端模式：", "已关闭", 1000)

    def send_terminal_data(self, data):
        if self.serial_port is not None and self.serial_port.is_open:
            try:
                self.serial_port.write(data.encode('latin-1'))
            except Exception as e:
                InfoBar.error(
                    title="发送失败：",
                    content=str(e),
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=3000,
                    parent=self,
                )

    def on_text_clicked(self):
        self.reception_area_text.clear()
        self._text_cleared = False
        self.show_success_info_bar("接收栏：", "已清空文本区", 1000)

    def on_Hex_clicked(self):
        self.reception_area_Hex_text.clear()
        self._hex_cleared = False
        self.show_success_info_bar("接收栏：", "已清空Hex区", 1000)

    def on_receive_clicked(self):
        self.reception_area_text.clear()
        self.reception_area_Hex_text.clear()
        self.reception_area_text.setMarkdown("# Text Mode \n")
        self.reception_area_Hex_text.setMarkdown("# Hex Mode \n")
        self._text_cleared = False
        self._hex_cleared = False
        self.show_success_info_bar("接收栏：", "已清空接收区", 1000)

    def onToggle_serial_start_pushbutton(self, checked):
        def reset_button_and_close_serial():
            self.serial_start_pushbutton.setText("开始监视")
            self.serial_start_pushbutton.setIcon(FIF.PLAY_SOLID)
            if self.serial_port is not None:
                self.serial_port.close()
                self.serial_port = None
                # 只有在data_read_thread存在时才尝试停止它
                if (
                    hasattr(self, "data_read_thread")
                    and self.data_read_thread is not None
                ):
                    self.data_read_thread.stop()
                    self.data_read_thread.wait()  # 确保线程结束
                    self.data_read_thread = None  # 清除对线程的引用
                    current_port_text = self.port_combo.currentText()
                    InfoBar.info(
                        title="串口已断开连接:",
                        content=f"串口-{current_port_text}",
                        orient=Qt.Horizontal,
                        isClosable=True,
                        position=InfoBarPosition.TOP,
                        duration=2000,
                        parent=self,
                    )

        if checked:
            current_port_text = self.port_combo.currentText()
            if not current_port_text:
                InfoBar.warning(
                    title="当前串口号为空:",
                    content="请先连接或选择一个有效的串口",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=2000,
                    parent=self,
                )
                self.serial_start_pushbutton.setChecked(False)
                return

            self.serial_start_pushbutton.setText("结束监视")
            self.serial_start_pushbutton.setIcon(FIF.PAUSE_BOLD)
            parity_to_char = self.parity_mapping.get(
                self.parity_combo.currentText(), "N"
            )
            try:
                self.serial_port = Serial(
                    port=current_port_text,
                    baudrate=int(self.baudrate_combo.currentText()),
                    bytesize=int(self.databit_combo.currentText()),
                    parity=parity_to_char,
                    timeout=0.1,
                    stopbits=float(self.stopbit_combo.currentText()),
                )
                self.serial_port.dtr = self.dtr_switch.isChecked()
                self.serial_port.rts = self.rts_switch.isChecked()
                self.data_read_thread = Serial_Data_Reader_Thread(
                    self.serial_port
                )
                self.data_read_thread.data_received.connect(
                    self.on_text_data_received
                )
                self.data_read_thread.hex_data_received.connect(
                    self.on_hex_data_received
                )
                self.data_read_thread.start()
                InfoBar.success(
                    title="串口已成功连接:",
                    content=f"串口-{current_port_text.split(':')[0]}",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=2000,
                    parent=self,
                )
            except Exception as e:
                print(f"串口打开失败: {e}")
                InfoBar.error(
                    title="串口连接失败:",
                    content="当前串口已被占用或不可用",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.BOTTOM_RIGHT,
                    duration=15000,
                    parent=self,
                )
                self.serial_start_pushbutton.setChecked(False)
                reset_button_and_close_serial()
        else:
            # 断开信号连接
            if hasattr(self, "data_read_thread") and self.data_read_thread is not None:
                self.data_read_thread.hex_data_received.disconnect(
                    self.on_hex_data_received
                )
            reset_button_and_close_serial()

    def on_text_data_received(self, text_data):
        if not self._text_cleared:
            self.reception_area_text.clear()
            self._text_cleared = True
        cursor = self.reception_area_text.textCursor()
        cursor.movePosition(cursor.End)
        cursor.insertText(text_data)
        self.reception_area_text.setTextCursor(cursor)
        self.reception_area_text.ensureCursorVisible()

    def on_hex_data_received(self, hex_data):
        if not self._hex_cleared:
            self.reception_area_Hex_text.clear()
            self._hex_cleared = True
        cursor = self.reception_area_Hex_text.textCursor()
        cursor.movePosition(cursor.End)
        cursor.insertText(hex_data)
        self.reception_area_Hex_text.setTextCursor(cursor)

    def on_export_clicked(self):
        if self.textMode_checkBox.isChecked():
            text_content = self.reception_area_text.toPlainText()
            default_name = "serial_text_log.txt"
        else:
            text_content = self.reception_area_Hex_text.toPlainText()
            default_name = "serial_hex_log.txt"

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "导出文件",
            default_name,
            "文本文件 (*.txt);;所有文件 (*)"
        )

        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(text_content)
                self.show_success_info_bar("导出成功：", f"文件已保存到 {file_path}")
            except Exception as e:
                InfoBar.error(
                    title="导出失败：",
                    content=str(e),
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=3000,
                    parent=self,
                )

    def get_serial_ports(self):
        ports = []
        for port_info in serial.tools.list_ports.comports():
            description = f"{port_info.device} : {port_info.description}"
            ports.append(description)
        return ports

    def check_serial_ports(self):
        new_ports = self.get_serial_ports()
        current_port_data = self.port_combo.currentPortData()
        current_port_device = current_port_data.split(" : ")[0] if " : " in current_port_data else ""

        if set(new_ports) == set(self.current_ports):
            return

        added_ports = [p for p in new_ports if p not in self.current_ports]
        removed_ports = [p for p in self.current_ports if p not in new_ports]
        removed_devices = [p.split(" : ")[0] for p in removed_ports]

        if self.serial_port is not None and self.serial_port.is_open:
            if self.serial_port.port in removed_devices:
                self._handle_serial_unplugged()

        self.port_combo.blockSignals(True)
        self.port_combo.addPortItems(new_ports)
        self.current_ports = new_ports

        if current_port_device:
            self.port_combo.setCurrentPortByDevice(current_port_device)
        elif new_ports:
            self.port_combo.setCurrentIndex(0)
            self.last_port_combo_text = ""
        self.port_combo.blockSignals(False)

        if added_ports and not self._is_first_load:
            self._show_ports_added_info(added_ports)

        if removed_ports and not self._is_first_load:
            self._show_ports_removed_info(removed_ports)

        if self._is_first_load and new_ports:
            self._is_first_load = False

    def _handle_serial_unplugged(self):
        if hasattr(self, "data_read_thread") and self.data_read_thread is not None:
            self.data_read_thread.running = False
            self.data_read_thread.hex_data_received.disconnect(self.on_hex_data_received)
            self.data_read_thread = None

        if self.serial_port is not None:
            try:
                self.serial_port.close()
            except:
                pass
            self.serial_port = None

        self.serial_start_pushbutton.setChecked(False)
        self.serial_start_pushbutton.setText("开始监视")
        self.serial_start_pushbutton.setIcon(FIF.PLAY_SOLID)

        InfoBar.warning(
            title="串口已断开",
            content="当前连接的串口已被拔出",
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=3000,
            parent=self,
        )

    def _show_ports_added_info(self, added_ports):
        numbered_ports = [f"{i + 1}. {port}" for i, port in enumerate(added_ports)]
        InfoBar.success(
            title="检测到新串口",
            content=f"新增：<br>{'<br>'.join(numbered_ports)}",
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=2000,
            parent=self,
        )

    def _show_ports_removed_info(self, removed_ports):
        InfoBar.warning(
            title="检测到串口移除",
            content=f"已移除：{', '.join(removed_ports)}",
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=2000,
            parent=self,
        )

    def on_combobox_changed(self, combo_box, title_prefix):
        current_text = combo_box.currentText()
        last_text_attr = f"last_{combo_box.objectName()}_text"
        
        if current_text and current_text != getattr(self, last_text_attr, None):
            self.show_success_info_bar(
                title=f"{title_prefix}成功设置为：", content=current_text
            )
            setattr(self, last_text_attr, current_text)
            self.serial_text_buffer.clear()

    def show_success_info_bar(self, title, content, duration=2000):
        InfoBar.success(
            title=title,
            content=content,
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=duration,
            parent=self,
        )

    def handle_error_occurred(self, error_message):
        InfoBar.error(
            title="串口连接失败:",
            content=error_message,
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.BOTTOM_RIGHT,
            duration=15000,
            parent=self,
        )

    def add_sub_interface(self, widget: QWidget, object_name, text):
        widget.setObjectName(object_name)
        self.stackedWidget.addWidget(widget)
        self.pivot.addItem(routeKey=object_name, text=text)


if __name__ == "__main__":
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)
    app = QApplication(sys.argv)
    w = Serial_Tools_Widget()
    w.show()
    sys.exit(app.exec_())

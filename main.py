import os
import sys
import json
import keyring
import requests
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                              QHBoxLayout, QLabel, QPushButton, QSpinBox, 
                              QDialog, QLineEdit, QMessageBox, QCheckBox, 
                              QComboBox, QSystemTrayIcon, QMenu)
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QIcon, QAction
from aliyunsdkcore.auth.credentials import AccessKeyCredential
from aliyunsdkcore.client import AcsClient
from aliyunsdkecs.request.v20140526.AuthorizeSecurityGroupRequest import AuthorizeSecurityGroupRequest
from aliyunsdkecs.request.v20140526.RevokeSecurityGroupRequest import RevokeSecurityGroupRequest
from aliyunsdkecs.request.v20140526.DescribeSecurityGroupsRequest import DescribeSecurityGroupsRequest

def resource_path(relative_path):
    """获取资源的绝对路径，支持开发环境和打包后的环境"""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

class ConfigDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("凭证配置")
        self.setModal(True)
        self.init_ui()
        self.load_credentials()

    def init_ui(self):
        layout = QVBoxLayout()
        
        # Access Key配置
        key_layout = QHBoxLayout()
        key_layout.addWidget(QLabel("Access Key:"))
        self.key_input = QLineEdit()
        key_layout.addWidget(self.key_input)
        layout.addLayout(key_layout)
        
        # Secret配置
        secret_layout = QHBoxLayout()
        secret_layout.addWidget(QLabel("Access Secret:"))
        self.secret_input = QLineEdit()
        self.secret_input.setEchoMode(QLineEdit.EchoMode.Password)
        secret_layout.addWidget(self.secret_input)
        layout.addLayout(secret_layout)
        
        # 区域配置
        region_layout = QHBoxLayout()
        region_layout.addWidget(QLabel("区域 ID:"))
        self.region_input = QLineEdit()
        self.region_input.setText("cn-hangzhou")
        region_layout.addWidget(self.region_input)
        layout.addLayout(region_layout)
        
        # 保存按钮
        self.save_btn = QPushButton("保存")
        self.save_btn.clicked.connect(self.save_credentials)
        layout.addWidget(self.save_btn)
        
        self.setLayout(layout)

    def load_credentials(self):
        try:
            credentials = keyring.get_password("network_updater", "credentials")
            if credentials:
                cred_dict = json.loads(credentials)
                self.key_input.setText(cred_dict['access_key'])
                self.region_input.setText(cred_dict['region_id'])
                
                secret = keyring.get_password("network_updater", "access_secret")
                if secret:
                    self.secret_input.setText(secret)
        except Exception as e:
            QMessageBox.warning(self, "警告", f"加载保存的凭证失败: {str(e)}")

    def save_credentials(self):
        try:
            credentials = {
                'access_key': self.key_input.text(),
                'region_id': self.region_input.text()
            }
            keyring.set_password("network_updater", "credentials", 
                               json.dumps(credentials))
            keyring.set_password("network_updater", "access_secret", 
                               self.secret_input.text())
            
            QMessageBox.information(self, "成功", "凭证保存成功！")
            self.accept()
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存凭证失败: {str(e)}")

class NetworkUpdater(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("安全组更新器")
        self.setGeometry(100, 100, 400, 300)
        
        # 存储当前规则的ID
        self.current_rule = None
        self.client = None
        self.auto_delete = True  # 默认启用自动删除
        self.auto_update = True  # 默认启用自动更新
        
        # 初始化系统托盘
        self.tray_icon = None
        self.setup_tray()
        
        # 初始化UI和其他组件
        self.init_ui()
        self.load_settings()
        self.init_client()
        
        # 设置定时器，每5分钟检查一次IP
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_security_group)
        self.timer.start(300000)  # 300000ms = 5分钟
        
        # 程序退出时清理规则
        app.aboutToQuit.connect(self.cleanup)

    def setup_tray(self):
        # 创建系统托盘图标
        self.tray_icon = QSystemTrayIcon(self)
        
        # 设置应用图标
        icon = QIcon.fromTheme("network-server")
        if icon.isNull():
            # 如果无法加载系统主题图标，使用内置图标
            icon = QIcon(resource_path("icon.png"))  # 使用资源路径加载图标
        self.tray_icon.setIcon(icon)
        self.setWindowIcon(icon)  # 同时设置窗口图标
        
        self.tray_icon.setToolTip("安全组更新器")
        
        # 创建托盘菜单
        tray_menu = QMenu()
        
        # 显示/隐藏主窗口
        show_action = QAction("显示主窗口", self)
        show_action.triggered.connect(self.show)
        tray_menu.addAction(show_action)
        
        # 立即更新
        update_action = QAction("立即更新", self)
        update_action.triggered.connect(self.update_security_group)
        tray_menu.addAction(update_action)
        
        # 分隔线
        tray_menu.addSeparator()
        
        # 退出程序
        quit_action = QAction("退出", self)
        quit_action.triggered.connect(self.quit_application)
        tray_menu.addAction(quit_action)
        
        # 设置托盘图标的菜单
        self.tray_icon.setContextMenu(tray_menu)
        
        # 显示托盘图标
        self.tray_icon.show()
        
        # 连接托盘图标的点击事件
        self.tray_icon.activated.connect(self.tray_icon_activated)

    def tray_icon_activated(self, reason):
        # 如果是左键点击，显示主窗口
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.show()
            self.activateWindow()  # 激活窗口（使其成为活动窗口）

    def closeEvent(self, event):
        # 重写关闭事件，点击关闭按钮时只隐藏窗口
        event.ignore()  # 忽略原始的关闭事件
        self.hide()     # 隐藏窗口
        
        # 显示提示消息
        if self.tray_icon:  # 检查托盘图标是否存在
            self.tray_icon.showMessage(
                "安全组更新器",
                "程序已最小化到系统托盘，右键点击图标可以退出程序。",
                QSystemTrayIcon.MessageIcon.Information,
                2000  # 显示2秒
            )

    def quit_application(self):
        # 真正的退出程序
        if self.current_rule and self.auto_delete:
            reply = QMessageBox.question(
                None, 
                "确认退出",
                "是否确认退出程序？当前的安全组规则将被删除。",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                QApplication.quit()
        else:
            QApplication.quit()

    def update_status(self, message):
        # 更新状态栏和托盘图标提示
        self.status_label.setText(f"状态: {message}")
        if self.tray_icon:  # 检查托盘图标是否存在
            self.tray_icon.setToolTip(f"安全组更新器\n{message}")

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout()
        
        # 安全组选择
        sg_layout = QHBoxLayout()
        sg_layout.addWidget(QLabel("安全组:"))
        self.sg_combo = QComboBox()
        self.sg_combo.setMinimumWidth(250)
        sg_layout.addWidget(self.sg_combo)
        self.refresh_sg_btn = QPushButton("刷新")
        self.refresh_sg_btn.clicked.connect(self.refresh_security_groups)
        sg_layout.addWidget(self.refresh_sg_btn)
        layout.addLayout(sg_layout)
        
        # 端口配置
        port_layout = QHBoxLayout()
        port_layout.addWidget(QLabel("端口:"))
        self.port_input = QSpinBox()
        self.port_input.setRange(1, 65535)
        self.port_input.setValue(8223)
        port_layout.addWidget(self.port_input)
        layout.addLayout(port_layout)
        
        # 自动删除选项
        self.auto_delete_cb = QCheckBox("退出时自动删除规则")
        self.auto_delete_cb.setChecked(True)
        self.auto_delete_cb.stateChanged.connect(self.on_auto_delete_changed)
        layout.addWidget(self.auto_delete_cb)
        
        # 自动更新选项
        self.auto_update_cb = QCheckBox("启动时自动更新规则")
        self.auto_update_cb.setChecked(True)
        self.auto_update_cb.stateChanged.connect(self.on_auto_update_changed)
        layout.addWidget(self.auto_update_cb)
        
        # 按钮布局
        button_layout = QHBoxLayout()
        self.config_btn = QPushButton("配置凭证")
        self.config_btn.clicked.connect(self.show_config_dialog)
        self.update_btn = QPushButton("立即更新")
        self.update_btn.clicked.connect(self.update_security_group)
        button_layout.addWidget(self.config_btn)
        button_layout.addWidget(self.update_btn)
        layout.addLayout(button_layout)
        
        # 状态显示
        self.status_label = QLabel("状态: 就绪")
        layout.addWidget(self.status_label)
        
        central_widget.setLayout(layout)

    def on_auto_delete_changed(self, state):
        self.auto_delete = bool(state)
        self.save_settings()

    def on_auto_update_changed(self, state):
        self.auto_update = bool(state)
        self.save_settings()

    def init_client(self):
        try:
            credentials = keyring.get_password("network_updater", "credentials")
            secret = keyring.get_password("network_updater", "access_secret")
            
            if credentials and secret:
                cred_dict = json.loads(credentials)
                credentials = AccessKeyCredential(cred_dict['access_key'], secret)
                self.client = AcsClient(region_id=cred_dict['region_id'], 
                                      credential=credentials)
                # 初始化客户端后自动刷新安全组列表
                self.refresh_security_groups()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"初始化客户端失败: {str(e)}")

    def refresh_security_groups(self):
        if not self.client:
            self.update_status("请先配置凭证")
            QMessageBox.warning(self, "警告", "请先配置凭证")
            return

        try:
            request = DescribeSecurityGroupsRequest()
            request.set_accept_format('json')
            response = json.loads(self.client.do_action_with_exception(request))
            
            self.sg_combo.clear()
            for sg in response.get('SecurityGroups', {}).get('SecurityGroup', []):
                # 显示格式：SecurityGroupName (SecurityGroupId)
                display_text = f"{sg.get('SecurityGroupName', '未命名')} ({sg.get('SecurityGroupId', '')})"
                self.sg_combo.addItem(display_text, sg.get('SecurityGroupId'))
                
            if self.sg_combo.count() > 0:
                self.update_status("已成功加载安全组列表")
                # 如果启用了自动更新且成功获取到安全组列表，执行更新
                if self.auto_update:
                    self.update_security_group()
            else:
                self.update_status("未找到安全组")
                
        except Exception as e:
            error_message = f"获取安全组列表失败: {str(e)}"
            self.update_status(error_message)
            QMessageBox.critical(self, "错误", error_message)

    def save_settings(self):
        try:
            settings = {
                'auto_delete': self.auto_delete,
                'auto_update': self.auto_update,
                'port': self.port_input.value()
            }
            keyring.set_password("network_updater", "settings", 
                               json.dumps(settings))
        except Exception:
            pass  # 设置保存失败不影响主要功能

    def load_settings(self):
        try:
            settings = keyring.get_password("network_updater", "settings")
            if settings:
                settings = json.loads(settings)
                self.auto_delete = settings.get('auto_delete', True)
                self.auto_update = settings.get('auto_update', True)
                self.auto_delete_cb.setChecked(self.auto_delete)
                self.auto_update_cb.setChecked(self.auto_update)
                self.port_input.setValue(settings.get('port', 8223))
        except Exception:
            pass  # 设置加载失败使用默认值

    def get_selected_security_group_id(self):
        return self.sg_combo.currentData()

    def update_security_group(self):
        if not self.client:
            self.update_status("请先配置凭证")
            QMessageBox.warning(self, "警告", "请先配置凭证")
            return
            
        try:
            # 如果存在旧规则，先删除
            if self.current_rule:
                self.revoke_security_group()
            
            # 获取当前公网IP
            current_ip = self.get_public_ip()
            if not current_ip:
                return
                
            # 创建新规则
            request = AuthorizeSecurityGroupRequest()
            request.set_accept_format('json')
            
            security_group_id = self.get_selected_security_group_id()
            if not security_group_id:
                self.update_status("请选择一个安全组")
                QMessageBox.warning(self, "警告", "请选择一个安全组")
                return
                
            request.set_SecurityGroupId(security_group_id)
            request.set_IpProtocol("tcp")
            request.set_PortRange(f"{self.port_input.value()}/{self.port_input.value()}")
            request.set_SourceCidrIp(f"{current_ip}/32")
            request.set_Description("由 NetworkUpdater 添加")
            
            response = self.client.do_action_with_exception(request)
            self.current_rule = {
                'ip': current_ip,
                'port': self.port_input.value(),
                'security_group_id': security_group_id
            }
            
            success_message = f"更新成功。当前IP: {current_ip}"
            self.update_status(success_message)
            if self.tray_icon:  # 检查托盘图标是否存在
                self.tray_icon.showMessage(
                    "安全组更新器",
                    success_message,
                    QSystemTrayIcon.MessageIcon.Information,
                    2000
                )
            
        except Exception as e:
            error_message = f"更新安全组规则失败: {str(e)}"
            self.update_status(error_message)
            QMessageBox.critical(self, "错误", error_message)

    def cleanup(self):
        if self.auto_delete and self.current_rule:
            self.revoke_security_group()

    def revoke_security_group(self):
        if not self.current_rule:
            return
            
        try:
            request = RevokeSecurityGroupRequest()
            request.set_accept_format('json')
            request.set_SecurityGroupId(self.current_rule['security_group_id'])
            request.set_IpProtocol("tcp")
            request.set_PortRange(f"{self.current_rule['port']}/{self.current_rule['port']}")
            request.set_SourceCidrIp(f"{self.current_rule['ip']}/32")
            
            self.client.do_action_with_exception(request)
            self.current_rule = None
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"撤销安全组规则失败: {str(e)}")

    def get_public_ip(self):
        # IP检测接口列表，按优先级排序
        ip_apis = [
            {
                'url': 'https://myip.ipip.net/json',
                'parser': lambda r: r.json()['data']['ip']
            },
            {
                'url': 'https://myip.ipip.net/',
                'parser': lambda r: r.text.split('IP：')[1].split(' ')[0]
            },
            {
                'url': 'http://ip.3322.net',
                'parser': lambda r: r.text.strip()
            },
            {
                'url': 'https://api.ipify.org?format=json',
                'parser': lambda r: r.json()['ip']
            }
        ]

        for api in ip_apis:
            try:
                response = requests.get(api['url'], timeout=5)
                if response.status_code == 200:
                    ip = api['parser'](response)
                    if ip and self.is_valid_ip(ip):
                        return ip
            except Exception:
                continue

        QMessageBox.critical(self, "错误", "从所有可用API获取公网IP失败")
        return None

    def is_valid_ip(self, ip):
        try:
            # 简单的IP地址格式验证
            parts = ip.split('.')
            return len(parts) == 4 and all(0 <= int(part) <= 255 for part in parts)
        except (AttributeError, TypeError, ValueError):
            return False

    def show_config_dialog(self):
        dialog = ConfigDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.init_client()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = NetworkUpdater()
    window.show()
    sys.exit(app.exec())

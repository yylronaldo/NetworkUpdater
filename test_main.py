import unittest
from unittest.mock import MagicMock, patch
import json
import keyring
from PySide6.QtWidgets import QApplication
from main import NetworkUpdater, ConfigDialog

class TestNetworkUpdater(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # 创建QApplication实例
        cls.app = QApplication([])
        
    def setUp(self):
        # 每个测试用例开始前创建NetworkUpdater实例
        self.updater = NetworkUpdater()
        
    def tearDown(self):
        # 每个测试用例结束后清理
        if hasattr(self, 'updater'):
            self.updater.cleanup()
            
    def test_init(self):
        """测试初始化状态"""
        self.assertIsNone(self.updater.current_rule)
        self.assertIsNone(self.updater.client)
        self.assertTrue(self.updater.auto_delete)
        self.assertTrue(self.updater.auto_update)
        self.assertIsNotNone(self.updater.tray_icon)
        
    @patch('requests.get')
    def test_get_public_ip(self, mock_get):
        """测试获取公网IP"""
        # 模拟ipip.net的响应
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {'data': {'ip': '1.2.3.4'}}
        
        ip = self.updater.get_public_ip()
        self.assertEqual(ip, '1.2.3.4')
        
        # 测试所有API失败的情况
        mock_get.side_effect = Exception("Connection error")
        ip = self.updater.get_public_ip()
        self.assertIsNone(ip)
        
    def test_is_valid_ip(self):
        """测试IP地址验证"""
        valid_ips = [
            "192.168.1.1",
            "10.0.0.0",
            "172.16.254.1",
            "1.2.3.4"
        ]
        invalid_ips = [
            "256.1.2.3",
            "1.2.3.4.5",
            "192.168.001.1",
            "abc.def.ghi.jkl",
            ""
        ]
        
        for ip in valid_ips:
            self.assertTrue(self.updater.is_valid_ip(ip))
            
        for ip in invalid_ips:
            self.assertFalse(self.updater.is_valid_ip(ip))
            
    @patch('keyring.get_password')
    @patch('keyring.set_password')
    def test_save_load_settings(self, mock_set, mock_get):
        """测试设置的保存和加载"""
        # 模拟保存设置
        settings = {
            'auto_delete': True,
            'auto_update': False,
            'port': 8223
        }
        mock_get.return_value = json.dumps(settings)
        
        # 测试加载设置
        self.updater.load_settings()
        self.assertEqual(self.updater.auto_delete, settings['auto_delete'])
        self.assertEqual(self.updater.auto_update, settings['auto_update'])
        self.assertEqual(self.updater.port_input.value(), settings['port'])
        
        # 测试保存设置
        self.updater.save_settings()
        mock_set.assert_called_once()
        
    @patch('aliyunsdkcore.client.AcsClient')
    def test_security_group_operations(self, mock_client):
        """测试安全组操作"""
        # 模拟阿里云客户端
        mock_client_instance = MagicMock()
        mock_client.return_value = mock_client_instance
        
        # 模拟获取安全组列表
        security_groups_response = {
            'SecurityGroups': {
                'SecurityGroup': [
                    {
                        'SecurityGroupId': 'sg-1',
                        'SecurityGroupName': 'test-group'
                    }
                ]
            }
        }
        mock_client_instance.do_action_with_exception.return_value = json.dumps(security_groups_response)
        
        # 初始化客户端
        self.updater.client = mock_client_instance
        
        # 测试刷新安全组列表
        self.updater.refresh_security_groups()
        self.assertEqual(self.updater.sg_combo.count(), 1)
        
        # 测试更新安全组规则
        with patch.object(self.updater, 'get_public_ip', return_value='1.2.3.4'):
            self.updater.update_security_group()
            # 验证是否调用了阿里云API
            self.assertTrue(mock_client_instance.do_action_with_exception.called)
            
class TestConfigDialog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication([])
        
    def setUp(self):
        self.dialog = ConfigDialog()
        
    @patch('keyring.get_password')
    def test_load_credentials(self, mock_get):
        """测试凭证加载"""
        credentials = {
            'access_key': 'test_key',
            'region_id': 'cn-hangzhou'
        }
        mock_get.side_effect = [json.dumps(credentials), 'test_secret']
        
        self.dialog.load_credentials()
        
        self.assertEqual(self.dialog.key_input.text(), 'test_key')
        self.assertEqual(self.dialog.region_input.text(), 'cn-hangzhou')
        
    @patch('keyring.set_password')
    def test_save_credentials(self, mock_set):
        """测试凭证保存"""
        # 设置测试数据
        self.dialog.key_input.setText('test_key')
        self.dialog.secret_input.setText('test_secret')
        self.dialog.region_input.setText('cn-hangzhou')
        
        # 保存凭证
        self.dialog.save_credentials()
        
        # 验证是否正确调用了keyring
        self.assertEqual(mock_set.call_count, 2)

if __name__ == '__main__':
    unittest.main()

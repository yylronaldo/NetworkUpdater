# Network Updater

Network Updater 是一个Mac桌面应用程序，用于自动更新阿里云安全组规则，使本地计算机可以访问云服务器的指定端口。

## 功能特点

- 自动获取本机公网IP
- 自动更新阿里云安全组规则
- 安全存储访问凭证（使用系统密钥库）
- 定时检查IP变化（每5分钟）
- 程序退出时自动清理安全组规则

## 安装依赖

```bash
pip install -r requirements.txt
```

## 使用方法

1. 运行程序：
```bash
python main.py
```

2. 在程序界面中填写以下信息：
   - Access Key：阿里云账号的Access Key ID
   - Access Secret：阿里云账号的Access Key Secret
   - Region ID：云服务器所在的地域（默认为cn-hangzhou）
   - Security Group ID：需要修改的安全组ID
   - Port：需要开放的端口号（默认为22）

3. 点击"Save Credentials"保存凭证

4. 点击"Update Now"立即更新安全组规则，或等待程序自动更新

## 注意事项

- 请确保填写正确的阿里云访问凭证
- 程序会在退出时自动删除添加的安全组规则
- 如果本地IP发生变化，程序会自动更新安全组规则

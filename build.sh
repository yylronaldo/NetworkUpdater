#!/bin/bash

# 清理之前的构建
rm -rf build dist

# 使用 PyInstaller 构建应用
pyinstaller app.spec

echo "应用程序已构建完成，可以在 dist 目录中找到 NetworkUpdater.app"

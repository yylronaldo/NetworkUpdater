#!/bin/bash

# 安装测试依赖
pip3 install -r requirements.txt

# 运行测试
python3 -m pytest

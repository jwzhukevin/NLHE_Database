#!/bin/bash

# 生成静态文件前清理旧数据（确保每次都是全新构建）
flask commands initdb --drop
flask commands initdb
flask commands forge
flask commands admin

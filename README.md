# NLHE Database JSmol Integration Guide

## Linux Installation Steps

1. 确保您已经安装了必要的工具：
   ```bash
   sudo apt-get update
   sudo apt-get install wget unzip
   ```

2. 给setup_jsmol.sh添加执行权限：
   ```bash
   chmod +x setup_jsmol.sh
   ```

3. 运行安装脚本：
   ```bash
   ./setup_jsmol.sh
   ```

4. 验证安装：
   - 检查 `app/static/jsmol` 目录是否包含完整的JSmol文件
   - 检查 `app/static/structures` 目录是否已创建

## 目录结构

```
app/
  ├── static/
  │   ├── jsmol/        # JSmol库文件
  │   │   ├── j2s/     # Java转JavaScript文件
  │   │   ├── JSmol.js
  │   │   └── JSmol.min.js
  │   └── structures/   # 结构文件存储目录
  └── templates/
      └── detail.html   # 结构显示页面
```

## 注意事项

1. 确保web服务器对`structures`目录有读写权限
2. 建议定期备份`structures`目录中的结构文件
3. 如果JSmol显示异常，检查浏览器控制台是否有JavaScript错误
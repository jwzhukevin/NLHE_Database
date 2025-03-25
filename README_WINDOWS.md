# NLHE Database JSmol Windows Integration Guide

## Windows Installation Steps

1. 确保您已经安装了PowerShell 5.0或更高版本。

2. 在PowerShell中运行以下命令来允许执行脚本（需要管理员权限）：
   ```powershell
   Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
   ```

3. 运行安装脚本：
   ```powershell
   .\setup_jsmol.ps1
   ```

4. 验证安装：
   - 检查 `app\static\jsmol` 目录是否包含完整的JSmol文件
   - 检查 `app\static\structures` 目录是否已创建

## 目录结构

```
app\
  ├── static\
  │   ├── jsmol\        # JSmol库文件
  │   │   ├── j2s\     # Java转JavaScript文件
  │   │   ├── JSmol.js
  │   │   └── JSmol.min.js
  │   └── structures\   # 结构文件存储目录
  └── templates\
      └── detail.html   # 结构显示页面
```

## 注意事项

1. 确保IIS或其他Web服务器对`structures`目录有读写权限
2. 建议定期备份`structures`目录中的结构文件
3. 如果JSmol显示异常，检查浏览器控制台是否有JavaScript错误
4. 如果下载过程中遇到SSL/TLS错误，可能需要更新PowerShell的安全协议：
   ```powershell
   [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
   ```
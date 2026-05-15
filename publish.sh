#!/bin/bash
# PawSync_miao 发布脚本

echo "=== 推送到 GitHub ==="
git remote add origin https://github.com/xiaofeiji7/PawSync_miao.git
git branch -M main
git push -u origin main

echo ""
echo "=== 推送到 Gitee（可选）==="
echo "如果你也想推送到 Gitee，请先在 Gitee 创建仓库，然后执行："
echo "git remote add gitee https://gitee.com/cold-nine/PawSync_miao.git"
echo "git push -u gitee main"

echo ""
echo "=== 创建 Release ==="
echo "1. 访问 https://github.com/xiaofeiji7/PawSync_miao/releases/new"
echo "2. Tag version: v1.0"
echo "3. Release title: v1.0 - 初始版本"
echo "4. 上传文件: dist/PawSync_miao.exe"
echo "5. 点击 Publish release"
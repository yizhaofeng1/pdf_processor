#!/usr/bin/env bash
set -e

# ==============================================================================
# ExamSplit AI - Linux 独立发行版打包脚本
# ==============================================================================

# 寻找 pyinstaller 可执行路径
if command -v pyinstaller &> /dev/null; then
    PYINSTALLER_CMD="pyinstaller"
elif [ -x "/home/ybr/miniconda3/envs/examsplit/bin/pyinstaller" ]; then
    PYINSTALLER_CMD="/home/ybr/miniconda3/envs/examsplit/bin/pyinstaller"
elif command -v python3 &> /dev/null && python3 -m PyInstaller --version &> /dev/null; then
    PYINSTALLER_CMD="python3 -m PyInstaller"
else
    echo "ERROR: 未找到 pyinstaller！请激活包含 pyinstaller 的环境或执行 pip install pyinstaller"
    exit 1
fi

echo ">>> [1/4] 清理旧构建缓存..."
rm -rf build dist

echo ">>> [2/4] 执行 PyInstaller 编译打包 ($PYINSTALLER_CMD)..."
$PYINSTALLER_CMD ExamSplitAI.spec --clean --noconfirm

echo ">>> [3/4] 创建 Linux 双击启动脚本与 Desktop 桌面快捷方式..."
cd dist/ExamSplitAI

# 创建通用双击启动脚本 (避免终端环境或当前工作目录不对导致的问题)
cat << 'EOF' > 启动ExamSplit.sh
#!/usr/bin/env bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"
exec "./ExamSplitAI" "$@"
EOF
chmod +x 启动ExamSplit.sh ExamSplitAI

# 创建 Linux 标准 .desktop 快捷方式
cat << EOF > ExamSplitAI.desktop
[Desktop Entry]
Name=ExamSplit AI
Comment=试卷 PDF 智能拆题与选题导出系统
Exec=sh -c '"\$(dirname "%k")/启动ExamSplit.sh"'
Icon=\$(dirname "%k")/_internal/resources/icon.png
Terminal=false
Type=Application
Categories=Education;Office;
EOF
chmod +x ExamSplitAI.desktop

cd ../..

echo ">>> [4/4] 压缩打包为便携归档包 (dist/ExamSplitAI_Linux_x64.tar.gz)..."
tar -czf dist/ExamSplitAI_Linux_x64.tar.gz -C dist ExamSplitAI

echo "=============================================================================="
echo "✅ Linux 独立发行版打包成功！"
echo "📂 发行文件夹: dist/ExamSplitAI"
echo "📦 压缩分发包: dist/ExamSplitAI_Linux_x64.tar.gz"
echo "🚀 运行方式: 解压后直接双击 '启动ExamSplit.sh' 或运行 './ExamSplitAI' 即可！"
echo "=============================================================================="

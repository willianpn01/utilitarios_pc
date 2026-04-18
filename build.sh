#!/bin/bash
# ============================================================
# Script para compilar o aplicativo com Nuitka no Linux
# Gera um executável standalone com todos os recursos
# ============================================================

set -e

echo ""
echo "=== Compilando Utilitários PC com Nuitka (Linux) ==="
echo ""

# Verificar se venv existe
if [ ! -f ".venv/bin/activate" ]; then
    echo "ERRO: Virtual environment não encontrado."
    echo "Execute: python3 -m venv .venv"
    exit 1
fi

# Ativar venv
source .venv/bin/activate

# Verificar se Nuitka está instalado
if ! python -m nuitka --version > /dev/null 2>&1; then
    echo "ERRO: Nuitka não encontrado."
    echo "Execute: pip install nuitka"
    exit 1
fi

# Criar pasta dist se não existir
mkdir -p dist

echo ""
echo "Iniciando compilação (pode demorar alguns minutos)..."
echo ""

# Compilar com Nuitka
python -m nuitka \
    --standalone \
    --onefile \
    --enable-plugin=pyqt6 \
    --include-data-dir=app/assets=app/assets \
    --include-data-files=app/icone.ico=app/icone.ico \
    --include-package=app \
    --include-package=app.core \
    --include-package=app.ui \
    --include-package=app.ui.widgets \
    --output-dir=dist \
    --output-filename=UtilitariosPC \
    --remove-output \
    --assume-yes-for-downloads \
    app/main.py

if [ $? -ne 0 ]; then
    echo ""
    echo "ERRO: Falha na compilação!"
    exit 1
fi

echo ""
echo "============================================================"
echo "=== Compilação concluída com sucesso! ==="
echo "============================================================"
echo ""
echo "Executável: dist/UtilitariosPC"
echo ""

# Mostrar tamanho do arquivo
if [ -f "dist/UtilitariosPC" ]; then
    SIZE=$(stat --printf="%s" dist/UtilitariosPC 2>/dev/null || stat -f%z dist/UtilitariosPC 2>/dev/null)
    echo "Tamanho: ${SIZE} bytes"
fi

# Criar arquivo .desktop para integração com o sistema
echo ""
echo "Criando arquivo .desktop..."
DESKTOP_FILE="dist/utilitarios-pc.desktop"
EXEC_PATH="$(realpath dist/UtilitariosPC 2>/dev/null || readlink -f dist/UtilitariosPC)"
ICON_PATH="$(realpath app/icone.ico 2>/dev/null || readlink -f app/icone.ico)"

cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Type=Application
Name=Utilitários PC
Comment=Suite de utilitários para organização de arquivos e produtividade
Exec=${EXEC_PATH}
Icon=${ICON_PATH}
Terminal=false
Categories=Utility;FileTools;
StartupNotify=true
EOF

echo "Arquivo .desktop criado: ${DESKTOP_FILE}"
echo ""
echo "Para instalar o atalho no menu:"
echo "  cp ${DESKTOP_FILE} ~/.local/share/applications/"
echo ""
echo "Para instalar o autostart:"
echo "  mkdir -p ~/.config/autostart"
echo "  cp ${DESKTOP_FILE} ~/.config/autostart/"
echo ""

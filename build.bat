@echo off
REM ============================================================
REM Script para compilar o aplicativo com Nuitka
REM Gera um executável standalone com todos os recursos
REM ============================================================

echo.
echo === Compilando Utilitarios PC com Nuitka ===
echo.

REM Verificar se venv existe
if not exist ".venv\Scripts\activate.bat" (
    echo ERRO: Virtual environment nao encontrado.
    echo Execute: python -m venv .venv
    pause
    exit /b 1
)

REM Ativar venv
call .venv\Scripts\activate.bat

REM Criar pasta dist se não existir
if not exist "dist" mkdir dist

echo.
echo Iniciando compilacao (pode demorar alguns minutos)...
echo.

REM Compilar com Nuitka
REM - Metadados completos para reduzir falsos positivos de antivirus
REM - Plugin PyQt6 para incluir todos os recursos
REM - Icone embutido no executável
REM - Assets incluídos corretamente para funcionar no executável final
python -m nuitka ^
    --standalone ^
    --onefile ^
    --windows-console-mode=disable ^
    --windows-icon-from-ico=app/icone.ico ^
    --enable-plugin=pyqt6 ^
    --include-data-dir=app/assets=app/assets ^
    --include-data-files=app/icone.ico=app/icone.ico ^
    --include-package=app ^
    --include-package=app.core ^
    --include-package=app.ui ^
    --include-package=app.ui.widgets ^
    --output-dir=dist ^
    --output-filename=UtilitariosPC.exe ^
    --company-name="Projeto Utilitarios" ^
    --product-name="Utilitarios PC" ^
    --file-version=1.0.0.0 ^
    --product-version=1.0.0.0 ^
    --file-description="Suite de utilitarios para organizacao de arquivos e produtividade no Windows" ^
    --copyright="Copyright (C) 2026 Projeto Utilitarios" ^
    --trademarks="Utilitarios PC" ^
    --remove-output ^
    --assume-yes-for-downloads ^
    app/main.py

if %ERRORLEVEL% neq 0 (
    echo.
    echo ERRO: Falha na compilacao!
    pause
    exit /b 1
)

echo.
echo ============================================================
echo === Compilacao concluida com sucesso! ===
echo ============================================================
echo.
echo Executavel: dist\UtilitariosPC.exe
echo.

REM Mostrar tamanho do arquivo
for %%I in (dist\UtilitariosPC.exe) do echo Tamanho: %%~zI bytes

echo.
echo Para criar o instalador:
echo   1. Abra o Inno Setup
echo   2. Abra o arquivo installer.iss
echo   3. Clique em Build -^> Compile
echo.
pause

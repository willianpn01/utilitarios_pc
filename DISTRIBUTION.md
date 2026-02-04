# 📦 Distribuição e Instalação

## Locais de Dados do Aplicativo

O aplicativo armazena dados do usuário nos seguintes locais:

### 📂 Diretório de Dados
```
%USERPROFILE%\.utilitarios\
├── undo_history\           # Histórico de organizações (CSVs para desfazer)
├── watcher_config.json     # Configuração das pastas monitoradas
└── clipboard_history.db    # Banco de dados do histórico da área de transferência
```

**Exemplo:** `C:\Users\willi\.utilitarios\`

### ⚙️ Registro do Windows

| Chave | Descrição |
|-------|-----------|
| `HKCU\Software\Projeto Utilitarios\Utilitarios PC` | Configurações do QSettings (preferências) |
| `HKCU\Software\Microsoft\Windows\CurrentVersion\Run\UtilitariosPC` | Entrada de autostart (se habilitado) |

---

## Criar Instalador

### Opção 1: Inno Setup (Recomendado)

1. **Instale o Inno Setup**: https://jrsoftware.org/isdl.php

2. **Compile o script:**
   ```batch
   "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
   ```

3. **Resultado:** `installer\UtilitariosPC_Setup_1.0.0.exe`

### Opção 2: NSIS

Se preferir NSIS, use o script `installer.nsi` (a criar).

---

## Variável de Ambiente

O usuário pode customizar o diretório de dados definindo a variável:

```batch
set UTILITARIOS_DATA_DIR=D:\MeusDados\Utilitarios
```

---

## Desinstalação Manual

Se precisar remover manualmente:

1. **Deletar executável** (onde foi instalado)

2. **Deletar dados do usuário:**
   ```batch
   rmdir /s /q "%USERPROFILE%\.utilitarios"
   ```

3. **Remover entradas do registro:**
   ```batch
   reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v UtilitariosPC /f
   reg delete "HKCU\Software\Projeto Utilitarios" /f
   ```

---

## Build Completo

```batch
REM 1. Compilar com Nuitka
build.bat

REM 2. Criar instalador
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss

REM 3. Resultado final
REM    installer\UtilitariosPC_Setup_1.0.0.exe
```

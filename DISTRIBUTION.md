# 📦 Distribuição e Instalação

## Locais de Dados do Aplicativo

O aplicativo armazena **todos** os dados do usuário em um único diretório, independente do sistema operacional:

### 📂 Diretório de Dados (Todos os OS)
```
~/.utilitarios/
├── config/                 # Configurações do app
├── logs/
│   └── app.log             # Log com rotação automática (5MB, 2 backups)
├── undo_history/           # Histórico de organizações (CSVs para desfazer)
├── settings.json           # Preferências do usuário
├── watcher_config.json     # Configuração das pastas monitoradas
├── clipboard_history.db    # Banco de dados do histórico da área de transferência
└── app.lock                # Lock de instância única (Linux/macOS)
```

**Exemplos por OS:**
- **Windows:** `C:\Users\seu_usuario\.utilitarios\`
- **Linux:** `/home/seu_usuario/.utilitarios/`
- **macOS:** `/Users/seu_usuario/.utilitarios/`

### ⚙️ Autostart (por sistema operacional)

| OS | Mecanismo | Localização |
|---|---|---|
| **Windows** | Registro | `HKCU\Software\Microsoft\Windows\CurrentVersion\Run\UtilitariosPC` |
| **Linux** | XDG Autostart | `~/.config/autostart/utilitarios-pc.desktop` |
| **macOS** | LaunchAgent | `~/Library/LaunchAgents/com.utilitarios.pc.plist` |

### ⚙️ Registro do Windows (apenas Windows)

| Chave | Descrição |
|-------|-----------|
| `HKCU\Software\Projeto Utilitarios\Utilitarios PC` | Configurações do QSettings (preferências) |
| `HKCU\Software\Microsoft\Windows\CurrentVersion\Run\UtilitariosPC` | Entrada de autostart (se habilitado) |

---

## Build do Executável

### 🪟 Windows — `build.bat`

```batch
REM 1. Compilar com Nuitka
build.bat

REM 2. Criar instalador
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss

REM 3. Resultado final
REM    installer\UtilitariosPC_Setup_1.0.0.exe
```

### 🐧 Linux — `build.sh`

```bash
# 1. Compilar com Nuitka
./build.sh

# 2. Resultado: dist/UtilitariosPC
# 3. Arquivo .desktop gerado: dist/utilitarios-pc.desktop

# 4. Instalar atalho no menu (opcional)
cp dist/utilitarios-pc.desktop ~/.local/share/applications/

# 5. Habilitar autostart (opcional)
mkdir -p ~/.config/autostart
cp dist/utilitarios-pc.desktop ~/.config/autostart/
```

---

## Criar Instalador (Windows)

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

O usuário pode customizar o diretório de dados definindo a variável de ambiente:

```bash
# Windows
set UTILITARIOS_DATA_DIR=D:\MeusDados\Utilitarios

# Linux / macOS
export UTILITARIOS_DATA_DIR=/opt/utilitarios/data
```

---

## Desinstalação Manual

### Windows

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

### Linux

1. **Deletar executável** (onde foi instalado)

2. **Deletar dados do usuário:**
   ```bash
   rm -rf ~/.utilitarios
   ```

3. **Remover autostart:**
   ```bash
   rm -f ~/.config/autostart/utilitarios-pc.desktop
   ```

4. **Remover atalho do menu (se instalado):**
   ```bash
   rm -f ~/.local/share/applications/utilitarios-pc.desktop
   ```

### macOS

1. **Deletar executável**

2. **Deletar dados:**
   ```bash
   rm -rf ~/.utilitarios
   ```

3. **Remover autostart:**
   ```bash
   rm -f ~/Library/LaunchAgents/com.utilitarios.pc.plist
   ```

---

## Ou via Script Python

Para limpar tudo programaticamente:

```python
from app.core.app_paths import remove_all_data, print_data_locations

# Ver o que será removido
print_data_locations()

# Remover tudo (dados + autostart + registro)
results = remove_all_data()
print(results)
```

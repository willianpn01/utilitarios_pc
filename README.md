# 🛠️ Aplicativo de Utilitários para PC

Aplicação desktop **multi-plataforma** em Python com PyQt6, oferecendo 8 ferramentas essenciais para produtividade e gerenciamento de arquivos. Funciona em **Windows**, **Linux** e **macOS**.

## ✨ Funcionalidades

### 1. 📁 Criador de Estrutura de Projetos
- Crie estruturas de pastas predefinidas para diferentes tipos de projetos
- Templates inclusos: Python, Web, React, Node.js, Data Science, Mobile
- Personalize templates com arquivos iniciais (.gitignore, README, etc.)
- Exportação e importação de templates customizados

### 2. 📝 Renomeador em Massa
- Renomeie múltiplos arquivos de uma vez
- **Modos de renomeação**:
  - Criar nomes completamente novos
  - Buscar e substituir (com suporte a regex)
- **Opções**:
  - Adicionar prefixo/sufixo
  - Numeração automática sequencial
  - Redimensionar por escala percentual
  - Conversão de caixa (maiúsculas, minúsculas, título)
  - Substituir espaços por underscore
  - Mudar extensão de arquivos
  - Separador personalizável
- Prévia antes de aplicar
- Interface intuitiva e amigável

### 3. 🗂️ Organizador Automático de Arquivos
- **Organização manual**: organize arquivos por tipo/extensão sob demanda
- **Modo Watchdog (Monitoramento)**: organiza arquivos automaticamente em tempo real
  - Monitore pastas (ex: Downloads) continuamente
  - Arquivos são movidos automaticamente conforme chegam
  - Log de atividades em tempo real
- Regras customizáveis (ex: Imagens: jpg, png, gif)
- Detecção automática de conflitos de extensão
- Opções de renomeação para arquivos duplicados
- Modo recursivo (incluir subpastas)
- Log CSV de todas as operações (undo manual)
- Cancelamento responsivo durante processamento
- **System Tray**: 
  - Minimize para bandeja do sistema
  - Notificações quando arquivos são organizados
  - Opção de iniciar com o sistema operacional

### 4. 🔍 Localizador de Duplicados
- Encontre arquivos duplicados por conteúdo (hash SHA-256)
- **Estratégia em 3 etapas**: tamanho → hash rápido (64KB) → hash completo
- Filtros: tamanho mínimo, extensões específicas
- **Visualização**:
  - Tabela agrupada por duplicatas
  - Top 20 maiores itens
  - Cores para identificação rápida
- **Ações**:
  - Seleção automática "manter o mais recente"
  - Enviar para Lixeira (seguro, reversível)
  - Exportar relatório CSV
- Menu de contexto: abrir pasta no gerenciador de arquivos nativo

### 5. 💾 Analisador de Espaço em Disco
- Analise o uso de espaço em pastas
- Visualização em árvore hierárquica (ordenada por tamanho)
- Top 20 maiores arquivos e pastas
- Profundidade de análise configurável (1-10 níveis)
- **Exportação de relatório HTML**:
  - Gráfico de pizza interativo (Chart.js)
  - Top 10 com distribuição visual
  - Tabela completa Top 20
  - Design moderno e responsivo
- Abrir pasta no gerenciador de arquivos nativo via menu de contexto

### 6. 🔄 Comparador de Pastas
- Compare duas pastas e identifique diferenças
- **Modos de comparação**:
  - Por nome, tamanho e data
  - Por conteúdo (hash MD5) - mais preciso
- **Categorias**:
  - Apenas em A (laranja)
  - Apenas em B (azul)
  - Diferentes (vermelho)
  - Idênticos (verde)
- **Ações de sincronização**:
  - Copiar A → B ou B → A
  - Excluir de A ou B
  - Confirmação antes de ações destrutivas
- Filtros por categoria
- Recomparação automática após sincronização

### 7. 🖼️ Redimensionador de Imagens
- Processe imagens em lote ou individualmente
- **Modos de redimensionamento**:
  - Largura fixa (altura proporcional)
  - Altura fixa (largura proporcional)
  - Ambas dimensões (fit proporcional)
  - Escala percentual (ex: 50%)
- **Formatos suportados**:
  - Entrada: JPEG, PNG, BMP, GIF, TIFF, WebP
  - Saída: JPEG, PNG, WebP, BMP
- **Recursos**:
  - Controle de qualidade (1-100) para JPEG/WebP
  - Preservar metadados EXIF
  - Correção automática de orientação
  - Sufixo personalizável no nome
  - Estatísticas de economia de espaço
- Processamento em thread (não trava a interface)

### 8. 📋 Histórico da Área de Transferência
- Monitore e salve tudo que você copia
- **Recursos**:
  - Monitoramento contínuo (ativável)
  - Persistência com SQLite (histórico entre sessões)
  - Pesquisa em tempo real
  - Fixar itens importantes
  - Adicionar categorias para organização
  - Prevenção de duplicatas (5 segundos)
- **Ações**:
  - Clique para copiar novamente
  - Clique direito: fixar, categorizar, excluir
  - Limpar histórico (mantém fixados)
- Estatísticas: total, fixados, dias com atividade

## 🚀 Instalação e Uso

### Pré-requisitos
- Python 3.10+
- Windows 10/11, Linux ou macOS

### Instalação

1. Clone o repositório:
```bash
git clone <url-do-repositorio>
cd Utilitários
```

2. Crie e ative o ambiente virtual:
```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux / macOS
source .venv/bin/activate
```

3. Instale as dependências:
```bash
# Produção
pip install -r requirements.txt

# Desenvolvimento (inclui pytest e ruff)
pip install -r requirements-dev.txt
```

### Executar

```bash
python app/main.py
```

## 📦 Dependências

### Produção
- **PyQt6** (6.7.1): Framework de interface gráfica
- **Pillow** (10.4.0): Processamento de imagens
- **Send2Trash** (1.8.3): Exclusão segura para Lixeira
- **watchdog** (4.0.0): Monitoramento de pastas em tempo real

### Desenvolvimento
- **pytest** (8.3.2): Testes automatizados
- **ruff** (0.4+): Linter e formatador

## 📂 Estrutura do Projeto

```
Utilitários/
├── app/
│   ├── main.py                 # Ponto de entrada (cross-platform)
│   ├── core/                   # Lógica de negócio
│   │   ├── app_paths.py        # Caminhos e helpers de plataforma
│   │   ├── app_settings.py     # Persistência de configurações
│   │   ├── autostart.py        # Autostart (Windows/Linux/macOS)
│   │   ├── project_templates.py
│   │   ├── batch_renamer.py
│   │   ├── auto_organizer.py
│   │   ├── folder_watcher.py
│   │   ├── watcher_config.py
│   │   ├── duplicates.py
│   │   ├── space_analyzer.py
│   │   ├── folder_compare.py
│   │   ├── image_resizer.py
│   │   ├── clipboard_history.py
│   │   ├── system_tray.py
│   │   └── logger.py
│   ├── ui/                     # Interface gráfica
│   │   ├── main_window.py
│   │   ├── custom_dialog.py
│   │   └── widgets/            # Widgets de cada funcionalidade
│   └── assets/
│       ├── styles/             # Temas QSS
│       └── icons/              # Ícones SVG
├── tests/                      # 77 testes automatizados
├── .github/workflows/ci.yml    # CI (Ubuntu + Windows)
├── build.bat                   # Build Windows (Nuitka)
├── build.sh                    # Build Linux (Nuitka)
├── requirements.txt            # Dependências de produção
├── requirements-dev.txt        # Dependências de desenvolvimento
└── README.md
```

## 🧪 Testes

Execute os testes automatizados:

```bash
pytest tests/ -v
```

Cobertura de testes (77 testes):
- **app_paths**: Helpers de plataforma, resolução de caminhos, variáveis de ambiente
- **auto_organizer**: Parse de regras, detecção de conflitos, plano de organização
- **batch_renamer**: Regras de renomeação, preview, aplicação, rollback
- **duplicates**: Hash de arquivos, detecção por conteúdo, filtros
- **folder_compare**: Varredura, comparação por tamanho e conteúdo
- **clipboard_history**: CRUD no SQLite, pin/unpin, busca, deduplicação

## 🌐 Compatibilidade Multi-Sistema

| Funcionalidade | Windows | Linux | macOS |
|---|:---:|:---:|:---:|
| Interface gráfica (PyQt6) | ✅ | ✅ | ✅ |
| Instância única | ✅ Mutex | ✅ flock | ✅ flock |
| Autostart | ✅ Registro | ✅ XDG .desktop | ✅ LaunchAgent |
| System Tray | ✅ | ✅ | ✅ |
| Abrir no gerenciador de arquivos | ✅ Explorer | ✅ xdg-open | ✅ Finder |
| Monitoramento (Watchdog) | ✅ | ✅ | ✅ |
| Organização de arquivos | ✅ | ✅ | ✅ |
| Clipboard history (SQLite) | ✅ | ✅ | ✅ |
| Build (Nuitka) | ✅ build.bat | ✅ build.sh | ✅ build.sh |

## 🎨 Personalização

### Temas
Os estilos são definidos em `app/assets/styles/theme.qss` usando Qt Style Sheets (QSS).

### Adicionar Templates de Projeto
Edite `app/core/project_templates.py` para adicionar novos templates predefinidos.

## 🔒 Segurança e Privacidade

- **Dados locais**: tudo armazenado em `~/.utilitarios/`
- **Exclusão de arquivos**: usa Send2Trash (reversível via Lixeira)
- **Sem telemetria**: nenhum dado é enviado para servidores externos

## 🤝 Contribuindo

Contribuições são bem-vindas! Sinta-se à vontade para:
- Reportar bugs
- Sugerir novas funcionalidades
- Enviar pull requests

## 📝 Licença

Este projeto é de código aberto. Consulte o arquivo LICENSE para mais detalhes.

## 🙏 Agradecimentos

- PyQt6 pela excelente framework de UI
- Pillow pela biblioteca de processamento de imagens
- Chart.js pelos gráficos interativos (relatórios HTML)

---

**Desenvolvido com ❤️ usando Python e PyQt6 — Funciona em Windows, Linux e macOS**

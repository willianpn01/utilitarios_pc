import os
import re

WIDGETS_DIR = r"c:\Projetos\Utilitários\app\ui\widgets"

def process_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    new_content = content

    # 1. Substituir QMessageBox.warning/information/critical -> CustomDialog.warning/information/critical
    new_content = re.sub(r'QMessageBox\.(warning|information|critical)', r'CustomDialog.\1', new_content)

    # 2. QMessageBox.question -> Isso é complexo pois tem linhas multiplas passadas.
    # O CustomDialog.question retorna bool. O QMessageBox retorna um Enum.
    # Pattern: 
    # resp = QMessageBox.question( ... )
    # if resp == QMessageBox.StandardButton.Yes:
    # 
    # Vamos trocar as incocações manualmente ou via Regex pesado.
    
    # regex pra remover o ", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No"
    # match de "QMessageBox.question(" até a proxima abertura/fechamento
    # Para simplificar: Replace de "QMessageBox.question" por "CustomDialog.question"
    new_content = new_content.replace('QMessageBox.question', 'CustomDialog.question')
    new_content = re.sub(r',\s*QMessageBox\.StandardButton\.Yes\s*\|\s*QMessageBox\.StandardButton\.No', '', new_content)
    
    # 3. Replaces de check do resp
    new_content = new_content.replace('resp == QMessageBox.StandardButton.Yes', 'resp')
    new_content = new_content.replace('resp != QMessageBox.StandardButton.Yes', 'not resp')

    # 4. Import replacement
    if 'QMessageBox' in content:
        # Remover QMessageBox,
        new_content = re.sub(r'QMessageBox,\s*', '', new_content)
        new_content = re.sub(r',\s*QMessageBox\b', '', new_content)
        new_content = re.sub(r'\bQMessageBox\b', '', new_content)
        
        # Inserir o novo import antes/depois dos de pyqt
        import_stmt = "from app.ui.custom_dialog import CustomDialog\n"
        if 'CustomDialog' not in new_content:
            new_content = re.sub(r'(from PyQt6.QtWidgets import[^\)]+\))', r'\1\n' + import_stmt, new_content, count=1)
            # se não achou com parenteses, tenta sem:
            if 'CustomDialog' not in new_content:
                new_content = re.sub(r'(from PyQt6.QtWidgets import[^\n]+)', r'\1\n' + import_stmt, new_content, count=1)

    if new_content != content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Update: {filepath}")


for filename in os.listdir(WIDGETS_DIR):
    if filename.endswith(".py"):
        process_file(os.path.join(WIDGETS_DIR, filename))

process_file(r"c:\Projetos\Utilitários\app\main.py")
print("Done")

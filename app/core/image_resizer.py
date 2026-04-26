from __future__ import annotations
import os
from dataclasses import dataclass
from typing import List, Optional, Tuple
from PIL import Image, ImageOps

from app.core.logger import get_logger

_log = get_logger("image_resizer")


@dataclass
class ResizeOptions:
    """Opções de redimensionamento"""
    # Modo de redimensionamento
    mode: str = 'width'  # 'width', 'height', 'both', 'scale'
    
    # Dimensões
    width: Optional[int] = None
    height: Optional[int] = None
    scale_percent: Optional[float] = None  # ex: 50.0 para 50%
    
    # Formato de saída
    output_format: str = 'JPEG'  # 'JPEG', 'PNG', 'WEBP', 'BMP'
    quality: int = 85  # 1-100 para JPEG/WEBP
    
    # Manter proporção
    maintain_aspect: bool = True
    
    # Preservar EXIF
    preserve_exif: bool = True


@dataclass
class ProcessResult:
    """Resultado do processamento de uma imagem"""
    src_path: str
    dst_path: str
    success: bool
    error_msg: str = ''
    original_size: Tuple[int, int] = (0, 0)
    new_size: Tuple[int, int] = (0, 0)
    original_file_size: int = 0
    new_file_size: int = 0


SUPPORTED_INPUT_FORMATS = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.webp'}


def get_image_files(directory: str, recursive: bool = False) -> List[str]:
    """Retorna lista de arquivos de imagem em um diretório"""
    image_files: List[str] = []
    
    if recursive:
        for root, _dirs, files in os.walk(directory):
            for file in files:
                if os.path.splitext(file)[1].lower() in SUPPORTED_INPUT_FORMATS:
                    image_files.append(os.path.join(root, file))
    else:
        try:
            for file in os.listdir(directory):
                full_path = os.path.join(directory, file)
                if os.path.isfile(full_path) and os.path.splitext(file)[1].lower() in SUPPORTED_INPUT_FORMATS:
                    image_files.append(full_path)
        except OSError:
            pass
    
    return sorted(image_files)


def calculate_dimensions(
    original_width: int,
    original_height: int,
    options: ResizeOptions
) -> Tuple[int, int]:
    """Calcula as dimensões finais baseado nas opções"""
    
    if options.mode == 'scale' and options.scale_percent:
        # Redimensionar por escala percentual
        factor = options.scale_percent / 100.0
        new_width = int(original_width * factor)
        new_height = int(original_height * factor)
        return (new_width, new_height)
    
    elif options.mode == 'width' and options.width:
        # Definir largura, calcular altura proporcionalmente
        new_width = options.width
        if options.maintain_aspect:
            ratio = original_height / original_width
            new_height = int(new_width * ratio)
        else:
            new_height = original_height
        return (new_width, new_height)
    
    elif options.mode == 'height' and options.height:
        # Definir altura, calcular largura proporcionalmente
        new_height = options.height
        if options.maintain_aspect:
            ratio = original_width / original_height
            new_width = int(new_height * ratio)
        else:
            new_width = original_width
        return (new_width, new_height)
    
    elif options.mode == 'both' and options.width and options.height:
        # Definir ambas dimensões
        if options.maintain_aspect:
            # Fit dentro das dimensões mantendo proporção
            ratio = min(options.width / original_width, options.height / original_height)
            new_width = int(original_width * ratio)
            new_height = int(original_height * ratio)
            return (new_width, new_height)
        else:
            return (options.width, options.height)
    
    # Fallback: manter dimensões originais
    return (original_width, original_height)


def resize_image(
    src_path: str,
    dst_path: str,
    options: ResizeOptions
) -> ProcessResult:
    """
    Redimensiona uma imagem e salva no destino.
    Retorna ProcessResult com informações do processamento.
    """
    try:
        # Obter tamanho original do arquivo
        original_file_size = os.path.getsize(src_path)
        
        # Abrir imagem
        with Image.open(src_path) as img:
            # Corrigir orientação baseado em EXIF
            img = ImageOps.exif_transpose(img)
            
            original_size = img.size
            
            # Calcular novas dimensões
            new_size = calculate_dimensions(img.width, img.height, options)
            
            # Redimensionar
            if new_size != original_size:
                # Usar LANCZOS para melhor qualidade
                resized_img = img.resize(new_size, Image.Resampling.LANCZOS)
            else:
                resized_img = img
            
            # Preparar para salvar
            save_kwargs = {}
            
            # Converter para RGB se necessário (para JPEG)
            if options.output_format.upper() in ['JPEG', 'JPG']:
                if resized_img.mode in ('RGBA', 'LA', 'P'):
                    # Criar fundo branco para transparência
                    background = Image.new('RGB', resized_img.size, (255, 255, 255))
                    if resized_img.mode == 'P':
                        resized_img = resized_img.convert('RGBA')
                    background.paste(resized_img, mask=resized_img.split()[-1] if resized_img.mode == 'RGBA' else None)
                    resized_img = background
                elif resized_img.mode != 'RGB':
                    resized_img = resized_img.convert('RGB')
                
                save_kwargs['quality'] = options.quality
                save_kwargs['optimize'] = True
            
            elif options.output_format.upper() == 'WEBP':
                save_kwargs['quality'] = options.quality
                save_kwargs['method'] = 6  # melhor compressão
            
            elif options.output_format.upper() == 'PNG':
                save_kwargs['optimize'] = True
            
            # Preservar EXIF se solicitado
            if options.preserve_exif and hasattr(img, 'info'):
                exif = img.info.get('exif')
                if exif:
                    save_kwargs['exif'] = exif
            
            # Criar diretório de destino se não existir
            os.makedirs(os.path.dirname(dst_path), exist_ok=True)
            
            # Salvar
            resized_img.save(dst_path, format=options.output_format.upper(), **save_kwargs)
            
            # Obter tamanho do arquivo de saída
            new_file_size = os.path.getsize(dst_path)
            
            return ProcessResult(
                src_path=src_path,
                dst_path=dst_path,
                success=True,
                original_size=original_size,
                new_size=new_size,
                original_file_size=original_file_size,
                new_file_size=new_file_size
            )
    
    except Exception as e:
        _log.exception("Falha ao processar imagem %s -> %s", src_path, dst_path)
        return ProcessResult(
            src_path=src_path,
            dst_path=dst_path,
            success=False,
            error_msg=str(e)
        )


def batch_resize(
    src_dir: str,
    dst_dir: str,
    options: ResizeOptions,
    recursive: bool = False,
    name_suffix: str = ''
) -> List[ProcessResult]:
    """
    Processa todas as imagens de um diretório em lote.
    
    Args:
        src_dir: diretório de origem
        dst_dir: diretório de destino
        options: opções de redimensionamento
        recursive: processar subpastas
        name_suffix: sufixo para adicionar ao nome do arquivo (ex: '_resized')
    """
    image_files = get_image_files(src_dir, recursive)
    results: List[ProcessResult] = []
    
    for src_path in image_files:
        # Calcular caminho de destino
        rel_path = os.path.relpath(src_path, src_dir)
        name, _ext = os.path.splitext(rel_path)
        
        # Adicionar sufixo se fornecido
        if name_suffix:
            name = name + name_suffix
        
        # Nova extensão baseada no formato de saída
        ext_map = {
            'JPEG': '.jpg',
            'PNG': '.png',
            'WEBP': '.webp',
            'BMP': '.bmp'
        }
        new_ext = ext_map.get(options.output_format.upper(), '.jpg')
        
        dst_path = os.path.join(dst_dir, name + new_ext)
        
        # Processar imagem
        result = resize_image(src_path, dst_path, options)
        results.append(result)
    
    return results

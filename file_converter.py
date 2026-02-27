import os
import subprocess
import tempfile
import logging
from PIL import Image
import pysubs2

logger = logging.getLogger(__name__)

class FileConverter:
    def __init__(self):
        self.temp_dir = tempfile.mkdtemp()

    def convert(self, input_path, target_format):
        """
        Конвертирует файл в указанный формат.
        Возвращает путь к сконвертированному файлу.
        """
        input_ext = os.path.splitext(input_path)[1].lower().lstrip('.')
        output_filename = os.path.basename(input_path).rsplit('.', 1)[0] + '.' + target_format
        output_path = os.path.join(self.temp_dir, output_filename)

        # Определяем категорию по расширению
        if input_ext in ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff', 'webp']:
            return self._convert_image(input_path, output_path, target_format)
        elif input_ext in ['mp3', 'wav', 'flac', 'aac', 'ogg', 'm4a']:
            return self._convert_audio(input_path, output_path, target_format)
        elif input_ext in ['mp4', 'avi', 'mkv', 'mov', 'wmv', 'flv', 'webm']:
            return self._convert_video(input_path, output_path, target_format)
        elif input_ext in ['doc', 'docx', 'odt', 'rtf', 'txt', 'pdf', 'xls', 'xlsx', 'ppt', 'pptx']:
            return self._convert_document(input_path, output_path, target_format)
        elif input_ext in ['srt', 'vtt', 'ass', 'ssa']:
            return self._convert_subtitle(input_path, output_path, target_format)
        else:
            raise ValueError(f"Unsupported input format: {input_ext}")

    def _convert_image(self, input_path, output_path, target_format):
        img = Image.open(input_path)
        img.save(output_path, format=target_format.upper())
        return output_path

    def _convert_audio(self, input_path, output_path, target_format):
        # ffmpeg -i input.mp3 output.wav
        cmd = ['ffmpeg', '-i', input_path, output_path]
        subprocess.run(cmd, check=True, capture_output=True)
        return output_path

    def _convert_video(self, input_path, output_path, target_format):
        cmd = ['ffmpeg', '-i', input_path, output_path]
        subprocess.run(cmd, check=True, capture_output=True)
        return output_path

    def _convert_document(self, input_path, output_path, target_format):
        # Используем unoconv или libreoffice
        # unoconv -f pdf input.docx
        cmd = ['unoconv', '-f', target_format, '-o', output_path, input_path]
        subprocess.run(cmd, check=True, capture_output=True)
        # unoconv создаст файл с именем как input, но с новым расширением, поэтому переименуем
        expected = os.path.splitext(input_path)[0] + '.' + target_format
        if os.path.exists(expected) and expected != output_path:
            os.rename(expected, output_path)
        return output_path

    def _convert_subtitle(self, input_path, output_path, target_format):
        subs = pysubs2.load(input_path)
        subs.save(output_path)
        return output_path

    def cleanup(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

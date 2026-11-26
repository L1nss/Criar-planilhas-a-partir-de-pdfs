from __future__ import annotations

import io
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

import pdfplumber


class ErroLeituraPDF(RuntimeError):
    pass


class OCRIndisponivel(ErroLeituraPDF):
    pass


@dataclass(slots=True)
class ResultadoLeitura:
    texto: str
    paginas: int
    metodo: str
    avisos: list[str] = field(default_factory=list)
    xmls_embutidos: list[str] = field(default_factory=list)


class LeitorPDF:
    def __init__(self, ocr: str = "auto", dpi: int = 300, idioma: str = "por+eng") -> None:
        if ocr not in {"auto", "sempre", "nunca"}:
            raise ValueError("ocr deve ser 'auto', 'sempre' ou 'nunca'.")
        self.ocr = ocr
        self.dpi = dpi
        self.idioma = idioma
        self.executavel_tesseract = shutil.which("tesseract")

    @staticmethod
    def _texto_util(texto: str) -> bool:
        alfanumericos = sum(caractere.isalnum() for caractere in texto)
        palavras = len(texto.split())
        return alfanumericos >= 80 and palavras >= 15

    def _ocr_pagina(self, pagina: pdfplumber.page.Page, numero: int) -> str:
        if not self.executavel_tesseract:
            raise OCRIndisponivel(
                "A página parece ser uma imagem, mas o Tesseract OCR não está instalado. "
                "Instale o pacote 'tesseract-ocr' e o idioma português para processá-la."
            )

        imagem = pagina.to_image(resolution=self.dpi, antialias=True).original
        with tempfile.TemporaryDirectory(prefix="nota_ocr_") as pasta:
            caminho_imagem = Path(pasta) / f"pagina_{numero}.png"
            imagem.save(caminho_imagem, format="PNG")
            comando = [
                self.executavel_tesseract,
                str(caminho_imagem),
                "stdout",
                "-l",
                self.idioma,
                "--oem",
                "1",
                "--psm",
                "6",
                "-c",
                "preserve_interword_spaces=1",
            ]
            processo = subprocess.run(comando, capture_output=True, text=True, check=False)
            if processo.returncode != 0:
                mensagem = processo.stderr.strip() or "falha desconhecida do Tesseract"
                raise ErroLeituraPDF(f"OCR falhou na página {numero}: {mensagem}")
            return processo.stdout.strip()

    @staticmethod
    def _xmls_embutidos(caminho: Path) -> list[str]:
        """Lê XML fiscal anexado ao PDF quando pypdf estiver disponível."""
        try:
            from pypdf import PdfReader
        except ImportError:
            return []

        xmls: list[str] = []
        try:
            leitor = PdfReader(str(caminho))
            anexos = getattr(leitor, "attachments", {}) or {}
            for nome, conteudos in anexos.items():
                if not nome.lower().endswith(".xml"):
                    continue
                if not isinstance(conteudos, list):
                    conteudos = [conteudos]
                for conteudo in conteudos:
                    if isinstance(conteudo, bytes):
                        xmls.append(conteudo.decode("utf-8", errors="replace"))
        except Exception:
            return []
        return xmls

    def ler(self, caminho_pdf: str | Path) -> ResultadoLeitura:
        caminho = Path(caminho_pdf)
        textos: list[str] = []
        paginas_ocr = 0
        avisos: list[str] = []

        try:
            with pdfplumber.open(caminho) as pdf:
                total_paginas = len(pdf.pages)
                for numero, pagina in enumerate(pdf.pages, start=1):
                    texto_nativo = pagina.extract_text(x_tolerance=2, y_tolerance=3) or ""
                    precisa_ocr = self.ocr == "sempre" or (
                        self.ocr == "auto" and not self._texto_util(texto_nativo)
                    )
                    if precisa_ocr:
                        try:
                            texto_ocr = self._ocr_pagina(pagina, numero)
                            if texto_ocr:
                                textos.append(texto_ocr)
                                paginas_ocr += 1
                            else:
                                textos.append(texto_nativo)
                                avisos.append(f"OCR não reconheceu conteúdo na página {numero}.")
                        except OCRIndisponivel:
                            if self._texto_util(texto_nativo):
                                textos.append(texto_nativo)
                                avisos.append(f"OCR indisponível; usado texto nativo na página {numero}.")
                            else:
                                raise
                    else:
                        textos.append(texto_nativo)
        except OCRIndisponivel:
            raise
        except Exception as erro:
            raise ErroLeituraPDF(f"Não foi possível ler '{caminho.name}': {erro}") from erro

        texto = "\n".join(textos).strip()
        if not texto:
            raise ErroLeituraPDF(f"Nenhum texto foi extraído de '{caminho.name}'.")

        if paginas_ocr == 0:
            metodo = "Texto nativo"
        elif paginas_ocr == total_paginas:
            metodo = "OCR"
        else:
            metodo = "Texto nativo + OCR"

        return ResultadoLeitura(
            texto=texto,
            paginas=total_paginas,
            metodo=metodo,
            avisos=avisos,
            xmls_embutidos=self._xmls_embutidos(caminho),
        )


def xml_valido(conteudo: str) -> bool:
    try:
        ET.fromstring(conteudo)
        return True
    except ET.ParseError:
        return False

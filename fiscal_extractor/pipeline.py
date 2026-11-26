from __future__ import annotations

from pathlib import Path
from typing import Callable

from .excel_writer import criar_excel
from .parser import analisar_documento
from .pdf_reader import LeitorPDF


def listar_pdfs(pasta: str | Path, recursivo: bool = True) -> list[Path]:
    raiz = Path(pasta).expanduser().resolve()
    if not raiz.is_dir():
        raise NotADirectoryError(f"Pasta não encontrada: {raiz}")
    padrao = "**/*.pdf" if recursivo else "*.pdf"
    return sorted((p for p in raiz.glob(padrao) if p.is_file()), key=lambda p: str(p).casefold())


def processar_pasta(
    pasta: str | Path,
    caminho_excel: str | Path,
    *,
    ocr: str = "auto",
    recursivo: bool = True,
    progresso: Callable[[int, int, str], None] | None = None,
) -> tuple[list, list[dict[str, str]], Path]:
    arquivos = listar_pdfs(pasta, recursivo=recursivo)
    if not arquivos:
        raise FileNotFoundError("Nenhum PDF foi encontrado na pasta selecionada.")

    leitor = LeitorPDF(ocr=ocr)
    notas = []
    erros: list[dict[str, str]] = []
    total = len(arquivos)
    for indice, caminho in enumerate(arquivos, start=1):
        if progresso:
            progresso(indice, total, caminho.name)
        try:
            leitura = leitor.ler(caminho)
            notas.append(analisar_documento(caminho, leitura))
        except Exception as erro:
            erros.append({"arquivo": caminho.name, "caminho": str(caminho), "erro": str(erro)})

    # Identifica duplicidades sem eliminar documentos.
    vistos: dict[str, str] = {}
    for nota in notas:
        identidade = nota.chave_acesso or "|".join(
            str(valor or "") for valor in (nota.emitente_cnpj_cpf, nota.numero, nota.serie, nota.valor_total)
        )
        if identidade.strip("|") and identidade in vistos:
            nota.observacoes.append(f"Possível duplicidade de '{vistos[identidade]}'.")
            nota.status = "Revisar"
        else:
            vistos[identidade] = nota.arquivo

    saida = criar_excel(notas, erros, caminho_excel)
    return notas, erros, saida

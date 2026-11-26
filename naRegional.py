from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from fiscal_extractor import processar_pasta


ARQUIVO_CONFIGURACAO = Path(__file__).with_name("configuracao.json")


def _selecionar_com_interface() -> tuple[Path, Path]:
    import tkinter as tk
    from tkinter import filedialog

    janela = tk.Tk()
    janela.withdraw()
    pasta = filedialog.askdirectory(title="Selecione a pasta com os PDFs de notas fiscais")
    if not pasta:
        janela.destroy()
        raise RuntimeError("Nenhuma pasta foi selecionada.")
    saida = filedialog.asksaveasfilename(
        title="Salvar planilha de notas fiscais",
        initialdir=pasta,
        initialfile="controle_notas.xlsx",
        defaultextension=".xlsx",
        filetypes=[("Planilha Excel", "*.xlsx")],
    )
    janela.destroy()
    if not saida:
        raise RuntimeError("Nenhum local de saída foi selecionado.")
    return Path(pasta), Path(saida)


def _salvar_configuracao(
    pasta: Path,
    saida: Path,
    caminho: Path = ARQUIVO_CONFIGURACAO,
) -> None:
    dados = {
        "pasta_pdfs": str(pasta.expanduser().resolve()),
        "arquivo_excel": str(saida.expanduser().resolve()),
    }
    caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")


def _carregar_configuracao(caminho: Path = ARQUIVO_CONFIGURACAO) -> tuple[Path, Path]:
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    pasta = Path(dados["pasta_pdfs"]).expanduser()
    saida = Path(dados["arquivo_excel"]).expanduser()
    if not pasta.is_dir():
        raise NotADirectoryError(f"A pasta configurada não existe mais: {pasta}")
    return pasta, saida


def _argumentos() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extrai dados de NF-e, NFC-e, NFS-e e outros documentos fiscais em PDF para Excel."
    )
    parser.add_argument("pasta", nargs="?", help="Pasta com os PDFs. Sem este argumento, abre a interface gráfica.")
    parser.add_argument("-o", "--saida", help="Caminho do arquivo .xlsx de saída.")
    parser.add_argument("--ocr", choices=["auto", "sempre", "nunca"], default="auto", help="Política de OCR por página.")
    parser.add_argument("--nao-recursivo", action="store_true", help="Não procurar PDFs dentro de subpastas.")
    parser.add_argument(
        "--configurar",
        action="store_true",
        help="Escolhe e salva novamente a pasta dos PDFs e o local da planilha.",
    )
    return parser.parse_args()


def main() -> int:
    args = _argumentos()
    try:
        if args.pasta:
            pasta = Path(args.pasta).expanduser()
            saida = Path(args.saida).expanduser() if args.saida else pasta / "controle_notas.xlsx"
        else:
            if args.configurar or not ARQUIVO_CONFIGURACAO.exists():
                print("Configuração: selecione a pasta dos PDFs e onde guardar a planilha.")
                pasta, saida = _selecionar_com_interface()
                _salvar_configuracao(pasta, saida)
                print(f"Configuração salva em: {ARQUIVO_CONFIGURACAO}")
            else:
                try:
                    pasta, saida = _carregar_configuracao()
                except (OSError, KeyError, ValueError, json.JSONDecodeError) as erro:
                    print(f"A configuração anterior não pôde ser usada: {erro}")
                    pasta, saida = _selecionar_com_interface()
                    _salvar_configuracao(pasta, saida)
            print(f"Pasta configurada para os PDFs: {pasta}")
            print(f"Planilha configurada: {saida}")

        def progresso(atual: int, total: int, nome: str) -> None:
            print(f"[{atual}/{total}] Processando {nome}")

        notas, erros, arquivo = processar_pasta(
            pasta,
            saida,
            ocr=args.ocr,
            recursivo=not args.nao_recursivo,
            progresso=progresso,
        )
        ok = sum(nota.status == "OK" for nota in notas)
        print(f"\nConcluído: {len(notas)} documento(s), {ok} OK, {len(notas) - ok} para revisar, {len(erros)} erro(s).")
        print(f"Planilha: {arquivo}")
        return 0 if not erros else 2
    except Exception as erro:
        print(f"Erro: {erro}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

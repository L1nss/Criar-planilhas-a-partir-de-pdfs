from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Iterable

from openpyxl import Workbook
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.table import Table, TableStyleInfo
from openpyxl.utils import get_column_letter

from .models import NotaFiscal


AZUL = "17365D"
BRANCO = "FFFFFF"
AMARELO = "FFF2CC"
VERMELHO = "F4CCCC"
BORDA = Side(style="thin", color="D9E1F2")


# Colunas vazias são campos de controle preenchidos pelo usuário no trabalho.
# As demais são preenchidas automaticamente a partir do PDF.
COLUNAS: list[tuple[str, Callable[[NotaFiscal], Any] | None]] = [
    ("Tipo de nota", lambda n: n.tipo_documento),
    ("Data de emissão", lambda n: n.data_emissao),
    ("Competência", lambda n: n.data_competencia),
    ("Fornecedor / Prestador", lambda n: n.emitente_nome),
    ("CNPJ / CPF", lambda n: n.emitente_cnpj_cpf),
    ("Número da nota", lambda n: n.numero),
    ("Série", lambda n: n.serie),
    ("Chave de acesso", lambda n: n.chave_acesso),
    ("Descrição / Objeto", lambda n: n.descricao_servico or _descricao_itens(n)),
    ("Valor dos produtos", lambda n: n.valor_produtos),
    ("Valor dos serviços", lambda n: n.valor_servicos),
    ("Desconto", lambda n: n.desconto),
    ("Retenções", lambda n: n.total_retencoes),
    ("Valor líquido", lambda n: n.valor_liquido),
    ("Valor total", lambda n: n.valor_total),
    ("Responsável", None),
    ("Observação", lambda n: _observacao(n)),
    ("Arquivo PDF", lambda n: n.arquivo),
]

COLUNAS_MANUAIS = {nome for nome, extrator in COLUNAS if extrator is None}
COLUNAS_MOEDA = {
    "Valor dos produtos",
    "Valor dos serviços",
    "Desconto",
    "Retenções",
    "Valor líquido",
    "Valor total",
}
COLUNAS_DATA = {
    "Data de emissão",
    "Competência",
}
COLUNAS_TEXTO = {"CNPJ / CPF", "Número da nota", "Série", "Chave de acesso"}


def _descricao_itens(nota: NotaFiscal) -> str | None:
    descricoes = [item.descricao for item in nota.itens if item.descricao]
    return " | ".join(descricoes) if descricoes else None


def _observacao(nota: NotaFiscal) -> str | None:
    observacoes = list(dict.fromkeys(nota.observacoes))
    if nota.status != "OK":
        observacoes.insert(0, f"Conferir extração ({nota.confianca}% de confiança)")
    return " | ".join(observacoes) or None


def _valor_excel(valor: Any) -> Any:
    return float(valor) if isinstance(valor, Decimal) else valor


def _ajustar_larguras(planilha) -> None:
    larguras = {
        "Tipo de nota": 15,
        "Data de emissão": 16,
        "Competência": 15,
        "Fornecedor / Prestador": 38,
        "CNPJ / CPF": 20,
        "Número da nota": 18,
        "Série": 10,
        "Chave de acesso": 48,
        "Descrição / Objeto": 55,
        "Responsável": 22,
        "Observação": 55,
        "Arquivo PDF": 42,
    }
    for coluna in range(1, planilha.max_column + 1):
        titulo = planilha.cell(1, coluna).value
        planilha.column_dimensions[get_column_letter(coluna)].width = larguras.get(titulo, 18)


def criar_excel(
    notas: Iterable[NotaFiscal],
    erros: list[dict[str, str]],
    caminho_saida: str | Path,
) -> Path:
    """Cria somente a planilha operacional de controle e lançamento."""
    notas = list(notas)
    destino = Path(caminho_saida)
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporario = destino.with_suffix(destino.suffix + ".tmp")

    wb = Workbook()
    ws = wb.active
    ws.title = "Controle de Notas"
    ws.sheet_view.showGridLines = False
    ws.freeze_panes = "D2"

    ws.append([nome for nome, _ in COLUNAS])
    for nota in notas:
        ws.append([
            _valor_excel(extrator(nota)) if extrator is not None else None
            for _, extrator in COLUNAS
        ])

    indice_observacao = next(i for i, (nome, _) in enumerate(COLUNAS, start=1) if nome == "Observação")
    indice_arquivo = next(i for i, (nome, _) in enumerate(COLUNAS, start=1) if nome == "Arquivo PDF")
    for erro in erros:
        linha = [None] * len(COLUNAS)
        linha[indice_observacao - 1] = f"ERRO DE LEITURA: {erro.get('erro', 'erro não informado')}"
        linha[indice_arquivo - 1] = erro.get("arquivo")
        ws.append(linha)

    for celula in ws[1]:
        celula.fill = PatternFill("solid", fgColor=AZUL)
        celula.font = Font(name="Arial", size=10, bold=True, color=BRANCO)
        celula.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        celula.border = Border(left=BORDA, right=BORDA, top=BORDA, bottom=BORDA)
    ws.row_dimensions[1].height = 32

    mapa = {ws.cell(1, coluna).value: coluna for coluna in range(1, ws.max_column + 1)}
    for linha in range(2, ws.max_row + 1):
        ws.row_dimensions[linha].height = 30
        for coluna in range(1, ws.max_column + 1):
            celula = ws.cell(linha, coluna)
            titulo = ws.cell(1, coluna).value
            celula.font = Font(name="Arial", size=10, color="222222")
            celula.alignment = Alignment(vertical="top", wrap_text=titulo in {"Descrição / Objeto", "Observação"})
            celula.border = Border(left=BORDA, right=BORDA, top=BORDA, bottom=BORDA)
            if titulo in COLUNAS_MANUAIS:
                celula.fill = PatternFill("solid", fgColor=AMARELO)
            if titulo in COLUNAS_MOEDA:
                celula.number_format = 'R$ #,##0.00'
            elif titulo in COLUNAS_DATA:
                celula.number_format = "dd/mm/yyyy"
            elif titulo in COLUNAS_TEXTO:
                celula.number_format = "@"

    if ws.max_row >= 2:
        referencia = f"A1:{get_column_letter(ws.max_column)}{ws.max_row}"
        tabela = Table(displayName="ControleNotas", ref=referencia)
        tabela.tableStyleInfo = TableStyleInfo(
            name="TableStyleMedium2",
            showFirstColumn=False,
            showLastColumn=False,
            showRowStripes=True,
            showColumnStripes=False,
        )
        ws.add_table(tabela)

        coluna_observacao = get_column_letter(mapa["Observação"])
        ws.conditional_formatting.add(
            f"{coluna_observacao}2:{coluna_observacao}{ws.max_row}",
            FormulaRule(
                formula=[f'ISNUMBER(SEARCH("ERRO",{coluna_observacao}2))'],
                fill=PatternFill("solid", fgColor=VERMELHO),
            ),
        )

    _ajustar_larguras(ws)
    ws.auto_filter.ref = ws.dimensions
    wb.properties.title = "Controle e lançamento de notas fiscais"
    wb.properties.subject = "Dados extraídos de PDFs para controle administrativo"
    wb.save(temporario)
    temporario.replace(destino)
    return destino

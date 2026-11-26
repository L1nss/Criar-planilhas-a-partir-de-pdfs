from __future__ import annotations

from dataclasses import asdict, dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class ItemFiscal:
    arquivo: str
    numero_item: int
    codigo: str | None = None
    descricao: str | None = None
    ncm: str | None = None
    cest: str | None = None
    cst_csosn: str | None = None
    cfop: str | None = None
    unidade: str | None = None
    quantidade: Decimal | None = None
    valor_unitario: Decimal | None = None
    desconto: Decimal | None = None
    valor_total: Decimal | None = None
    base_icms: Decimal | None = None
    valor_icms: Decimal | None = None
    valor_ipi: Decimal | None = None
    aliquota_icms: Decimal | None = None
    aliquota_ipi: Decimal | None = None


@dataclass(slots=True)
class CampoAdicional:
    arquivo: str
    rotulo: str
    valor: str
    pagina: int | None = None


@dataclass(slots=True)
class NotaFiscal:
    arquivo: str
    caminho: str
    tipo_documento: str = "Documento fiscal não classificado"
    numero: str | None = None
    serie: str | None = None
    chave_acesso: str | None = None
    data_emissao: str | None = None
    hora_emissao: str | None = None
    data_competencia: str | None = None
    data_saida_entrada: str | None = None
    natureza_operacao: str | None = None
    protocolo_autorizacao: str | None = None
    codigo_verificacao: str | None = None
    numero_dps: str | None = None

    emitente_nome: str | None = None
    emitente_cnpj_cpf: str | None = None
    emitente_ie: str | None = None
    emitente_im: str | None = None
    emitente_endereco: str | None = None
    emitente_municipio: str | None = None
    emitente_uf: str | None = None

    destinatario_nome: str | None = None
    destinatario_cnpj_cpf: str | None = None
    destinatario_ie: str | None = None
    destinatario_endereco: str | None = None
    destinatario_municipio: str | None = None
    destinatario_uf: str | None = None

    descricao_servico: str | None = None
    codigo_servico: str | None = None
    codigo_nbs: str | None = None
    municipio_prestacao: str | None = None

    valor_produtos: Decimal | None = None
    valor_servicos: Decimal | None = None
    valor_frete: Decimal | None = None
    valor_seguro: Decimal | None = None
    desconto: Decimal | None = None
    outras_despesas: Decimal | None = None
    base_icms: Decimal | None = None
    valor_icms: Decimal | None = None
    base_icms_st: Decimal | None = None
    valor_icms_st: Decimal | None = None
    valor_ipi: Decimal | None = None
    base_iss: Decimal | None = None
    valor_iss: Decimal | None = None
    valor_pis: Decimal | None = None
    valor_cofins: Decimal | None = None
    valor_irrf: Decimal | None = None
    valor_inss: Decimal | None = None
    valor_csll: Decimal | None = None
    total_retencoes: Decimal | None = None
    valor_liquido: Decimal | None = None
    valor_total: Decimal | None = None

    forma_pagamento: str | None = None
    vencimento: str | None = None
    informacoes_complementares: str | None = None
    paginas: int = 0
    metodo_leitura: str = "texto"
    confianca: int = 0
    status: str = "Revisar"
    observacoes: list[str] = field(default_factory=list)
    itens: list[ItemFiscal] = field(default_factory=list)
    campos_adicionais: list[CampoAdicional] = field(default_factory=list)
    texto_extraido: str = field(default="", repr=False)

    @property
    def nome_arquivo(self) -> str:
        return Path(self.arquivo).name

    def calcular_confianca(self) -> None:
        essenciais = (
            self.numero,
            self.data_emissao,
            self.emitente_nome,
            self.emitente_cnpj_cpf,
            self.valor_total,
        )
        pontos = sum(valor not in (None, "") for valor in essenciais) * 15
        pontos += 10 if self.tipo_documento != "Documento fiscal não classificado" else 0
        pontos += 8 if self.chave_acesso else 0
        pontos += 5 if self.destinatario_nome else 0
        pontos += 2 if self.itens or self.descricao_servico else 0
        if "ocr" in self.metodo_leitura.lower():
            pontos -= 5
        self.confianca = max(0, min(100, pontos))
        self.status = "OK" if self.confianca >= 80 else "Revisar"

        faltantes = [
            nome
            for nome, valor in (
                ("número", self.numero),
                ("data de emissão", self.data_emissao),
                ("emitente", self.emitente_nome),
                ("CNPJ/CPF do emitente", self.emitente_cnpj_cpf),
                ("valor total", self.valor_total),
            )
            if valor in (None, "")
        ]
        if faltantes:
            self.observacoes.append("Campos essenciais não encontrados: " + ", ".join(faltantes))

    def dados_planilha(self) -> dict[str, Any]:
        ignorar = {"itens", "campos_adicionais", "texto_extraido", "observacoes"}
        dados = {k: v for k, v in asdict(self).items() if k not in ignorar}
        dados["observacoes"] = " | ".join(dict.fromkeys(self.observacoes))
        return dados

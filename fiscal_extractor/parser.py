from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from decimal import Decimal
from pathlib import Path

from .models import CampoAdicional, ItemFiscal, NotaFiscal
from .pdf_reader import ResultadoLeitura, xml_valido
from .utils import (
    DATA_RE,
    buscar_primeiro,
    decimal_br,
    extrair_campos_rotulados,
    linha_depois_dos_rotulos,
    localizar_chave_acesso,
    localizar_documentos,
    moedas,
    normalizar_espacos,
    sem_acentos,
    somente_digitos,
    trecho,
)


def _tipo_documento(texto: str) -> str:
    normalizado = sem_acentos(texto).upper()
    if "DOCUMENTO AUXILIAR DA NFS-E" in normalizado or "DANFSE" in normalizado:
        return "NFS-e"
    if "DOCUMENTO AUXILIAR DA NOTA FISCAL DE CONSUMIDOR" in normalizado or "NFC-E" in normalizado:
        return "NFC-e"
    if "DACTE" in normalizado or "CONHECIMENTO DE TRANSPORTE ELETRONICO" in normalizado:
        return "CT-e"
    if "DANFE" in normalizado or "NOTA FISCAL ELETRONICA" in normalizado or "NF-E" in normalizado:
        return "NF-e"
    if "NOTA FISCAL DE SERVICO" in normalizado:
        return "NFS-e"
    if "NOTA FISCAL" in normalizado:
        return "Nota Fiscal"
    return "Documento fiscal não classificado"


def _linha_valores_apos(texto: str, padrao_cabecalho: str) -> list[Decimal]:
    linhas = texto.splitlines()
    for indice, linha in enumerate(linhas[:-1]):
        if re.search(padrao_cabecalho, sem_acentos(linha), re.IGNORECASE):
            for proxima in linhas[indice + 1 : indice + 4]:
                encontrados = moedas(proxima)
                if encontrados:
                    return encontrados
    return []


def _nome_apos_cabecalho(secao: str) -> str | None:
    linhas = secao.splitlines()
    for indice, linha in enumerate(linhas[:-1]):
        normalizada = sem_acentos(linha).upper()
        if "NOME / NOME EMPRESARIAL" in normalizada or "NOME/RAZAO SOCIAL" in normalizada:
            for proxima in linhas[indice + 1 : indice + 4]:
                valor = normalizar_espacos(proxima)
                if valor and not re.search(r"ENDERECO|MUNICIPIO|CNPJ|CPF", sem_acentos(valor), re.I):
                    documentos = re.findall(r"\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}", valor)
                    if documentos:
                        valor = normalizar_espacos(valor.split(documentos[0])[0])
                    valor = re.sub(r"\s+\S+@\S+\s*$", "", valor).strip()
                    return valor
    return None


def _documento_secao(secao: str) -> str | None:
    documentos = localizar_documentos(secao)
    return documentos[0] if documentos else None


def _extrair_nacional_nfse(nota: NotaFiscal, texto: str) -> None:
    nota.numero = buscar_primeiro(
        texto,
        [
            r"Número\s+da\s+NFS.?e[^\n]*\n\s*(\d+)",
            r"NFS.?e\s*(?:n[ºo.]?|número)?\s*[:#-]?\s*(\d+)",
        ],
    )
    linha_numero = linha_depois_dos_rotulos(texto, r"Numero da NFS.?e.*Competencia.*Data.*emissao")
    if linha_numero:
        partes = linha_numero.split()
        if partes and partes[0].isdigit():
            nota.numero = nota.numero or partes[0]
        datas = DATA_RE.findall(linha_numero)
        if datas:
            nota.data_competencia = datas[0]
            nota.data_emissao = datas[-1]
        hora = re.search(r"\b(\d{2}:\d{2}(?::\d{2})?)\b", linha_numero)
        if hora:
            nota.hora_emissao = hora.group(1)

    linha_dps = linha_depois_dos_rotulos(texto, r"Numero da DPS.*Serie da DPS.*Data.*emissao")
    if linha_dps:
        partes = linha_dps.split()
        if partes:
            nota.numero_dps = somente_digitos(partes[0])

    emitente = trecho(texto, r"EMITENTE\s+DA\s+NFS.?E", [r"TOMADOR\s+DO\s+SERVIÇO"])
    tomador = trecho(texto, r"TOMADOR\s+DO\s+SERVIÇO", [r"INTERMEDIÁRIO", r"SERVIÇO\s+PRESTADO"])
    nota.emitente_cnpj_cpf = _documento_secao(emitente)
    nota.emitente_nome = _nome_apos_cabecalho(emitente)
    nota.destinatario_cnpj_cpf = _documento_secao(tomador)
    nota.destinatario_nome = _nome_apos_cabecalho(tomador)

    linha_end_emitente = linha_depois_dos_rotulos(emitente, r"Endereco.*Municipio.*UF.*CEP")
    linha_end_dest = linha_depois_dos_rotulos(tomador, r"Endereco.*Municipio.*UF.*CEP")
    municipio_cabecalho = re.search(r"MUNICÍPIO\s+DE\s+(.+?)\s*[-/]\s*([A-Z]{2})", texto, re.I)
    if linha_end_emitente:
        nota.emitente_endereco = linha_end_emitente
        if municipio_cabecalho and municipio_cabecalho.group(1).upper() in linha_end_emitente.upper():
            nota.emitente_municipio = normalizar_espacos(municipio_cabecalho.group(1))
            nota.emitente_uf = municipio_cabecalho.group(2).upper()
    if linha_end_dest:
        nota.destinatario_endereco = linha_end_dest
        if municipio_cabecalho and municipio_cabecalho.group(1).upper() in linha_end_dest.upper():
            nota.destinatario_municipio = normalizar_espacos(municipio_cabecalho.group(1))
            nota.destinatario_uf = municipio_cabecalho.group(2).upper()

    servico = trecho(texto, r"SERVIÇO\s+PRESTADO", [r"TRIBUTAÇÃO\s+MUNICIPAL", r"VALOR\s+TOTAL"])
    linha_codigos = linha_depois_dos_rotulos(servico, r"Codigo de Tributacao.*Local da Prestacao.*Codigo da NBS")
    if linha_codigos:
        codigo = re.match(r"\s*(\d{3,})", linha_codigos)
        nbs = re.search(r"(\d{9})\s*$", linha_codigos)
        if codigo:
            nota.codigo_servico = codigo.group(1)
        if nbs:
            nota.codigo_nbs = nbs.group(1)
        if codigo:
            meio = linha_codigos[codigo.end() : nbs.start() if nbs else None]
            nota.municipio_prestacao = normalizar_espacos(meio)

    descricao = trecho(servico, r"Descrição\s+do\s+Serviço[^\n]*\n", [r"TRIBUTAÇÃO", r"Valor\s+do\s+Serviço"])
    descricao = re.sub(r"R\$\s*[\d.]+,\d{2}", "", descricao)
    nota.descricao_servico = normalizar_espacos(descricao)

    valores_servico = _linha_valores_apos(texto, r"Valor do Servico.*Desconto Incondicionado.*Deducoes")
    if valores_servico:
        nota.valor_servicos = valores_servico[0]
        if len(valores_servico) > 1:
            nota.desconto = valores_servico[1]
    valores_iss = _linha_valores_apos(texto, r"BC ISSQN.*Aliquota.*ISSQN")
    if valores_iss:
        nota.base_iss = valores_iss[0]
        nota.valor_iss = valores_iss[-1]
    valores_federais = _linha_valores_apos(texto, r"IRRF.*Contribuicao Previdenciaria.*Contribuicoes Sociais")
    if valores_federais:
        nota.valor_irrf = valores_federais[0]
        if len(valores_federais) > 1:
            nota.valor_inss = valores_federais[1]
        if len(valores_federais) > 2:
            nota.valor_csll = valores_federais[2]
    valores_pis_cofins = _linha_valores_apos(texto, r"PIS.*COFINS")
    if valores_pis_cofins:
        nota.valor_pis = valores_pis_cofins[0]
        if len(valores_pis_cofins) > 1:
            nota.valor_cofins = valores_pis_cofins[1]
    totais = _linha_valores_apos(texto, r"VALOR TOTAL DA NFS.?E.*Valor da Operacao")
    if totais:
        nota.valor_total = totais[0]
        nota.valor_servicos = nota.valor_servicos or totais[0]
    liquidos = _linha_valores_apos(texto, r"Total das Retencoes.*Valor Liquido")
    if liquidos:
        nota.total_retencoes = liquidos[0]
        if len(liquidos) > 1:
            nota.valor_liquido = liquidos[1]

    if nota.descricao_servico:
        nota.itens.append(
            ItemFiscal(
                arquivo=nota.arquivo,
                numero_item=1,
                codigo=nota.codigo_servico,
                descricao=nota.descricao_servico,
                quantidade=Decimal("1"),
                valor_unitario=nota.valor_servicos,
                valor_total=nota.valor_servicos,
            )
        )


def _emitente_nfe(texto: str) -> str | None:
    nome = buscar_primeiro(
        texto,
        [
            r"RECEBEMOS\s+DE\s+(.+?)\s+OS\s+PRODUTOS",
            r"Recebemos\s+de\s+(.+?)\s+os\s+produtos",
        ],
    )
    if nome:
        nome = re.sub(r"^\s*\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\s*", "", nome)
        return normalizar_espacos(nome)
    return None


def _extrair_itens_nfe(nota: NotaFiscal, texto: str) -> None:
    bloco = trecho(
        texto,
        r"(?:DADOS\s+DOS\s+PRODUTOS/SERVIÇOS|CÓDIGO\s+DESCRIÇÃO\s+NCM/SH)",
        [r"CÁLCULO\s+DO\s+ISSQN", r"DADOS\s+ADICIONAIS"],
    )
    if not bloco:
        return

    padrao = re.compile(
        r"^\s*(?P<codigo>\S+)\s+(?P<descricao>.+?)\s+"
        r"(?P<ncm>\d{8})\s+(?P<cst>\d{3,4})\s+(?P<cfop>\d{4})\s+"
        r"(?P<unidade>[A-Z]{1,6})\s+(?P<numeros>.+)$",
        re.IGNORECASE,
    )
    item_atual: ItemFiscal | None = None
    for linha in bloco.splitlines():
        normalizada = sem_acentos(linha).upper()
        if "DESCRICAO" in normalizada and "NCM" in normalizada:
            continue
        correspondencia = padrao.match(linha)
        if correspondencia:
            numeros = re.findall(r"-?\d[\d.]*,\d+|-?\d+", correspondencia.group("numeros"))
            valores = [decimal_br(numero) for numero in numeros]
            item_atual = ItemFiscal(
                arquivo=nota.arquivo,
                numero_item=len(nota.itens) + 1,
                codigo=correspondencia.group("codigo"),
                descricao=normalizar_espacos(correspondencia.group("descricao")),
                ncm=correspondencia.group("ncm"),
                cst_csosn=correspondencia.group("cst"),
                cfop=correspondencia.group("cfop"),
                unidade=correspondencia.group("unidade"),
                quantidade=valores[0] if len(valores) > 0 else None,
                valor_unitario=valores[1] if len(valores) > 1 else None,
                valor_total=valores[2] if len(valores) > 2 else None,
                desconto=valores[3] if len(valores) > 3 else None,
                base_icms=valores[4] if len(valores) > 4 else None,
                valor_icms=valores[5] if len(valores) > 5 else None,
                valor_ipi=valores[6] if len(valores) > 6 else None,
                aliquota_icms=valores[-2] if len(valores) >= 9 else None,
                aliquota_ipi=valores[-1] if len(valores) >= 9 else None,
            )
            nota.itens.append(item_atual)
        elif item_atual and linha.strip() and not re.search(r"CALCULO|DADOS ADICIONAIS", normalizada):
            complemento = normalizar_espacos(linha)
            if complemento:
                item_atual.descricao = normalizar_espacos(f"{item_atual.descricao} {complemento}")


def _extrair_nfe(nota: NotaFiscal, texto: str) -> None:
    nota.numero = buscar_primeiro(
        texto,
        [r"N[º°o.]?\s*[:#-]?\s*([\d.]{2,})", r"NÚMERO\s+DA\s+NF[^\n]*\n\s*([\d.]+)"],
    )
    if nota.numero:
        nota.numero = somente_digitos(nota.numero)
    nota.serie = buscar_primeiro(texto, [r"S[ÉE]RIE\s*[:#-]?\s*(\d+)"])
    nota.natureza_operacao = buscar_primeiro(
        texto,
        [r"NATUREZA\s+DA\s+OPERAÇÃO[^\n]*\n\s*(.+?)(?=\s+\d{15}\b|\n)"],
    )
    protocolo = buscar_primeiro(
        texto,
        [r"PROTOCOLO\s+DE\s+AUTORIZAÇÃO\s+DE\s+USO[^\n]*\n.*?(\d{15})"],
    )
    nota.protocolo_autorizacao = protocolo

    nota.emitente_nome = _emitente_nfe(texto)
    documentos = localizar_documentos(texto)
    if documentos:
        nota.emitente_cnpj_cpf = documentos[0]
    linha_ie = linha_depois_dos_rotulos(texto, r"INSCRICAO ESTADUAL.*(?:SUBST|SUBS).*CNPJ")
    if linha_ie:
        ie = re.match(r"\s*([\d.\-]+)", linha_ie)
        if ie:
            nota.emitente_ie = somente_digitos(ie.group(1))

    # O endereço do emitente aparece normalmente no cabeçalho do DANFE.
    linhas_cabecalho = texto.splitlines()[:22]
    for indice, linha in enumerate(linhas_cabecalho):
        normalizada = sem_acentos(linha).upper()
        if re.search(r"\b(RUA|AVENIDA|AV\.?|RODOVIA|ESTRADA|TRAVESSA)\b", normalizada):
            endereco = re.split(r"\s+[01]\s*-\s*(?:SAIDA|ENTRADA)|\s+CHAVE\s+(?:DE\s+)?ACESSO", linha, flags=re.I)[0]
            if indice + 1 < len(linhas_cabecalho) and re.search(r"\bCEP\b", linhas_cabecalho[indice + 1], re.I):
                complemento = re.split(r"\s+N[ºO.]?\s*[:#]?", linhas_cabecalho[indice + 1], flags=re.I)[0]
                endereco = f"{endereco} {complemento}"
            nota.emitente_endereco = normalizar_espacos(endereco)
            uf = re.search(r"\b([A-Z]{2})\s*-?\s*CEP\b", sem_acentos(endereco).upper())
            if uf:
                nota.emitente_uf = uf.group(1)
            municipio = re.search(r",\s*([^,]+),\s*([A-Z]{2})\s*-?\s*CEP\b", endereco, re.I)
            if municipio:
                nota.emitente_municipio = normalizar_espacos(municipio.group(1))
                nota.emitente_uf = municipio.group(2).upper()
            if not nota.emitente_municipio:
                contexto_cep = " ".join(linhas_cabecalho)
                municipio = re.search(r"CEP\s*:?\s*[\d.-]+\s+([A-ZÀ-Ý][A-ZÀ-Ý ]+?)\s*-\s*([A-Z]{2})\b", contexto_cep, re.I)
                if municipio:
                    nota.emitente_municipio = normalizar_espacos(municipio.group(1))
                    nota.emitente_uf = municipio.group(2).upper()
            break

    destinatario = trecho(
        texto,
        r"DESTINATÁRIO\s*/?\s*REMETENTE",
        [r"FATURA", r"CÁLCULO\s+DO\s+IMPOSTO"],
    )
    linha_dest = linha_depois_dos_rotulos(destinatario, r"NOME/RAZAO SOCIAL.*CNPJ/CPF.*DATA DA EMISSAO")
    if linha_dest:
        docs_dest = localizar_documentos(linha_dest)
        if docs_dest:
            nota.destinatario_cnpj_cpf = docs_dest[0]
            formato = re.search(r"\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}", linha_dest)
            if formato:
                nota.destinatario_nome = normalizar_espacos(linha_dest[: formato.start()])
        datas = DATA_RE.findall(linha_dest)
        if datas:
            nota.data_emissao = datas[-1]
    if not nota.destinatario_nome:
        nota.destinatario_nome = _nome_apos_cabecalho(destinatario)
    if not nota.destinatario_cnpj_cpf:
        nota.destinatario_cnpj_cpf = _documento_secao(destinatario)

    linha_end_dest = linha_depois_dos_rotulos(destinatario, r"ENDERECO.*BAIRRO.*CEP")
    if linha_end_dest:
        nota.destinatario_endereco = normalizar_espacos(linha_end_dest)
    linha_municipio = linha_depois_dos_rotulos(destinatario, r"MUNICIPIO.*UF.*(?:INSCRICAO|INCRICAO) ESTADUAL")
    if linha_municipio:
        partes = linha_municipio.split()
        indices_uf = [i for i, parte in enumerate(partes) if re.fullmatch(r"[A-Z]{2}", parte)]
        if indices_uf:
            indice_uf = indices_uf[-1]
            nota.destinatario_municipio = normalizar_espacos(" ".join(partes[:indice_uf]))
            nota.destinatario_uf = partes[indice_uf]
            resto = " ".join(partes[indice_uf + 1 :])
            if re.fullmatch(r"[\d.\-]+", resto):
                nota.destinatario_ie = somente_digitos(resto)

    nota.data_emissao = nota.data_emissao or buscar_primeiro(
        texto, [r"DATA\s+DA\s+EMISSÃO[^\n]*\n[^\n]*?(\d{2}/\d{2}/\d{4})", r"Emissão\s*[:\-]?\s*(\d{2}/\d{2}/\d{4})"]
    )

    impostos = _linha_valores_apos(texto, r"BASE DE CALCULO DO ICMS.*VALOR DO ICMS.*VALOR TOTAL DOS PRODUTOS")
    if impostos:
        nota.base_icms = impostos[0]
        nota.valor_icms = impostos[1] if len(impostos) > 1 else None
        nota.base_icms_st = impostos[2] if len(impostos) > 2 else None
        nota.valor_icms_st = impostos[3] if len(impostos) > 3 else None
        nota.valor_produtos = impostos[4] if len(impostos) > 4 else None
    totais = _linha_valores_apos(texto, r"VALOR DO FRETE.*VALOR DO SEGURO.*DESCONTO.*VALOR TOTAL DA NOTA")
    if totais:
        nota.valor_frete = totais[0]
        nota.valor_seguro = totais[1] if len(totais) > 1 else None
        nota.desconto = totais[2] if len(totais) > 2 else None
        nota.outras_despesas = totais[3] if len(totais) > 3 else None
        nota.valor_ipi = totais[4] if len(totais) > 4 else None
        nota.valor_total = totais[5] if len(totais) > 5 else totais[-1]

    _extrair_itens_nfe(nota, texto)
    complemento = trecho(texto, r"INFORMAÇÕES\s+COMPLEMENTARES", [r"RESERVADO\s+AO\s+FISCO"])
    nota.informacoes_complementares = normalizar_espacos(complemento)
    if nota.informacoes_complementares:
        for forma in ("PIX", "DINHEIRO", "CARTÃO", "BOLETO", "TEF"):
            if forma in nota.informacoes_complementares.upper():
                nota.forma_pagamento = forma
                break


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _filho(elemento: ET.Element | None, nome: str) -> ET.Element | None:
    if elemento is None:
        return None
    return next((x for x in elemento.iter() if _local(x.tag) == nome), None)


def _texto_xml(elemento: ET.Element | None, nome: str) -> str | None:
    encontrado = _filho(elemento, nome)
    return normalizar_espacos(encontrado.text) if encontrado is not None else None


def _decimal_xml(elemento: ET.Element | None, nome: str) -> Decimal | None:
    return decimal_br((_texto_xml(elemento, nome) or "").replace(".", ","))


def _aplicar_xml_nfe(nota: NotaFiscal, xml: str) -> bool:
    if not xml_valido(xml):
        return False
    raiz = ET.fromstring(xml)
    inf_nfe = _filho(raiz, "infNFe")
    if inf_nfe is None:
        return False
    ide, emit, dest, total = (_filho(inf_nfe, nome) for nome in ("ide", "emit", "dest", "total"))
    nota.tipo_documento = "NF-e (XML embutido)"
    nota.numero = _texto_xml(ide, "nNF") or nota.numero
    nota.serie = _texto_xml(ide, "serie") or nota.serie
    emissao = _texto_xml(ide, "dhEmi") or _texto_xml(ide, "dEmi")
    if emissao:
        data_iso = re.match(r"(\d{4})-(\d{2})-(\d{2})(?:T(\d{2}:\d{2}:\d{2}))?", emissao)
        if data_iso:
            nota.data_emissao = f"{data_iso.group(3)}/{data_iso.group(2)}/{data_iso.group(1)}"
            nota.hora_emissao = data_iso.group(4)
    nota.natureza_operacao = _texto_xml(ide, "natOp") or nota.natureza_operacao
    nota.emitente_nome = _texto_xml(emit, "xNome") or nota.emitente_nome
    nota.emitente_cnpj_cpf = _texto_xml(emit, "CNPJ") or _texto_xml(emit, "CPF") or nota.emitente_cnpj_cpf
    nota.emitente_ie = _texto_xml(emit, "IE") or nota.emitente_ie
    nota.destinatario_nome = _texto_xml(dest, "xNome") or nota.destinatario_nome
    nota.destinatario_cnpj_cpf = _texto_xml(dest, "CNPJ") or _texto_xml(dest, "CPF") or nota.destinatario_cnpj_cpf
    nota.destinatario_ie = _texto_xml(dest, "IE") or nota.destinatario_ie
    nota.valor_produtos = _decimal_xml(total, "vProd") or nota.valor_produtos
    nota.valor_frete = _decimal_xml(total, "vFrete") or nota.valor_frete
    nota.valor_seguro = _decimal_xml(total, "vSeg") or nota.valor_seguro
    nota.desconto = _decimal_xml(total, "vDesc") or nota.desconto
    nota.valor_icms = _decimal_xml(total, "vICMS") or nota.valor_icms
    nota.valor_ipi = _decimal_xml(total, "vIPI") or nota.valor_ipi
    nota.valor_pis = _decimal_xml(total, "vPIS") or nota.valor_pis
    nota.valor_cofins = _decimal_xml(total, "vCOFINS") or nota.valor_cofins
    nota.valor_total = _decimal_xml(total, "vNF") or nota.valor_total

    id_nfe = inf_nfe.attrib.get("Id", "")
    chave = re.sub(r"\D", "", id_nfe)
    if len(chave) == 44:
        nota.chave_acesso = chave

    itens: list[ItemFiscal] = []
    for det in (x for x in inf_nfe if _local(x.tag) == "det"):
        prod = _filho(det, "prod")
        itens.append(
            ItemFiscal(
                arquivo=nota.arquivo,
                numero_item=int(det.attrib.get("nItem", len(itens) + 1)),
                codigo=_texto_xml(prod, "cProd"),
                descricao=_texto_xml(prod, "xProd"),
                ncm=_texto_xml(prod, "NCM"),
                cest=_texto_xml(prod, "CEST"),
                cfop=_texto_xml(prod, "CFOP"),
                unidade=_texto_xml(prod, "uCom"),
                quantidade=_decimal_xml(prod, "qCom"),
                valor_unitario=_decimal_xml(prod, "vUnCom"),
                desconto=_decimal_xml(prod, "vDesc"),
                valor_total=_decimal_xml(prod, "vProd"),
            )
        )
    if itens:
        nota.itens = itens
    return True


def analisar_documento(caminho: str | Path, leitura: ResultadoLeitura) -> NotaFiscal:
    caminho = Path(caminho)
    texto = leitura.texto
    nota = NotaFiscal(
        arquivo=caminho.name,
        caminho=str(caminho.resolve()),
        tipo_documento=_tipo_documento(texto),
        chave_acesso=localizar_chave_acesso(texto),
        paginas=leitura.paginas,
        metodo_leitura=leitura.metodo,
        observacoes=list(leitura.avisos),
        texto_extraido=texto,
    )

    if nota.tipo_documento == "NFS-e":
        _extrair_nacional_nfse(nota, texto)
    elif nota.tipo_documento in {"NF-e", "NFC-e", "Nota Fiscal"}:
        _extrair_nfe(nota, texto)
    else:
        # Extrator genérico: mantém os campos centrais e marca para revisão.
        nota.numero = buscar_primeiro(texto, [r"(?:Nota Fiscal|NF|Nº)\s*[:#-]?\s*(\d[\d.]*)"])
        nota.data_emissao = buscar_primeiro(texto, [r"(?:Data de Emissão|Emissão)\s*[:#-]?\s*(\d{2}/\d{2}/\d{4})"])
        documentos = localizar_documentos(texto)
        nota.emitente_cnpj_cpf = documentos[0] if documentos else None
        valores = re.findall(r"(?:VALOR TOTAL|TOTAL DA NOTA)\s*[:#-]?\s*(R\$\s*)?([\d.]+,\d{2})", texto, re.I)
        if valores:
            nota.valor_total = decimal_br(valores[-1][1])

    for xml in leitura.xmls_embutidos:
        if _aplicar_xml_nfe(nota, xml):
            nota.metodo_leitura += " + XML embutido"
            break

    nota.campos_adicionais = [
        CampoAdicional(arquivo=nota.arquivo, rotulo=rotulo, valor=valor)
        for rotulo, valor in extrair_campos_rotulados(texto, nota.arquivo)
    ]
    nota.calcular_confianca()
    return nota

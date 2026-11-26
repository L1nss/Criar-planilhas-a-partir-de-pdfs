from __future__ import annotations

import re
import unicodedata
from decimal import Decimal, InvalidOperation


MOEDA_RE = re.compile(r"(?:R\$\s*)?-?\d{1,3}(?:\.\d{3})*,\d{2}|(?:R\$\s*)?-?\d+,\d{2}")
DATA_RE = re.compile(r"\b(\d{2}/\d{2}/\d{4})\b")
CNPJ_CPF_RE = re.compile(
    r"(?<!\d)(\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}|\d{3}\.?\d{3}\.?\d{3}-?\d{2}|\d{11}|\d{14})(?!\d)"
)


def sem_acentos(valor: str) -> str:
    return "".join(
        caractere
        for caractere in unicodedata.normalize("NFKD", valor)
        if not unicodedata.combining(caractere)
    )


def normalizar_espacos(valor: str | None) -> str | None:
    if valor is None:
        return None
    limpo = re.sub(r"[ \t\r\f\v]+", " ", valor).strip(" :-\t\n")
    return limpo or None


def somente_digitos(valor: str | None) -> str | None:
    if not valor:
        return None
    digitos = re.sub(r"\D", "", valor)
    return digitos or None


def decimal_br(valor: str | None) -> Decimal | None:
    if not valor:
        return None
    limpo = re.sub(r"[^\d,.-]", "", valor).strip()
    if not limpo:
        return None
    if "," in limpo:
        limpo = limpo.replace(".", "").replace(",", ".")
    elif limpo.count(".") > 1:
        partes = limpo.split(".")
        limpo = "".join(partes[:-1]) + "." + partes[-1]
    try:
        return Decimal(limpo)
    except InvalidOperation:
        return None


def moedas(linha: str) -> list[Decimal]:
    return [v for v in (decimal_br(x) for x in MOEDA_RE.findall(linha)) if v is not None]


def buscar_primeiro(texto: str, padroes: list[str], grupo: int = 1) -> str | None:
    for padrao in padroes:
        resultado = re.search(padrao, texto, re.IGNORECASE | re.MULTILINE | re.DOTALL)
        if resultado:
            return normalizar_espacos(resultado.group(grupo))
    return None


def localizar_documentos(texto: str) -> list[str]:
    encontrados: list[str] = []
    for valor in CNPJ_CPF_RE.findall(texto):
        digitos = somente_digitos(valor)
        if digitos and len(digitos) in {11, 14} and digitos not in encontrados:
            encontrados.append(digitos)
    return encontrados


def localizar_chave_acesso(texto: str) -> str | None:
    regioes = re.findall(
        r"(?:CHAVE\s+(?:DE\s+)?ACESSO|CHAVE\s+DE\s+ACESSO\s+DA\s+NFS.?E)(.{0,180})",
        texto,
        re.IGNORECASE,
    )
    for regiao in regioes + [texto]:
        candidatos = re.findall(r"(?:\d[ .]?){44,55}", regiao)
        for candidato in candidatos:
            digitos = re.sub(r"\D", "", candidato)
            if len(digitos) == 44:
                return digitos
            # A chave nacional da NFS-e possui 50 posições. Em DANFEs, o
            # número da nota às vezes fica na mesma linha e é concatenado pela
            # extração; nesses casos a chave correta são os 44 últimos dígitos.
            if len(digitos) == 50:
                return digitos
            if 44 < len(digitos) <= 55:
                return digitos[-44:]
    return None


def trecho(texto: str, inicio: str, fins: list[str]) -> str:
    comeco = re.search(inicio, texto, re.IGNORECASE)
    if not comeco:
        return ""
    restante = texto[comeco.end() :]
    limites = [m.start() for fim in fins if (m := re.search(fim, restante, re.IGNORECASE))]
    return restante[: min(limites)] if limites else restante


def linha_depois_dos_rotulos(texto: str, padrao_rotulos: str) -> str | None:
    linhas = texto.splitlines()
    for indice, linha in enumerate(linhas[:-1]):
        if re.search(padrao_rotulos, sem_acentos(linha), re.IGNORECASE):
            for proxima in linhas[indice + 1 : indice + 4]:
                if proxima.strip():
                    return proxima.strip()
    return None


def extrair_campos_rotulados(texto: str, arquivo: str) -> list[tuple[str, str]]:
    """Captura rótulos simples sem substituir os extratores fiscais específicos."""
    resultado: list[tuple[str, str]] = []
    vistos: set[tuple[str, str]] = set()
    for linha in texto.splitlines():
        linha = normalizar_espacos(linha) or ""
        correspondencia = re.match(r"^([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ0-9 /()._-]{2,45})\s*:\s*(.{1,160})$", linha)
        if not correspondencia:
            continue
        rotulo = normalizar_espacos(correspondencia.group(1)) or ""
        valor = normalizar_espacos(correspondencia.group(2)) or ""
        chave = (rotulo.casefold(), valor.casefold())
        if chave not in vistos:
            resultado.append((rotulo, valor))
            vistos.add(chave)
    return resultado

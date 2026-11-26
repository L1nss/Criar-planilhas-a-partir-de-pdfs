<p align="center">
  <img src="assets/icone-notas.png" alt="Ícone do Montador de planilha com PDFs" width="150">
</p>

# Montador de planilha com PDFs

Aplicação em Python que lê uma pasta com notas fiscais em PDF, extrai os dados
encontrados e monta automaticamente uma planilha Excel organizada para controle
administrativo.

## O que o programa faz

- Processa todos os PDFs de uma pasta e, opcionalmente, de suas subpastas.
- Reconhece NF-e, DANFE, NFC-e, NFS-e e layouts fiscais semelhantes.
- Usa o texto original do PDF sempre que possível.
- Aciona OCR por página quando o documento é uma imagem digitalizada.
- Lê XML de NF-e anexado ao PDF quando estiver disponível.
- Identifica possíveis documentos duplicados sem excluir arquivos.
- Calcula uma pontuação de confiança para indicar o que precisa de revisão.
- Gera uma planilha Excel com divisórias entre as células, filtros e cabeçalho fixo.
- Mostra quantos documentos deram certo, precisam de revisão ou apresentaram erro.
- Guarda um log da última execução em `logs\ultima_execucao.log`.

Cada PDF gera uma linha na aba **Controle de Notas**. A planilha contém:

- tipo da nota;
- data de emissão e competência;
- fornecedor ou prestador;
- CNPJ ou CPF;
- número e série da nota;
- chave de acesso;
- descrição ou objeto;
- valores de produtos e serviços;
- desconto, retenções, valor líquido e valor total;
- responsável, observações e nome do arquivo PDF.

A coluna amarela **Responsável** é destinada ao preenchimento manual. O
programa não inventa valores: campos ausentes ou extrações com baixa confiança
são sinalizados na coluna **Observação**.

## O que instalar

### Obrigatório

- Windows 10 ou Windows 11;
- [Python 3](https://www.python.org/downloads/windows/), marcando a opção
  **Add Python to PATH** durante a instalação;
- conexão com a internet na primeira execução para instalar as bibliotecas.

### Opcional para PDFs escaneados

- [Tesseract OCR para Windows](https://github.com/UB-Mannheim/tesseract/wiki),
  com o idioma português instalado.

O arquivo `EXECUTAR_NO_WINDOWS.bat` verifica o Python e o Tesseract, cria o
ambiente virtual e instala automaticamente as bibliotecas do
`requirements.txt`.

## Como usar no Windows

1. Baixe o projeto e extraia o arquivo ZIP.
2. Abra a pasta extraída.
3. Dê dois cliques em `EXECUTAR_NO_WINDOWS.bat`.
4. Na primeira execução, escolha a pasta onde estão os PDFs.
5. Escolha onde a planilha Excel deve ser salva.
6. Aguarde o processamento e confira o resumo exibido na tela.

As escolhas são guardadas no arquivo local `configuracao.json`. Nas próximas
execuções, o programa reutiliza os mesmos locais e começa automaticamente após
três segundos. Para escolher novos locais, pressione **C** durante essa
contagem.

O `.bat` também cria na Área de Trabalho um atalho chamado **Extrator de Notas
Fiscais**, usando o ícone personalizado do projeto.

## Instalação manual

### Windows

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Para instalar o OCR no Ubuntu ou Debian:

```bash
sudo apt update
sudo apt install tesseract-ocr tesseract-ocr-por
```

No Fedora:

```bash
sudo dnf install tesseract tesseract-langpack-por
```

## Como executar manualmente

Interface gráfica:

```bash
python naRegional.py
```

Informando a pasta e o arquivo de saída pelo terminal:

```bash
python naRegional.py "C:\caminho\das\notas" -o "C:\caminho\controle_notas.xlsx"
```

Opções disponíveis:

```bash
python naRegional.py --help
python naRegional.py --configurar
python naRegional.py "C:\notas" --ocr sempre
python naRegional.py "C:\notas" --ocr nunca
python naRegional.py "C:\notas" --nao-recursivo
```

O modo padrão `--ocr auto` usa OCR somente nas páginas em que o texto nativo é
insuficiente.

## Limitações

Os modelos de documentos fiscais variam entre prefeituras, fornecedores e
sistemas emissores. Digitalizações cortadas ou ilegíveis também podem impedir a
leitura de alguns campos. Por isso, confira as linhas marcadas para revisão e a
coluna **Observação** antes de usar os dados em processos oficiais.

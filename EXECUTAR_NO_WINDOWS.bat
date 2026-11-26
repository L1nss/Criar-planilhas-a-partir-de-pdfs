@echo off
setlocal EnableExtensions
chcp 65001 >nul
title Extrator de notas fiscais

cd /d "%~dp0"
set "PASTA_PROGRAMA=%~dp0"
set "ARQUIVO_PYTHON=%PASTA_PROGRAMA%naRegional.py"
set "ARQUIVO_REQUISITOS=%PASTA_PROGRAMA%requirements.txt"
set "PASTA_AMBIENTE=%PASTA_PROGRAMA%.venv"
set "PYTHON_AMBIENTE=%PASTA_AMBIENTE%\Scripts\python.exe"
set "PASTA_LOGS=%PASTA_PROGRAMA%logs"
set "RUN_LOG=%PASTA_LOGS%\ultima_execucao.log"
set "ARQUIVO_CONFIGURACAO=%PASTA_PROGRAMA%configuracao.json"
set "ARQUIVO_ICONE=%PASTA_PROGRAMA%icone_notas.ico"
set "ARQUIVO_BAT=%~f0"

echo ============================================================
echo          EXTRATOR DE NOTAS FISCAIS PARA EXCEL
echo ============================================================
echo.
echo Pasta do programa:
echo %PASTA_PROGRAMA%
echo.

if not exist "%ARQUIVO_PYTHON%" (
    echo [ERRO] O arquivo naRegional.py nao foi encontrado.
    goto :falha
)

if not exist "%ARQUIVO_REQUISITOS%" (
    echo [ERRO] O arquivo requirements.txt nao foi encontrado.
    goto :falha
)

if exist "%ARQUIVO_ICONE%" (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "$desktop=[Environment]::GetFolderPath('Desktop'); $atalho=Join-Path $desktop 'Extrator de Notas Fiscais.lnk'; $shell=New-Object -ComObject WScript.Shell; $link=$shell.CreateShortcut($atalho); $link.TargetPath=$env:ARQUIVO_BAT; $link.WorkingDirectory=$env:PASTA_PROGRAMA; $link.IconLocation=$env:ARQUIVO_ICONE + ',0'; $link.Description='Extrator de notas fiscais para Excel'; $link.Save()" >nul 2>&1
    if not errorlevel 1 echo Atalho com icone criado na Area de Trabalho.
)

set "INICIADOR_PYTHON="
py -3 --version >nul 2>&1
if not errorlevel 1 set "INICIADOR_PYTHON=py -3"

if not defined INICIADOR_PYTHON (
    python --version >nul 2>&1
    if not errorlevel 1 set "INICIADOR_PYTHON=python"
)

if not defined INICIADOR_PYTHON (
    echo [ERRO] Python 3 nao esta instalado ou nao esta no PATH.
    echo.
    echo Instale pelo endereco:
    echo https://www.python.org/downloads/windows/
    echo.
    echo Durante a instalacao, marque a opcao "Add Python to PATH".
    goto :falha
)

if not exist "%PYTHON_AMBIENTE%" (
    echo [1/4] Criando o ambiente do programa...
    %INICIADOR_PYTHON% -m venv "%PASTA_AMBIENTE%"
    if errorlevel 1 (
        echo [ERRO] Nao foi possivel criar o ambiente virtual.
        goto :falha
    )
) else (
    echo [1/4] Ambiente do programa ja existe.
)

echo [2/4] Instalando ou atualizando as bibliotecas...
"%PYTHON_AMBIENTE%" -m pip install --disable-pip-version-check --prefer-binary -r "%ARQUIVO_REQUISITOS%"
if errorlevel 1 (
    echo [ERRO] Nao foi possivel instalar as bibliotecas.
    echo Verifique a conexao com a internet e tente novamente.
    goto :falha
)

if exist "%ProgramFiles%\Tesseract-OCR\tesseract.exe" (
    set "PATH=%ProgramFiles%\Tesseract-OCR;%PATH%"
)

where tesseract >nul 2>&1
if errorlevel 1 (
    echo [3/4] AVISO: Tesseract OCR nao encontrado.
    echo       PDFs normais funcionarao, mas PDFs escaneados podem falhar.
    echo       Download: https://github.com/UB-Mannheim/tesseract/wiki
) else (
    echo [3/4] Tesseract OCR encontrado.
)

if not exist "%PASTA_LOGS%" mkdir "%PASTA_LOGS%"

echo [4/4] Iniciando o processamento...
echo.

if exist "%ARQUIVO_CONFIGURACAO%" (
    echo Configuracao encontrada.
    echo O programa usara automaticamente as pastas escolhidas anteriormente.
    echo.
    choice /C EC /N /T 3 /D E /M "Pressione [C] para alterar ou aguarde para [E] executar: "
    if errorlevel 2 (
        echo.
        echo Abrindo as configuracoes...
        powershell -NoProfile -ExecutionPolicy Bypass -Command "& { & $env:PYTHON_AMBIENTE $env:ARQUIVO_PYTHON '--configurar' 2>&1 | Tee-Object -FilePath $env:RUN_LOG; exit $LASTEXITCODE }"
    ) else (
        powershell -NoProfile -ExecutionPolicy Bypass -Command "& { & $env:PYTHON_AMBIENTE $env:ARQUIVO_PYTHON 2>&1 | Tee-Object -FilePath $env:RUN_LOG; exit $LASTEXITCODE }"
    )
) else (
    echo Primeira execucao: configure onde estao os PDFs e onde salvar a planilha.
    echo Essas escolhas serao guardadas para as proximas execucoes.
    echo.
    powershell -NoProfile -ExecutionPolicy Bypass -Command "& { & $env:PYTHON_AMBIENTE $env:ARQUIVO_PYTHON 2>&1 | Tee-Object -FilePath $env:RUN_LOG; exit $LASTEXITCODE }"
)

set "CODIGO_RESULTADO=%ERRORLEVEL%"
echo.
echo ============================================================
if "%CODIGO_RESULTADO%"=="0" (
    echo PROCESSAMENTO CONCLUIDO COM SUCESSO.
) else if "%CODIGO_RESULTADO%"=="2" (
    echo PROCESSAMENTO CONCLUIDO COM AVISOS.
    echo Alguns PDFs apresentaram erro. Consulte o resumo acima e o log.
) else (
    echo O PROCESSAMENTO NAO FOI CONCLUIDO.
    echo Consulte a mensagem de erro acima e o arquivo de log.
)
echo.
echo Log da ultima execucao:
echo %RUN_LOG%
echo ============================================================
echo.
pause
exit /b %CODIGO_RESULTADO%

:falha
echo.
echo O programa nao foi executado.
echo Pasta atual: %PASTA_PROGRAMA%
echo.
pause
exit /b 1

@echo off
rem Chamada unica da coleta: faz o que falta e sai. E o que a Tarefa Agendada
rem executa, e serve para rodar a mao com um duplo clique.
rem
rem Sem acento neste arquivo, de proposito: o cmd.exe le em ANSI e um "rem"
rem com caractere acentuado vira comando invalido no meio da execucao.
rem
rem Por que a tarefa passa por aqui em vez de chamar o Python direto: sob o
rem Agendador nao ha console, e processo que morre cedo nao deixa rastro. A
rem tarefa aparece como bem-sucedida e o acervo nao anda. Estas linhas
rem registram a partida e capturam o que o Python escrever em erro padrao.
echo %date% %time%  cmd iniciou>>"%~dp0dados\agendado.log"
"%~dp0.venv\Scripts\python.exe" "%~dp0coleta\rodar_agendado.py" >>"%~dp0dados\agendado_saida.log" 2>&1
echo %date% %time%  cmd terminou com codigo %ERRORLEVEL%>>"%~dp0dados\agendado.log"

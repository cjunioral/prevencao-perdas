# ===========================================================================
# Registra a tarefa diária no Agendador de Tarefas do Windows (rodar UMA vez,
# no PowerShell como o usuário que vai executar a carga):
#
#   powershell -ExecutionPolicy Bypass -File agendamento\registrar_tarefa_windows.ps1
#
# Configurações e por quê:
#   - Diária às 06:00: antes do horário comercial, banco da Consinco tranquilo.
#   - WakeToRun: se o computador estiver suspenso, o Windows o acorda às 06h00.
#   - Roda com o usuário logado (sessão bloqueada serve; logoff não). Para rodar
#     sem ninguém logado, registre com -User/-Password (exige permissão local).
#   - StartWhenAvailable: se o computador estava desligado às 06h00, roda assim
#     que ligar (a janela móvel recupera os dias perdidos).
#   - MultipleInstances IgnoreNew: se a anterior ainda estiver rodando, o
#     Windows não inicia outra (1ª proteção; a 2ª é o advisory lock no banco).
#   - ExecutionTimeLimit 2h: uma execução travada não fica para sempre.
#   - RestartCount 2 / 15 min: tenta de novo em caso de falha transitória.
# Para conferir:  Get-ScheduledTask -TaskName PrevencaoPerdas_ETL | Get-ScheduledTaskInfo
# Para rodar já:  Start-ScheduledTask -TaskName PrevencaoPerdas_ETL
# ===========================================================================
$raiz = Split-Path -Parent $PSScriptRoot
$acao = New-ScheduledTaskAction -Execute "$raiz\agendamento\executar_etl.bat" -WorkingDirectory $raiz
$gatilho = New-ScheduledTaskTrigger -Daily -At 06:00
$config = New-ScheduledTaskSettingsSet -StartWhenAvailable -WakeToRun -MultipleInstances IgnoreNew `
          -ExecutionTimeLimit (New-TimeSpan -Hours 2) -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 15)

Register-ScheduledTask -TaskName "PrevencaoPerdas_ETL" -Action $acao -Trigger $gatilho -Settings $config `
    -Description "Carga diária do banco analítico de Prevenção de Perdas (Consinco + planilha de inventário)" -Force
Write-Host "Tarefa PrevencaoPerdas_ETL registrada: diariamente às 06:00."

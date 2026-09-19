<# Interactive entry point for the project-root shortcut. #>
[CmdletBinding()]
param([string]$Port, [switch]$All, [switch]$Apply, [switch]$PreviewOnly)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$logPath = Join-Path $projectRoot 'usb-restart.log'
$toolPath = Join-Path $PSScriptRoot 'restart_usb_port.ps1'
$launchId = [guid]::NewGuid().ToString('N')
$phase = 'START'
$outcome = 'INCOMPLETE'
$completedPorts = @()
$eventSequence = 0
$eventsPath = Join-Path $projectRoot 'usb-restart-events.jsonl'
$eventWriter = $null
$transcribing = $false

function Write-LaunchEvent {
    param([string]$Action, [string]$Details, [hashtable]$Data = @{}, $ErrorInfo = $null)
    $script:eventSequence++
    $event = [ordered]@{
        schema = 1
        type = 'usb_restart_event'
        utc = [DateTime]::UtcNow.ToString('o')
        launch_id = $launchId
        sequence = $script:eventSequence
        action = $Action
        level = $(if ($ErrorInfo) { 'error' } else { 'info' })
        port = $Data.port
        target = $Data.target
        message = $Details
        data = $Data
        error = $ErrorInfo
    }
    $json = $event | ConvertTo-Json -Depth 16 -Compress
    # Emit a complete machine-readable line even when journal creation failed.
    Write-Output ('JSON ' + $json)
    if ($eventWriter) {
        $eventWriter.WriteLine($json)
        $eventWriter.Flush()
    }
    Write-Host "[$(Get-Date -Format o)] launch_id=$launchId action=$Action $Details"
}

try {
    # One writer for the full launch. Failure stops before discovery or mutation.
    $eventStream = [IO.File]::Open($eventsPath, [IO.FileMode]::Append, [IO.FileAccess]::Write, [IO.FileShare]::Read)
    $eventWriter = [IO.StreamWriter]::new($eventStream, [Text.UTF8Encoding]::new($false))
    Start-Transcript -LiteralPath $logPath -Append -ErrorAction Stop | Out-Null
    $transcribing = $true
    Write-Host "USB restart launcher - $(Get-Date -Format o)"
    Write-Host "Launch log: $logPath"
    Write-LaunchEvent 'START' "script=$PSCommandPath preview_only=$PreviewOnly apply=$Apply" -Data @{script=$PSCommandPath; preview_only=[bool]$PreviewOnly; apply=[bool]$Apply; all=[bool]$All; port=$Port; events_path=$eventsPath}
    if ($Port -and $All) { throw 'Choose Port or All, not both.' }
    if ($Apply -and $PreviewOnly) { throw 'Choose Apply or PreviewOnly, not both.' }
    if ($Apply -and -not ($Port -or $All)) { throw 'Unattended Apply requires explicit Port or All.' }
    $phase = 'DISCOVER'
    $devices = @(& $toolPath -ListPorts)
    foreach ($device in $devices) {
        Write-LaunchEvent 'DISCOVERED' "port=$($device.port) target=$($device.target) status=$($device.status) name=$($device.name)" -Data @{port=$device.port; target=$device.target; response=$device}
    }
    if ($devices.Count -eq 0) { throw 'No USB Serial adapters found.' }
    if ($Port) {
        $Port = $Port.Trim().ToUpperInvariant()
        if ($Port -notmatch '^COM[1-9][0-9]*$') { throw 'Invalid port. Use COM followed by a positive number.' }
        $selected = @($devices | Where-Object port -eq $Port)
        if ($selected.Count -ne 1) { throw 'Selected USB Serial port was not found uniquely.' }
        $selection = $Port
    } else {
        $selected = $devices
        $selection = 'ALL'
    }
    $phase = 'PREVIEW'
    foreach ($device in $selected) {
        $preview = & $toolPath -Port $device.port -ExpectedInstanceId $device.target
        Write-LaunchEvent 'TARGET' "port=$($device.port) target=$($preview.target) before_status=$($preview.before_status)" -Data @{port=$device.port; target=$preview.target; response=$preview}
    }
    if ($PreviewOnly) {
        $outcome = 'PREVIEW_ONLY'
        Write-LaunchEvent 'PREVIEW_ONLY' "selection=$selection count=$($selected.Count) restart_attempted=false" -Data @{selection=$selection; count=$selected.Count; restart_attempted=$false}
        return
    }
    Write-Host 'Check that this is the intended board. Stop your serial monitor; no flashing may be in progress.'
    if (-not $Apply) {
        $confirmation = Read-Host "Type RESTART $selection to restart the displayed selection, or press Enter to cancel"
        if ($confirmation -cne "RESTART $selection") {
            $outcome = 'CANCELLED'
            Write-LaunchEvent 'CANCELLED' "selection=$selection restart_attempted=false" -Data @{selection=$selection; restart_attempted=$false}
            Write-Host 'CANCELLED: restart not confirmed. No restart requested.'
            return
        }
    }
    foreach ($device in $selected) {
        $port = $device.port
        $phase = 'APPLY'
        Write-LaunchEvent 'APPLY' "port=$port target=$($device.target)" -Data @{port=$port; target=$device.target; command='restart_usb_port.ps1'; arguments=@('-Port',$port,'-ExpectedInstanceId',$device.target,'-Apply')}
        $result = & $toolPath -Port $port -ExpectedInstanceId $device.target -Apply
        # Full JSON avoids Format-List truncation of native output and action history.
        $result | ConvertTo-Json -Depth 8 | Out-Host
        Write-LaunchEvent 'RESULT' "port=$port target=$($result.target) result=$($result.result) exit_code=$($result.exit_code) after_status=$($result.after_status) uart_verified=false" -Data @{port=$port; target=$result.target; response=$result}
        if ($result.result -ne 'RESTART_COMMAND_SUCCEEDED' -or $result.exit_code -ne 0 -or $result.after_error -or $result.after_status -ne 'OK') {
            throw 'Restart or PnP post-check is not confirmed; remaining ports were not restarted.'
        }
        $completedPorts += $port
    }
    $outcome = 'COMPLETED'
    Write-Host 'Completed. See usb-restart.jsonl and the separate JSON receipt for the result.'
} catch {
    $failure = $_
    $outcome = 'ERROR'
    $errorInfo = [ordered]@{message=$failure.Exception.Message; exception_type=$failure.Exception.GetType().FullName; id=$failure.FullyQualifiedErrorId; category=[string]$failure.CategoryInfo.Category; phase=$phase}
    $errorData = @{port=$port; completed_ports=@($completedPorts); receipt_path=$failure.Exception.Data['usb_receipt_path']; operation_id=$failure.Exception.Data['usb_operation_id']; response=$failure.Exception.Data['usb_receipt']}
    if ($errorData.response) { $errorData.target = $errorData.response.target }
    try {
        Write-LaunchEvent 'ERROR' "phase=$phase port=$port message=$($failure.Exception.Message)" -Data $errorData -ErrorInfo $errorInfo
    } catch { Write-Host "JSON journal write failed: $($_.Exception.Message)" -ForegroundColor Red }
    Write-Host "ERROR: $($failure.Exception.Message)" -ForegroundColor Red
    throw $failure
} finally {
    try {
        Write-LaunchEvent 'END' "port=$port last_phase=$phase outcome=$outcome" -Data @{port=$port; phase=$phase; outcome=$outcome; completed_ports=@($completedPorts); uart_verified=$false}
    } finally {
        if ($eventWriter) { $eventWriter.Dispose() }
        if ($transcribing) { Stop-Transcript | Out-Null }
    }
}

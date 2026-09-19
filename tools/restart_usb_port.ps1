<#
.SYNOPSIS
Preview or restart exactly one USB serial adapter. Does not open COM.
.DESCRIPTION
Default is read-only preview. Apply requires an exact InstanceId from a fresh
preview. Journal and default receipts are written in the project root.
A non-admin Apply opens one Windows UAC prompt.
See ../docs/USB_COM_RECOVERY.md for operator and AI instructions.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, ParameterSetName = 'Port')]
    [ValidatePattern('^COM[1-9][0-9]*$')]
    [string]$Port,
    [Parameter(Mandatory = $true, ParameterSetName = 'List')]
    [switch]$ListPorts,
    [string]$ExpectedInstanceId,
    [switch]$Apply,
    [string]$ReceiptPath,
    [Parameter(DontShow = $true)]
    [switch]$ElevatedChild
)

$ErrorActionPreference = 'Stop'
$script:UsbRestartScriptPath = $PSCommandPath

function Get-UsbPortTarget {
    param([string]$Port, [string]$ExpectedInstanceId)
    $portPattern = '\(' + [regex]::Escape($Port) + '\)$'
    $devices = @(Get-PnpDevice -PresentOnly -Class Ports -ErrorAction Stop |
        Where-Object { $_.FriendlyName -match $portPattern })
    if ($devices.Count -ne 1) { throw 'Expected exactly one present device for this COM port.' }
    $device = $devices[0]
    if ($device.InstanceId -notmatch '^USB\\[^\\*?]+\\[^\\*?]+$') {
        throw 'Target is not an individual USB serial device.'
    }
    if ($ExpectedInstanceId -and $device.InstanceId -ine $ExpectedInstanceId) {
        throw 'USB identity/mapping changed; restart cancelled.'
    }
    return $device
}

function Test-UsbRestartAdministrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Invoke-UsbDeviceRestart {
    param([string]$InstanceId)
    # pnputil redirects text in the Windows ANSI code page, which may differ
    # from a newly opened PowerShell console's OEM code page (1251 vs 866).
    $previousEncoding = [Console]::OutputEncoding
    $nativeEncoding = [Text.Encoding]::GetEncoding((Get-WinSystemLocale).TextInfo.ANSICodePage)
    try {
        [Console]::OutputEncoding = $nativeEncoding
        $output = & "$env:SystemRoot\System32\pnputil.exe" /restart-device $InstanceId 2>&1
        $code = $LASTEXITCODE
        return [pscustomobject]@{ exit_code = $code; output = ($output | Out-String).Trim(); output_code_page = $nativeEncoding.CodePage }
    } finally {
        [Console]::OutputEncoding = $previousEncoding
    }
}

function New-UsbRestartEncodedCommand {
    param([string]$ScriptPath, [string]$Port, [string]$ExpectedInstanceId, [string]$ReceiptPath)
    # PowerShell literals, then UTF-16 Base64: no cmd.exe or string interpolation
    # of user arguments into executable expressions in the elevated process.
    $toolLiteral = "'" + $ScriptPath.Replace("'", "''") + "'"
    $portLiteral = "'" + $Port.Replace("'", "''") + "'"
    $idLiteral = "'" + $ExpectedInstanceId.Replace("'", "''") + "'"
    $receiptLiteral = "'" + $ReceiptPath.Replace("'", "''") + "'"
    $command = "try { & $toolLiteral -Port $portLiteral -ExpectedInstanceId $idLiteral -Apply -ReceiptPath $receiptLiteral -ElevatedChild | Out-Null; exit 0 } catch { exit 1 }"
    return [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($command))
}

function Start-UsbRestartElevated {
    param([string]$EncodedCommand)
    $shellPath = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
    try {
        $process = Start-Process -FilePath $shellPath -Verb RunAs -WindowStyle Hidden -Wait -PassThru `
            -ArgumentList "-NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -EncodedCommand $EncodedCommand"
        return $process.ExitCode
    } catch {
        throw "Administrator launch failed or UAC was cancelled; no automatic retry. $($_.Exception.Message)"
    }
}

function Invoke-UsbRestartCommand {
    param([string]$Port, [string]$ExpectedInstanceId, [switch]$Apply,
        [string]$ReceiptPath, [switch]$ElevatedChild)
    # The parent owns the journal across UAC; the child only writes the receipt.
    if (-not $Apply -or $ElevatedChild) {
        return Invoke-UsbRestartCore @PSBoundParameters
    }
    $projectRoot = Split-Path -Parent (Split-Path -Parent $script:UsbRestartScriptPath)
    $operationId = [guid]::NewGuid().ToString('N')
    if (-not $ReceiptPath) {
        $ReceiptPath = Join-Path $projectRoot ('usb-restart-' + $operationId + '.json')
    }
    $ReceiptPath = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($ReceiptPath)
    $receiptWasPresent = Test-Path -LiteralPath $ReceiptPath
    $journalPath = Join-Path $projectRoot 'usb-restart.jsonl'
    # Refuse the operation if the journal cannot be opened. Keep a single writer
    # until completion; a concurrent invocation cannot silently interleave runs.
    $stream = [IO.File]::Open($journalPath, [IO.FileMode]::Append,
        [IO.FileAccess]::Write, [IO.FileShare]::Read)
    $writer = [IO.StreamWriter]::new($stream, [Text.UTF8Encoding]::new($false))
    $entry = [ordered]@{
        schema = 1
        operation_id = $operationId
        utc = [DateTime]::UtcNow.ToString('o')
        port = $Port
        expected_target = $ExpectedInstanceId
        receipt_path = $ReceiptPath
        result = 'STARTED'
        uart_verified = $false
    }
    try {
        $writer.WriteLine(($entry | ConvertTo-Json -Depth 8 -Compress))
        $writer.Flush()
        Write-Host "USB restart journal: $journalPath"
        Write-Host "USB restart receipt: $ReceiptPath"
        try {
            $result = Invoke-UsbRestartCore -Port $Port -ExpectedInstanceId $ExpectedInstanceId `
                -Apply -ReceiptPath $ReceiptPath
            $result | Add-Member -NotePropertyName receipt_path -NotePropertyValue $ReceiptPath -Force
            $result | Add-Member -NotePropertyName operation_id -NotePropertyValue $operationId -Force
            $entry.result = $result.result
            $entry.receipt = $result
        } catch {
            $entry.result = 'STOP'
            $entry.error = $_.Exception.Message
            $_.Exception.Data['usb_receipt_path'] = $ReceiptPath
            $_.Exception.Data['usb_operation_id'] = $operationId
            # Attach only newly created evidence for this exact request.
            if (-not $receiptWasPresent -and (Test-Path -LiteralPath $ReceiptPath -PathType Leaf)) {
                try {
                    $failureReceipt = Get-Content -LiteralPath $ReceiptPath -Raw -Encoding UTF8 | ConvertFrom-Json
                    if ($failureReceipt.port -ieq $Port -and $failureReceipt.target -ieq $ExpectedInstanceId) {
                        $entry.receipt = $failureReceipt
                        $_.Exception.Data['usb_receipt'] = $failureReceipt
                    }
                } catch {
                    $entry.receipt_read_error = $_.Exception.Message
                }
            }
            Write-Host "USB restart STOP: port=$Port target=$ExpectedInstanceId error=$($entry.error) receipt=$ReceiptPath"
            # A missing receipt is an unknown outcome, never evidence of success.
            throw
        } finally {
            $entry.utc = [DateTime]::UtcNow.ToString('o')
            $writer.WriteLine(($entry | ConvertTo-Json -Depth 8 -Compress))
            $writer.Flush()
        }
        return $result
    } finally {
        $writer.Dispose()
    }
}

function Invoke-UsbRestartCore {
    param([string]$Port, [string]$ExpectedInstanceId, [switch]$Apply,
        [string]$ReceiptPath, [switch]$ElevatedChild)
    if (-not $Apply -or (Test-UsbRestartAdministrator)) {
        return Restart-SelectedUsbPort -Port $Port -ExpectedInstanceId $ExpectedInstanceId -Apply:$Apply -ReceiptPath $ReceiptPath
    }
    if ($ElevatedChild) { throw 'Elevated child has no administrator token; refusing another UAC request.' }
    # All non-mutating input checks happen before showing UAC.
    if ($Port -notmatch '^COM[1-9][0-9]*$') { throw 'Invalid COM port.' }
    if (-not $ExpectedInstanceId) { throw 'Apply requires ExpectedInstanceId from a fresh preview.' }
    if (-not $ReceiptPath) { throw 'Apply requires a new ReceiptPath.' }
    $null = Get-UsbPortTarget -Port $Port -ExpectedInstanceId $ExpectedInstanceId
    $receiptFullPath = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($ReceiptPath)
    if (Test-Path -LiteralPath $receiptFullPath) { throw 'Receipt already exists; choose a new file.' }
    if (-not (Test-Path -LiteralPath (Split-Path -Parent $receiptFullPath) -PathType Container)) {
        throw 'Receipt directory does not exist.'
    }
    $encoded = New-UsbRestartEncodedCommand -ScriptPath $script:UsbRestartScriptPath -Port $Port `
        -ExpectedInstanceId $ExpectedInstanceId -ReceiptPath $receiptFullPath
    Write-Host "Requesting administrator permission to restart $Port. Confirm the Windows UAC prompt."
    $childExit = Start-UsbRestartElevated -EncodedCommand $encoded
    if (-not (Test-Path -LiteralPath $receiptFullPath -PathType Leaf)) {
        throw "Administrator process exited ($childExit) without a receipt; restart is not confirmed. No automatic retry."
    }
    $result = Get-Content -LiteralPath $receiptFullPath -Raw -Encoding UTF8 | ConvertFrom-Json
    Write-Host ('Elevated receipt: ' + ($result | ConvertTo-Json -Depth 8 -Compress))
    if ($result.target -ine $ExpectedInstanceId -or $result.port -ine $Port) {
        throw 'Administrator receipt target mismatch; restart is not confirmed.'
    }
    if ($childExit -ne 0 -or $result.result -ne 'RESTART_COMMAND_SUCCEEDED' -or $result.exit_code -ne 0) {
        throw "Administrator restart not confirmed; inspect $receiptFullPath. No automatic retry."
    }
    return $result
}

function Restart-SelectedUsbPort {
    param([string]$Port, [string]$ExpectedInstanceId, [switch]$Apply, [string]$ReceiptPath)
    if ($Port -notmatch '^COM[1-9][0-9]*$') { throw 'Invalid COM port.' }
    $device = Get-UsbPortTarget -Port $Port -ExpectedInstanceId $ExpectedInstanceId
    $receipt = [ordered]@{
        schema = 1
        utc = [DateTime]::UtcNow.ToString('o')
        port = $Port.ToUpperInvariant()
        target = [string]$device.InstanceId
        name = [string]$device.FriendlyName
        before_status = [string]$device.Status
        result = 'PREVIEW_ONLY'
        restart_attempted = $false
        uart_verified = $false
        steps = @()
    }
    if (-not $Apply) { return [pscustomobject]$receipt }
    if (-not $ExpectedInstanceId) { throw 'Apply requires ExpectedInstanceId from a fresh preview.' }
    if (-not $ReceiptPath) { throw 'Apply requires a new ReceiptPath.' }
    if (-not (Test-UsbRestartAdministrator)) {
        throw 'Open PowerShell as Administrator. No restart was attempted.'
    }

    # Reserve a new receipt before mutation; never overwrite earlier evidence.
    $receiptFullPath = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($ReceiptPath)
    $stream = [IO.File]::Open($receiptFullPath, [IO.FileMode]::CreateNew,
        [IO.FileAccess]::Write, [IO.FileShare]::Read)
    $writer = [IO.StreamWriter]::new($stream, [Text.UTF8Encoding]::new($false))
    try {
        $receipt.result = 'PREPARED'
        $receipt.steps += [ordered]@{ utc=[DateTime]::UtcNow.ToString('o'); action='PREPARED'; port=$Port; target=$device.InstanceId }
        $writer.Write(($receipt | ConvertTo-Json -Depth 5))
        $writer.Flush()
        # Recheck after opening the receipt, immediately before the native call.
        $null = Get-UsbPortTarget -Port $Port -ExpectedInstanceId $ExpectedInstanceId
        $receipt.restart_attempted = $true
        $receipt.result = 'RESTART_REQUESTED'
        $receipt.command = 'pnputil.exe /restart-device "' + $device.InstanceId + '"'
        $receipt.steps += [ordered]@{ utc=[DateTime]::UtcNow.ToString('o'); action='RESTART_REQUESTED'; command=$receipt.command }
        $writer.BaseStream.Position = 0
        $writer.BaseStream.SetLength(0)
        $writer.Write(($receipt | ConvertTo-Json -Depth 5))
        $writer.Flush()
        $native = Invoke-UsbDeviceRestart -InstanceId $device.InstanceId
        $receipt.exit_code = $native.exit_code
        $receipt.output = $native.output
        $receipt.output_code_page = $native.output_code_page
        $receipt.steps += [ordered]@{ utc=[DateTime]::UtcNow.ToString('o'); action='NATIVE_RETURNED'; exit_code=$native.exit_code; output=$native.output }
        if ($native.exit_code -ne 0) { throw "PnP restart returned exit code $($native.exit_code); check the receipt." }
        $receipt.result = 'RESTART_COMMAND_SUCCEEDED'
        try {
            $after = Get-UsbPortTarget -Port $Port -ExpectedInstanceId $ExpectedInstanceId
            $receipt.after_status = [string]$after.Status
            $receipt.steps += [ordered]@{ utc=[DateTime]::UtcNow.ToString('o'); action='PNP_AFTER'; status=$receipt.after_status; target=$after.InstanceId }
        } catch {
            $receipt.after_error = $_.Exception.Message
            $receipt.steps += [ordered]@{ utc=[DateTime]::UtcNow.ToString('o'); action='PNP_AFTER_ERROR'; error=$receipt.after_error }
        }
    } catch {
        $receipt.result = 'STOP'
        $receipt.error = $_.Exception.Message
        $receipt.steps += [ordered]@{ utc=[DateTime]::UtcNow.ToString('o'); action='STOP'; error=$receipt.error }
        throw
    } finally {
        try {
            $writer.BaseStream.Position = 0
            $writer.BaseStream.SetLength(0)
            $writer.Write(($receipt | ConvertTo-Json -Depth 5))
            $writer.Flush()
        } finally {
            $writer.Dispose()
        }
    }
    return [pscustomobject]$receipt
}

if ($ListPorts) {
    if ($Apply -or $ExpectedInstanceId -or $ReceiptPath -or $ElevatedChild) { throw 'ListPorts is read-only; do not combine it with restart arguments.' }
    Get-PnpDevice -PresentOnly -Class Ports -ErrorAction Stop | ForEach-Object {
        if ($_.InstanceId -match '^USB\\[^\\*?]+\\[^\\*?]+$' -and $_.FriendlyName -match '\((COM[1-9][0-9]*)\)$') {
            [pscustomobject]@{ port=$Matches[1]; target=$_.InstanceId; name=$_.FriendlyName; status=$_.Status }
        }
    } | Sort-Object port
} else {
    Invoke-UsbRestartCommand -Port $Port -ExpectedInstanceId $ExpectedInstanceId -Apply:$Apply -ReceiptPath $ReceiptPath -ElevatedChild:$ElevatedChild
}

"""Run the portable PowerShell recovery script with all hardware calls mocked."""
from pathlib import Path
import json
import shutil
import subprocess
import tempfile
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
HARNESS = r'''
param([string]$ToolPath, [string]$EvidenceDir)
$ErrorActionPreference = 'Stop'
$script:devices = @([pscustomobject]@{
    InstanceId = 'USB\VID_1A86&PID_7523\TEST'; FriendlyName = 'USB-SERIAL CH340 (COM4)'; Status = 'OK'
})
$script:nativeCalls = 0
$script:admin = $false
$script:nativeCode = 0
$script:reads = 0
$script:changeOnRead = 0
$script:elevations = 0
$script:elevationMode = 'cancel'
$script:elevationReceipt = ''
function Start-Process {
    param([string]$FilePath, [string]$Verb, [string]$WindowStyle,
        [switch]$Wait, [switch]$PassThru, [string]$ArgumentList)
    $script:elevations++
    if ($Verb -ne 'RunAs' -or $WindowStyle -ne 'Hidden' -or -not $Wait -or -not $PassThru) {
        throw 'Wrong elevation options'
    }
    if ($ArgumentList -notmatch ' -EncodedCommand ([A-Za-z0-9+/=]+)$') { throw 'Unsafe command transport' }
    $command = [Text.Encoding]::Unicode.GetString([Convert]::FromBase64String($Matches[1]))
    $null = [scriptblock]::Create($command)
    if ($script:elevationMode -eq 'cancel') { throw [ComponentModel.Win32Exception]::new(1223) }
    if ($script:elevationMode -eq 'missing') { return [pscustomobject]@{ ExitCode = 1 } }
    $result = 'RESTART_COMMAND_SUCCEEDED'; $code = 0
    if ($script:elevationMode -eq 'failure') { $result = 'STOP'; $code = 5 }
    $savedTarget = 'USB\VID_1A86&PID_7523\TEST'
    if ($script:elevationMode -eq 'mismatch') { $savedTarget = 'USB\OTHER\DEVICE' }
    [ordered]@{ port='COM4'; target=$savedTarget; result=$result; exit_code=$code; uart_verified=$false } |
        ConvertTo-Json | Set-Content -LiteralPath $script:elevationReceipt -Encoding UTF8
    return [pscustomobject]@{ ExitCode = $code }
}
function Get-PnpDevice {
    [CmdletBinding()]
    param([switch]$PresentOnly, [string]$Class)
    if (-not $PresentOnly -or $Class -ne 'Ports') { throw 'Unexpected discovery scope' }
    $script:reads++
    if ($script:changeOnRead -and $script:reads -ge $script:changeOnRead) { return @() }
    return $script:devices
}
function Assert-True([bool]$Condition, [string]$Message) {
    if (-not $Condition) { throw $Message }
}
function Expect-Failure([scriptblock]$Action) {
    $failed = $false
    try { & $Action | Out-Null } catch { $failed = $true }
    Assert-True $failed 'Expected refusal'
}
# Dot-source ONLY preview; Get-PnpDevice is already a fake. No COM or native call.
$originalDevices = $script:devices
$script:devices += [pscustomobject]@{InstanceId='ACPI\TEST'; FriendlyName='Serial (COM7)'; Status='OK'}
$listed = @(. $ToolPath -ListPorts)
Assert-True ($listed.Count -eq 1 -and $listed[0].port -eq 'COM4') 'Discovery included a non-USB port'
Expect-Failure { & $ToolPath -ListPorts -Apply }
$script:devices = $originalDevices
$preview = . $ToolPath -Port COM4
Assert-True ($preview.result -eq 'PREVIEW_ONLY') 'Preview result'
Assert-True (-not $preview.restart_attempted) 'Preview must not mutate'
$projectRoot = Split-Path -Parent (Split-Path -Parent $ToolPath)
$journalPath = Join-Path $projectRoot 'usb-restart.jsonl'
Assert-True (-not (Test-Path -LiteralPath $journalPath)) 'Preview created journal'
function Test-UsbRestartAdministrator { return $script:admin }
function Invoke-UsbDeviceRestart {
    param([string]$InstanceId)
    Assert-True ($InstanceId -ceq 'USB\VID_1A86&PID_7523\TEST') 'Native target changed'
    $script:nativeCalls++
    return [pscustomobject]@{ exit_code = $script:nativeCode; output = 'mock native output' }
}
$target = $preview.target
$receipt = Join-Path $EvidenceDir 'receipt one.json'
Expect-Failure { Restart-SelectedUsbPort -Port 'COM*' }
Expect-Failure { Restart-SelectedUsbPort -Port COM5 }
Expect-Failure { Restart-SelectedUsbPort -Port COM4 -ExpectedInstanceId 'USB\OTHER\TEST' -Apply -ReceiptPath $receipt }
Expect-Failure { Restart-SelectedUsbPort -Port COM4 -Apply -ReceiptPath $receipt }
Expect-Failure { Restart-SelectedUsbPort -Port COM4 -ExpectedInstanceId $target -Apply }
Expect-Failure { Restart-SelectedUsbPort -Port COM4 -ExpectedInstanceId $target -Apply -ReceiptPath $receipt }
Assert-True (-not (Test-Path -LiteralPath $receipt)) 'No receipt before admin gate'
Assert-True ($script:nativeCalls -eq 0) 'Refusals must not restart'
$script:admin = $true
Expect-Failure { Restart-SelectedUsbPort -Port COM4 -ExpectedInstanceId $target -Apply -ReceiptPath (Join-Path $EvidenceDir 'missing/receipt.json') }
$original = $script:devices
$script:devices = @($original[0], $original[0])
Expect-Failure { Restart-SelectedUsbPort -Port COM4 }
$script:devices = @([pscustomobject]@{ InstanceId='ACPI\TEST'; FriendlyName='Serial (COM4)'; Status='OK' })
Expect-Failure { Restart-SelectedUsbPort -Port COM4 }
$script:devices = $original
# Changed mapping during the preflight must stop before native mutation.
$script:reads = 0; $script:changeOnRead = 2
Expect-Failure { Restart-SelectedUsbPort -Port COM4 -ExpectedInstanceId $target -Apply -ReceiptPath $receipt }
$saved = Get-Content -Raw -LiteralPath $receipt | ConvertFrom-Json
Assert-True ($saved.result -eq 'STOP' -and -not $saved.restart_attempted) 'Mapping refusal receipt'
Assert-True ($script:nativeCalls -eq 0) 'Race must not restart'
$script:changeOnRead = 0
# Existing evidence must never be overwritten.
$before = [IO.File]::ReadAllText($receipt)
Expect-Failure { Restart-SelectedUsbPort -Port COM4 -ExpectedInstanceId $target -Apply -ReceiptPath $receipt }
Assert-True ([IO.File]::ReadAllText($receipt) -ceq $before) 'Receipt overwritten'
Assert-True ($script:nativeCalls -eq 0) 'Existing receipt must stop restart'
$receipt = Join-Path $EvidenceDir 'success.json'
$result = Restart-SelectedUsbPort -Port com4 -ExpectedInstanceId $target -Apply -ReceiptPath $receipt
$saved = Get-Content -Raw -LiteralPath $receipt | ConvertFrom-Json
Assert-True ($script:nativeCalls -eq 1) 'Exactly one native restart expected'
Assert-True ($result.result -eq 'RESTART_COMMAND_SUCCEEDED' -and $saved.exit_code -eq 0) 'Success receipt'
Assert-True ($saved.restart_attempted -and -not $saved.uart_verified) 'Do not claim UART acceptance'
Assert-True ($saved.after_status -eq 'OK') 'PnP post-read'
Assert-True (($saved.steps.action -join ',') -eq 'PREPARED,RESTART_REQUESTED,NATIVE_RETURNED,PNP_AFTER') 'Action history incomplete'
Assert-True ($saved.command -match 'pnputil.exe /restart-device') 'Native command missing'
$script:nativeCode = 5
$receipt = Join-Path $EvidenceDir 'failure.json'
Expect-Failure { Restart-SelectedUsbPort -Port COM4 -ExpectedInstanceId $target -Apply -ReceiptPath $receipt }
$saved = Get-Content -Raw -LiteralPath $receipt | ConvertFrom-Json
Assert-True ($saved.result -eq 'STOP' -and $saved.exit_code -eq 5 -and $saved.restart_attempted) 'Native failure receipt'
Assert-True ($script:nativeCalls -eq 2) 'No automatic retry'
# The public entry point raises UAC exactly once, and never from preview.
$script:admin = $false
$null = Invoke-UsbRestartCommand -Port COM4
Assert-True ($script:elevations -eq 0) 'Preview raised UAC'
Expect-Failure { Invoke-UsbRestartCommand -Port COM4 -Apply -ElevatedChild }
Expect-Failure { Invoke-UsbRestartCommand -Port COM4 -Apply }
Expect-Failure { Invoke-UsbRestartCommand -Port COM4 -ExpectedInstanceId $target -Apply -ReceiptPath $receipt }
Assert-True ($script:elevations -eq 0) 'Invalid input or child recursively raised UAC'
$script:elevationReceipt = Join-Path $EvidenceDir 'uac cancelled.json'
Expect-Failure { Invoke-UsbRestartCommand -Port COM4 -ExpectedInstanceId $target -Apply -ReceiptPath $script:elevationReceipt }
Assert-True ($script:elevations -eq 1 -and -not (Test-Path -LiteralPath $script:elevationReceipt)) 'UAC cancellation retried or wrote receipt'
foreach ($mode in @('missing', 'failure', 'mismatch')) {
    $script:elevationMode = $mode
    $script:elevationReceipt = Join-Path $EvidenceDir ($mode + '-uac.json')
    Expect-Failure { Invoke-UsbRestartCommand -Port COM4 -ExpectedInstanceId $target -Apply -ReceiptPath $script:elevationReceipt }
}
$script:elevationMode = 'success'
$script:elevationReceipt = Join-Path $EvidenceDir 'uac success.json'
$result = Invoke-UsbRestartCommand -Port COM4 -ExpectedInstanceId $target -Apply -ReceiptPath $script:elevationReceipt
Assert-True ($result.result -eq 'RESTART_COMMAND_SUCCEEDED' -and $script:elevations -eq 5) 'UAC success not returned'
Assert-True ($script:nativeCalls -eq 2) 'Non-admin parent performed native restart'
$script:admin = $true; $script:nativeCode = 0
$null = Invoke-UsbRestartCommand -Port COM4 -ExpectedInstanceId $target -Apply -ReceiptPath (Join-Path $EvidenceDir 'already admin.json')
Assert-True ($script:nativeCalls -eq 3 -and $script:elevations -eq 5) 'Admin path unnecessarily raised UAC'
# Public calls journal the whole operation, including failures before a receipt.
$entries = @(Get-Content -LiteralPath $journalPath -Encoding UTF8 | ForEach-Object { $_ | ConvertFrom-Json })
Assert-True ($entries.Count -eq 16) 'Expected STARTED and final records for eight parent Apply calls'
for ($i = 0; $i -lt $entries.Count; $i += 2) {
    Assert-True ($entries[$i].result -eq 'STARTED') 'Missing start record'
    Assert-True ($entries[$i].operation_id -eq $entries[$i + 1].operation_id) 'Operation IDs differ'
}
Assert-True ($entries[4 + 1].error -match 'UAC was cancelled') 'UAC cancellation not journalled'
Assert-True ($entries[-1].receipt.exit_code -eq 0 -and -not $entries[-1].uart_verified) 'Success evidence missing'
$journalBefore = [IO.File]::ReadAllText($journalPath)
$null = Invoke-UsbRestartCommand -Port COM4
Assert-True ([IO.File]::ReadAllText($journalPath) -ceq $journalBefore) 'Preview changed journal'
# Default receipt is rooted at the relocated project, independent of cwd.
$null = Invoke-UsbRestartCommand -Port COM4 -ExpectedInstanceId $target -Apply
$last = Get-Content -LiteralPath $journalPath -Tail 1 | ConvertFrom-Json
Assert-True ((Split-Path -Parent $last.receipt_path) -eq $projectRoot) 'Default receipt used cwd'
Assert-True (Test-Path -LiteralPath $last.receipt_path) 'Default receipt missing'
Assert-True ([IO.File]::ReadAllText($journalPath).StartsWith($journalBefore)) 'Journal history overwritten'
$successReceipt = $last.receipt_path
$successBefore = [IO.File]::ReadAllText($successReceipt)
Expect-Failure { Invoke-UsbRestartCommand -Port COM4 -ExpectedInstanceId $target -Apply -ReceiptPath $successReceipt }
Assert-True ([IO.File]::ReadAllText($successReceipt) -ceq $successBefore) 'Public call overwrote receipt'
$callsBefore = $script:nativeCalls
$held = [IO.File]::Open($journalPath, [IO.FileMode]::Open, [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
try {
    Expect-Failure { Invoke-UsbRestartCommand -Port COM4 -ExpectedInstanceId $target -Apply }
} finally { $held.Dispose() }
Assert-True ($script:nativeCalls -eq $callsBefore) 'Restart happened without writable journal'
$script:nativeCode = 5
try {
    $null = Invoke-UsbRestartCommand -Port COM4 -ExpectedInstanceId $target -Apply
    throw 'Expected native failure'
} catch {
    Assert-True ($_.Exception.Data['usb_receipt'].exit_code -eq 5) 'Machine-readable exception lost native result'
    Assert-True ([bool]$_.Exception.Data['usb_receipt_path']) 'Machine-readable exception lost receipt path'
}
$last = Get-Content -LiteralPath $journalPath -Tail 1 | ConvertFrom-Json
$failedReceipt = Get-Content -LiteralPath $last.receipt_path -Raw | ConvertFrom-Json
Assert-True ($last.result -eq 'STOP' -and $last.error -match 'exit code 5') 'Native failure missing from journal'
Assert-True ($failedReceipt.restart_attempted -and $failedReceipt.exit_code -eq 5) 'Failure receipt missing'
Assert-True ($script:nativeCalls -eq $callsBefore + 1) 'Failed operation retried'
$script:nativeCode = 0
# Execute encoded payload against a harmless stub in a relocated path containing
# spaces, apostrophe, ampersand and dollar: values must arrive literally.
$stub = Join-Path $EvidenceDir "stub ' & `$ tool.ps1"
$stubOutput = Join-Path $EvidenceDir "receipt ' & `$ literal.json"
@'
param([string]$Port, [string]$ExpectedInstanceId, [switch]$Apply, [string]$ReceiptPath, [switch]$ElevatedChild)
@{port=$Port; target=$ExpectedInstanceId; apply=[bool]$Apply; child=[bool]$ElevatedChild} |
 ConvertTo-Json | Set-Content -LiteralPath $ReceiptPath -Encoding UTF8
'@ | Set-Content -LiteralPath $stub -Encoding UTF8
$encoded = New-UsbRestartEncodedCommand -ScriptPath $stub -Port COM4 -ExpectedInstanceId $target -ReceiptPath $stubOutput
$childShell = (Get-Process -Id $PID).Path
& $childShell -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -EncodedCommand $encoded
Assert-True ($LASTEXITCODE -eq 0) 'Encoded stub failed'
$saved = Get-Content -LiteralPath $stubOutput -Raw | ConvertFrom-Json
Assert-True ($saved.target -ceq $target -and $saved.apply -and $saved.child -and $saved.port -eq 'COM4') 'Argument quoting changed values'
Write-Output 'USB recovery mocked checks PASS; hardware NOT_RUN'
'''


class UsbRestartTests(unittest.TestCase):
    def test_interactive_launcher_logs_cancel_success_and_errors(self):
        shell = shutil.which('powershell') or shutil.which('pwsh')
        if shell is None:
            self.skipTest('PowerShell unavailable')
        with tempfile.TemporaryDirectory(prefix='usb-launcher-') as folder:
            root = Path(folder)
            portable = root / 'portable tester' / 'tools'
            portable.mkdir(parents=True)
            launcher = portable / 'restart_usb_interactive.ps1'
            shutil.copyfile(ROOT / 'tools/restart_usb_interactive.ps1', launcher)
            # Replace the entire hardware-facing script with an inert fixture.
            (portable / 'restart_usb_port.ps1').write_text(r'''
param([string]$Port, [string]$ExpectedInstanceId, [switch]$Apply, [switch]$ListPorts)
if ($ListPorts) {
    if ($global:scenario -eq 'no_devices') { return }
    [pscustomobject]@{port='COM4'; target='USB\MOCK\TEST'; status='OK'}
    [pscustomobject]@{port='COM5'; target='USB\MOCK\SECOND'; status='OK'}
    return
}
if ($global:scenario -eq 'preview_failure') { throw 'Mock preview failure' }
if ($Apply) {
    $expected = if ($Port -eq 'COM4') { 'USB\MOCK\TEST' } else { 'USB\MOCK\SECOND' }
    if ($ExpectedInstanceId -cne $expected) { throw 'Wrong target' }
    Add-Content -LiteralPath (Join-Path $PSScriptRoot 'calls.txt') -Value $Port
    if ($global:scenario -eq 'apply_failure') {
        $error = [Exception]::new('Mock apply failure')
        $error.Data['usb_receipt_path'] = 'failure.json'
        $error.Data['usb_operation_id'] = 'mock-operation'
        $error.Data['usb_receipt'] = [pscustomobject]@{port=$Port; target=$expected; result='STOP'; exit_code=5; output="native error`nsecond line"}
        throw $error
    }
    [pscustomobject]@{port=$Port; target=$expected; result='RESTART_COMMAND_SUCCEEDED'; exit_code=0; after_status='OK'; output="native output`nsecond line"}
} else { [pscustomobject]@{port=$Port; target=$ExpectedInstanceId; result='PREVIEW_ONLY'} }
''', encoding='utf-8')
            harness = root / 'harness.ps1'
            harness.write_text(r'''
param([string]$Launcher, [string]$Scenario)
$global:scenario = $Scenario
$global:answers = [Collections.Generic.Queue[string]]::new()
switch ($Scenario) {
    'blank' { $global:answers.Enqueue('') }
    'cancel' { $global:answers.Enqueue('') }
    default { $global:answers.Enqueue('RESTART ALL') }
}
function Read-Host { param([string]$Prompt); return $global:answers.Dequeue() }
$failed = $false
try {
    switch ($Scenario) {
        'invalid' { & $Launcher -Port 'COM*' }
        'preview_only' { & $Launcher -All -PreviewOnly }
        'selected' { & $Launcher -Port COM5 -Apply }
        default { & $Launcher }
    }
} catch { $failed = $true }
if ($failed -ne ($Scenario -in @('invalid', 'preview_failure', 'apply_failure', 'no_devices'))) { exit 1 }
''', encoding='utf-8')
            previous = ''
            previous_event_count = 0
            for scenario in ('blank', 'invalid', 'cancel', 'preview_failure', 'success', 'apply_failure', 'preview_only', 'selected', 'no_devices'):
                with self.subTest(scenario=scenario):
                    result = subprocess.run(
                        [shell, '-NoLogo', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
                         '-File', str(harness), '-Launcher', str(launcher), '-Scenario', scenario],
                        cwd=root, capture_output=True, text=True, timeout=15,
                    )
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    log = (portable.parent / 'usb-restart.log').read_text(encoding='utf-8-sig')
                    self.assertTrue(log.startswith(previous), 'Earlier log was overwritten')
                    added = log[len(previous):]
                    self.assertIn('USB restart launcher', added)
                    if scenario in ('blank', 'cancel'):
                        self.assertIn('CANCELLED', added)
                    elif scenario in ('invalid', 'preview_failure', 'apply_failure', 'no_devices'):
                        self.assertIn('ERROR:', added)
                    elif scenario == 'preview_only':
                        self.assertIn('action=PREVIEW_ONLY', added)
                    else:
                        self.assertIn('Completed.', added)
                    previous = log
                    events_path = portable.parent / 'usb-restart-events.jsonl'
                    events = [json.loads(line) for line in events_path.read_text(encoding='utf-8-sig').splitlines()]
                    current = events[previous_event_count:]
                    previous_event_count = len(events)
                    visible = [json.loads(line[5:]) for line in result.stdout.splitlines() if line.startswith('JSON ')]
                    self.assertEqual(visible, current)
                    self.assertEqual([row['sequence'] for row in current], list(range(1, len(current) + 1)))
                    self.assertEqual(len({row['launch_id'] for row in current}), 1)
                    self.assertEqual(current[0]['action'], 'START')
                    self.assertEqual(current[-1]['action'], 'END')
                    if scenario in ('invalid', 'preview_failure', 'apply_failure', 'no_devices'):
                        self.assertEqual(current[-1]['data']['outcome'], 'ERROR')
                        failure = next(row for row in current if row['action'] == 'ERROR')
                        self.assertTrue(failure['error']['message'])
                        if scenario == 'apply_failure':
                            self.assertEqual(failure['data']['response']['exit_code'], 5)
                            self.assertEqual(failure['data']['response']['output'], 'native error\nsecond line')
                    if scenario in ('success', 'selected'):
                        self.assertEqual(current[-1]['data']['outcome'], 'COMPLETED')
                        responses = [row for row in current if row['action'] == 'RESULT']
                        self.assertTrue(responses)
                        self.assertEqual(responses[0]['data']['response']['output'], 'native output\nsecond line')
                    reader = subprocess.run(
                        [sys.executable, '-B', str(ROOT / 'tools/read_usb_restart_events.py'),
                         '--input', str(events_path), '--last-launch'], capture_output=True, text=True,
                    )
                    self.assertEqual(reader.returncode, 0, reader.stderr)
                    self.assertEqual([json.loads(line) for line in reader.stdout.splitlines()], current)
            self.assertEqual((portable / 'calls.txt').read_text().splitlines(), ['COM4', 'COM5', 'COM4', 'COM5'])
            reader = subprocess.run(
                [sys.executable, '-B', str(ROOT / 'tools/read_usb_restart_events.py'),
                 '--input', str(events_path), '--last-launch', '--errors'], capture_output=True, text=True,
            )
            self.assertEqual(reader.returncode, 0, reader.stderr)
            self.assertEqual([json.loads(line)['action'] for line in reader.stdout.splitlines()], ['ERROR'])
            with events_path.open('a', encoding='utf-8') as stream:
                stream.write('{broken\n')
            reader = subprocess.run(
                [sys.executable, '-B', str(ROOT / 'tools/read_usb_restart_events.py'), '--input', str(events_path)],
                capture_output=True, text=True,
            )
            self.assertEqual(reader.returncode, 1)
            self.assertEqual(json.loads(reader.stderr)['type'], 'usb_restart_reader_error')
            self.assertEqual(reader.stdout, '')

    def test_portable_preview_guards_receipts_and_native_result(self):
        shell = shutil.which('powershell') or shutil.which('pwsh')
        if shell is None:
            self.skipTest('PowerShell unavailable; USB recovery test not run')
        with tempfile.TemporaryDirectory(prefix='usb-recovery-') as folder:
            root = Path(folder)
            portable = root / 'portable tester' / 'tools'
            portable.mkdir(parents=True)
            tool = portable / 'restart_usb_port.ps1'
            shutil.copyfile(ROOT / 'tools/restart_usb_port.ps1', tool)
            harness = root / 'harness.ps1'
            harness.write_text(HARNESS, encoding='utf-8')
            result = subprocess.run(
                [shell, '-NoLogo', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
                 '-File', str(harness), '-ToolPath', str(tool), '-EvidenceDir', str(root)],
                cwd=root, capture_output=True, text=True, timeout=25,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('mocked checks PASS', result.stdout)


if __name__ == '__main__':
    unittest.main()

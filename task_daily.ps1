$ErrorActionPreference = "Continue"
$root = "C:\Users\86150\Desktop\personal-assistant"
$py   = "E:\Anaconda\python.exe"
$log  = Join-Path $root "logs\daily.log"
New-Item -ItemType Directory -Force (Join-Path $root "logs") | Out-Null
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

function RunStep {
    param([string]$Name, [string]$Script, [string]$Arg)
    if ($Arg) {
        $step = & $py -X utf8 (Join-Path $root $Script) $Arg 2>&1
    } else {
        $step = & $py -X utf8 (Join-Path $root $Script) 2>&1
    }
    $txt = ($step | Out-String) -replace "`n", "`r`n"
    Add-Content -Path $log -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $Name" -Encoding UTF8
    Add-Content -Path $log -Value $txt -Encoding UTF8
}

Add-Content -Path $log -Value "==== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') START ====" -Encoding UTF8
RunStep -Name "FETCH"    -Script "tools\tool_imap.py" -Arg "24"
RunStep -Name "CLASSIFY" -Script "classify.py"
RunStep -Name "REPORT"   -Script "report.py"
Add-Content -Path $log -Value "==== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') END ====" -Encoding UTF8

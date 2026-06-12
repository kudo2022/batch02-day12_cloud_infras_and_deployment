param(
    [ValidateSet("start", "status", "stop")]
    [string]$Action = "start",
    [int]$Port = 8501
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$StateDir = Join-Path $Root ".quick_demo"
$StreamlitPidFile = Join-Path $StateDir "streamlit.pid"
$CloudflaredPidFile = Join-Path $StateDir "cloudflared.pid"
$StreamlitOut = Join-Path $StateDir "streamlit.out"
$StreamlitErr = Join-Path $StateDir "streamlit.err"
$CloudflaredOut = Join-Path $StateDir "cloudflared.out"
$CloudflaredErr = Join-Path $StateDir "cloudflared.err"

function Ensure-StateDir {
    if (-not (Test-Path $StateDir)) {
        New-Item -ItemType Directory -Path $StateDir | Out-Null
    }
}

function Get-PythonExe {
    $candidates = @(
        (Join-Path $Root "env\Scripts\python.exe"),
        (Join-Path $Root ".venv\Scripts\python.exe")
    )
    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }
    throw "Khong tim thay python.exe trong env\\Scripts hoac .venv\\Scripts."
}

function Get-CloudflaredExe {
    $candidates = @(
        (Join-Path $Root "cloudflared_extract\cloudflared\cloudflared.exe"),
        (Join-Path $Root "cloudflared.exe")
    )
    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }
    throw "Khong tim thay cloudflared.exe."
}

function Remove-IfExists([string]$Path) {
    if (Test-Path $Path) {
        Remove-Item -LiteralPath $Path -Force
    }
}

function Get-PidFromFile([string]$PidFile) {
    if (-not (Test-Path $PidFile)) {
        return $null
    }
    $raw = (Get-Content -LiteralPath $PidFile -Raw).Trim()
    if (-not $raw) {
        return $null
    }
    return [int]$raw
}

function Get-ProcessSafe([int]$ProcessId) {
    try {
        return Get-Process -Id $ProcessId -ErrorAction Stop
    } catch {
        return $null
    }
}

function Stop-ProcessIfRunning([string]$PidFile) {
    $pidValue = Get-PidFromFile $PidFile
    if ($null -eq $pidValue) {
        return
    }
    $proc = Get-ProcessSafe $pidValue
    if ($null -ne $proc) {
        Stop-Process -Id $pidValue -Force
    }
    Remove-IfExists $PidFile
}

function Wait-ForLocalApp([int]$AppPort, [int]$TimeoutSec = 30) {
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        try {
            $resp = Invoke-WebRequest -Uri "http://127.0.0.1:$AppPort" -UseBasicParsing -TimeoutSec 4
            if ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 500) {
                return $true
            }
        } catch {
        }
        Start-Sleep -Seconds 1
    }
    return $false
}

function Wait-ForTunnelUrl([int]$TimeoutSec = 30) {
    $pattern = 'https://[a-z0-9-]+\.trycloudflare\.com'
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        if (Test-Path $CloudflaredErr) {
            $match = Select-String -Path $CloudflaredErr -Pattern $pattern | Select-Object -First 1
            if ($match) {
                return $match.Matches[0].Value
            }
        }
        Start-Sleep -Seconds 1
    }
    return $null
}

function Show-Status {
    $streamlitPid = Get-PidFromFile $StreamlitPidFile
    $cloudflaredPid = Get-PidFromFile $CloudflaredPidFile
    $streamlitRunning = $false
    $cloudflaredRunning = $false

    if ($null -ne $streamlitPid) {
        $streamlitRunning = $null -ne (Get-ProcessSafe $streamlitPid)
    }
    if ($null -ne $cloudflaredPid) {
        $cloudflaredRunning = $null -ne (Get-ProcessSafe $cloudflaredPid)
    }

    $url = Wait-ForTunnelUrl -TimeoutSec 1

    Write-Output ""
    Write-Output "Quick demo status"
    Write-Output "-----------------"
    Write-Output "Streamlit   : $streamlitRunning (PID: $streamlitPid)"
    Write-Output "Cloudflared : $cloudflaredRunning (PID: $cloudflaredPid)"
    Write-Output "Local URL   : http://localhost:$Port"
    if ($url) {
        Write-Output "Public URL  : $url"
    } else {
        Write-Output "Public URL  : chua tim thay trong log"
    }
    Write-Output ""
    Write-Output "Logs:"
    Write-Output "  $StreamlitErr"
    Write-Output "  $CloudflaredErr"
}

function Start-Demo {
    Ensure-StateDir

    Stop-ProcessIfRunning $CloudflaredPidFile
    Stop-ProcessIfRunning $StreamlitPidFile

    Remove-IfExists $StreamlitOut
    Remove-IfExists $StreamlitErr
    Remove-IfExists $CloudflaredOut
    Remove-IfExists $CloudflaredErr

    $pythonExe = Get-PythonExe
    $cloudflaredExe = Get-CloudflaredExe

    $streamlitProc = Start-Process `
        -FilePath $pythonExe `
        -ArgumentList '-m', 'streamlit', 'run', 'streamlit_app.py', '--server.port', "$Port", '--server.address', '0.0.0.0' `
        -WorkingDirectory $Root `
        -RedirectStandardOutput $StreamlitOut `
        -RedirectStandardError $StreamlitErr `
        -WindowStyle Hidden `
        -PassThru
    Set-Content -LiteralPath $StreamlitPidFile -Value $streamlitProc.Id

    if (-not (Wait-ForLocalApp -AppPort $Port -TimeoutSec 30)) {
        throw "Streamlit khong len tren localhost:$Port. Xem log: $StreamlitErr"
    }

    $cloudflaredProc = Start-Process `
        -FilePath $cloudflaredExe `
        -ArgumentList 'tunnel', '--url', "http://localhost:$Port", '--no-autoupdate' `
        -WorkingDirectory $Root `
        -RedirectStandardOutput $CloudflaredOut `
        -RedirectStandardError $CloudflaredErr `
        -WindowStyle Hidden `
        -PassThru
    Set-Content -LiteralPath $CloudflaredPidFile -Value $cloudflaredProc.Id

    $publicUrl = Wait-ForTunnelUrl -TimeoutSec 30
    if (-not $publicUrl) {
        throw "Tunnel da start nhung chua lay duoc public URL. Xem log: $CloudflaredErr"
    }

    Write-Output ""
    Write-Output "Agent demo da san sang."
    Write-Output "Local URL  : http://localhost:$Port"
    Write-Output "Public URL : $publicUrl"
    Write-Output ""
    Write-Output "Lenh huu ich:"
    Write-Output "  .\\quick_demo.ps1 status"
    Write-Output "  .\\quick_demo.ps1 stop"
}

function Stop-Demo {
    Stop-ProcessIfRunning $CloudflaredPidFile
    Stop-ProcessIfRunning $StreamlitPidFile
    Write-Output "Da dung Streamlit va Cloudflare Tunnel."
}

switch ($Action) {
    "start" { Start-Demo }
    "status" { Show-Status }
    "stop" { Stop-Demo }
}

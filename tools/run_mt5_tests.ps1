<#
  รัน Strategy Tester ของ MT5 เทียบ EA หลายรุ่นอัตโนมัติ แล้วสรุปผลเป็นตาราง

  วิธีใช้ (PowerShell):
    1. ปิดโปรแกรม MT5 ก่อน (ถ้าเปิดอยู่ Strategy Tester จากคำสั่งจะไม่ทำงาน)
    2. cd ไปที่โฟลเดอร์ repo นี้ แล้วรัน
         powershell -ExecutionPolicy Bypass -File tools\run_mt5_tests.ps1 `
           -Terminal "C:\Program Files\XM Global MT5\terminal64.exe" `
           -DataDir  "C:\Users\<ชื่อผู้ใช้>\AppData\Roaming\MetaQuotes\Terminal\<รหัสยาว>"
       DataDir ดูได้จาก MT5: เมนู File > Open Data Folder

  ค่าที่ปรับได้: -Symbol -From -To -Deposit -Leverage -Model
    Model: 0 = Every tick, 1 = 1 minute OHLC, 4 = Every tick based on real ticks
#>
param(
    [Parameter(Mandatory = $true)][string]$Terminal,
    [Parameter(Mandatory = $true)][string]$DataDir,
    [string]$Symbol   = "GOLD#",
    [string]$From     = "2024.01.01",
    [string]$To       = "2026.11.22",
    [int]$Deposit     = 10000,
    [string]$Leverage = "1:500",
    [int]$Model       = 4
)

$ErrorActionPreference = "Stop"
$Repo    = Split-Path -Parent $PSScriptRoot
$Experts = Join-Path $DataDir "MQL5\Experts"
$Sets    = Join-Path $DataDir "MQL5\Profiles\Tester"
$Reports = Join-Path $Repo "results\mt5_reports"
$Editor  = Join-Path (Split-Path -Parent $Terminal) "metaeditor64.exe"

foreach ($p in @($Terminal, $Editor, $Experts)) {
    if (-not (Test-Path $p)) { throw "ไม่พบ $p - ตรวจ -Terminal และ -DataDir" }
}
if (Get-Process terminal64 -ErrorAction SilentlyContinue) {
    throw "MT5 ยังเปิดอยู่ ปิดโปรแกรม MT5 ก่อนแล้วรันใหม่"
}
New-Item -ItemType Directory -Force -Path $Sets, $Reports | Out-Null

# ---------- 1) คัดลอกและ compile EA ----------
$eas = @("ICT_Wyckoff_Gold_EA", "ICT_Wyckoff_Gold_EA_v111")
foreach ($ea in $eas) {
    $src = Join-Path $Repo "mql5\$ea.mq5"
    $dst = Join-Path $Experts "$ea.mq5"
    Copy-Item $src $dst -Force
    $log = Join-Path $Reports "$ea.compile.log"
    Start-Process -FilePath $Editor -ArgumentList "/compile:`"$dst`"", "/log:`"$log`"" -Wait -WindowStyle Hidden
    $txt = Get-Content $log -Raw -Encoding Unicode -ErrorAction SilentlyContinue
    if (-not $txt) { $txt = Get-Content $log -Raw -ErrorAction SilentlyContinue }
    if ($txt -match "(\d+) errors?") {
        Write-Host "compile $ea : $($Matches[0])"
        if ([int]$Matches[1] -gt 0) { throw "compile $ea ไม่ผ่าน ดู $log" }
    } else {
        Write-Host "compile $ea : อ่านผลไม่ได้ ดู $log"
    }
}

# ---------- 2) ชุดที่จะรัน: ชื่อ, EA, ค่า input ที่ต่างจากค่าเริ่มต้น ----------
$runs = @(
    @{ Name = "A_v111_Profit";        EA = "ICT_Wyckoff_Gold_EA_v111"; Inputs = @{} },
    @{ Name = "B_v121_default";       EA = "ICT_Wyckoff_Gold_EA";      Inputs = @{} },
    @{ Name = "C_v121_no_fomc";       EA = "ICT_Wyckoff_Gold_EA";      Inputs = @{ InpSkipFomc = "false" } },
    @{ Name = "D_v121_risk05";        EA = "ICT_Wyckoff_Gold_EA";      Inputs = @{ InpRiskPct = "0.5" } }
)

$rows = @()
foreach ($r in $runs) {
    # ไฟล์ค่า input (.set): บรรทัด ชื่อ=ค่า, ค่าที่ไม่ระบุใช้ค่าเริ่มต้นในโค้ด
    $setName = "ICTWY_$($r.Name).set"
    $setLines = @()
    foreach ($k in $r.Inputs.Keys) { $setLines += "$k=$($r.Inputs[$k])" }
    $setLines | Out-File -FilePath (Join-Path $Sets $setName) -Encoding Unicode

    $report = Join-Path $Reports $r.Name
    Remove-Item "$report.htm*" -ErrorAction SilentlyContinue
    $ini = Join-Path $Reports "$($r.Name).ini"
    @(
        "[Tester]",
        "Expert=$($r.EA)",
        "ExpertParameters=$setName",
        "Symbol=$Symbol",
        "Period=M5",
        "Model=$Model",
        "FromDate=$From",
        "ToDate=$To",
        "Deposit=$Deposit",
        "Currency=USD",
        "Leverage=$Leverage",
        "Optimization=0",
        "Visual=0",
        "Report=$report",
        "ReplaceReport=1",
        "ShutdownTerminal=1"
    ) | Out-File -FilePath $ini -Encoding ASCII

    Write-Host "กำลังรัน $($r.Name) ... (หน้าต่าง MT5 จะเปิดและปิดเองเมื่อเสร็จ)"
    $t0 = Get-Date
    Start-Process -FilePath $Terminal -ArgumentList "/config:`"$ini`"" -Wait
    Write-Host ("  เสร็จใน {0:N0} นาที" -f ((Get-Date) - $t0).TotalMinutes)

    # ---------- 3) อ่านผลจากรายงาน ----------
    $file = Get-ChildItem "$report.htm*" -ErrorAction SilentlyContinue | Select-Object -First 1
    $row = [ordered]@{ Run = $r.Name; NetProfit = ""; PF = ""; Trades = ""; BalanceDD = ""; EquityDD = "" }
    if ($file) {
        $html = Get-Content $file.FullName -Raw -Encoding Unicode
        function Pick($label) {
            if ($html -match "$label[^<]*</td>\s*<td[^>]*>\s*(?:<b>)?([^<]+)") { return $Matches[1].Trim() }
            return ""
        }
        $row.NetProfit = Pick "Total Net Profit"
        $row.PF        = Pick "Profit Factor"
        $row.Trades    = Pick "Total Trades"
        $row.BalanceDD = Pick "Balance Drawdown Maximal"
        $row.EquityDD  = Pick "Equity Drawdown Maximal"
    } else {
        $row.NetProfit = "ไม่พบรายงาน"
    }
    $rows += [pscustomobject]$row
}

$rows | Format-Table -AutoSize
$rows | Export-Csv (Join-Path $Reports "summary.csv") -NoTypeInformation -Encoding UTF8
Write-Host "รายงานทั้งหมดอยู่ที่ $Reports"

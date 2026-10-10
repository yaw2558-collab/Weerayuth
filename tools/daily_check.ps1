# ThaiCustoms daily health check — รันอัตโนมัติตอนเปิดเครื่องผ่าน Scheduled Task "ThaiCustomsDailyCheck"
# ตรวจ: gateway (หน้าเว็บ + packages + stats) และเว็บโชว์สินค้า แล้วโชว์ toast + เขียน log
# หมายเหตุ: /healthz บน Cloud Run โดน Google Frontend ดัก (404) จึงเช็ค / กับ /billing/packages แทน
# คีย์แอดมิน (สำหรับ /admin/stats) อยู่นอก repo: ~/.thai-customs-check/admin_key.txt (ไม่มี = ข้ามข้อนั้น)

$ErrorActionPreference = "Stop"
$GATEWAY = "https://gateway-1008099094873.asia-southeast1.run.app"
$SITE = "https://yaw2558-collab.github.io/Weerayuth/"
$TIMEOUT = 30

$BaseDir = Join-Path $HOME ".thai-customs-check"
$LogDir = Join-Path $BaseDir "logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$LogFile = Join-Path $LogDir "check-$Stamp.log"
$AdminKeyFile = Join-Path $BaseDir "admin_key.txt"

$script:logLines = @()
function Log($msg) {
  $line = "[{0}] {1}" -f (Get-Date -Format "HH:mm:ss"), $msg
  $script:logLines += $line
  Write-Output $line
}

function Get-Url($url, $headers) {
  $r = Invoke-WebRequest -Uri $url -Headers $headers -TimeoutSec $TIMEOUT -UseBasicParsing
  return @{ Status = [int]$r.StatusCode; Text = [string]$r.Content }
}

function Show-Toast($title, $body) {
  try {
    [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
    $tpl = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent(
      [Windows.UI.Notifications.ToastTemplateType]::ToastText02)
    $texts = $tpl.GetElementsByTagName("text")
    $texts.Item(0).AppendChild($tpl.CreateTextNode($title)) | Out-Null
    $texts.Item(1).AppendChild($tpl.CreateTextNode($body)) | Out-Null
    $notifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("ThaiCustomsDailyCheck")
    $notifier.Show([Windows.UI.Notifications.ToastNotification]::new($tpl))
  } catch {
    Log ("toast ล้มเหลว (ข้ามได้): " + $_.Exception.Message)
  }
}

function Invoke-Suite {
  $results = @()

  # 1. Gateway หน้าเว็บ
  try {
    $r = Get-Url "$GATEWAY/"
    if ($r.Status -ne 200) { throw "HTTP $($r.Status)" }
    foreach ($m in @("mailto:yaw2558@gmail.com", "AW-955537182", "getReader")) {
      if ($r.Text -notmatch [regex]::Escape($m)) { throw "marker หาย: $m" }
    }
    $results += @{ Name = "gateway/"; Ok = $true; Detail = "200 + markers ครบ" }
  } catch { $results += @{ Name = "gateway/"; Ok = $false; Detail = $_.Exception.Message } }

  # 2. Gateway packages (live prices ต้องครบ 3 ตัว)
  try {
    $r = Get-Url "$GATEWAY/billing/packages"
    if ($r.Status -ne 200) { throw "HTTP $($r.Status)" }
    $n = ((($r.Text | ConvertFrom-Json).packages) | Measure-Object).Count
    if ($n -ne 3) { throw "packages=$n (ต้องเป็น 3)" }
    $results += @{ Name = "packages"; Ok = $true; Detail = "live 3 แพ็กเกจ" }
  } catch { $results += @{ Name = "packages"; Ok = $false; Detail = $_.Exception.Message } }

  # 3. Gateway stats (ต้องมี admin key — ไม่มีคีย์ = ข้าม)
  if (Test-Path $AdminKeyFile) {
    try {
      $key = (Get-Content $AdminKeyFile -Raw).Trim()
      $r = Get-Url "$GATEWAY/admin/stats" @{ "x-admin-key" = $key }
      if ($r.Status -ne 200) { throw "HTTP $($r.Status)" }
      $s = $r.Text | ConvertFrom-Json
      $results += @{ Name = "stats"; Ok = $true; Detail = ("users {0} / q {1} / live {2} / fail {3}" -f $s.users, $s.queries, $s.revenue_live_thb, $s.payments_failed) }
    } catch { $results += @{ Name = "stats"; Ok = $false; Detail = $_.Exception.Message } }
  } else {
    $results += @{ Name = "stats"; Ok = $true; Skipped = $true; Detail = "ข้าม (ไม่มี admin_key.txt)" }
  }

  # 4. เว็บโชว์สินค้า (GitHub Pages)
  try {
    $r = Get-Url $SITE
    if ($r.Status -ne 200) { throw "HTTP $($r.Status)" }
    foreach ($m in @("mailto:yaw2558@gmail.com", "ThaiCustoms")) {
      if ($r.Text -notmatch [regex]::Escape($m)) { throw "marker หาย: $m" }
    }
    $results += @{ Name = "site"; Ok = $true; Detail = "200 + markers ครบ" }
  } catch { $results += @{ Name = "site"; Ok = $false; Detail = $_.Exception.Message } }

  return $results
}

$sw = [Diagnostics.Stopwatch]::StartNew()
$results = Invoke-Suite
$failed = @($results | Where-Object { -not $_.Ok })
if ($failed.Count -gt 0) {
  # ตอนบูตเน็ตอาจยังไม่พร้อม — รอ 30 วิแล้วลองใหม่อีกรอบก่อนตัดสิน
  Log ("รอบแรกfail ({0}) — รอ 30 วิแล้วลองใหม่" -f ($failed.Name -join ","))
  Start-Sleep -Seconds 30
  $results = Invoke-Suite
  $failed = @($results | Where-Object { -not $_.Ok })
}
$sw.Stop()

foreach ($r in $results) {
  $icon = if ($r.Ok) { "PASS" } else { "FAIL" }
  Log ("[{0}] {1}: {2}" -f $icon, $r.Name, $r.Detail)
}
$ok = @($results | Where-Object { $_.Ok }).Count
$total = $results.Count
$summary = "ThaiCustoms: {0} {1}/{2} ({3:n0}วิ)" -f $(if ($failed.Count -eq 0) { "ปกติ" } else { "ผิดปกติ!" }), $ok, $total, $sw.Elapsed.TotalSeconds
Log $summary

# เก็บ log + ประวัติย่อ (ลบ log เกิน 30 วัน)
$script:logLines | Set-Content -Path $LogFile -Encoding UTF8
$summary | Set-Content -Path (Join-Path $BaseDir "last_result.txt") -Encoding UTF8
"{0},{1},{2},{3}" -f $Stamp, $ok, $total, (($failed | ForEach-Object { $_.Name }) -join ";") |
  Add-Content -Path (Join-Path $BaseDir "history.csv") -Encoding UTF8
Get-ChildItem $LogDir -Filter "check-*.log" -ErrorAction SilentlyContinue |
  Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-30) } | Remove-Item -Force

$body = if ($failed.Count -eq 0) {
  ($results | ForEach-Object { "{0}: {1}" -f $_.Name, $_.Detail }) -join "`n"
} else {
  "ล้มเหลว: {0} — ดู {1}" -f ($failed.Name -join ", "), $LogFile
}
Show-Toast $summary $body

if ($failed.Count -gt 0) { exit 1 } else { exit 0 }

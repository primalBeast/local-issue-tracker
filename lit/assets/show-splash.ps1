# Borderless splash until Local Issue Tracker's main window is ready.
# Closed when the named event LocalIssueTracker.SplashClose is signaled.
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$created = $false
$mutex = New-Object System.Threading.Mutex($true, "LocalIssueTracker.Splash", [ref]$created)
if (-not $created) { exit 0 }

Add-Type @"
using System.Runtime.InteropServices;
public static class LitAppId {
  [DllImport("shell32.dll", CharSet = CharSet.Unicode)]
  public static extern int SetCurrentProcessExplicitAppUserModelID(string AppID);
}
"@
[void][LitAppId]::SetCurrentProcessExplicitAppUserModelID("primalBeast.LocalIssueTracker")

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$splashPng = Join-Path $here "splash.png"
$iconIco = Join-Path $here "app.ico"

$close = New-Object System.Threading.EventWaitHandle(
  $false,
  [System.Threading.EventResetMode]::ManualReset,
  "LocalIssueTracker.SplashClose"
)
$close.Reset() | Out-Null

$form = New-Object System.Windows.Forms.Form
$form.Text = "Local Issue Tracker"
$form.FormBorderStyle = [System.Windows.Forms.FormBorderStyle]::None
$form.StartPosition = [System.Windows.Forms.FormStartPosition]::CenterScreen
$form.ClientSize = New-Object System.Drawing.Size 720, 430
$form.BackColor = [System.Drawing.Color]::FromArgb(11, 13, 18)
$form.TopMost = $true
$form.ShowInTaskbar = $true
$form.ControlBox = $false
if (Test-Path $iconIco) {
  $form.Icon = New-Object System.Drawing.Icon($iconIco)
}

$picture = New-Object System.Windows.Forms.PictureBox
$picture.Location = New-Object System.Drawing.Point 0, 0
$picture.Size = New-Object System.Drawing.Size 720, 378
$picture.SizeMode = [System.Windows.Forms.PictureBoxSizeMode]::Zoom
$picture.BackColor = $form.BackColor
if (Test-Path $splashPng) {
  $picture.Image = [System.Drawing.Image]::FromFile($splashPng)
}
$form.Controls.Add($picture)

$bar = New-Object System.Windows.Forms.Panel
$bar.Location = New-Object System.Drawing.Point 0, 378
$bar.Size = New-Object System.Drawing.Size 720, 52
$bar.BackColor = [System.Drawing.Color]::FromArgb(18, 21, 28)
$form.Controls.Add($bar)

$caption = New-Object System.Windows.Forms.Label
$caption.Text = "Local Issue Tracker"
$caption.ForeColor = [System.Drawing.Color]::FromArgb(232, 234, 237)
$caption.Font = New-Object System.Drawing.Font("Segoe UI", 12, [System.Drawing.FontStyle]::Bold)
$caption.Location = New-Object System.Drawing.Point 18, 14
$caption.AutoSize = $true
$bar.Controls.Add($caption)

$status = New-Object System.Windows.Forms.Label
$status.Text = "Starting..."
$status.ForeColor = [System.Drawing.Color]::FromArgb(110, 168, 254)
$status.Font = New-Object System.Drawing.Font("Segoe UI", 10)
$status.Location = New-Object System.Drawing.Point 560, 16
$status.AutoSize = $true
$bar.Controls.Add($status)

$script:elapsed = 0
$timer = New-Object System.Windows.Forms.Timer
$timer.Interval = 200
$timer.Add_Tick({
  $script:elapsed += $timer.Interval
  if ($close.WaitOne(0) -or $script:elapsed -gt 90000) {
    $timer.Stop()
    $form.Close()
  }
})
$form.Add_Shown({ $timer.Start() })
$form.Add_FormClosed({
  $timer.Dispose()
  if ($picture.Image) { $picture.Image.Dispose() }
  $close.Dispose()
  try { $mutex.ReleaseMutex() } catch {}
  $mutex.Dispose()
})

[System.Windows.Forms.Application]::EnableVisualStyles()
[System.Windows.Forms.Application]::Run($form)

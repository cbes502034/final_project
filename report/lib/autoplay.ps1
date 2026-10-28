# 讓簡報裡的影片一進到那一頁就自動播放（同一頁有好幾段就一起播）。
# pptxgenjs 做不到，借用這台電腦上的 PowerPoint：打開、每段影片加一個「播放」動畫（上一個之後）、存檔。
#   powershell -NoProfile -ExecutionPolicy Bypass -File report/lib/autoplay.ps1 <簡報.pptx>
# ⚠️ 只動這一份簡報：PowerPoint 本來就開著（使用者在用）就不關它。
param([Parameter(Mandatory = $true)][string]$Path)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$full = (Resolve-Path -LiteralPath $Path).Path
$wasRunning = [bool](Get-Process POWERPNT -ErrorAction SilentlyContinue)
$app = New-Object -ComObject PowerPoint.Application
try {
    # Open(檔名, 唯讀, 無標題, 開視窗)：0 = msoFalse
    $pres = $app.Presentations.Open($full, 0, 0, 0)
    $n = 0
    foreach ($slide in $pres.Slides) {
        foreach ($shape in $slide.Shapes) {
            if ($shape.Type -eq 16) {                       # msoMedia
                # 83 = msoAnimEffectMediaPlay；3 = msoAnimTriggerAfterPrevious：一進到這頁就播，同一頁的幾段一起播
                [void]$slide.TimeLine.MainSequence.AddEffect($shape, 83, 0, 3)
                $n++
            }
        }
    }
    $pres.Save()
    $pres.Close()
    "影片自動播放：$n 段"
}
finally {
    if (-not $wasRunning -and $app.Presentations.Count -eq 0) { $app.Quit() }
    [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($app)
}

# 在 Windows PowerShell 或 CMD 中运行此脚本（不要用 Cursor 内置终端）
# 原因：Cursor 会自动添加 "Co-authored-by: Cursor" 导致 cursoragent 出现在 Contributors

Write-Host "修复 GitHub Contributors - 移除 cursoragent" -ForegroundColor Cyan
Write-Host ""

$repoPath = "c:\Users\Root\Downloads\LNG\LNG_Arbitrage_Monitor"
Set-Location $repoPath

# 修改最近一次提交，移除 Co-authored-by
$msg = @"
Initial commit: Global LNG Arbitrage Monitor - Complete project with LNG economics calculator, NLP sentiment analysis, and professional visualizations
"@

git commit --amend -m $msg --no-verify

Write-Host ""
Write-Host "检查提交信息（不应包含 Co-authored-by）：" -ForegroundColor Yellow
git log -1 --format=%B
Write-Host ""

$confirm = Read-Host "确认无误后按 Enter 强制推送到 GitHub，或输入 q 退出"
if ($confirm -eq "q") { exit }

git push origin main --force

Write-Host ""
Write-Host "完成！请刷新 GitHub 页面查看 Contributors。" -ForegroundColor Green

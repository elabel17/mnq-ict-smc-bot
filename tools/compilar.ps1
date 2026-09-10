# Compila la estrategia contra los ensamblados reales de NinjaTrader 8.
# Sirve como puerta: ningun archivo se copia a NinjaTrader sin pasar por aqui.
$csc = "C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
$ntb = "C:\Program Files\NinjaTrader 8\bin"
$cus = "C:\Users\diazl\Documents\NinjaTrader 8\bin\Custom"
$wpf = "C:\Windows\Microsoft.NET\Framework64\v4.0.30319\WPF"
$src = $args[0]
& $csc /nologo /t:library /out:"$env:TEMP\nt_check.dll" `
  "/r:$cus\NinjaTrader.Custom.dll" "/r:$ntb\NinjaTrader.Core.dll" "/r:$ntb\NinjaTrader.Gui.dll" `
  "/r:$wpf\WindowsBase.dll" "/r:$wpf\PresentationCore.dll" "/r:$wpf\PresentationFramework.dll" `
  /r:System.dll /r:System.Core.dll /r:System.Xml.dll /r:System.Drawing.dll `
  /r:System.ComponentModel.DataAnnotations.dll $src
if ($LASTEXITCODE -eq 0) { Write-Output "COMPILA LIMPIO" } else { Write-Output "FALLA" }

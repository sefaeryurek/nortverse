' Nortverse - .bat dosyasini PENCERE ACMADAN calistirir ve bitmesini bekler.
' Gorev Zamanlayici bunu cagirir: wscript.exe run-hidden.vbs "C:\...\script.bat"
' Pencere olmadigi icin kullanici yanlislikla kapatip isi yarida birakamaz.
If WScript.Arguments.Count < 1 Then WScript.Quit 2
Set shell = CreateObject("WScript.Shell")
exitCode = shell.Run("cmd.exe /c """ & WScript.Arguments(0) & """", 0, True)
WScript.Quit exitCode

' Runs auto_news_crawler.py silently in the background without opening a command prompt window
Set objShell = CreateObject("WScript.Shell")
Set objFSO = CreateObject("Scripting.FileSystemObject")
strCurrentDir = objFSO.GetParentFolderName(WScript.ScriptFullName)

strPythonw = strCurrentDir & "\.venv\Scripts\pythonw.exe"
If Not objFSO.FileExists(strPythonw) Then
    strPythonw = "pythonw.exe"
End If

strCmd = """" & strPythonw & """ """ & strCurrentDir & "\auto_news_crawler.py"""
objShell.Run strCmd, 0, False

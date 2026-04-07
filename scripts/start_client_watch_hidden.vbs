Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
scriptPath = fso.BuildPath(fso.GetParentFolderName(WScript.ScriptFullName), "start_client_watch.bat")

If WScript.Arguments.Count > 0 Then
    deviceId = WScript.Arguments(0)
    shell.Run Chr(34) & scriptPath & Chr(34) & " " & Chr(34) & deviceId & Chr(34), 0, False
Else
    shell.Run Chr(34) & scriptPath & Chr(34), 0, False
End If

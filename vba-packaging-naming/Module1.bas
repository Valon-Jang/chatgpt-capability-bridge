Attribute VB_Name = "Module1"
Option Explicit

Public NextTick As Date
Public Const PW As String = "Naming2026!"
Public Const MAIN_IDX As Long = 1
Public Const CAND_IDX As Long = 2
Public Const VOTE_IDX As Long = 3
Public Const USER_IDX As Long = 4
Public Const CFG_IDX As Long = 5

Public Function MainWs() As Worksheet
    Set MainWs = ThisWorkbook.Worksheets(MAIN_IDX)
End Function

Public Function CandWs() As Worksheet
    Set CandWs = ThisWorkbook.Worksheets(CAND_IDX)
End Function

Public Function VoteWs() As Worksheet
    Set VoteWs = ThisWorkbook.Worksheets(VOTE_IDX)
End Function

Public Function UserWs() As Worksheet
    Set UserWs = ThisWorkbook.Worksheets(USER_IDX)
End Function

Public Function CfgWs() As Worksheet
    Set CfgWs = ThisWorkbook.Worksheets(CFG_IDX)
End Function

Public Function Cfg(ByVal key As String) As String
    Dim ws As Worksheet, lastRow As Long, i As Long
    Set ws = CfgWs()
    lastRow = ws.Cells(ws.Rows.Count, 1).End(xlUp).Row
    For i = 2 To lastRow
        If CStr(ws.Cells(i, 1).Value) = key Then
            Cfg = CStr(ws.Cells(i, 2).Value)
            Exit Function
        End If
    Next i
    Cfg = key
End Function

Public Function StageNow() As Long
    Dim t As Date
    t = Now
    If t < DateSerial(2026, 9, 10) Then
        StageNow = 1
    ElseIf t < DateSerial(2026, 9, 10) + TimeSerial(9, 0, 0) Then
        StageNow = 2
    ElseIf t < DateSerial(2026, 9, 10) + TimeSerial(12, 0, 0) Then
        StageNow = 3
    Else
        StageNow = 4
    End If
End Function

Public Function StageLabel(ByVal st As Long) As String
    Select Case st
        Case 1: StageLabel = Cfg("StageProposal")
        Case 2: StageLabel = Cfg("StageWaiting")
        Case 3: StageLabel = Cfg("StageVoting")
        Case Else: StageLabel = Cfg("StageResults")
    End Select
End Function

Public Function CleanText(ByVal s As String) As String
    On Error Resume Next
    CleanText = Application.WorksheetFunction.Trim(CStr(s))
    If Err.Number <> 0 Then
        Err.Clear
        CleanText = Trim$(CStr(s))
    End If
    On Error GoTo 0
End Function

Public Function Norm(ByVal s As String) As String
    Norm = LCase$(CleanText(s))
End Function

Public Sub InitNaming()
    On Error GoTo EH
    Application.ScreenUpdating = False
    Randomize
    PrepareSheets
    RefreshUI
    ScheduleTick
Done:
    Application.ScreenUpdating = True
    Exit Sub
EH:
    MsgBox Err.Description, vbExclamation
    Resume Done
End Sub

Public Sub PrepareSheets()
    Dim i As Long, m As Worksheet
    On Error Resume Next
    ThisWorkbook.Unprotect Password:=PW
    For i = 2 To ThisWorkbook.Worksheets.Count
        ThisWorkbook.Worksheets(i).Visible = xlSheetVeryHidden
        ThisWorkbook.Worksheets(i).Unprotect Password:=PW
        ThisWorkbook.Worksheets(i).Protect Password:=PW, UserInterfaceOnly:=True
    Next i
    Set m = MainWs()
    m.Visible = xlSheetVisible
    m.Unprotect Password:=PW
    m.Cells.Locked = True
    m.Range("B9:D9").Locked = False
    m.Range("B12:E12").Locked = False
    m.Columns("Z:Z").Hidden = True
    m.Protect Password:=PW, UserInterfaceOnly:=True
    ThisWorkbook.Protect Password:=PW, Structure:=True, Windows:=False
    On Error GoTo 0
End Sub

Public Sub ScheduleTick()
    On Error Resume Next
    CancelSchedules
    NextTick = Now + TimeSerial(0, 0, 15)
    Application.OnTime EarliestTime:=NextTick, Procedure:="NamingTick", Schedule:=True
    On Error GoTo 0
End Sub

Public Sub CancelSchedules()
    On Error Resume Next
    If NextTick > 0 Then
        Application.OnTime EarliestTime:=NextTick, Procedure:="NamingTick", Schedule:=False
    End If
    NextTick = 0
    On Error GoTo 0
End Sub

Public Sub NamingTick()
    On Error Resume Next
    RefreshUI
    ScheduleTick
    On Error GoTo 0
End Sub

Public Sub HandleHyperlink(ByVal rowNum As Long)
    On Error GoTo EH
    If rowNum = 6 Then
        RefreshUI
        Exit Sub
    End If
    If rowNum = 12 Then
        SubmitProposal
        Exit Sub
    End If
    If StageNow() = 3 And rowNum >= 22 Then
        ToggleVote rowNum
    End If
    Exit Sub
EH:
    MsgBox Err.Description, vbExclamation
End Sub

Public Sub RefreshUI()
    Dim m As Worksheet, st As Long, uname As String
    On Error GoTo EH
    Application.ScreenUpdating = False
    Set m = MainWs()
    st = StageNow()
    uname = CleanText(CStr(m.Range("B9").Value))
    m.Unprotect Password:=PW
    m.Range("B6").Value = StageLabel(st)
    SetActionLink m.Range("G6:H6"), Cfg("Refresh"), RGB(237, 241, 245), RGB(35, 49, 65)
    m.Range("A15").Value = Cfg("FinalCandidates") & vbLf & CStr(CandidateCount()) & " " & Cfg("CountUnit")
    If st = 1 Then
        m.Range("A12").Value = Cfg("Candidate")
        SetActionLink m.Range("F12:H12"), Cfg("Register"), RGB(37, 99, 235), RGB(255, 255, 255)
        m.Range("B12:E12").Interior.Color = RGB(255, 255, 255)
    Else
        On Error Resume Next
        m.Range("F12:H12").Hyperlinks.Delete
        On Error GoTo EH
        m.Range("F12:H12").Value = ""
        m.Range("B12:E12").Interior.Color = RGB(244, 246, 248)
    End If
    ClearDynamic
    Select Case st
        Case 1: RenderProposal uname
        Case 2: RenderWaiting
        Case 3: RenderVoting uname
        Case 4: RenderResults
    End Select
    m.Range("B9:D9").Locked = False
    m.Range("B12:E12").Locked = False
    m.Protect Password:=PW, UserInterfaceOnly:=True
Done:
    Application.ScreenUpdating = True
    Exit Sub
EH:
    On Error Resume Next
    MainWs().Protect Password:=PW, UserInterfaceOnly:=True
    On Error GoTo 0
    MsgBox Err.Description, vbExclamation
    Resume Done
End Sub

Private Sub ClearDynamic()
    Dim m As Worksheet
    Set m = MainWs()
    On Error Resume Next
    m.Range("A21:H1000").Hyperlinks.Delete
    m.Range("A21:H1000").UnMerge
    m.Range("A21:H1000").Clear
    m.Range("Z21:Z1000").ClearContents
    On Error GoTo 0
End Sub

Private Sub SetActionLink(ByVal rng As Range, ByVal label As String, ByVal fillColor As Long, ByVal fontColor As Long)
    Dim m As Worksheet
    Set m = MainWs()
    On Error Resume Next
    rng.Hyperlinks.Delete
    rng.UnMerge
    rng.Merge
    On Error GoTo 0
    rng.Value = label
    rng.Interior.Color = fillColor
    rng.Font.Bold = True
    rng.Font.Color = fontColor
    rng.HorizontalAlignment = xlCenter
    rng.VerticalAlignment = xlCenter
    rng.Locked = False
    m.Hyperlinks.Add Anchor:=rng.Cells(1, 1), Address:="", SubAddress:="'" & m.Name & "'!$Z$1", TextToDisplay:=label
End Sub

Private Sub FormatListRow(ByVal rng As Range, Optional ByVal fillColor As Long = -1)
    With rng
        .Borders.LineStyle = xlContinuous
        .Borders.Color = RGB(223, 229, 234)
        .Borders.Weight = xlThin
        If fillColor <> -1 Then .Interior.Color = fillColor
        .Font.Size = 11
        .VerticalAlignment = xlCenter
        .WrapText = True
    End With
End Sub

Private Sub RenderProposal(ByVal uname As String)
    Dim m As Worksheet, c As Worksheet, lastRow As Long, i As Long, outRow As Long, key As String
    Set m = MainWs()
    Set c = CandWs()
    m.Range("A19").Value = Cfg("ProposalHeader")
    If Len(uname) = 0 Then
        m.Range("A21:H22").Merge
        m.Range("A21").Value = Cfg("MsgEnterName")
        FormatListRow m.Range("A21:H22"), RGB(238, 245, 255)
        Exit Sub
    End If
    key = Norm(uname)
    outRow = 21
    lastRow = c.Cells(c.Rows.Count, 1).End(xlUp).Row
    For i = 2 To lastRow
        If Norm(CStr(c.Cells(i, 4).Value)) = key Then
            m.Range("A" & outRow & ":H" & outRow).Merge
            m.Cells(outRow, 1).Value = CStr(c.Cells(i, 2).Value)
            FormatListRow m.Range("A" & outRow & ":H" & outRow), RGB(255, 255, 255)
            m.Rows(outRow).RowHeight = 24
            outRow = outRow + 1
        End If
    Next i
    If outRow = 21 Then
        m.Range("A21:H22").Merge
        m.Range("A21").Value = Cfg("None")
        FormatListRow m.Range("A21:H22"), RGB(248, 250, 252)
    End If
End Sub

Private Sub RenderWaiting()
    Dim m As Worksheet, c As Worksheet, lastRow As Long, i As Long, outRow As Long
    Set m = MainWs()
    Set c = CandWs()
    m.Range("A19").Value = Cfg("WaitingHeader")
    m.Range("A21:H22").Merge
    m.Range("A21").Value = Cfg("WaitingMessage")
    FormatListRow m.Range("A21:H22"), RGB(238, 245, 255)
    outRow = 24
    lastRow = c.Cells(c.Rows.Count, 1).End(xlUp).Row
    For i = 2 To lastRow
        m.Range("A" & outRow & ":H" & outRow).Merge
        m.Cells(outRow, 1).Value = CStr(c.Cells(i, 2).Value)
        FormatListRow m.Range("A" & outRow & ":H" & outRow), RGB(255, 255, 255)
        outRow = outRow + 1
    Next i
End Sub

Private Sub RenderVoting(ByVal uname As String)
    Dim m As Worksheet, c As Worksheet, lastRow As Long, i As Long, outRow As Long
    Dim userKey As String, csv As String, cid As String, selected As Boolean
    Set m = MainWs()
    Set c = CandWs()
    m.Range("A19").Value = Cfg("VotingHeader")
    m.Range("A21:H21").Merge
    m.Range("A21").Value = Cfg("VotingMessage")
    FormatListRow m.Range("A21:H21"), RGB(238, 245, 255)
    If Len(uname) = 0 Then
        m.Range("A23:H24").Merge
        m.Range("A23").Value = Cfg("MsgEnterName")
        FormatListRow m.Range("A23:H24"), RGB(255, 248, 232)
        Exit Sub
    End If
    userKey = Norm(uname)
    csv = GetVoteCsv(userKey)
    outRow = 23
    lastRow = c.Cells(c.Rows.Count, 1).End(xlUp).Row
    For i = 2 To lastRow
        cid = CStr(c.Cells(i, 1).Value)
        selected = CsvHas(csv, cid)
        m.Range("A" & outRow & ":E" & outRow).Merge
        m.Cells(outRow, 1).Value = CStr(c.Cells(i, 2).Value)
        FormatListRow m.Range("A" & outRow & ":E" & outRow), IIf(selected, RGB(244, 248, 255), RGB(255, 255, 255))
        m.Cells(outRow, 26).Value = cid
        If selected Then
            SetActionLink m.Range("F" & outRow & ":H" & outRow), Cfg("Selected"), RGB(37, 99, 235), RGB(255, 255, 255)
        Else
            SetActionLink m.Range("F" & outRow & ":H" & outRow), Cfg("Select"), RGB(237, 241, 245), RGB(35, 49, 65)
        End If
        outRow = outRow + 1
    Next i
End Sub

Private Sub RenderResults()
    Dim arr As Variant, n As Long, m As Worksheet, i As Long, outRow As Long
    Set m = MainWs()
    m.Range("A19").Value = Cfg("ResultsHeader")
    BuildRanking arr, n
    If n = 0 Then
        m.Range("A21:H22").Merge
        m.Range("A21").Value = Cfg("None")
        FormatListRow m.Range("A21:H22"), RGB(248, 250, 252)
        Exit Sub
    End If
    RenderTopCard arr, n, 1, m.Range("A21:B24"), RGB(255, 247, 214)
    If n >= 2 Then RenderTopCard arr, n, 2, m.Range("C21:E24"), RGB(241, 245, 249)
    If n >= 3 Then RenderTopCard arr, n, 3, m.Range("F21:H24"), RGB(255, 239, 222)
    outRow = 27
    m.Cells(outRow, 1).Value = Cfg("Rank")
    m.Range("B" & outRow & ":D" & outRow).Merge
    m.Cells(outRow, 2).Value = Cfg("Candidate")
    m.Cells(outRow, 5).Value = Cfg("Votes")
    m.Cells(outRow, 6).Value = Cfg("Proposer")
    m.Range("G" & outRow & ":H" & outRow).Merge
    m.Cells(outRow, 7).Value = Cfg("Voters")
    With m.Range("A" & outRow & ":H" & outRow)
        .Interior.Color = RGB(51, 65, 85)
        .Font.Color = RGB(255, 255, 255)
        .Font.Bold = True
        .HorizontalAlignment = xlCenter
        .Borders.LineStyle = xlContinuous
        .Borders.Color = RGB(223, 229, 234)
    End With
    For i = 1 To n
        outRow = outRow + 1
        m.Cells(outRow, 1).Value = RankText(arr, i, n)
        m.Range("B" & outRow & ":D" & outRow).Merge
        m.Cells(outRow, 2).Value = CStr(arr(i, 2))
        m.Cells(outRow, 5).Value = CLng(arr(i, 3))
        m.Cells(outRow, 6).Value = CStr(arr(i, 4))
        m.Range("G" & outRow & ":H" & outRow).Merge
        If Len(CStr(arr(i, 5))) = 0 Then
            m.Cells(outRow, 7).Value = Cfg("None")
        Else
            m.Cells(outRow, 7).Value = CStr(arr(i, 5))
        End If
        FormatListRow m.Range("A" & outRow & ":H" & outRow), RGB(255, 255, 255)
        m.Rows(outRow).RowHeight = 30
    Next i
End Sub

Private Sub RenderTopCard(ByRef arr As Variant, ByVal n As Long, ByVal idx As Long, ByVal rng As Range, ByVal fillColor As Long)
    If idx > n Then Exit Sub
    On Error Resume Next
    rng.UnMerge
    rng.Merge
    On Error GoTo 0
    rng.Value = RankText(arr, idx, n) & vbLf & CStr(arr(idx, 2)) & vbLf & CStr(arr(idx, 3)) & " " & Cfg("VoteUnit") & vbLf & Cfg("Proposer") & ": " & CStr(arr(idx, 4))
    rng.Interior.Color = fillColor
    rng.Font.Bold = True
    rng.Font.Size = 12
    rng.HorizontalAlignment = xlCenter
    rng.VerticalAlignment = xlCenter
    rng.WrapText = True
    rng.Borders.LineStyle = xlContinuous
    rng.Borders.Color = RGB(223, 229, 234)
End Sub

Public Sub SubmitProposal()
    Dim m As Worksheet, c As Worksheet, uname As String, cname As String, key As String
    Dim lastRow As Long, i As Long, newRow As Long, cid As String
    If StageNow() <> 1 Then
        MsgBox Cfg("MsgProposalClosed"), vbInformation
        Exit Sub
    End If
    Set m = MainWs()
    Set c = CandWs()
    uname = CleanText(CStr(m.Range("B9").Value))
    cname = CleanText(CStr(m.Range("B12").Value))
    If Len(uname) = 0 Then
        MsgBox Cfg("MsgEnterName"), vbInformation
        Exit Sub
    End If
    If Len(cname) = 0 Then
        MsgBox Cfg("MsgEnterCandidate"), vbInformation
        Exit Sub
    End If
    key = Norm(cname)
    lastRow = c.Cells(c.Rows.Count, 1).End(xlUp).Row
    For i = 2 To lastRow
        If CStr(c.Cells(i, 3).Value) = key Then
            MsgBox Cfg("MsgDuplicate"), vbExclamation
            Exit Sub
        End If
    Next i
    EnsureUser uname
    newRow = lastRow + 1
    cid = NewCandidateId()
    c.Cells(newRow, 1).Value = cid
    c.Cells(newRow, 2).Value = cname
    c.Cells(newRow, 3).Value = key
    c.Cells(newRow, 4).Value = uname
    c.Cells(newRow, 5).Value = Now
    m.Range("B12").Value = ""
    On Error Resume Next
    ThisWorkbook.Save
    On Error GoTo 0
    MsgBox Cfg("MsgRegistered"), vbInformation
    RefreshUI
End Sub

Private Function NewCandidateId() As String
    NewCandidateId = Format$(Now, "yyyymmddhhnnss") & "_" & Format$(CLng(Timer * 1000), "00000000") & "_" & Format$(Int(Rnd() * 1000000), "000000")
End Function

Private Function CandidateCount() As Long
    Dim c As Worksheet, lastRow As Long
    Set c = CandWs()
    lastRow = c.Cells(c.Rows.Count, 1).End(xlUp).Row
    If lastRow < 2 Then CandidateCount = 0 Else CandidateCount = lastRow - 1
End Function

Private Sub EnsureUser(ByVal uname As String)
    Dim u As Worksheet, key As String, lastRow As Long, i As Long, newRow As Long
    Set u = UserWs()
    key = Norm(uname)
    lastRow = u.Cells(u.Rows.Count, 1).End(xlUp).Row
    For i = 2 To lastRow
        If CStr(u.Cells(i, 1).Value) = key Then
            If CStr(u.Cells(i, 2).Value) <> uname Then u.Cells(i, 2).Value = uname
            Exit Sub
        End If
    Next i
    newRow = lastRow + 1
    u.Cells(newRow, 1).Value = key
    u.Cells(newRow, 2).Value = uname
    u.Cells(newRow, 3).Value = Now
End Sub

Private Function FindVoteRow(ByVal userKey As String) As Long
    Dim v As Worksheet, lastRow As Long, i As Long
    Set v = VoteWs()
    lastRow = v.Cells(v.Rows.Count, 1).End(xlUp).Row
    For i = 2 To lastRow
        If CStr(v.Cells(i, 1).Value) = userKey Then
            FindVoteRow = i
            Exit Function
        End If
    Next i
    FindVoteRow = 0
End Function

Private Function GetVoteCsv(ByVal userKey As String) As String
    Dim r As Long
    r = FindVoteRow(userKey)
    If r > 0 Then GetVoteCsv = CStr(VoteWs().Cells(r, 3).Value) Else GetVoteCsv = ""
End Function

Private Function CsvHas(ByVal csv As String, ByVal cid As String) As Boolean
    Dim parts As Variant, i As Long
    If Len(CleanText(csv)) = 0 Then Exit Function
    parts = Split(csv, ",")
    For i = LBound(parts) To UBound(parts)
        If CStr(parts(i)) = cid Then
            CsvHas = True
            Exit Function
        End If
    Next i
End Function

Private Function CsvCount(ByVal csv As String) As Long
    If Len(CleanText(csv)) = 0 Then
        CsvCount = 0
    Else
        CsvCount = UBound(Split(csv, ",")) + 1
    End If
End Function

Private Function CsvRemove(ByVal csv As String, ByVal cid As String) As String
    Dim parts As Variant, i As Long, out As String
    If Len(CleanText(csv)) = 0 Then Exit Function
    parts = Split(csv, ",")
    For i = LBound(parts) To UBound(parts)
        If CStr(parts(i)) <> cid Then
            If Len(out) > 0 Then out = out & ","
            out = out & CStr(parts(i))
        End If
    Next i
    CsvRemove = out
End Function

Private Function CsvAdd(ByVal csv As String, ByVal cid As String) As String
    If Len(CleanText(csv)) = 0 Then
        CsvAdd = cid
    Else
        CsvAdd = csv & "," & cid
    End If
End Function

Public Sub ToggleVote(ByVal rowNum As Long)
    Dim m As Worksheet, uname As String, userKey As String, cid As String, csv As String
    If StageNow() <> 3 Then
        MsgBox Cfg("MsgNotVoting"), vbInformation
        Exit Sub
    End If
    Set m = MainWs()
    uname = CleanText(CStr(m.Range("B9").Value))
    If Len(uname) = 0 Then
        MsgBox Cfg("MsgEnterName"), vbInformation
        Exit Sub
    End If
    cid = CStr(m.Cells(rowNum, 26).Value)
    If Len(cid) = 0 Then Exit Sub
    userKey = Norm(uname)
    csv = GetVoteCsv(userKey)
    If CsvHas(csv, cid) Then
        csv = CsvRemove(csv, cid)
    Else
        If CsvCount(csv) >= 3 Then
            MsgBox Cfg("MsgMax3"), vbExclamation
            Exit Sub
        End If
        csv = CsvAdd(csv, cid)
    End If
    SaveVoteCsv userKey, uname, csv
    RefreshUI
End Sub

Private Sub SaveVoteCsv(ByVal userKey As String, ByVal uname As String, ByVal csv As String)
    Dim v As Worksheet, r As Long, lastRow As Long
    Set v = VoteWs()
    EnsureUser uname
    r = FindVoteRow(userKey)
    If r = 0 Then
        lastRow = v.Cells(v.Rows.Count, 1).End(xlUp).Row
        r = lastRow + 1
        v.Cells(r, 1).Value = userKey
    End If
    v.Cells(r, 2).Value = uname
    v.Cells(r, 3).Value = csv
    v.Cells(r, 4).Value = Now
    On Error Resume Next
    ThisWorkbook.Save
    On Error GoTo 0
End Sub

Private Sub BuildRanking(ByRef arr As Variant, ByRef n As Long)
    Dim c As Worksheet, v As Worksheet, lastC As Long, lastV As Long
    Dim countD As Object, voterD As Object, nameD As Object, proposerD As Object
    Dim i As Long, j As Long, id As String, csv As String, parts As Variant, voter As String
    Set c = CandWs()
    Set v = VoteWs()
    Set countD = CreateObject("Scripting.Dictionary")
    Set voterD = CreateObject("Scripting.Dictionary")
    Set nameD = CreateObject("Scripting.Dictionary")
    Set proposerD = CreateObject("Scripting.Dictionary")
    lastC = c.Cells(c.Rows.Count, 1).End(xlUp).Row
    n = 0
    For i = 2 To lastC
        id = CStr(c.Cells(i, 1).Value)
        If Len(id) > 0 Then
            n = n + 1
            countD(id) = 0
            voterD(id) = ""
            nameD(id) = CStr(c.Cells(i, 2).Value)
            proposerD(id) = CStr(c.Cells(i, 4).Value)
        End If
    Next i
    If n = 0 Then Exit Sub
    lastV = v.Cells(v.Rows.Count, 1).End(xlUp).Row
    For i = 2 To lastV
        csv = CStr(v.Cells(i, 3).Value)
        voter = CStr(v.Cells(i, 2).Value)
        If Len(csv) > 0 Then
            parts = Split(csv, ",")
            For j = LBound(parts) To UBound(parts)
                id = CStr(parts(j))
                If countD.Exists(id) Then
                    countD(id) = CLng(countD(id)) + 1
                    If Len(CStr(voterD(id))) = 0 Then
                        voterD(id) = voter
                    Else
                        voterD(id) = CStr(voterD(id)) & ", " & voter
                    End If
                End If
            Next j
        End If
    Next i
    ReDim arr(1 To n, 1 To 6)
    i = 0
    Dim k As Variant
    For Each k In nameD.Keys
        i = i + 1
        arr(i, 1) = CStr(k)
        arr(i, 2) = CStr(nameD(k))
        arr(i, 3) = CLng(countD(k))
        arr(i, 4) = CStr(proposerD(k))
        arr(i, 5) = CStr(voterD(k))
        arr(i, 6) = 0
    Next k
    Dim a As Long, b As Long
    For a = 1 To n - 1
        For b = a + 1 To n
            If CLng(arr(b, 3)) > CLng(arr(a, 3)) Or _
               (CLng(arr(b, 3)) = CLng(arr(a, 3)) And StrComp(CStr(arr(b, 2)), CStr(arr(a, 2)), vbTextCompare) < 0) Then
                SwapRankRow arr, a, b
            End If
        Next b
    Next a
    Dim currentRank As Long, prevCount As Long
    currentRank = 0
    prevCount = -1
    For i = 1 To n
        If CLng(arr(i, 3)) <> prevCount Then currentRank = i
        arr(i, 6) = currentRank
        prevCount = CLng(arr(i, 3))
    Next i
End Sub

Private Sub SwapRankRow(ByRef arr As Variant, ByVal a As Long, ByVal b As Long)
    Dim j As Long, tmp As Variant
    For j = 1 To 6
        tmp = arr(a, j)
        arr(a, j) = arr(b, j)
        arr(b, j) = tmp
    Next j
End Sub

Private Function RankText(ByRef arr As Variant, ByVal idx As Long, ByVal n As Long) As String
    Dim j As Long, tied As Boolean
    For j = 1 To n
        If j <> idx Then
            If CLng(arr(j, 6)) = CLng(arr(idx, 6)) Then
                tied = True
                Exit For
            End If
        End If
    Next j
    If tied Then
        RankText = Cfg("Joint") & CStr(arr(idx, 6)) & Cfg("Place")
    Else
        RankText = CStr(arr(idx, 6)) & Cfg("Place")
    End If
End Function

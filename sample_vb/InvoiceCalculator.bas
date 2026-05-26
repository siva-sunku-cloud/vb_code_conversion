' ============================================================
' Module: InvoiceCalculator
' Purpose: Calculate invoice totals, apply discounts, and
'          compute VAT for a retail billing system.
' ============================================================
Option Explicit

' ── User-Defined Types ─────────────────────────────────────
Type LineItem
    ProductCode As String
    Description As String
    Quantity    As Integer
    UnitPrice   As Currency
End Type

Type Invoice
    InvoiceNumber As String
    CustomerID    As String
    Items()       As LineItem
    ItemCount     As Integer
    DiscountPct   As Double
    VATRate       As Double
End Type

' ── Constants ──────────────────────────────────────────────
Const MAX_DISCOUNT As Double = 0.3
Const DEFAULT_VAT  As Double = 0.2

' ── Public Functions ───────────────────────────────────────

Public Function CalcSubtotal(inv As Invoice) As Currency
    Dim i As Integer
    Dim total As Currency
    total = 0
    For i = 0 To inv.ItemCount - 1
        total = total + (inv.Items(i).Quantity * inv.Items(i).UnitPrice)
    Next i
    CalcSubtotal = total
End Function

Public Function ApplyDiscount(subtotal As Currency, discountPct As Double) As Currency
    If discountPct < 0 Or discountPct > MAX_DISCOUNT Then
        On Error GoTo DiscountError
        Err.Raise 1001, "InvoiceCalculator", "Discount out of range: " & discountPct
    End If
    ApplyDiscount = subtotal * (1 - discountPct)
    Exit Function
DiscountError:
    ApplyDiscount = subtotal
End Function

Public Function CalcVAT(amount As Currency, vatRate As Double) As Currency
    CalcVAT = amount * vatRate
End Function

Public Function CalcTotal(inv As Invoice) As Currency
    Dim subtotal As Currency
    Dim discounted As Currency
    Dim vat As Currency

    On Error Resume Next
    subtotal  = CalcSubtotal(inv)
    discounted = ApplyDiscount(subtotal, inv.DiscountPct)
    vat        = CalcVAT(discounted, inv.VATRate)
    CalcTotal  = discounted + vat
End Function

Public Sub PrintInvoiceSummary(inv As Invoice)
    Dim total As Currency
    total = CalcTotal(inv)
    Debug.Print "Invoice: " & inv.InvoiceNumber
    Debug.Print "Customer: " & inv.CustomerID
    Debug.Print "Total (inc VAT): " & Format(total, "Currency")
End Sub

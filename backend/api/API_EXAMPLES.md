# Ledgerly API: curl.exe examples (PowerShell)

Use `curl.exe`, not `curl` (in Windows PowerShell 5, `curl` is an alias for Invoke-WebRequest).
Run from the repo root with the server on port 8000. For readable Devanagari output:

    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8

JSON bodies go through a file, because quoting inline JSON in PowerShell is painful.

## Upload a page (slow unless LEDGERLY_FAKE_EXTRACT=1 is set on the server)
    curl.exe -s -F "image=@data/pages/page01.jpg" http://localhost:8000/api/pages/

## Reload a page
    curl.exe -s http://localhost:8000/api/pages/1/

## Confirm reviewed rows
    @'
    {"rows": [
      {"row_index": 0, "date_text": "01/10", "name": "Ramesh Kumar", "item": "Atta (5Kg)",
       "amount": 240, "type": "credit", "struck_out": false,
       "customer_id": null, "create_new_customer": true},
      {"row_index": null, "date_text": "07/10", "name": "Harish", "item": null,
       "amount": 50, "type": "payment", "struck_out": false,
       "customer_id": null, "create_new_customer": true}
    ]}
    '@ | Set-Content body.json -Encoding utf8
    curl.exe -s -H "Content-Type: application/json" --data-binary "@body.json" http://localhost:8000/api/pages/1/confirm/

A second confirm of the same page returns HTTP 409.

## Customers
    curl.exe -s http://localhost:8000/api/customers/
    curl.exe -s http://localhost:8000/api/customers/1/

## Reports
    curl.exe -s http://localhost:8000/api/reports/balances/
    curl.exe -s http://localhost:8000/api/reports/aging/
    curl.exe -s -o balances.png http://localhost:8000/api/reports/balances.png
    curl.exe -s -o aging.png http://localhost:8000/api/reports/aging.png

## Current "mistakes to avoid" rules
    curl.exe -s http://localhost:8000/api/rules/

## Same calls with Invoke-RestMethod (no curl needed)
    Invoke-RestMethod http://localhost:8000/api/customers/
    Invoke-RestMethod -Method Post -ContentType "application/json" -InFile body.json http://localhost:8000/api/pages/1/confirm/

# prebuilt-invoice vs LLM extraction (20 invoices, 5 shared fields)

| system | fields right |
|---|---|
| prebuilt-invoice | 94/100 (94%) |
| prebuilt-invoice(en-AU) | 100/100 (100%) |
| llm-layout | 97/100 (97%) |
| llm-vision | 99/100 (99%) |

**prebuilt-invoice misses:**
- `test-B01-01 invoice_date: '2026-11-07' vs '11/07/2026'`
- `test-B06-01 invoice_date: '2026-01-09' vs '01/09/2026'`
- `test-B09-01 invoice_date: '2026-01-08' vs '01/08/2026'`
- `test-B10-01 invoice_date: '2026-02-07' vs '02/07/2026'`
- `test-B14-01 invoice_date: '2026-11-08' vs '11/08/2026'`
- `test-B15-01 invoice_date: '2026-01-09' vs '01/09/2026'`

**llm-layout misses:**
- `test-B06-01 seller: 'LANKA SPICE MILLS (PVT) LTD 206 Industrial Rd, Vietnam' vs 'Lanka Spice Mills (Pvt) Ltd'`
- `test-B09-01 seller: 'GOLDEN VALLEY EXPORTS CO. LTD 204 Industrial Rd, Turkey' vs 'Golden Valley Exports Co. Ltd'`
- `test-B17-01 seller: 'LANKA SPICE MILLS (PVT) LTD 316 Industrial Rd, Vietnam' vs 'Lanka Spice Mills (Pvt) Ltd'`

**llm-vision misses:**
- `test-B13-01 total_amount: '35,721:28' vs '35,721.28'`

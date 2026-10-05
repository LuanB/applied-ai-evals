# extract — eval report

**Gate: PASS ✅** · mode `replay` · headline `field_accuracy`

```
ok   llm-layout: field_accuracy 0.974 beats best baseline 0.474 (margin 0.05)
ok   llm-vision: field_accuracy 0.979 beats best baseline 0.474 (margin 0.05)
```

| system | field_accuracy | page_all_fields_right | cost (USD) | wall (s) |
|---|---|---|---|---|
| regex-on-ocr *(baseline)* | 47.4% | 0.0% | 0.1656 | 0.0 |
| **llm-layout** | 97.4% | 83.7% | 1.1335 | 0.1 |
| **llm-vision** | 97.9% | 85.9% | 0.0775 | 0.1 |

## llm-layout: 15 of 92 cases not passed

| case | score | detail |
|---|---|---|
| `test-B00-03` | 0.88 | port_of_loading: got 'Izmir:' want 'Izmir' |
| `test-B01-02` | 0.83 | invoice_number: got 'INV-3.7060' want 'INV-37060' |
| `test-B01-03` | 0.88 | bl_number: got 'MEDU48520.404' want 'MEDU48520404' |
| `test-B03-02` | 0.83 | invoice_number: got 'INV-6446.3' want 'INV-64463' |
| `test-B05-02` | 0.67 | packing_list_number: got 'PL-416.70' want 'PL-41670'; container_number: got 'CMAU34.35592' want 'CMAU3435592' |
| `test-B05-06` | 0.80 | certificate_number: got 'CO91-5766' want 'CO915766' |
| `test-B06-01` | 0.88 | seller: got 'LANKA SPICE MILLS (PVT) LTD 206 Industrial Rd, Vietnam' want 'Lanka Spice Mills (Pvt) Ltd' |
| `test-B07-03` | 0.88 | bl_number: got 'MEDU973998.60' want 'MEDU97399860' |
| `test-B09-01` | 0.88 | seller: got 'GOLDEN VALLEY EXPORTS CO. LTD 204 Industrial Rd, Turkey' want 'Golden Valley Exports Co. Ltd' |
| `test-B10-02` | 0.83 | net_weight_kg: got '3.5650.8' want '35650.8' |
| `test-B11-02` | 0.83 | container_number: got 'TGHU628.9625' want 'TGHU6289625' |
| `test-B12-03` | 0.88 | container_number: got 'COLU3552106' want 'OOLU3552106' |
| `test-B15-01` | 0.88 | hs_code: got '0904:11' want '0904.11' |
| `test-B17-01` | 0.88 | seller: got 'LANKA SPICE MILLS (PVT) LTD 316 Industrial Rd, Vietnam' want 'Lanka Spice Mills (Pvt) Ltd' |
| `test-B17-05` | 0.80 | hs_code: got '08.01.32' want '0801.32' |

## llm-vision: 13 of 92 cases not passed

| case | score | detail |
|---|---|---|
| `test-B01-04` | 0.80 | certificate_number: got 'C0589528' want 'CO589528' |
| `test-B01-05` | 0.83 | certificate_number: got 'C0500802' want 'CO500802' |
| `test-B03-04` | 0.80 | certificate_number: got 'C0294523' want 'CO294523' |
| `test-B04-02` | 0.83 | container_number: got 'TGH04492083' want 'TGHU4492083' |
| `test-B05-06` | 0.80 | certificate_number: got 'C0915766' want 'CO915766' |
| `test-B06-04` | 0.80 | certificate_number: got 'C0844521' want 'CO844521' |
| `test-B07-06` | 0.80 | certificate_number: got 'C0931747' want 'CO931747' |
| `test-B08-05` | 0.80 | certificate_number: got 'C0771879' want 'CO771879' |
| `test-B11-04` | 0.80 | certificate_number: got 'C0893597' want 'CO893597' |
| `test-B13-01` | 0.88 | total_amount: got '35,721:28' want '35,721.28' |
| `test-B15-01` | 0.88 | hs_code: got '0904:11' want '0904.11' |
| `test-B18-04` | 0.80 | certificate_number: got 'C0713515' want 'CO713515' |
| `test-B19-02` | 0.83 | container_number: got 'MSK09489387' want 'MSKU9489387' |

_Replayed from cassettes: $0 spent on this run. Costs shown are what the recorded calls cost when they were made live._

Trace: `traces/extract-20261004-153500.jsonl`

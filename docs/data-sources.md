# Data sources — SICAP spike results

Spike date: 20 September 2026. Method: the public JSON API behind
`www.e-licitatie.ro`, called from the browser, same origin.

> **Read this first.** The findings below were measured on 20 September 2026
> against the live portal. The code in this repository was rebuilt from this
> document on 27 September 2026 **without** live access, so the code matches
> the document but has **not** been re-checked against the portal. Run
> `bidscout watch --days 1` on a machine that can reach e-licitatie.ro to
> confirm, and correct this file if anything has moved.

---

## 1. The headline result

For a full contract notice, the two most important hard gates arrive as
**plain text in a JSON field**. You do not need to parse a PDF to get them.

From `GetSection3View`, notice `CN1096282`:

| Field | Content (shortened) |
|---|---|
| `efCriteriaMin` | "Media cifrei de afaceri generale anuale pe ultimele 3 exerciții financiare ... trebuie să fie mai mare sau egala cu **2.700.000,00 Lei**" |
| `tpCriteriaQAStandardMin` | "Ofertantul trebuie să fi prestat în ultimii 3 ani, în cadrul a maxim 2 contracte, a căror valoare cumulată să fie cel puțin egală cu **1.804.000,00 lei**, exclusiv TVA, implementarea a cel puțin un sistem software integrat" |

Coverage test on the 5 IT notices in the window:

- `efCriteriaMin` filled: **4 of 5**
- `tpCriteriaQAStandardMin` filled: **5 of 5**
- notices with attached documents: **5 of 5**, 38 files in total

**Effect on the plan.** Reading PDFs and OCR move down one level. They serve
the Caiet de sarcini and the technical offer. The go/no-go gates come from
JSON first, and the PDF is the proof, not the source.

---

## 2. Endpoints

Base: `https://www.e-licitatie.ro/api-pub/`. No API key. No cookie needed.
Content type `application/json`.

### 2.1 Search contract notices

```
POST /api-pub/NoticeCommon/GetCNoticeList/
```

Minimum body that the site itself sends:

```json
{ "sysNoticeTypeIds": [], "sortProperties": [], "pageSize": 5,
  "hasUnansweredQuestions": false, "pageIndex": 0 }
```

Response: `{ total, items[], searchTooLong }`. One item has 25 fields, among
them `cNoticeId`, `noticeId`, `procedureId`, `noticeNo`, `sysNoticeTypeId`,
`contractingAuthorityNameAndFN`, `contractTitle`, `cpvCodeAndName`,
`estimatedValueRon`, `noticeStateDate`, `minTenderReceiptDeadline`,
`hasLots`, `sysProcedureState`.

**Sort** — the shape comes from the app source:

```json
"sortProperties": [ { "sortProperty": "noticeStateDate", "descending": true } ]
```

**Filters that work** (tested):

| Field | Type | Test result |
|---|---|---|
| `startPublicationDate` / `endPublicationDate` | ISO 8601 string | 15–20 Sep 2026 → `total: 378` |
| `startTenderReceiptDeadline` / `endTenderReceiptDeadline` | ISO 8601 | Oct–Nov 2026 → `total: 940` |
| `cPVId` | integer, one value only | 18260 → only CPV 72… notices |
| `sysProcedureTypeId` | integer | filters, but stays above the cap |
| `pageSize` | integer | 200 accepted |

**Filters that do nothing** — the server ignores an unknown key and returns
the unfiltered set: `cpvCode`, `cpvCodeId`, `cpvCategoryId`, `contractTitle`,
`publicationDateStart`. Do not trust a filter until you see the count change.
These names are enforced in `src/bidscout/sicap/filters.py`.

`GetCNoticeListFiltered/` exists and behaves the same as `GetCNoticeList/`
in every test. Use `GetCNoticeList/`.

**The 3000 cap.** A wide search returns `total: 3000` and
`searchTooLong: true`. That is a cap, not a count. The watcher must always
send a date window narrow enough to stay under the cap.

### 2.2 CPV lookup

```
GET /api-pub/Cpv/SearchCpv?text=72000000
→ [{ "cpvCodeID": 18260, "code": "72000000-5",
     "name": "Servicii IT: consultanta, dezvoltare de software...",
     "parentID": 10000, "hasChildren": true }]
```

Also available: `/api-pub/Cpv/GetAll`, `/api-pub/Cpv/GetCpvWithParent`.

**`cPVId` matches one node only. It does not include the children.** An array
value makes the call fail. So the watcher loops over the CPV watchlist, one
request per code. About 30 requests per poll — acceptable.

### 2.3 Notice detail and sections

```
GET /api-pub/PUBLICCNotice/getPubCNoticeView/?cNoticeId={cNoticeId}
GET /api-pub/NoticeCommon/GetSection1View/?initNoticeId={id}&sysNoticeTypeId=2
GET /api-pub/NoticeCommon/GetSection21View/?dfNoticeId={..}&initNoticeId={id}&sysNoticeTypeId=2
GET /api-pub/NoticeCommon/GetSection3View/?initNoticeId={id}&sysNoticeTypeId=2
GET /api-pub/NoticeCommon/GetSection4View/?initNoticeId={id}&sysNoticeTypeId=2
GET /api-pub/NoticeCommon/GetSection6View/?initNoticeId={id}&sysNoticeTypeId=2
POST /api-pub/NoticeCommon/GetSection22LotList/
GET /api-pub/PUBLICCNotice/CheckDfDocumentsAndClarifications/?cNoticeId={id}
```

**Section 3 is the one that matters.** Size about 15 KB. Fields:
`personalSituation`, `efCriteria`, `efCriteriaMin`, `efCriteriaBold1/2`,
`tpCriteriaQAStandard`, `tpCriteriaQAStandardMin`, `depositsAndWarranties`,
`legalFormOfSuppliers`, `mandatoryProfesionalQualif`, `prCriteria`.
The values hold HTML. Strip the tags before you parse.

*Open:* `getPubCNoticeView` returns `null` for a simplified notice
(`sysNoticeTypeId` 17, prefix `SCN`). Find the matching endpoint for that
type. Simplified notices are a large part of the flow.

### 2.4 Documents

```
GET /api-pub/NoticeCommon/GetDfNoticeSectionFiles/?initNoticeId={id}&sysNoticeTypeId=2
```

Returns groups: `dfNoticeDocs`, `duaeDocs`, `contractingStrategyDocs`,
`decisionDocs`, `exAnteDocs`. Each entry:

```json
{ "noticeDocumentUrl": "api-pub/files/noticedoc/28c82dc9e28547f795cc5ac9553e5a35",
  "noticeDocumentName": "02 Caiet de sarcini servicii Digitalizare Chetani.pdf",
  "noticeDocumentCode": "CN1096282/00003" }
```

Download test: `GET /api-pub/files/noticedoc/{guid}` → 200,
`application/octet-stream`, 1,912,819 bytes. No sign-in. The file type comes
from the name, not from the header, so read the extension and sniff the
magic bytes.

The DUAE comes as an XML file (`DUAE_CERERE_384463.xml`). The draft stage can
fill a real XML, not a copy of a PDF.

### 2.5 Direct acquisitions

```
POST /api-pub/DirectAcquisitionCommon/GetDirectAcquisitionList/
```

Item fields: `directAcquisitionId`, `directAcquisitionName`,
`uniqueIdentificationCode` (for example `DA22780457`), `cpvCode`,
`publicationDate`, `finalizationDate`, `caDecisionDeadline`,
`supplierDecisionDeadline`, `supplier`, `contractingAuthority`,
`estimatedValueRon`, `closingValue`, `sysDirectAcquisitionState`.

Cap: 2000.

| Filter | Result |
|---|---|
| `finalizationDateStart` / `finalizationDateEnd` | **works** |
| `sysDirectAcquisitionStateId` | **works** |
| `startPublicationDate`, `publicationDateStart`, `dateFrom`, `cPVId` | ignored |

*Open:* find the publication-date and CPV filter names for this endpoint.

### 2.6 Reference lists

```
GET /api-pub/comboPub/getSysProcedureTypes/
GET /api-pub/comboPub/getSysProcedureStates
GET /api-pub/comboPub/getSysProcedurePhases/
GET /api-pub/comboPub/getSysAwardCriteriaTypes/
GET /api-pub/comboPub/getSysFinancingTypes/
GET /api-pub/comboPub/getSysEuropeanFund/
GET /api-pub/NoticeCommon/GetNutsCodes/
GET /api-pub/time/getServerTime/
```

Pull these once at start and cache them. `getServerTime` gives the server
clock — use it for the deadline maths, not the local clock.

---

## 3. Volume — what the IT market really looks like

Contract notices published 1 August to 19 September 2026 (50 days), by
primary CPV code:

| CPV | Name | Notices |
|---|---|---|
| 48000000-8 | Pachete software si sisteme informatice | 21 |
| 30200000-1 | Echipament si accesorii pentru computer | 17 |
| 72000000-5 | Servicii IT: consultanta, dezvoltare software | 5 |
| 72260000-5 | Servicii de software | 4 |
| 72212931-4 | Servicii de dezvoltare de software de formare | 1 |
| 72500000-0 | Servicii informatice | 1 |
| 51600000-8 | Instalare de computere si echipamente | 1 |
| 79132000-8 | Servicii de certificare | 1 |
| | **Total** | **≈ 51** |

**This is about one IT contract notice per day.** The daily volume sits in
**direct acquisitions**, not in contract notices. Version 1 must cover both.

---

## 4. Rules for the adapter

1. **One module owns every call.** `src/bidscout/sicap/client.py`.
2. **Never trust a filter you did not test.** Enforced by `filters.py`.
3. **Watch the cap.** `searchTooLong: true` is an error, not a result.
4. **Poll by publication window, not by page.**
5. **Store the raw JSON** before you parse anything.
6. **Be a good guest.** One request at a time, a pause between them, and a
   User-Agent that names the project.
7. **Use the server clock** from `getServerTime` for deadlines.

---

## 5. Filter vocabulary

Pulled from the site's own JavaScript. Most are not valid on every endpoint.

`cPVId`, `cpvCategoryId`, `cpvCodeId`, `cpvCodeText`, `contractingAuthorityId`,
`startPublicationDate`, `endPublicationDate`, `startTenderReceiptDeadline`,
`endTenderReceiptDeadline`, `startNoticeState`, `endNoticeState`,
`publicationDateStart`, `publicationDateEnd`, `finalizationDateStart`,
`finalizationDateEnd`, `caDecisionDeadlineStart`, `caDecisionDeadlineEnd`,
`supplierDecisionDeadlineStart`, `supplierDecisionDeadlineEnd`,
`createDateStart`, `createDateEnd`, `sendToPublicationDateStart`,
`sendToPublicationDateEnd`, `nutsCodeIds`, `sysProcedureTypeId`,
`sysProcedureStateId`, `sysProcedurePhaseId`, `sysAcquisitionContractTypeId`,
`sysContractAssigmentTypeId`, `sysAwardCriteriaTypeId`, `sysFinancingTypeId`,
`sysEuropeanFundId`, `sysNoticeStateId`, `sysNoticeTypeId`,
`sysNoticeTypeIds`, `sysDirectAcquisitionStateId`, `uniqueIdentificationCode`,
`supplierId`, `winnerId`, `noticeNumber`, `hasUnansweredQuestions`,
`pageIndex`, `pageSize`, `sortProperties`.

---

## 6. Legal and ethical position

- The data is public. The portal publishes it for public use.
- No sign-in, no token, no paywall is passed.
- The agent names itself in the User-Agent and keeps the rate low.
- Each extracted fact keeps a link to its source, so a user can check it.
- The output is never called legal advice. A human approves before sending.

---

## 7. Open items

1. Find the detail endpoint for simplified notices (`sysNoticeTypeId` 17).
2. Find the publication-date and CPV filters for direct acquisitions.
3. Check whether Section 3 exists for simplified notices.
4. Measure how stable `efCriteriaMin` and `tpCriteriaQAStandardMin` are over
   100 notices, not 5.
5. Build the contract test suite: one test per endpoint, run daily.
6. Decide the full CPV watchlist for the IT vertical.

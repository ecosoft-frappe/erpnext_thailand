## ERPNext Thailand

Additional tax functionality to comply with Thailand Tax regulation.

1. **Tax (VAT)**:
   - **Item Tax**: Tax point occur when deliver product and invoice document is issued
   - **Service VAT**: Tax point occur on payment or whenever the tax invoice/receipt is issued  (on sales/purchase invioce, record GL as "Undued Tax" and move to "Tax" on payment / receipt of tax invoice)

2. **Withholding Tax and Withholding Tax Certificate**:
   - **Withholding Tax on Payment**: I.e., Withhold 3% for services and etc.
   - **Issue Withholding Tax Certificate**: Printout Withholding Tax Cert for the supplier being tax withheld

3. **Tax Reports for Revenue Department**:
   - **Purchase and Sales Tax Report**: Printout PDF or Excel for RD submission
   - **Support Tax 0%**: I.e., for export case 
   - **PND Report**: Printout PDF or Excel for RD submission

4. **Sales and Purchase Billing**:
   - As optional process, in case the customer require Billing process (ขั้นตอนการวางบิล)

5. **Deposit Invoicing**:
   - **Deposit Invoice Creation**: Allow creation of 1st invoice as Deposit Invoice
   - **Deposit Allocation**: Allow auto/manual deposit allocation on following invoices

6. **Thai Tax Settings**:
   - Setup Thai Tax in one place
   - Setup Tax Address

7. **Thai Language**:
   - Amount to Words on printout
   - Thai Date on printout

9. **Currency Exchange from BOT**:
   - An option to use BOT as source of currency exchange

9. **Print Format Enhancement**:
    - Number of Copies
    - Auto choose print format based on document context

10. **Thai Address Web Service**:
    - Pull address from Postal Code
    - Pull address from Company Tax ID

11. **e-Tax Invoice & e-Receipt**:
    - Sign Sales Invoice, Credit Note, Debit Note and customer Payment Entry (receipt) as e-Tax documents through a Frappe e-Tax server ([etax_inet](https://github.com/ecosoft-frappe/etax_inet))
    - Signed PDF and XML are attached back to the document, every request is kept in Integration Request
    - Sign from the form or many documents from the list view, follow the status (Processing, Success, Error, Replaced)
    - Create Replacement of a signed document, Credit/Debit Note with e-Tax purpose code

## Setup

### Installation

```
$ cd frappe-bench
$ bench get-app https://github.com/ecosoft-frappe/erpnext_thailand
$ bench install-app erpnext_thailand
```

### Configurations

#### For Tax Invoice setup

1. In chart of account, make sure to have with Rate, i.e, 7% for Thailand Tax (Tax)
    - Sales Tax and Undue Sales Tax
    - Purchase Tax and Undue Purchase Tax
2. Open Thai Tax Settings, and setup above taxes
3. Setup Sales / Purchase Taxes and Charges Template, we just want to make sure that,
    - When buy/sell product, Sales/Purchase Tax is record on invoice
    - When buy/sell service, Undue Sales/Purchase Tax is record on invoice, then on payment, clear Undue Tax and record Tax
4. Make sure you have setup Company's Billing Address, as it will be used for Tax Invoice
5. Make sure all Supplier/Customer have setup Billing Address, they will be used for Tax Invoice

Whenever Tax is recorded (with Tax Invoice and Tax Date), Sales/Purchase Tax Invoice will be created.

#### For Withholding Tax setup

1. In chart of account, make sure to have Withholding Tax Account
2. Create Withholding Tax Types (1%, 2%, 3% and 5%)

During payment, user will manually choose to deduct with one of these Withholding Tax Type, and then click button Create Withholding Tax cert with the deducted amount plus some additional deduction information.

#### For e-Tax setup

Requires a Frappe e-Tax server with the [etax_inet](https://github.com/ecosoft-frappe/etax_inet) app, registered with INET for the company.

1. Open **eTax Connection** (Thai Tax workspace) and create one per company
    - Server URL of the e-Tax server, API Key and API Secret of its user
    - Send Email: let the e-Tax server email the signed document to the customer's e-Tax Email
    - Require Email: block signing when the customer has no e-Tax Email
    - Replacement Lock Day: a replacement is allowed until this day of the month after the document date, 0 for no limit
    - Uncheck Enabled to stop e-Tax for the company, the e-Tax tab is then hidden on documents not signed yet
2. Create **eTax Document Type** for each document to sign
    - Applies To: Sales Invoice, Credit Note, Debit Note or Payment Entry
    - Document Type Code: i.e., T02 (invoice/tax invoice), 388 (tax invoice), 380 (invoice), T01 (receipt), T03 (receipt/tax invoice), 81 (credit note), 80 (debit note)
    - Template Source: ERPNext sends the PDF of the Print Format, eTax Server uses a print format of the e-Tax server
3. eTax Document Type Code and eTax Purpose Code are installed with the app, a purpose code changed by the user is kept on migrate
4. Customer: fill in Tax ID, Branch Code and e-Tax Email (Tax tab), and a billing address with country.
   For a customer with several branches, the Tax ID and Branch Code of the address are used
5. Company: fill in Tax ID, the Branch Code of the company address is the seller branch
6. Roles: Accounts User and Accounts Manager can sign e-Tax and read the e-Tax request logs (Integration Request of service "e-Tax" only).
   Create Replacement needs the Cancel permission, i.e., Accounts Manager for Sales Invoice

#### Using e-Tax

- **Sign**: submit the document, then **e-Tax > Sign e-Tax** and select the eTax Document Type, or select documents in the list view and **Actions > Sign e-Tax** (more than 10 documents are signed in background, the result shows on screen when done and comes as a notification)
- **Status**: Success attaches the signed PDF/XML, Error shows the server message in the e-Tax tab (correct the data and sign again), Processing is updated every minute or by **e-Tax > Refresh e-Tax Status**
- **Lines**: check **Skip e-Tax** on an item row not to send it, a discount or a negative line (i.e., deposit deduction) is sent as line allowance.
  The unit price is sent before VAT, also when the rate includes VAT
- **VAT rate**: taken from the tax rows of the document (or the Item Tax Template of the item), nothing is fixed at 7%.
  A VAT-exempt item uses an Item Tax Template with **Not Applicable** VAT and is sent as FRE, a 0% template is sent as VAT 0% (zero rate, i.e., export).
  When the VAT rate changes, update the Sales Taxes and Charges / Item Tax Templates and the **Tax Rate** of the sales tax accounts (also the undue one)
- **Taxes and charges**: VAT must be calculated On Net Total (VAT On Previous Row Total or Actual is blocked).
  A charge row that is not on a tax account, i.e., shipping or service charge, is sent as its own line without VAT
- **Currency**: an invoice is sent in its currency, a receipt with Sales Tax Invoices (undue VAT) in the company currency
- **Credit / Debit Note**: create the Return (credit note) or **Create > Debit Note** from the invoice, select the e-Tax Purpose Code in the e-Tax tab (it can be set after submit until signed), then sign with document type code 81 / 80.
  An invoice signed as 380 (not a tax invoice) has no e-Tax credit/debit note or replacement
- **Replacement**: a signed document cannot be cancelled. Use **e-Tax > Create Replacement** with a purpose code, the document is cancelled and amended, sign the amendment with the same document type and the original becomes Replaced.
  The Sales Tax Invoices of the document are cancelled with it and created again when the replacement is submitted
- **Receipt (Payment Entry)**: only for Receive from Customer. Without undue VAT use T01, the lines are the amount paid per invoice.
  With undue VAT (Sales Tax Invoice created on payment) use T03, the lines are the Sales Tax Invoices
- **Undue VAT (service)**: the VAT is due on payment, so the invoice is not a tax invoice. Sign it with 380 (or not at all)
  and sign the receipt with T03 as the tax invoice. Its credit/debit notes are not sent as e-Tax

-----------------------
#### License

MIT

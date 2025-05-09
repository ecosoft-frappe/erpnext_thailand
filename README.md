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

-----------------------
#### License

MIT

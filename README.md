# ERPNext Thailand

Thailand localization for ERPNext — additional tax functionality, reporting, and business process support to comply with Thai regulations.

---

## Features

### 1. Tax (VAT)

- **Item Tax**: Tax point occurs when the product is delivered and the invoice is issued. A Sales/Purchase Tax Invoice is created automatically on GL entry.
- **Service (Undue) Tax**: Tax point occurs on payment or when a tax invoice/receipt is issued. On the sales/purchase invoice, GL is posted to an "Undue Tax" account; on payment, the undue tax is cleared and posted to the actual Tax account.
- **Tax on Expense Claims**: Tax invoice details can be recorded directly on Expense Claims.
- **Tax on Journal Entries**: Tax invoice details can be captured in Journal Entries.
- **Support for 0% Tax**: Handles export and zero-rated transactions.

### 2. Withholding Tax and Withholding Tax Certificate

- **Withholding Tax on Payment**: Deduct WHT at source during Payment Entry (e.g., 1%, 2%, 3%, 5%).
- **Auto-detect WHT from Items**: Automatically reads the WHT type from invoice line items; differentiates between individual and juristic-person suppliers.
- **Type of Income**: Configurable income type codes for PND forms (Types 1–6, including subtypes 4.1.x and 4.2.x).
- **Withholding Tax Certificate**: Create and print a WHT certificate from a Payment Entry, with supplier name, address, income type, and tax amount.

### 3. Tax Reports for the Revenue Department

- **Sales Tax Report**: Printable PDF or Excel for RD submission.
- **Purchase Tax Report**: Printable PDF or Excel for RD submission.
- **PND3 Report**: Withholding tax report for individual payees.
- **PND53 Report**: Withholding tax report for juristic-person payees.

### 4. Sales and Purchase Billing

- **Sales Billing**: Consolidate multiple sales invoices into a single billing document for a customer.
- **Purchase Billing**: Consolidate multiple purchase invoices from a supplier.
- **Payment Receipt**: Optionally auto-create a Payment Receipt document when payment is recorded against a Sales Billing.
- **Outstanding Tracking**: Billing documents track total outstanding amount and close automatically when fully paid.

### 5. Deposit Invoicing

- **Deposit Invoice Creation**: Create the first invoice as a Deposit Invoice directly from a Sales Order or Purchase Order.
- **Deposit Allocation**: Subsequent invoices against the same order automatically deduct the deposit balance, using either a **Percent** or **Full Amount** deduction method.
- **Untied Deposits**: Deposits not linked to any order can also be allocated against invoices for the same customer/supplier.
- **Deposit Balance Tracking**: The system tracks remaining deposit balance across all subsequent invoices.
- **Manual Override**: Users can switch to manual deposit allocation when auto-allocation is not appropriate.

### 6. Petty Cash Management

- **Petty Cash Holder**: Define petty cash custodians, each linked to a dedicated petty cash account with a configured float limit.
- **Petty Cash Account Flag**: Mark any account as a petty cash account; validated during Payment Entry submission.
- **Top-up and Withdrawal**: Create Journal Entries for topping up or withdrawing from a petty cash holder directly from the form.
- **Petty Cash Report**: Summarized report of petty cash transactions per holder.
- **Integration with Expense Claim**: Expense Claims can be marked as petty cash, linking the holder and petty cash account through the payment workflow.

### 7. Thai Tax Settings

- **Centralized Setup**: Configure all Thai tax accounts in one place (Thai Tax Settings).
- **Multi-Company Support**: Each company can have its own tax account configuration.
- **Tax Address**: Manage company billing addresses used on tax invoices.

### 8. Thai Language Support

- **Amount in Thai Baht Words**: Convert numeric amounts to Thai text (บาทถ้วน) for use in print formats.
- **Multi-Currency Words**: Convert amounts to words in Thai or English depending on the transaction currency.
- **Thai Buddhist Calendar Date**: Display dates in full Thai format (e.g., `30 ตุลาคม 2560`) for print formats.

### 9. Currency Exchange from BOT (Bank of Thailand)

- **BOT Exchange Rate Integration**: Fetch daily average exchange rates from the Bank of Thailand API (gateway.api.bot.or.th).
- **Configurable Token**: API token is stored securely in Currency Exchange Settings.
- **Fallback Lookup**: Looks back up to 5 days to find the latest available rate when the exact date has no data.

### 10. Print Format Enhancements

- **Number of Copies**: Configure how many copies to print (original + N additional copies); copy index is available in Jinja for watermarking (e.g., "Original", "Copy").
- **Auto-select Print Format**: Define a condition (Jinja expression) on each print format; the system automatically selects the matching format based on the document context.
- **Hide Non-default Formats**: Print formats that do not match the current document context can be hidden from the selection list.

### 11. Thai Address Web Services

- **Lookup by Postal Code**: Query the Thai Zip Code database to auto-fill sub-district (tambon), district (amphur), and province on an Address form.
- **Lookup by Tax ID**: Call the Revenue Department Web Service (rdws.rd.go.th) with a Tax ID and branch number to retrieve the registered business address.
- **Address-to-Party Sync**: When a billing address is updated with a new Tax ID or Branch Code, the linked Customer or Supplier records are automatically updated.

### 12. Naming Series Enhancements

- **Date-based Variables**: Additional naming series variables that use the document's `posting_date` or `transaction_date`:
  - `YYYY-DATE` — 4-digit year
  - `YY-DATE` — 2-digit year
  - `MM-DATE` — 2-digit month
  - `DD-DATE` — 2-digit day
  - `WW-DATE` — consecutive week number

---

## Setup

### Installation

```bash
cd frappe-bench
bench get-app https://github.com/ecosoft-frappe/erpnext_thailand
bench install-app erpnext_thailand
```

### Configuration

#### Tax Invoice (VAT)

1. In the Chart of Accounts, create the following accounts (with the appropriate tax rate, e.g., 7%):
   - Sales Tax and Undue Sales Tax
   - Purchase Tax and Undue Purchase Tax
2. Open **Thai Tax Settings** and link each company to the accounts above.
3. Set up **Sales Taxes and Charges Templates** and **Purchase Taxes and Charges Templates** so that:
   - Product purchases/sales post directly to the Tax account.
   - Service purchases/sales post to the Undue Tax account (cleared to Tax on payment).
4. Ensure the **Company Billing Address** is configured — it appears on all Tax Invoices.
5. Ensure each **Supplier** and **Customer** has a Billing Address with a Tax ID.

Once configured, Sales/Purchase Tax Invoices are created automatically whenever a taxable GL entry is posted.

#### Withholding Tax

1. In the Chart of Accounts, create a **Withholding Tax** payable account.
2. Create **Withholding Tax Types** (e.g., 1%, 2%, 3%, 5%) and link them to the WHT account per company.
3. Assign WHT types to **Items** (separately for individual and juristic suppliers).

During Payment Entry, the system detects the applicable WHT type from invoice line items. Users can then click **Create Withholding Tax Cert** to generate a printable certificate.

#### Petty Cash

1. Mark the relevant GL account as **Is Petty Cash Account** in the Account form.
2. Create a **Petty Cash Holder**, link it to the petty cash account, and set the float amount.
3. Use the **Top Up** and **Withdraw** buttons on the Petty Cash Holder form to move funds.
4. In Expense Claims and Payment Entries, check **Is Petty Cash** and select the holder to route transactions through the petty cash account.

#### Deposit Invoicing

1. Create a **Deposit Item** (`is_deposit_item = 1`) and configure the income/expense account.
2. On Sales Orders or Purchase Orders, enable **Has Deposit** and choose the deduction method (Percent or Full Amount).
3. From the order, click **Create Deposit Invoice** to issue the first deposit invoice.
4. All subsequent invoices for the same order will automatically show deposit deduction rows.

#### BOT Currency Exchange

1. Register for an API token at the Bank of Thailand developer portal.
2. In **Currency Exchange Settings**, select **BOT** as the service and enter the API token.

---

## License

MIT

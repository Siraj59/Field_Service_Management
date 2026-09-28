# Axiom field service workflow

This is the first working slice for FSRs, quotations, customer POs, and invoices.

1. Create a **Service Request** for the customer and system. Create a **Service Quotation** from it and submit the quote.
2. Create a **Service Order** from the accepted quote. Enter the customer's PO number in **Customer PO Number** when it arrives.
3. Create and schedule a **Service Appointment** from the order. After the visit, use **Create → Field Service Report** on the appointment. Fill in the reported problem, action performed, tests/results, and equipment disposition. Save drafts while work is ongoing; Submit to finalize the FSR. Attach photos and any signed checklist to the report using the standard Attachments sidebar.
4. Use **Create → Sales Invoice** from the order or appointment. The new invoice carries the PO number and its service reference. Check the due date and payment terms before submitting. Track payment through the standard ERPNext Sales Invoice outstanding amount and payment entries.

The Service workspace now links to Field Service Reports and Sales Invoices. The service order, appointment, quotation, PO, equipment serial, and customer are visible on the FSR. FSRs are printable from their form.

## Update a development site

From the bench directory on the machine running Frappe, update the app checkout to the branch containing these changes, then run:

```sh
bench --site <your-site-name> migrate
bench build --app beveren_fsm
bench --site <your-site-name> clear-cache
```

Restart the development server if it is already running, then reload the Service workspace in the browser.

## Pilot check

Use a test customer and a sample OEC 9900 job. Verify that the order PO appears on a new FSR and invoice, that an FSR cannot be submitted without the four required completion fields, that a partial invoice updates billed quantities without an error, and that cancelling that invoice restores the unbilled quantities. Confirm the invoice due date according to Axiom's actual terms before sending it.

## Remaining rollout work

Before company use, configure the company, tax and payment defaults, service items, technician access, customer records, and quote/invoice branding. Test PDF appearance and customer sign-off with a real Axiom report. Back up the site and run the pilot on a staging site before moving historical invoices or service records into ERPNext.

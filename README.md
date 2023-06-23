Credit Card Autopay Service

Currently most credit card autopay products are set up so that your bill is paid on or after the due date (once a month) but studies have shown that you can improve your credit score by ensuring that your balance is always below 30% of your total credit limit. (30% is what most experts say -- although this can vary & it's called your credit utilization rate.)

This is an autopay service that auto pays your credit card bill once you're balance is higher than 30% of your total credit limit, rather than waiting till the end. 


# This is a proof of concept product, meaning that it is by no means ready to go into production. It's my first time building a financial app from scratch, so largely testing to see if the idea was possible technically. It also only works right now on the very perfect happy case. Doesn't handle most edge cases. More details below


I'll walk through high level what the product does and each of the main files + technical decisions I made. A quick note before: 

1. You'll notice that as it's a proof of concept, I didn't use a real database -- instead wrote information to csv files and read from there. You'll see in the code, it'll say open(creditcard.csv) or (paymentinfo.csv) -> you can think of those csv files as storing all my data. 

I did not push those files to this repo as they did contain bank_id's and routing numbers as well. For the most part, they were Sandbox approved items, but out of caution, since it's financial data not uploading it. However I'll include the format of the CSV file and what I stored in my explanation below. 

2. Previously, the front-end mostly existed to link credit card using Plaid & test out OCR on PDF's to get the mailing address for the check. The OCR had a high error rate and later found out that Column has an API to get us a financial institution's physical address. Right now, the front-end has largely been phased -- atleast while it's a POC -- out since there is no more uploading PDF's. The Front-end is really just boilerplate and has the Plaid Link Component, but not fully functional. I've mostly been testing on the backend within my sandbox environment by using Plaid's provided '/simulate/' endpoints to simulate user activity. As such, this is currently a backend focused project. 


# TECHNICAL OVERVIEW

There are 3 main files. They can be found under 'autopay-backend'. I'll go in the order that they're executed in a user flow. 

1. setup_autopay.py: This is responsible for linking the user's credit card & bank_account from which they'll pay their bill. Uses Plaid to connect with a user's financial institutions. A few key notes here: since this is a POC, KYC has not been implemented -- I don't collect information about the 'user'. Each 'user' in this case is a unique credit card. 
I connect with Plaid to get information about the credit card & then save to 'creditcard.csv' information about the credit card (it's corresponsing bank's mailing address -> using Column's API to get this). 

When connecting a new credit card, I make sure it's not already in the database. This file also verifies that 'autopay' is setup by making sure we have all the credit card details we need and all the payment_information we need. We do this by making sure all the fields in the CSV for that specific credit_card are filled. 

2. get_bill.py: This is what determines whether it's time to pay the bill on a certain credit card and if so how much the payment should be. The main way this happens is by setting up a webhook using Plaid where everytime there is an update to the linked credit card, we check basic conditions (amt_due, due_date, utilization_rate and determine if it's time to make a payment -- if we do, then we create a CheckPayment object and issue a check)

3. pay_bill.py: This is really where the meat of the logic is. Once we've decided that we need to make a payment, we need to first transfer funds from the customer's bank into our Column Bank. We need to make sure that the funds have arrived (which I've done again via listening to the ACH events using Column's webhook), once they've arrived we need to issue and send out a check & then again listen to the events to find the status of the check. 


Note: this works in happy, good cases -- it's definitely missing a lot of edge cases. 



I'll quickly mention two big technical decisions I made for the POC. 

1. I chose to go with 'csv' files instead of a real database -- this would definitely not fly in production and even when building this out, I felt some painpoints around it, but it was really easy for testing & just for POC to see if it would even work. I didn't want all the large overhead I would bring by setting up a database. But, in production, I'll likely use Postgres. 

2. Initially, I considered running a cron job every day at a certain time, to see if we need to make a payment but instead decided to listen to events via webhooks --> and make a payment as soon as an update came in. It's more real time; webhooks provide way more detailed information (more I can do with it in the future & cron jobs only make sense for 'static' tasks -- tasks you know will always stay the same at the same time.)


# TESTING


1. As it's a proof of concept, I haven't written test cases. Instead been testing via Sandbox endpoints using Postman / curl requests from command line & verifying via updated csv files or via the Plaid/Column Dashboards where I can see all activity. 


TODO: 
1. Many More Edge Cases to Consider -- when to not pay the full current_balance? 
2. There is a bit of a slight confusion around what uniquely identifies a credit card right now -- the access_token, item_id, or a combination of it's mask & institution number. I should settle on one and use that -- right now different CSV files use different identifcations. 
3. TESTING TESTING! 
4. Web Systems Related Issues -- what happens if a user quits between linking a credit card and adding a payment method?
5. More strict tests -- not enough funds, not saving sensitive information
6. Adding better logging ability & how to claw back checks & better check status tracking. 


Due, to how much I've redacted, running this will be difficult. You'll need to create the csv files as described above. As well as get all the API_KEYS and set up the Webhooks in your Column Dashboard as Intended. Make sure all API keys + env is set to Sandbox. 
To run this -> make sure it works with sandbox; not ready to test in dev yet for security reasons + not all features not fully developed

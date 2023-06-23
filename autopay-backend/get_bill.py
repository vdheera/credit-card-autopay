import datetime
import plaid
from dotenv import load_dotenv
import os
from flask import Flask, request
from plaid.api import plaid_api
from plaid.model.liabilities_get_request import LiabilitiesGetRequest
from pay_bill import CheckPayment
from setup_autopay import app, client
import requests

"""There still need to be a lot of checks around dates / edge cases as to when new bills come in / check processing time."""

class CreditCardBill:
    
    def __init__(self, credit_card_id, credit_limit, last_paid_date, due_date, curr_balance) -> None:
        self.credit_card_id = credit_card_id
        self.credit_limit = credit_limit
        self.credit_utilization_rate = 0.3
        self.last_paid_date = last_paid_date
        self.due_date = due_date
        self.current_balance = curr_balance
        self.last_paid_initiated_date = None

    def determine_if_bill_needs_to_be_paid(self):
        '''Bill Needs to be paid if due date is within 10 days (to account for check processing time)'''
        bill_needs_to_be_paid = False
        if self.due_date - datetime.now() < 10 and self.current_balance > 0:
            bill_needs_to_be_paid = True
        elif self.current_balance > self.credit_utilization_rate * self.credit_limit:
            bill_needs_to_be_paid = True
        # There are edge cases where the bill has been paid yesterday, but check takes time to process so it's not yet reflected, but yet balance goes up, so webhook is fired again
        if self.last_paid_initiated_date and self.last_paid_initiated_date > self.last_paid_date:
            bill_needs_to_be_paid = False
        if self.last_paid_initiated_date - datetime.now() > 10:
            self.last_paid_initiated_date = self.last_paid_date # if it's been over 10 days, assume check failed and that the payment has not been made
        # ignoring cases, when the check does not go through
        
    
        return bill_needs_to_be_paid
        
    
    def determine_how_much_to_pay(self):
        if self.determine_if_bill_needs_to_be_paid():
            '''There are a lot of edge cases to be worked out here'''
            # There are additional edge cases around the current_balance and making sure it's only reflecting what is due at the current month.
            return self.current_balance
        else:
            return 0
        
    
    def handle_bill(self): 
        if self.determine_if_bill_needs_to_be_paid():
            amount = self.determine_how_much_to_pay()
            check = CheckPayment(self.credit_card_id, amount)
            check.pay_bill()
        else:
            pass

@app.route('/webhooks/credit_bill_updates', methods=['POST'])
def credit_bill_updates():
        '''make sure autopay is enabled for the credit card bill'''
        webhook_data = request.json()
        for key, value in webhook_data.items():
            print(key, value)
        access_token = webhook_data['item_id']
        '''Due to the nature of webhooks, even credit card bills for cards that have not fully set up autopay will be sent here.
        If autopay is not set up, then we should not do anything & instead send an error message.'''
        autopay_enabled = requests.get('/is_autopay_enabled/{{access_token}}')['autopay_enabled']
        if autopay_enabled:
            getLiabilitiesrequest = LiabilitiesGetRequest(access_token=access_token)
            liabilitiesResponse = client.liabilities_get(getLiabilitiesrequest)
            credit_bill_info = liabilitiesResponse['liabilities']['credit'][0] # assumes only one credit card
            due_date = credit_bill_info['payment_due_date']
            last_paid_date = credit_bill_info['last_payment_amount']['date']
            curr_balance = credit_bill_info['balances']['current']
            credit_limit = credit_bill_info['credit_limit']
            # search for credit_card_id in database
            credit_card_id = credit_bill_info['account_id']
            bill = CreditCardBill(credit_card_id, credit_limit, last_paid_date, due_date, curr_balance)
            bill.handle_bill()
        else:
            return "Autopay is not enabled for this credit card bill. Missing information.", 400
    





        

    # essentially if anything above changes, via webhooks, then update
    # after updating, then check if the bill needs to be paid

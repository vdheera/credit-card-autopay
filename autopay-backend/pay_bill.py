
"""Use Column API for this! """

# Need to Create an Entity for the bill
# Column must first fund the account with the amount of the bill (using counterparty)
# Check balance of that account before issuing the check; Column API already does this but an extra check is good

# Then, use Column's API to issue the check & track the status of the check

# on load, get all existing bills from the database
# then, listen to webhooks for any changes to the bills -> 


import hashlib
import hmac
from flask import request
from setup_autopay import app
import os, requests


class CheckPayment: 

    def __init__(self, credit_card_id, payment_amount, payee_name, mask) -> None:
        self.payment_amount = payment_amount
        self.corresponding_credit_card_id = credit_card_id
        self.mail_to_address = None
        self.counterparty_account_number = None
        self.counterparty_routing_number = None
        self.receivedfunds = False
        self.check_status = 'N/A'
        self.checkId = None
        self.payee_name = None
        self.credit_card_number = mask

    def get_bank_address(self): 
        # open creditcard.csv and get the bank address
        csv_file = open('creditcard.csv', 'r')
        csv_file.readline() # skip the first line
        for line in csv_file:
            line = line.split(',')
            if line[0] == self.corresponding_credit_card_id:
                self.mail_to_address = line[3]
                break
        csv_file.close()

    def fund_account(self):
        csv_file = open('creditcard.csv', 'r')
        csv_file.readline() # skip the first line
        for line in csv_file:
            line = line.split(',')
            if line[0] == self.corresponding_credit_card_id:
                self.counterparty_routing_number = line[1]
                self.counterparty_account_number = line[2]
                break
        csv_file.close()
        try: 
            headers = {"header": os.getenv("COLUMN_API_KEY"), "Content-Type": "application/json"}
            body = {'routing_number': self.counterparty_routing_number, 'account_number': self.counterparty_account_number}
            response = requests.post('https://api.column.com/counterparties', headers= headers, body=body)
            counterparty_id = response.json()['id']
            self.payment_amount = self.convert_amount_to_cents(self.payment_amount)
            body = {'amount': self.payment_amount, 'currency_code': 'USD', 'account_number_id': os.getenv('COLUMN_HOST_ID'), 'counterparty_id': counterparty_id, 'type': 'DEBIT'}
            achTransferID = requests.post('https://api.column.com/transfers/ach', headers=headers, body=body)['id']
            # need to make sure that the counterparty account has enough funds
        except: 
            print("Error: Could not issue transfer funds")

    def convert_amount_to_cents(self):
        return self.payment_amount * 100


    def issue_check(self):
        if self.receivedfunds:
            headers = {"header": os.getenv("COLUMN_API_KEY"), "Content-Type": "application/json"}
            body = {'bank_account_id': os.getenv('COLUMN_HOST_ID'), 'positive_pay_amount': self.payment_amount,  'mail_check_request': {'payee_address': self.mail_to_address},  'memo': 'Payment for Credit Card Bill for account ending in {{self.creditcardnumber}}'}
            response = requests.post('https://api.column.com/transfers/checks/issue', headers=headers, body=body)
            self.log_check(response['id'], )
            pass

    def log_check(self, checkid):
        csv_writer = open('check.csv', 'a')
        csv_writer.write(checkid + ',' + self.checkstatus + ',' + self.creditcardid + ',' + self.issue_date + ',' + self.amount + '\n')
        pass


    
    def pay_bill(self, userid, amount):
        check = CheckPayment(userid, amount)
        check.get_bank_address()
        check.fund_account()


@app.route('/webhooks/ach_transfer', methods=['POST'])
def update_ach_transfer_status(CheckPayment):
    # waiting to make sure the ACH transfer has been received before issuing the check
    # make sure the webhook event came from Column
    webhook_data = request.json()
    # Compute HMAC with SHA-256
    computed_hmac = hmac.new(os.getenv("COLUMN_ACH_WEBHOOK_SECRET"), webhook_data, hashlib.sha256).hexdigest()
    if computed_hmac != request.headers['X-Column-Signature']:
        return "Error: Could not verify webhook signature", 400
    else: 
        if webhook_data['type'] == 'ach.incoming_transfer.completed' and webhook_data['id'] == achTransferID:
            CheckPayment.receivedfunds = True
            CheckPayment.send_check()
    return "Success", 200


@app.route('/webhooks/check_status', methods=['POST'])
def update_check_status(CheckPayment):
    webhook_data = request.json()
    computed_hmac = hmac.new(os.getenv("COLUMN_CHECK_WEBHOOK_SECRET"), webhook_data, hashlib.sha256).hexdigest()
    if computed_hmac != request.headers['X-Column-Signature']:
        return "Error: Could not verify webhook signature", 400
    else: 
        if webhook_data['type'].startsWith('check'): 
            CheckPayment.check_status = webhook_data['type']
            # overwrite the check.csv file with the new status
            # check.csv file should be in the format: checkid, checkstatus, creditcardid, issue_date, amount
            csv_file = open('check.csv', 'r')
            csv_file.readline() # skip the first line
            lineNumber = 0
            for i, line in enumerate(csv_file):
                line = line.split(',')
                if line[0] == CheckPayment.checkId:
                    lineNumber = i
                    break
            csv_file.write_through(lineNumber, CheckPayment.checkId + ',' + CheckPayment.check_status + ',' + CheckPayment.corresponding_credit_card_id + ',' + CheckPayment.issue_date + ',' + CheckPayment.payment_amount + '\n')
    return "Success", 200



    


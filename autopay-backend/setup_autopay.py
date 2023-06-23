# Description: This file contains the backend code for setting up autopay for a new credit card.
import csv, os, requests
from dotenv import load_dotenv
from flask import Flask, request
import plaid
from plaid.api import plaid_api
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_account_filters import LinkTokenAccountFilters
from plaid.model.liabilities_get_request import LiabilitiesGetRequest
from plaid.model.products import Products
from plaid.model.country_code import CountryCode
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.credit_filter import CreditFilter
from plaid.model.credit_account_subtypes import CreditAccountSubtypes
from plaid.model.credit_account_subtype import CreditAccountSubtype
from plaid.model.auth_get_request import AuthGetRequest

"""
This sets up autopay for a new credit card. 
Linking a new credit card is done via Plaid's API.
This also determines the mailing address of the credit card company (this is where we'll send the check to)
The 'user' here is a singular credit card for which autopay is being set up.' -> essentially I'm not doing any KYC here. 
The corresponding 'model' here can be found in the creditcard.csv file. 
"""


load_dotenv()

app = Flask(__name__)

configuration = plaid.Configuration(
    host=plaid.Environment.Sandbox,
    api_key={
        'clientId': os.getenv('PLAID_CLIENT_ID'),
        'secret': os.getenv('PLAID_SANDBOX_SECRET')
    }
)
api_client = plaid.ApiClient(configuration)
client = plaid_api.PlaidApi(api_client)

csv_reader = csv.DictReader('creditcard.csv')
numCreditCardsLinked = len(csv_reader) - 1


''' Initial route that is called when a user clicks 'Get Started' on Landing Page.
This route creates a link_token, which is used to initialize the Plaid Link flow on the front-end.
'''
@app.route('/setup_new_card_autopay', methods=['POST'])
def setup_new_credit_card_autopay():
    try: 
        createLink = LinkTokenCreateRequest(
            products=[Products('auth'), Products('liabilties')],
            client_name="Autopay",
            country_codes=[CountryCode('US')],
            redirect_uri='https://localhost:8000/link-payment-method.html',
            language='en',
            webhook='https://localhost:3000/webhooks/credit_bill_updates',
            link_customization_name='default',
            account_filters=LinkTokenAccountFilters(
                credit=CreditFilter(
                    account_subtypes=CreditAccountSubtypes(
                    [CreditAccountSubtype('credit card')]
                )
                )
            ),
            user=LinkTokenCreateRequestUser(
                client_user_id= "user-id"
                '''right now, the way it's setup this largely does nothing but a user is required for the API call
                it's irrelevant in this context, because I haven't added 'Login/User' functionality yet, so we don't have a real userid to mark which user is linking a credit card
                this will change in the future'''
            ),
        )
        link_token = client.link_token_create(createLink)['link_token']
        return {'link_token': link_token}, 200
    except plaid.ApiException as e:
        return {'error': e}, 400
    
'''Public token is sent to this route from the front-end in exchange for an access_token.'''
'''If the linked item is a credit card, we use the access_token to get the credit card info and mailing address of the linked credit card.
We'll need the credit card info to identify 'unique' credit cards & save to the creditcard.csv file and the mailing address to send the check to.
If the linked item is a bank account, we use the access_token to get the bank account info & save that -- this is the account we'll be using where the check amount will come from.'''

@app.route('/get_access_token/<public_token>', methods=['POST'])
def exchange_public_token_for_access_token(public_token, linkItem, credit_card_id=0):
    try: 
        exchange_request = client.item_public_token_exchange(public_token)
        access_token = exchange_request['access_token']
        if linkItem == 'credit_card':
            # use the Auth Product to get the credit card info
            if (get_credit_card_info(access_token) == 'error'):
                return {'error': 'Credit Card already linked'}, 400
            # need to map access_token to account id
            # save to credit card database
        else:
            credit_cardID = credit_card_id # payment method is associated with this credit card. 
            get_bank_account_info(access_token)
            csv_writer = csv.DictWriter('paymentinfo.csv')
            csv_writer.writerow({'id': credit_cardID, 'counterpartyroutingnumber': access_token, 'counterpartyaccountnumber': ''})

            # save to credit card database
        return {'access_token': access_token}, 200
    except plaid.ApiException as e:
        return {'error': e}, 400


def get_bank_account_info(access_token):
    '''Need to get the bank account info to save to the database.'''
    try:
        request = LiabilitiesGetRequest(access_token=access_token)
        response = client.liabilities_get(request)
        bank_account_info = response['accounts'][0]
        routing = bank_account_info['routing']
        account_number = bank_account_info['account_number']
        '''Write to paymentinfo.csv'''
        csv_writer = csv.DictWriter('paymentinfo.csv')
        csv_writer.writerow({'id': access_token, 'counterpartyroutingnumber': routing, 'counterpartyaccountnumber': account_number})
        # save to database
    except plaid.ApiException as e:
        return {'error': e}, 400
    


def get_credit_card_info(access_token):
    '''Need to Get the ABA or BIC Number of the Linked Credit Card -> needed to get mailing address for check. 
    Also need to get information to uniquely identify this credit card.'''
    try:
        request = AuthGetRequest(access_token=access_token)
        response = client.auth_get(request)
        # there theoretically could be multiple linked credit cards under one access token, however for the proof of concept, we're ignoring this case
        # TODO: less of a technical problem, more of a financial understanding problem / UX problem -- how can someone link two credit cards to one access token?
        credit_card_info = response['accounts'][0]
        check_mailing_address = get_mailing_address(credit_card_info['routing'])
        # The name & mask is how we'll uniquely identify the credit card -- not perfect; but it's the best we can do for now -> in any case, duplicates aren't a HUGE problem because the bill should be paid off anyways by the time it checks the duplicate. 
        credit_card_name = credit_card_info['name']
        credit_card_mask = credit_card_info['mask']
        # check if credit card already exists in database
        csv_reader = csv.DictReader('creditcard.csv')
        for row in csv_reader:
            if row['name'] == credit_card_name and row['mask'] == credit_card_mask:
                return "error"
        credit_card_info = {'id': numCreditCardsLinked, 'name': credit_card_name, 'mask': credit_card_mask, 'mailing_address': check_mailing_address}
        numCreditCardsLinked+=1
        csv_writer = csv.DictWriter('creditcard.csv')
        csv_writer.writerow({'id': credit_card_info['id'], 'name': credit_card_info['name'], 'mask': credit_card_info['mask'], 'mailing_address': credit_card_info['mailing_address'], 'numBillsPayed': 0})
        return credit_card_info
    except:
        return "Internal Server Error. Unable to get credit card info.", 500



def get_mailing_address(routing_number):
    '''I'll get the mailing address from the routing number using Column's API.
    Previously this was an additional POST request route, where users could upload a PDF and used OCR
    to get the mailing address.
    That was a lot of work + high error rate + not great user experience
    Learned that Column's API gives us this
    however, not entirely 100% sure on accuracy rate -- less of a technical problem, and more of a business problem
    is the bank's address the same place you make checks payable to?  
    It doesn't look like Column's API has a Python SDK, so I'll have to use the requests library.
    '''
    try: 
        headers = {"header": os.getenv("COLUMN_API_KEY"), "Content-Type": "application/json"}
        response = requests.get("https://api.column.com/institutions/{}".format(routing_number), headers=headers)
        mailing_address = response['street_address'] + " " + response['city'] + " " + response['state'] + " " + response['zip_code']
        return mailing_address
    except Exception as e:
        return "Internal Server Error. Unable to get mailing address."


@app.route('/link_payment_method/<credit_card_id>', methods=['POST'])
def link_payment_method(credit_card_id):
    '''Credit Card ID is the internal credit card id that we generate.
    This links a payment method to how we pay off the credit card.
    The payment method cannot be another credit card.
    At the current moment, don't support changing payment method.'''
    try: 
        createLink = LinkTokenCreateRequest({ 
            'client_name': 'AutoPay',
            'products': ['auth', 'balance'],
            'country_codes': ['US'],
            'language': 'en',
            'account_filters': LinkTokenAccountFilters(depository=LinkTokenAccountFiltersDepository(account_subtypes=['credit'])),
            'user': LinkTokenCreateRequest.User(client_user_id='1')
        })
        link_token = client.link_token_create(createLink)['link_token']
        # only when this successfully runs, write to the CSV file.
        return {'link_token': link_token}, 200
    except plaid.ApiException as e:
        return {'error': e}, 400
    # find associated credit_card_id and store payment method with that credit card


@app.route('/is_autopay_enabled/<credit_card_id>')
def is_autopay_enabled(credit_card_id):
    cc_csv_reader = csv.DictReader('creditcard.csv')
    paymentinfo_csv_reader = csv.DictReader('paymentinfo.csv')
    for row in cc_csv_reader:
        if row['creditcard_id'] == credit_card_id:
            if row['autopay_enabled'] == True:
                return {'autopay_enabled': True}, 200
            else:
                return {'autopay_enabled': False}, 200
    for row in paymentinfo_csv_reader:
        if row['creditcard_id'] == credit_card_id:
            return {'autopay_enabled': True}, 200
    
    return {'autopay_enabled': True}, 200

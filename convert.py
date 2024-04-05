from pprint import pprint
from datetime import datetime
import copy, re, os

from alive_progress import alive_bar

import firefly_iii_client
from firefly_iii_client.api import (
    about_api,
    transactions_api,
    attachments_api,
    links_api,
    search_api,
    accounts_api,
)
from firefly_iii_client.model.transaction_store import TransactionStore
from firefly_iii_client.model.transaction_split_store import TransactionSplitStore
from firefly_iii_client.model.transaction_type_property import TransactionTypeProperty
from firefly_iii_client.model.attachment_store import AttachmentStore
from firefly_iii_client.model.attachable_type import AttachableType
from firefly_iii_client.model.transaction_link_store import TransactionLinkStore
from firefly_iii_client.model.account_type_filter import AccountTypeFilter
from firefly_iii_client.model.account_search_field_filter import AccountSearchFieldFilter
from firefly_iii_client.model.account_store import AccountStore
from firefly_iii_client.model.short_account_type_property import ShortAccountTypeProperty
from config import (
    HOST,
    APIKEY,
    DB_FILE,
    DB_CONFIG,
    DEFAULT_CURRENCY,
    ATTACHMENTS_FOLDER,
    LINKS,
    DESC_AS_ACC,
)
from db import bluecoinsDB


def fmt_amount(amount: int) -> str:
    return str(abs(round(int(amount) / 1000000, 2)))


def fmt_note(note: str) -> str:
    return str


def upload_attachment(attachment: str, attachable_id: str):
    path = os.path.join("./", ATTACHMENTS_FOLDER, attachment)
    if not os.path.isfile(path):
        print("!!! Attchment %s not found, skipping" % path)
        return
    attachment_store = AttachmentStore(
        filename=attachment,
        attachable_type=AttachableType("TransactionJournal"),
        attachable_id=attachable_id,
        title=attachment,
    )
    try:
        attach_resp = api_attachments_instance.store_attachment(attachment_store)
        attach_id = attach_resp["data"].id
    except firefly_iii_client.ApiException as e:
        print("Exception when calling AttachmentsApi->store_attachment: %s\n" % e)
        return
    body = open(path, "rb")
    try:
        api_attachments_instance.upload_attachment(attach_id, body=body)
    except firefly_iii_client.ApiException as e:
        print("Exception when calling AttachmentsApi->upload_attachment: %s\n" % e)
    finally:
        body.close()


# Check API connection
configuration = firefly_iii_client.Configuration(host=HOST, access_token=APIKEY)
api_client = firefly_iii_client.ApiClient(configuration)
api_about_instance = about_api.AboutApi(api_client)
try:
    api_response = api_about_instance.get_about()
    pprint(api_response)
except firefly_iii_client.ApiException as e:
    print("Exception when calling AboutApi->get_about: %s\n" % e)

# Open Database
db = bluecoinsDB(DB_FILE)

# Prepare API
api_transaction_instance = transactions_api.TransactionsApi(api_client)
api_attachments_instance = attachments_api.AttachmentsApi(api_client)
api_links_instance = links_api.LinksApi(api_client)
api_links_instance.store_transaction_link_endpoint.settings['endpoint_path'] = '/api/v1/transaction-links'
api_search_instance = search_api.SearchApi(api_client)
api_accounts_instance = accounts_api.AccountsApi(api_client)

default_transaction_store = TransactionStore(
    error_if_duplicate_hash=True, apply_rules=True, fire_webhooks=True, transactions=[]
)

## MAIN 1: Transactions
total_txs = db.query_transactions_count()
txs = db.query_transactions()

with alive_bar(total_txs, force_tty=True, title="Transactions") as bar:
    for tx in txs:  # noqa: MC0001
        bar.text(tx["itemName"])

        # Prepare Result Row
        ids = tx["transactionsTableIDs"].split(",")
        amounts = tx["amounts"].split(",")
        category_ids = tx["categoryIDs"].split(",")
        account_ids = tx["accountIDs"].split(",")
        notes = tx["notes"].split(chr(0x1D)) if tx["notes"] else []
        labels = tx["labelNames"].split(",") if tx["labelNames"] else []
        attachments = tx["pictureFileName"].split(",") if tx["pictureFileName"] else []
        date = datetime.strptime(tx["date"], DB_CONFIG["DATE_FORMAT"])

        transactions = {
            "deposit": {},
            "withdrawal": {},
        }

        for i, id in enumerate(ids):
            if int(amounts[i]) == 0:
                continue

            transaction = TransactionSplitStore(
                type=TransactionTypeProperty("deposit")
                if int(amounts[i]) > 0
                else TransactionTypeProperty("withdrawal"),
                date=date,
                amount=fmt_amount(amounts[i]),
                description=tx["itemName"],
                order=i,
                currency_code=DEFAULT_CURRENCY,
                # budget_id
                category_name=db.category_name(category_ids[i]),
                reconciled=True if tx["status"] == 2 else False,
                tags=labels,
                notes=notes[i].strip() if len(notes) >= (i + 1) else None,
                external_id=ids[i],
            )

            # Source/Destionation
            account = db.account_name(account_ids[i])
            if DESC_AS_ACC:
                exp_acc_search_res = [a for a in api_search_instance.search_accounts(tx["itemName"], AccountSearchFieldFilter("name"), type=AccountTypeFilter("expense")).data if a['attributes']['name'] == tx["itemName"]]
                if len(exp_acc_search_res) == 0:
                    account_store = AccountStore(
                        name=tx["itemName"],
                        type=ShortAccountTypeProperty("expense"),
                    )
                    try:
                        api_response = api_accounts_instance.store_account(account_store)
                        new_exp_account_id = api_response['data']['id']
                    except firefly_iii_client.ApiException as e:
                        print("Exception when calling AccountsApi->store_account: %s\n" % e)
                else:
                    new_exp_account_id = exp_acc_search_res[0]['id']
            if transaction.type == TransactionTypeProperty("deposit"):
                transaction.destination_name = account
                if DESC_AS_ACC:
                    transaction.source_id = new_exp_account_id
                else:
                    transaction.source_id = str(DB_CONFIG["CASH_ACCOUNT_ID"])
                type = "deposit"
            elif transaction.type == TransactionTypeProperty("withdrawal"):
                transaction.source_name = account
                if DESC_AS_ACC:
                    transaction.destination_id = new_exp_account_id
                else:
                    transaction.destination_id = str(DB_CONFIG["CASH_ACCOUNT_ID"])
                type = "withdrawal"


            # Handle conversion
            if tx["transactionCurrency"] != DEFAULT_CURRENCY:
                transaction.currency_code = tx["transactionCurrency"]
                transaction.amount = fmt_amount(
                    int(amounts[i]) * float(tx["conversionRateNew"])
                )

            if account not in transactions[type]:
                transactions[type][account] = []

            transactions[type][account].append(transaction)

        trans_link = []
        for accounts in transactions.values():
            for account, splits in accounts.items():
                transaction = copy.deepcopy(default_transaction_store)
                transaction.transactions = splits

                if len(splits) > 1:
                    transaction.group_title = tx["itemName"]

                for split in transaction.transactions:
                    # Split note handling
                    if not split.notes:
                        continue
                    note = re.findall(r"^\[\{(.*)\}\](.*)$", split.notes, re.DOTALL)
                    if len(note) == 0:
                        continue
                    split.notes = note[0][0].strip()
                    if len(note[0][1]) != 0:  # Required field
                        split.description = note[0][1].strip()

                try:
                    transaction_resp = api_transaction_instance.store_transaction(
                        transaction
                    )
                except firefly_iii_client.ApiException as e:
                    print(
                        "Exception when calling TransactionsApi->store_transaction: %s\n"
                        % e
                    )
                    continue

                if len(trans_link) != 0:
                    for link in trans_link:
                        try:
                            link_resp = api_links_instance.store_transaction_link(
                                TransactionLinkStore(
                                    link_type_id=str(LINKS["RELATED"]),
                                    inward_id=transaction_resp["data"].id,
                                    outward_id=link,
                                )
                            )
                        except firefly_iii_client.ApiException as e:
                            print(
                                "Exception when calling LinksApi->store_transaction_link: %s\n"
                                % e
                            )
                trans_link.append(transaction_resp["data"].id)

                # Attachments
                for attachment in attachments:
                    upload_attachment(
                        attachment,
                        transaction_resp["data"]
                        .attributes.transactions[0]
                        .transaction_journal_id,
                    )

        bar()

## MAIN 2: Transfers
total_txs = db.query_transfers_count()
txs = db.query_transfers()

with alive_bar(total_txs, force_tty=True, title="Transfers   ") as bar:
    for tx in txs:  # noqa: MC0001
        # Prepare Result Row
        bar.text(tx["itemName"])

        attachments = tx["pictureFileName"].split(",") if tx["pictureFileName"] else []
        date = datetime.strptime(tx["date"], DB_CONFIG["DATE_FORMAT"])
        notes = tx["notes"].split(chr(0x1D)) if tx["notes"] else []
        labels = tx["labelNames"].split(",") if tx["labelNames"] else []
        account_from = db.account_name(tx["from_accountID"])
        account_to = db.account_name(tx["to_accountID"])

        if fmt_amount(tx["from_amount"]) != fmt_amount(tx["to_amount"]):
            print(
                "!!! Cannot create transfer, amounts are different? From: %s, To: %s"
                % tx["from_amount"],
                tx["to_amount"],
            )
            continue

        transaction_store = TransactionSplitStore(
            type=TransactionTypeProperty("transfer"),
            date=date,
            amount=fmt_amount(int(tx["from_amount"]) * float(tx["from_conversionRate"])),
            description=tx["itemName"],
            currency_code=tx['from_currency'],
            source_name=account_from,
            destination_name=account_to,
            reconciled=True if tx["status"] == 2 else False,
            tags=labels,
            notes=tx["notes"].strip(),
            external_id=str(tx["from_id"]),
        )
        # Handle conversion
        if tx["from_currency"] != tx["to_currency"]:
            transaction_store.foreign_currency_code = tx["to_currency"]
            transaction_store.foreign_amount = fmt_amount(
                int(tx["to_amount"]) * float(tx["to_conversionRate"])
            )

        # Insert
        transaction = copy.deepcopy(default_transaction_store)
        transaction.transactions = [transaction_store]
        try:
            transaction_resp = api_transaction_instance.store_transaction(transaction)
        except firefly_iii_client.ApiException as e:
            print("Exception when calling TransactionsApi->store_transaction: %s\n" % e)
            continue

        # Attachments
        for attachment in attachments:
            upload_attachment(
                attachment,
                transaction_resp["data"]
                .attributes.transactions[0]
                .transaction_journal_id,
            )

        bar()

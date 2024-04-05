HOST = ""  # Firefly III host, without trailing /!
APIKEY = ""  # Firefly III API Key
DB_FILE = "bluecoins-data/bluecoins.fydb"
ATTACHMENTS_FOLDER = "bluecoins-data/Pictures/"
DEFAULT_CURRENCY = "EUR"
DESC_AS_ACC = True

# These values shouldn't change, but I can't really verify it.
# They are used internally by BlueCoins.
DB_CONFIG = {
    "TRANSACTION_NEWACCOUNT": 2,
    "TRANSACTION_WITHDRAWAL": 3,
    "TRANSACTION_DEPOSIT": 4,
    "TRANSACTION_TRANSFER": 5,
    "DATE_FORMAT": "%Y-%m-%d %H:%M:%S",
    "CASH_ACCOUNT_ID": 7,
}

# Default link types used in Firefly III.
LINKS = {
    "RELATED": 1,
    "REIMBURSED": 2,
    "PAYEDBY": 3,
    "SETTLES": 4,
}

# Bluecoins to Firefly III importer

Python script to import a [Bluecoins](https://play.google.com/store/apps/details?id=com.rammigsoftware.bluecoins) database into a [Firefly III](https://github.com/firefly-iii/firefly-iii/) instance

## How to Use

1. Set up a config file (see example in `config.example.py`)
2. Make an export in Bluecoins, put the resulting `bluecoins.fydb` file into the folder `bluecoins-data`.
3. If you used attachments, put the `Pictures` folder (e.g. from a Google Drive export, or locally on your phone from `Internal Storage/Bluecoins/`) also inside `bluecoins-data`.
4. Run `convert.py`, check the output.

## Notes

- Use this on an new (empty) Firefly III instance, or with a backup at hand. It might mess stuff up.
- Set up all needed currencies first inside Firefly III, transactions with unknown currency will throw an error when trying to import them.
- It's best to set up rules inside Firefly III first to modify the transactions according to your needs.
  - This is also the way to go to assign actual source/destination accounts (instead of `(Cash)`).
- Set `DESC_AS_ACC` in `config.py` to `True` to use the "Description" field as the opposing account name (expenses account created if not already present)
- The initial bank statements are not imported. You can set them manually in Firefly III after the import for each account.
- Firefly III has some limitations that Bluecoins has not:
  - Split transaction always needs to have the same source account.
  - A split transaction needs to be the same type throughout (i.e. cannot be split between Deposit & Withdrawal).
  - The Transaction Fees feature of Bluecoins not feasible in Firefly III. Instead, a separate Withdrawal is created, with a link to the original transaction.

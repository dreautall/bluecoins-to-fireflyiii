import sqlite3
from config import DB_CONFIG


class bluecoinsDB:
    _cache_categories = {}
    _cache_accounts = {}
    conn: sqlite3.Connection = None

    def __init__(self, db_file: str):
        try:
            self.conn = sqlite3.connect(db_file)
            self.conn.row_factory = self.dict_factory
        except sqlite3.Error as e:
            print(e)

    def dict_factory(self, cursor: sqlite3.Cursor, row):
        d = {}
        for idx, col in enumerate(cursor.description):
            d[col[0]] = row[idx]
        return d

    def query_transactions(self) -> sqlite3.Cursor:
        sql = (
            "SELECT"
            "   GROUP_CONCAT(transactionsTableID) AS transactionsTableIDs, "
            "   ITEMTABLE.itemName, "
            "   GROUP_CONCAT(amount) AS amounts, "
            "   transactionCurrency, "
            "   conversionRateNew, "
            "   date, "
            "   status, "
            "   transactionTypeID, "
            "   GROUP_CONCAT(categoryID) AS categoryIDs, "
            "   GROUP_CONCAT(accountID) as accountIDs, "
            "   GROUP_CONCAT(notes, CHAR(0x1D)) as notes, "
            "   (CASE WHEN newsplittransactionid IS 0 THEN NULL ELSE newsplittransactionid END) AS mergedSplitTransactionID, "
            "   (SELECT GROUP_CONCAT(labelName) FROM LABELSTABLE WHERE transactionIDLabels = transactionsTableID GROUP BY transactionIDLabels) AS labelNames, "
            "   (SELECT GROUP_CONCAT(pictureFileName) FROM PICTURETABLE WHERE transactionID = transactionsTableID GROUP BY transactionID) AS pictureFileName "
            "FROM "
            "   TRANSACTIONSTABLE "
            "INNER JOIN ITEMTABLE "
            "   ON ITEMTABLE.itemTableID = TRANSACTIONSTABLE.itemID "
            "WHERE "
            "   reminderTransaction is NULL "
            f"  AND transactionTypeID IN ({DB_CONFIG['TRANSACTION_DEPOSIT']},{DB_CONFIG['TRANSACTION_WITHDRAWAL']}) "
            "   AND deletedTransaction = 6 "
            "   AND status <> 3 "
            "GROUP BY "
            "   IFNULL(CASE WHEN newsplittransactionid IS 0 THEN NULL ELSE newsplittransactionid END, transactionstableid) "
            "ORDER BY "
            "   date DESC, transactionsTableID ASC "
        )
        cur = self.conn.cursor()

        return cur.execute(sql)

    def query_transactions_count(self) -> int:
        sql = (
            "SELECT COUNT(*) AS count FROM "
            "   (SELECT "
            "       transactionsTableID "
            "       FROM "
            "           TRANSACTIONSTABLE "
            "       INNER JOIN ITEMTABLE "
            "           ON ITEMTABLE.itemTableID = TRANSACTIONSTABLE.itemID "
            "       WHERE "
            "           reminderTransaction is NULL "
            f"          AND transactionTypeID IN ({DB_CONFIG['TRANSACTION_DEPOSIT']},{DB_CONFIG['TRANSACTION_WITHDRAWAL']}) "
            "           AND deletedTransaction = 6 "
            "           AND status <> 3 "
            "       GROUP BY "
            "           IFNULL( "
            "              CASE WHEN newsplittransactionid IS 0 THEN NULL ELSE newsplittransactionid END, "
            "           transactionstableid) "
            "   )"
        )
        cur = self.conn.cursor()
        res = cur.execute(sql)
        count = res.fetchone()

        return count["count"]

    def query_transfers(self) -> sqlite3.Cursor:
        sql = (
            "SELECT "
            "   ITEMTABLE.itemName, "
            "   t1.transactionsTableID AS from_id, t2.transactionsTableID AS to_id, "
            "   t1.amount AS from_amount, t2.amount AS to_amount, "
            "   t1.transactionCurrency as from_currency, t2.transactionCurrency as to_currency, "
            "   t1.conversionRateNew as from_conversionRate, t2.conversionRateNew as to_conversionRate, "
            "   t1.date, "
            "   t1.accountID AS from_accountID, t2.accountID AS to_accountID, "
            "   t1.notes, "
            "   t1.status, "
            "   (SELECT GROUP_CONCAT(labelName) FROM LABELSTABLE WHERE transactionIDLabels = t1.transactionsTableID GROUP BY transactionIDLabels) "
            "       AS labelNames, "
            "   (SELECT GROUP_CONCAT(pictureFileName) FROM PICTURETABLE WHERE transactionID = t1.transactionsTableID GROUP BY transactionID) "
            "       AS pictureFileName "
            "FROM "
            "   TRANSACTIONSTABLE t1 "
            "INNER JOIN TRANSACTIONSTABLE t2 "
            "   ON t2.transactionsTableID = t1.uidPairID AND t1.transactionsTableID < t2.transactionsTableID "
            "INNER JOIN ITEMTABLE "
            "   ON ITEMTABLE.itemTableID = t1.itemID "
            "WHERE "
            "   t1.reminderTransaction is NULL "
            f"   AND t1.transactionTypeID = {DB_CONFIG['TRANSACTION_TRANSFER']} "
            "   AND t1.deletedTransaction = 6 "
            "ORDER BY "
            "   t1.date DESC, t1.transactionsTableID ASC "
        )
        cur = self.conn.cursor()

        return cur.execute(sql)

    def query_transfers_count(self) -> int:
        sql = (
            "SELECT "
            "   COUNT(*) AS count "
            "FROM "
            "   TRANSACTIONSTABLE t1 "
            "INNER JOIN TRANSACTIONSTABLE t2 "
            "   ON t2.transactionsTableID = t1.uidPairID AND t1.transactionsTableID < t2.transactionsTableID "
            "INNER JOIN ITEMTABLE "
            "   ON ITEMTABLE.itemTableID = t1.itemID "
            "WHERE "
            "   t1.reminderTransaction is NULL "
            f"   AND t1.transactionTypeID = {DB_CONFIG['TRANSACTION_TRANSFER']} "
            "   AND t1.deletedTransaction = 6 "
        )
        cur = self.conn.cursor()
        res = cur.execute(sql)
        count = res.fetchone()

        return count["count"]

    def category_name(self, id: int) -> str:
        if len(self._cache_categories) == 0:
            sql = (
                "SELECT "
                "   categoryTableID, "
                "   childCategoryName "
                "FROM "
                "   CHILDCATEGORYTABLE"
            )
            cur = self.conn.cursor()
            for res in cur.execute(sql):
                self._cache_categories[res["categoryTableID"]] = res[
                    "childCategoryName"
                ]

        return self._cache_categories[int(id)]

    def account_name(self, id: int) -> str:
        if len(self._cache_accounts) == 0:
            sql = (
                "SELECT "
                "   accountsTableID, "
                "   accountName "
                "FROM "
                "   ACCOUNTSTABLE"
            )
            cur = self.conn.cursor()
            for res in cur.execute(sql):
                self._cache_accounts[res["accountsTableID"]] = res["accountName"]

        return self._cache_accounts[int(id)]

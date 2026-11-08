import os
import pandas as pd
from app.db import get_engine

SQL = """
SELECT lower(trim(oi.name))             AS product_key,
       min(oi.name)                     AS example_name,
       count(DISTINCT oi.offer_external_id) AS offers,
       sum(oi.quantity)                 AS units,
       round(avg(oi.unit_price), 2)     AS avg_price_gross,
       min(co.ordered_at)::date         AS first_sale,
       max(co.ordered_at)::date         AS last_sale
FROM order_item oi
JOIN customer_order co ON co.order_id = oi.order_id
WHERE co.status <> 'CANCELLED'
GROUP BY lower(trim(oi.name))
ORDER BY units DESC
"""


def run():
    df = pd.read_sql(SQL, get_engine())
    df["unit_cost_net"] = ""
    df["vat_rate"] = 0.23
    os.makedirs("data", exist_ok=True)
    df.to_csv("data/product_costs.csv", index=False, sep=";",
              encoding="utf-8-sig")
    print(len(df), "produktow zapisano do data/product_costs.csv")


if __name__ == "__main__":
    run()
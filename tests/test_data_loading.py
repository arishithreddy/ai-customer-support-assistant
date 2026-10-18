from pathlib import Path
import pandas as pd

DATA_DIR = Path("data/mock_business")
def main():
    files = [
        "customers.csv",
        "orders.csv",
        "products.csv",
        "refunds.csv",
        "support_tickets.csv",
    ]

    for file_name in files:
        file_path = DATA_DIR / file_name
        df = pd.read_csv(file_path)
        print(f"{file_name}: {df.shape[0]} rows, {df.shape[1]} columns")
        print(df.head(2))
        print("-" * 80)

if __name__ == "__main__":
    main()

"""Utilities to load EDI transaction records from Azure AI Search, convert to DataFrame, analyze, and export to Excel."""

import os
import json
from datetime import datetime, date
from pathlib import Path
from typing import List, Dict, Optional

import pandas as pd
import openpyxl  
from azure.azure_blob_container_client import AzureBlobContainerClient
from azure.azure_search_setup import EDISearchService

class EDIDataLoader:
    def __init__(self, start_date: str, end_date: str):
        self.start_date = start_date
        self.end_date = end_date
        # Initialize Azure AI Search service (preferred data source)
        self.search_service = EDISearchService()
        # Kept for backward compatibility but unused in search mode
        self.connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
        self.json_container_name = os.getenv("AZURE_JSON_STORAGE_CONTAINER_NAME", "edi-json-structured")
        self.azure_blob_container_client = None
        


    def _parse_date(self, value: str) -> date:
        """Parse YYYY-MM-DD string to date."""
        return datetime.strptime(value, "%Y-%m-%d").date()


    def _within_range(self, d: str, start: date, end: date) -> bool:
        """Check if date string YYYY-MM-DD is within [start, end] inclusive."""
        try:
            return start <= self._parse_date(d) <= end
        except Exception:
            return False


    def _load_search_records(self, start_date: str, end_date: str) -> List[Dict]:
        """Query Azure AI Search for transactions within [start_date, end_date]."""
        # effective_date is stored as YYYY-MM-DD string and is filterable; string range works lexicographically
        filter_expr = f"effective_date ge '{start_date}' and effective_date le '{end_date}'"

        # Page through results using skip/top
        batch_size = 1000
        skip = 0
        records: List[Dict] = []

        # Select only fields needed downstream; include all core fields
        select_fields = [
            "trace_number",
            "amount",
            "effective_date",
            "originator",
            "receiver",
            "page_number",
            "routing_id_credit",
            "routing_id_debit",
            "company_id_debit",
            "mutually_defined",
            "file_name",
        ]

        while True:
            results = self.search_service.search_client.search(
                search_text="",  # filter-only query
                filter=filter_expr,
                select=select_fields,
                top=batch_size,
                skip=skip,
            )
            batch = [dict(r) for r in results]
            records.extend(batch)
            if len(batch) < batch_size:
                break
            skip += batch_size

        return records


    def load_edi_json(self, start_date: str, end_date: str) -> List[Dict]:
        """Load EDI transaction records from Azure AI Search within the date range.

        The `effective_date` is expected in YYYY-MM-DD format.
        """
        # Validate date inputs
        _ = self._parse_date(start_date)
        _ = self._parse_date(end_date)

        records = self._load_search_records(start_date, end_date)
        return records


    def to_dataframe(self, records: List[Dict]) -> pd.DataFrame:
        """Convert records to a pandas DataFrame and normalize types."""
        df = pd.DataFrame(records or [])
        if df.empty:
            return df

        # Normalize types
        if "effective_date" in df.columns:
            df["effective_date"] = pd.to_datetime(df["effective_date"], errors="coerce").dt.date
        if "amount" in df.columns:
            df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
        return df


    def analyze(self, df: pd.DataFrame) -> Dict[str, pd.DataFrame]:
        """Compute basic aggregations for quick insights."""
        if df.empty:
            empty = pd.DataFrame()
            return {
                "summary_totals": empty,
                "daily_totals": empty,
                "by_originator": empty,
                "by_receiver": empty,
            }

        # Summary totals
        totals = pd.DataFrame({
            "count": [len(df)],
            "sum_amount": [df["amount"].sum(skipna=True) if "amount" in df else 0.0],
            "avg_amount": [df["amount"].mean(skipna=True) if "amount" in df else 0.0],
        })

        # Daily totals
        if "effective_date" in df.columns:
            daily = (
                df.dropna(subset=["effective_date"])  # type: ignore[arg-type]
                .groupby("effective_date", dropna=False)["amount"]
                .sum(min_count=1)
                .reset_index()
                .rename(columns={"amount": "sum_amount"})
            )
        else:
            daily = pd.DataFrame()

        # By originator
        if "originator" in df.columns:
            by_originator = (
                df.groupby("originator", dropna=False)["amount"]
                .agg(["count", "sum", "mean"])
                .reset_index()
                .rename(columns={"sum": "sum_amount", "mean": "avg_amount"})
                .sort_values("sum_amount", ascending=False)
            )
        else:
            by_originator = pd.DataFrame()

        # By receiver
        if "receiver" in df.columns:
            by_receiver = (
                df.groupby("receiver", dropna=False)["amount"]
                .agg(["count", "sum", "mean"])
                .reset_index()
                .rename(columns={"sum": "sum_amount", "mean": "avg_amount"})
                .sort_values("sum_amount", ascending=False)
            )
        else:
            by_receiver = pd.DataFrame()

        return {
            "summary_totals": totals,
            "daily_totals": daily,
            "by_originator": by_originator,
            "by_receiver": by_receiver,
        }


    def export_to_excel(self, df: pd.DataFrame, analyses: Dict[str, pd.DataFrame], excel_path: str) -> str:
        """Export raw data and analyses to an Excel file with multiple sheets."""
        output_path = Path(excel_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            (df if not df.empty else pd.DataFrame()).to_excel(writer, index=False, sheet_name="raw")
            for name, adf in analyses.items():
                (adf if not adf.empty else pd.DataFrame()).to_excel(writer, index=False, sheet_name=name[:31])
        return str(output_path)


    def _default_output_path(self, start_date: str, end_date: str) -> str:
        backend_dir = Path(__file__).resolve().parent
        fname = f"edi_export_{start_date}_to_{end_date}.xlsx"
        return str(backend_dir / "processed_data" / fname)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Load EDI JSON from Azure, analyze, and export to Excel")
    parser.add_argument("--start", required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="End date YYYY-MM-DD")
    parser.add_argument("--out", default=None, help="Optional Excel output path")
    args = parser.parse_args()

    records = EDIDataLoader(args.start, args.end)._load_search_records(args.start, args.end)
    df = EDIDataLoader(args.start, args.end).to_dataframe(records)
    analyses = EDIDataLoader(args.start, args.end).analyze(df)

    excel_path = args.out or EDIDataLoader(args.start, args.end)._default_output_path(args.start, args.end)
    path = EDIDataLoader(args.start, args.end).export_to_excel(df, analyses, excel_path)
    print(f"Exported Excel to: {path}")
    print(f"Rows exported: {len(df)}")


if __name__ == "__main__":
    main()
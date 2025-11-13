"""Utilities to load Master EDI transaction records from Azure AI Search, convert to DataFrame, analyze, and export to Excel."""

import os
import json
from datetime import datetime, date
from pathlib import Path
from typing import List, Dict, Optional

import pandas as pd
import openpyxl  
from azure.azure_blob_container_client import AzureBlobContainerClient
from azure.azure_search_setup import EDISearchService

class MASTER_EDI_DataLoader:
    def __init__(self, start_date: str, end_date: str):
        self.start_date = start_date
        self.end_date = end_date
        # Initialize Azure AI Search service (preferred data source)
        self.search_service = EDISearchService(index_name="master-edi")
        

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


        # Select only fields needed downstream; include all core fields
        select_fields = [
            "id",
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
            "input_format",
            "demand_account_credit",
            "line_items",
        ]

        # Use orderby to ensure consistent ordering across pagination requests
        # Order by trace_number (unique identifier) to guarantee deterministic results
        orderby_fields = ["trace_number asc"]
        
     
        results = self.search_service.search_client.search(
            search_text="",  # filter-only query
            filter=filter_expr,
            select=select_fields,
            order_by=orderby_fields
        )
        records = [dict(r) for r in results]
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
    
    def get_dashboard_data(self, start_date: str, end_date: str) -> Dict:
        """Get dashboard data for the given date range."""
        records = self.load_edi_json(start_date, end_date)
        total_records = len(records)
        total_amount = sum(float(record["amount"]) for record in records)
        return {
            "total_records": total_records,
            "total_amount": total_amount
        }


    def to_dataframe(self, records: List[Dict]) -> pd.DataFrame:
        """Convert records to a pandas DataFrame and normalize types."""
        if not records:
            return pd.DataFrame()
        
        # Handle line_items: serialize complex nested structure as JSON string for DataFrame
        processed_records = []
        for record in records:
            processed_record = record.copy()
            # Convert line_items (list of dicts) to JSON string for Excel compatibility
            if "line_items" in processed_record and processed_record["line_items"]:
                if isinstance(processed_record["line_items"], list):
                    processed_record["line_items"] = json.dumps(processed_record["line_items"])
                elif processed_record["line_items"] is None:
                    processed_record["line_items"] = ""
            else:
                processed_record["line_items"] = ""
            processed_records.append(processed_record)
        
        df = pd.DataFrame(processed_records)
        if df.empty:
            return df

        # Normalize types
        if "effective_date" in df.columns:
            df["effective_date"] = pd.to_datetime(df["effective_date"], errors="coerce").dt.date
        if "amount" in df.columns:
            df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
        
        # Ensure all expected columns exist (fill missing with empty strings)
        expected_columns = [
            "trace_number", "amount", "effective_date", "originator", "receiver",
            "page_number", "routing_id_credit", "routing_id_debit", "company_id_debit",
            "mutually_defined", "file_name", "input_format", "demand_account_credit", "line_items"
        ]
        for col in expected_columns:
            if col not in df.columns:
                df[col] = ""
        
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
            # Convert date objects to strings for JSON serialization
            if not daily.empty and daily["effective_date"].dtype == "object":
                # Check if it's a date type and convert to string
                daily["effective_date"] = daily["effective_date"].apply(
                    lambda x: x.strftime("%Y-%m-%d") if hasattr(x, 'strftime') else str(x) if pd.notna(x) else ""
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
            # Export raw data
            if not df.empty:
                # Reorder columns for better readability
                column_order = [
                    "trace_number", "amount", "effective_date", "originator", "receiver",
                    "input_format", "file_name", "page_number", 
                    "routing_id_credit", "demand_account_credit", "routing_id_debit", 
                    "company_id_debit", "mutually_defined", "line_items"
                ]
                # Only include columns that exist in the dataframe
                available_columns = [col for col in column_order if col in df.columns]
                # Add any remaining columns
                remaining_columns = [col for col in df.columns if col not in available_columns]
                final_columns = available_columns + remaining_columns
                df[final_columns].to_excel(writer, index=False, sheet_name="raw")
            else:
                pd.DataFrame().to_excel(writer, index=False, sheet_name="raw")
            
            # Export analysis sheets
            for name, adf in analyses.items():
                sheet_name = name[:31]  # Excel sheet name limit
                if not adf.empty:
                    adf.to_excel(writer, index=False, sheet_name=sheet_name)
                else:
                    pd.DataFrame().to_excel(writer, index=False, sheet_name=sheet_name)
        
        return str(output_path)


    def _default_output_path(self, start_date: str, end_date: str) -> str:
        backend_dir = Path(__file__).resolve().parent
        fname = f"master_edi_export_{start_date}_to_{end_date}.xlsx"
        return str(backend_dir / "processed_data" / fname)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Load Master EDI JSON from Azure, analyze, and export to Excel")
    parser.add_argument("--start", required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="End date YYYY-MM-DD")
    parser.add_argument("--out", default=None, help="Optional Excel output path")
    args = parser.parse_args()

    loader = MASTER_EDI_DataLoader(args.start, args.end)
    records = loader._load_search_records(args.start, args.end)
    df = loader.to_dataframe(records)
    analyses = loader.analyze(df)

    excel_path = args.out or loader._default_output_path(args.start, args.end)
    path = loader.export_to_excel(df, analyses, excel_path)
    print(f"Exported Excel to: {path}")
    print(f"Rows exported: {len(df)}")


if __name__ == "__main__":
    main()
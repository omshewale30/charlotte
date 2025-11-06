"""Utilities to load AlignRx report records from Azure AI Search, convert to DataFrame, analyze, and export to Excel."""

import os
from datetime import datetime, date
from pathlib import Path
from typing import List, Dict

import pandas as pd
import openpyxl  
from azure.azure_alignRx_search_setup import AlignRxSearchService

class AlignRxDataLoader:
    def __init__(self, start_date: str, end_date: str):
        self.start_date = start_date
        self.end_date = end_date
        # Initialize Azure AI Search service (preferred data source)
    
        self.search_service = AlignRxSearchService()
        # No blob fallback for AlignRx flow
        


    def _parse_date(self, value: str) -> date:
        """Parse YYYY-MM-DD string to date."""
        return datetime.strptime(value, "%Y-%m-%d").date()


    def _within_range(self, d: str, start: date, end: date) -> bool:
        """Check if date string YYYY-MM-DD is within [start, end] inclusive."""
        try:
            return start <= self._parse_date(d) <= end
        except Exception:
            return False

    def _deduplicate_records(self, records: List[Dict]) -> List[Dict]:
        """
        Remove duplicate records based on pay_date, destination, and payment_amount.
        Uses a small tolerance for payment_amount to handle floating point precision issues.
        Keeps the first occurrence of each duplicate group.
        
        Args:
            records: List of record dictionaries
            
        Returns:
            Deduplicated list of records
        """
        if not records:
            return records
        
        # Tolerance for floating point comparison (0.01 cents)
        tolerance = 0.01
        
        # Normalize pay_date to string format for comparison
        # pay_date might be datetime, date, or string
        def normalize_date(d):
            if d is None:
                return None
            if isinstance(d, str):
                # Try to parse and normalize
                try:
                    dt = pd.to_datetime(d)
                    return dt.strftime('%Y-%m-%d') if hasattr(dt, 'strftime') else str(dt.date())
                except:
                    return str(d)
            elif hasattr(d, 'date'):  # datetime object
                return d.date().isoformat()
            elif hasattr(d, 'isoformat'):  # date object
                return d.isoformat()
            return str(d)
        
        # Use a dictionary keyed by (date, destination) to store lists of amounts
        # This allows O(1) lookup and O(n) overall performance
        seen_groups = {}  # {(date, destination): [amount1, amount2, ...]}
        deduplicated = []
        duplicates_removed = 0
        
        for record in records:
            pay_date = normalize_date(record.get('pay_date'))
            destination = record.get('destination')
            payment_amount = record.get('payment_amount')
            
            # Skip if any key field is missing
            if not all([pay_date, destination, payment_amount is not None]):
                # Keep records with missing fields (they can't be duplicates)
                deduplicated.append(record)
                continue
            
            # Create a key for grouping (date + destination)
            group_key = (pay_date, destination)
            
            # Check if we've seen a record with same date/destination and similar amount
            is_duplicate = False
            if group_key in seen_groups:
                # Check all amounts in this group for tolerance match
                for seen_amount in seen_groups[group_key]:
                    if abs(seen_amount - payment_amount) <= tolerance:
                        is_duplicate = True
                        duplicates_removed += 1
                        break
            
            if not is_duplicate:
                # Add to seen groups
                if group_key not in seen_groups:
                    seen_groups[group_key] = []
                seen_groups[group_key].append(payment_amount)
                deduplicated.append(record)
        
        if duplicates_removed > 0:
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Deduplication removed {duplicates_removed} duplicate record(s) based on pay_date, destination, and payment_amount")
        
        return deduplicated

    def _load_search_records(self, start_date: str, end_date: str) -> List[Dict]:
        """Query Azure AI Search for alignRx reports within [start_date, end_date].

        pay_date is stored as Edm.DateTimeOffset; filter must use ISO 8601 with timezone.
        """
        # Build DateTimeOffset range for entire days
        start_dt = f"{start_date}T00:00:00Z"
        end_dt = f"{end_date}T23:59:59Z"
        filter_expr = f"pay_date ge {start_dt} and pay_date le {end_dt}"

        # Page through results using skip/top
        batch_size = 1000
        skip = 0
        records: List[Dict] = []

        # Select only fields needed downstream; include all core fields
        select_fields = [
            "report_id",
            "source_file",
            "pay_date",
            "destination",
            "processing_fee",
            "payment_amount",
            "central_payments",
        ]

        while True:
            results = self.search_service.search_client.search( # type: ignore
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
        """Load AlignRx report records from Azure AI Search within the date range.

        The `pay_date` is expected in YYYY-MM-DD format.
        Note: Deduplication happens automatically in to_dataframe() method.
        """
        # Validate date inputs
        _ = self._parse_date(start_date)
        _ = self._parse_date(end_date)

        records = self._load_search_records(start_date, end_date)
        return records


    def to_dataframe(self, records: List[Dict]) -> pd.DataFrame:
        """Convert records to a pandas DataFrame and normalize types.
        
        Automatically deduplicates records based on pay_date, destination, and payment_amount
        before converting to DataFrame.
        """
        # Deduplicate records first to handle race condition duplicates
        records = self._deduplicate_records(records or [])
        
        df = pd.DataFrame(records)
        if df.empty:
            return df

        # Normalize types
        if "pay_date" in df.columns:
            df["pay_date"] = pd.to_datetime(df["pay_date"], errors="coerce").dt.date
        if "payment_amount" in df.columns:
            df["payment_amount"] = pd.to_numeric(df["payment_amount"], errors="coerce")
        return df


    def analyze(self, df: pd.DataFrame) -> Dict[str, pd.DataFrame]:
        """Compute aggregations for AlignRx reports with nested central payments."""
        if df.empty:
            empty = pd.DataFrame()
            return {
                "summary_totals": empty,
                "daily_totals": empty,
                "by_destination": empty,
                "by_sender": empty,
            }

        # Summary totals
        totals = pd.DataFrame({
            "count": [len(df)],
            "sum_payment_amount": [df["payment_amount"].sum(skipna=True) if "payment_amount" in df else 0.0],
            "avg_payment_amount": [df["payment_amount"].mean(skipna=True) if "payment_amount" in df else 0.0],
            "sum_processing_fee": [df["processing_fee"].sum(skipna=True) if "processing_fee" in df else 0.0],
            "avg_processing_fee": [df["processing_fee"].mean(skipna=True) if "processing_fee" in df else 0.0],
        })

        # Daily totals (payment and fee)
        if "pay_date" in df.columns:
            daily_pay = (
                df.dropna(subset=["pay_date"])  # type: ignore[arg-type]
                .groupby("pay_date", dropna=False)["payment_amount"]
                .sum(min_count=1)
                .reset_index()
                .rename(columns={"payment_amount": "sum_payment_amount"})
            )
            if "processing_fee" in df.columns:
                daily_fee = (
                    df.dropna(subset=["pay_date"])  # type: ignore[arg-type]
                    .groupby("pay_date", dropna=False)["processing_fee"]
                    .sum(min_count=1)
                    .reset_index()
                    .rename(columns={"processing_fee": "sum_processing_fee"})
                )
                daily = pd.merge(daily_pay, daily_fee, on="pay_date", how="outer")
            else:
                daily = daily_pay
        else:
            daily = pd.DataFrame()

        # By destination (payment amounts)
        if "destination" in df.columns:
            by_destination = (
                df.groupby("destination", dropna=False)["payment_amount"]
                .agg(["count", "sum", "mean"])
                .reset_index()
                .rename(columns={"sum": "sum_payment_amount", "mean": "avg_payment_amount"})
                .sort_values("sum_payment_amount", ascending=False)
            )
        else:
            by_destination = pd.DataFrame()

        # By sender from nested central_payments
        if "central_payments" in df.columns:
            # Expand list of dicts into rows
            rows = []
            for _, rec in df.iterrows():
                payments = rec.get("central_payments") or []
                if isinstance(payments, list):
                    for p in payments:
                        if isinstance(p, dict):
                            rows.append({
                                "sender": p.get("sender"),
                                "check_num": p.get("check_num"),
                                "amount": p.get("amount"),
                                "report_id": rec.get("report_id"),
                                "pay_date": rec.get("pay_date"),
                                "destination": rec.get("destination"),
                            })
            nested_df = pd.DataFrame(rows)
            if not nested_df.empty:
                by_sender = (
                    nested_df.groupby("sender", dropna=False)["amount"]
                    .agg(["count", "sum", "mean"])
                    .reset_index()
                    .rename(columns={"count": "num_checks", "sum": "sum_amount", "mean": "avg_amount"})
                    .sort_values("sum_amount", ascending=False)
                )
            else:
                by_sender = pd.DataFrame()
        else:
            by_sender = pd.DataFrame()

        return {
            "summary_totals": totals,
            "daily_totals": daily,
            "by_destination": by_destination,
            "by_sender": by_sender,
        }


    def export_to_excel(self, df: pd.DataFrame, analyses: Dict[str, pd.DataFrame], excel_path: str) -> str:
        """Export raw data and analyses to an Excel file with multiple sheets."""
        output_path = Path(excel_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Build an expanded view of central payments where each sender/check becomes its own row
        expanded_rows: List[Dict] = []
        if df is not None and not df.empty and "central_payments" in df.columns:
            for _, rec in df.iterrows():
                payments = rec.get("central_payments") or []
                if isinstance(payments, list) and payments:
                    for p in payments:
                        if not isinstance(p, dict):
                            continue
                        expanded_rows.append({
                            "report_id": rec.get("report_id"),
                            "pay_date": rec.get("pay_date"),
                            "destination": rec.get("destination"),
                            "payment_amount": rec.get("payment_amount"),
                            "sender": p.get("sender"),
                            "check_num": p.get("check_num"),
                            "amount": p.get("amount"),
                            "source_file": rec.get("source_file"),
                        })
        expanded_df = pd.DataFrame(expanded_rows)

        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            # Report-level data (one row per report) - only Destination, Pay Date, Payment Amount
            if df is not None and not df.empty:
                selected_cols = []
                rename_map: Dict[str, str] = {}
                if "destination" in df.columns:
                    selected_cols.append("destination")
                    rename_map["destination"] = "Destination"
                if "pay_date" in df.columns:
                    selected_cols.append("pay_date")
                    rename_map["pay_date"] = "Pay Date"
                if "payment_amount" in df.columns:
                    selected_cols.append("payment_amount")
                    rename_map["payment_amount"] = "Payment Amount"

                reports_df = df[selected_cols].rename(columns=rename_map) if selected_cols else pd.DataFrame()
            else:
                reports_df = pd.DataFrame()

            reports_df.to_excel(writer, index=False, sheet_name="reports")

            # Expanded central payments (one row per sender/check per report)
            (expanded_df if not expanded_df.empty else pd.DataFrame()).to_excel(writer, index=False, sheet_name="central_payments")

            # Analysis sheets
            for name, adf in analyses.items():
                (adf if adf is not None and not adf.empty else pd.DataFrame()).to_excel(writer, index=False, sheet_name=name[:31])
        return str(output_path)


    def _default_output_path(self, start_date: str, end_date: str) -> str:
        backend_dir = Path(__file__).resolve().parent
        fname = f"alignrx_export_{start_date}_to_{end_date}.xlsx"
        return str(backend_dir / "processed_data" / fname)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Load AlignRx JSON from Azure, analyze, and export to Excel")
    parser.add_argument("--start", required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="End date YYYY-MM-DD")
    parser.add_argument("--out", default=None, help="Optional Excel output path")
    args = parser.parse_args()

    loader = AlignRxDataLoader(args.start, args.end)
    records = loader._load_search_records(args.start, args.end)
    df = loader.to_dataframe(records)
    analyses = loader.analyze(df)

    excel_path = args.out or loader._default_output_path(args.start, args.end)
    path = loader.export_to_excel(df, analyses, excel_path)
    print(f"Exported Excel to: {path}")
    print(f"Rows exported: {len(df)}")


if __name__ == "__main__":
    main()
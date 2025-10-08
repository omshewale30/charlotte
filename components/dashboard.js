/**

 * need to create a dashboard page
 * the dashboard page will be the EDI data visualizations and excel export
 * 
 * Input- user can select the start date and end date for the data they want to visualize
 * The backend json-to-excel.py will be used to load the data into a pandas dataframe
 * The dataframe will be used to create the visualizations
 * The visualizations will be displayed in a chart or table
 * The user can download the data in excel format
 * 
 */
"use client";

import { useState, useRef, useEffect } from "react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { SendIcon, Loader2, Menu } from "lucide-react";
import { APIClient } from "@/lib/api-client";
import { useAuth } from "@/components/auth-context-msal";
import { azureCosmosClient } from "@/lib/azure-cosmos-client";


export default function Dashboard() {
    const { getAuthHeaders } = useAuth();
    const apiClient = new APIClient(getAuthHeaders);

    const [startDate, setStartDate] = useState("");
    const [endDate, setEndDate] = useState("");
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [result, setResult] = useState(null);

    const formatCurrency = (value) => {
        if (value === null || value === undefined || isNaN(Number(value))) return "-";
        return new Intl.NumberFormat(undefined, { style: 'currency', currency: 'USD', maximumFractionDigits: 2 }).format(Number(value));
    };

    const formatNumber = (value) => {
        if (value === null || value === undefined || isNaN(Number(value))) return "-";
        return new Intl.NumberFormat(undefined).format(Number(value));
    };

    const handleAnalyze = async () => {
        if (!startDate || !endDate) {
            setError("Please select a start and end date.");
            return;
        }
        setLoading(true);
        setError(null);
        try {
            const data = await apiClient.analyzeEdiRange({ start: startDate, end: endDate });
            setResult(data);
        } catch (e) {
            setError(e.message || "Failed to load analysis");
        } finally {
            setLoading(false);
        }
    };

    const handleDownload = async () => {
        if (!startDate || !endDate) {
            setError("Please select a start and end date.");
            return;
        }
        setError(null);
        try {
            const blob = await apiClient.downloadEdiExcel({ start: startDate, end: endDate });
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `edi_export_${startDate}_to_${endDate}.xlsx`;
            document.body.appendChild(a);
            a.click();
            a.remove();
            window.URL.revokeObjectURL(url);
        } catch (e) {
            setError(e.message || "Failed to download Excel");
        }
    };

    return (
        <div className="max-w-5xl mx-auto p-6 space-y-6">
            <h1 className="text-2xl font-semibold">Dashboard</h1>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 items-end">
                <div className="flex flex-col gap-2">
                    <label className="text-sm text-muted-foreground">Start date</label>
                    <input
                        type="date"
                        value={startDate}
                        onChange={(e) => setStartDate(e.target.value)}
                        className="border border-input bg-background text-foreground rounded-md px-3 py-2"
                    />
                </div>
                <div className="flex flex-col gap-2">
                    <label className="text-sm text-muted-foreground">End date</label>
                    <input
                        type="date"
                        value={endDate}
                        onChange={(e) => setEndDate(e.target.value)}
                        className="border border-input bg-background text-foreground rounded-md px-3 py-2"
                    />
                </div>
                <div className="flex gap-2">
                    <Button onClick={handleAnalyze} disabled={loading || !startDate || !endDate}>
                        {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : "Load"}
                    </Button>
                    <Button variant="outline" onClick={handleDownload} disabled={!startDate || !endDate}>
                        Download Excel
                    </Button>
                </div>
            </div>

            {error && (
                <div className="text-red-500 text-sm">{error}</div>
            )}

            {result && (
                <div className="space-y-6">
                    {/* KPI cards */}
                    {(() => {
                        const summary = (result.analyses?.summary_totals || [])[0] || {};
                        return (
                            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                                <div className="border rounded-md p-4">
                                    <div className="text-sm text-muted-foreground">Rows</div>
                                    <div className="text-xl font-medium">{formatNumber(result.row_count)}</div>
                                </div>
                                <div className="border rounded-md p-4">
                                    <div className="text-sm text-muted-foreground">Total Amount</div>
                                    <div className="text-xl font-medium">{formatCurrency(summary.sum_amount)}</div>
                                </div>
                                <div className="border rounded-md p-4">
                                    <div className="text-sm text-muted-foreground">Average Amount</div>
                                    <div className="text-xl font-medium">{formatCurrency(summary.avg_amount)}</div>
                                </div>
                                <div className="border rounded-md p-4">
                                    <div className="text-sm text-muted-foreground">Date Range</div>
                                    <div className="text-sm font-medium">{result.range?.start} → {result.range?.end}</div>
                                </div>
                            </div>
                        );
                    })()}

                    {/* Daily Totals Table */}
                    <div className="border rounded-md">
                        <div className="p-4 border-b">
                            <div className="text-lg font-semibold">Daily Totals</div>
                            <div className="text-xs text-muted-foreground">Sum of amounts per day (first 60 rows)</div>
                        </div>
                        <div className="max-h-96 overflow-auto">
                            <table className="w-full text-sm">
                                <thead className="sticky top-0 bg-background border-b">
                                    <tr>
                                        <th className="text-left px-4 py-2 w-1/2">Date</th>
                                        <th className="text-left px-4 py-2">Sum Amount</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {(result.analyses?.daily_totals || [])
                                        .slice()
                                        .sort((a, b) => (a.effective_date || "").localeCompare(b.effective_date || ""))
                                        .slice(0, 60)
                                        .map((row, idx) => (
                                            <tr key={`daily-${idx}`} className="border-b last:border-0">
                                                <td className="px-4 py-2">{row.effective_date || "-"}</td>
                                                <td className="px-4 py-2">{formatCurrency(row.sum_amount)}</td>
                                            </tr>
                                        ))}
                                </tbody>
                            </table>
                        </div>
                    </div>

                    {/* By Originator Table */}
                    <div className="border rounded-md">
                        <div className="p-4 border-b">
                            <div className="text-lg font-semibold">By Originator</div>
                            <div className="text-xs text-muted-foreground">Top 50 by total amount</div>
                        </div>
                        <div className="max-h-96 overflow-auto">
                            <table className="w-full text-sm">
                                <thead className="sticky top-0 bg-background border-b">
                                    <tr>
                                        <th className="text-left px-4 py-2">Originator</th>
                                        <th className="text-left px-4 py-2">Count</th>
                                        <th className="text-left px-4 py-2">Sum Amount</th>
                                        <th className="text-left px-4 py-2">Avg Amount</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {(result.analyses?.by_originator || [])
                                        .slice()
                                        .sort((a, b) => Number(b.sum_amount || 0) - Number(a.sum_amount || 0))
                                        .slice(0, 50)
                                        .map((row, idx) => (
                                            <tr key={`org-${idx}`} className="border-b last:border-0">
                                                <td className="px-4 py-2">{row.originator || "-"}</td>
                                                <td className="px-4 py-2">{formatNumber(row.count)}</td>
                                                <td className="px-4 py-2">{formatCurrency(row.sum_amount)}</td>
                                                <td className="px-4 py-2">{formatCurrency(row.avg_amount)}</td>
                                            </tr>
                                        ))}
                                </tbody>
                            </table>
                        </div>
                    </div>

                    {/* By Receiver Table */}
                    <div className="border rounded-md">
                        <div className="p-4 border-b">
                            <div className="text-lg font-semibold">By Receiver</div>
                            <div className="text-xs text-muted-foreground">Top 50 by total amount</div>
                        </div>
                        <div className="max-h-96 overflow-auto">
                            <table className="w-full text-sm">
                                <thead className="sticky top-0 bg-background border-b">
                                    <tr>
                                        <th className="text-left px-4 py-2">Receiver</th>
                                        <th className="text-left px-4 py-2">Count</th>
                                        <th className="text-left px-4 py-2">Sum Amount</th>
                                        <th className="text-left px-4 py-2">Avg Amount</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {(result.analyses?.by_receiver || [])
                                        .slice()
                                        .sort((a, b) => Number(b.sum_amount || 0) - Number(a.sum_amount || 0))
                                        .slice(0, 50)
                                        .map((row, idx) => (
                                            <tr key={`rcv-${idx}`} className="border-b last:border-0">
                                                <td className="px-4 py-2">{row.receiver || "-"}</td>
                                                <td className="px-4 py-2">{formatNumber(row.count)}</td>
                                                <td className="px-4 py-2">{formatCurrency(row.sum_amount)}</td>
                                                <td className="px-4 py-2">{formatCurrency(row.avg_amount)}</td>
                                            </tr>
                                        ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}

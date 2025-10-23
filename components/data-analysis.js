/**
 * Data Analysis component for the application
 * Contains the logic for the data analysis page
 * Includes visualizations, tables, and Excel export functionality
 * Uses the APIClient to fetch data from the backend
 * Uses the useAuth hook to get the authentication headers
 */
"use client";

import { useState, useRef, useEffect } from "react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { SendIcon, Loader2, Menu } from "lucide-react";
import { APIClient } from "@/lib/api-client";
import { useAuth } from "@/components/auth-context-msal";
import { azureCosmosClient } from "@/lib/azure-cosmos-client";
import {
    ResponsiveContainer,
    BarChart,
    Bar,
    XAxis,
    YAxis,
    Tooltip,
    CartesianGrid,
    PieChart,
    Pie,
    Cell,
    Legend
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";


export default function DataAnalysis() {
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
                    {/* Charts */}
                    {(() => {
                        const daily = (result.analyses?.daily_totals || [])
                            .slice()
                            .sort((a, b) => (a.effective_date || "").localeCompare(b.effective_date || ""));
                        const byOriginatorRaw = (result.analyses?.by_originator || []);
                        const byReceiverRaw = (result.analyses?.by_receiver || []);

                        // Aggregate long tails into an "Other" slice to reduce label clutter
                        const topWithOther = (arr, nameKey) => {
                            const sorted = arr.slice().sort((a, b) => Number(b.sum_amount || 0) - Number(a.sum_amount || 0));
                            const TOP_N = 8;
                            const top = sorted.slice(0, TOP_N);
                            const rest = sorted.slice(TOP_N);
                            const otherTotal = rest.reduce((acc, r) => acc + Number(r.sum_amount || 0), 0);
                            return otherTotal > 0
                                ? [...top, { [nameKey]: "Other", sum_amount: otherTotal }]
                                : top;
                        };

                        const byOriginator = topWithOther(byOriginatorRaw, "originator");
                        const byReceiver = topWithOther(byReceiverRaw, "receiver");

                        const CAROLINA = "#4B9CD3";
                        const CAROLINA_DARK = "#2B6FA6";
                        const ACCENTS = [
                            // High-contrast, UNC-leaning palette (blues/teals with clear accents)
                            "#0F3D63", // deep navy
                            "#4B9CD3", // carolina blue
                            "#1E40AF", // indigo
                            "#10B981", // emerald
                            "#F59E0B", // amber accent
                            "#2563EB", // blue
                            "#22C55E", // green
                            "#F97316", // orange accent
                            "#111827", // near-black
                            "#06B6D4", // cyan
                            "#D97706", // dark amber
                            "#93C5FD"  // light blue
                        ];

                        // Custom external pie label positioned with radial offset
                        const RADIAN = Math.PI / 180;
                        const renderExternalLabel = ({ cx, cy, midAngle, outerRadius, percent, name }) => {
                            if (!percent || percent < 0.03) return null; // hide ultra-small labels
                            const radius = outerRadius + 18;
                            const x = cx + radius * Math.cos(-midAngle * RADIAN);
                            const y = cy + radius * Math.sin(-midAngle * RADIAN);
                            const labelText = `${(name || "").toString().slice(0, 20)} ${(percent * 100).toFixed(0)}%`;
                            const textAnchor = x > cx ? "start" : "end";
                            return (
                                <text x={x} y={y} fill="#334155" textAnchor={textAnchor} dominantBaseline="central" style={{ fontSize: 12 }}>
                                    {labelText}
                                </text>
                            );
                        };

                        return (
                            <div className="grid grid-cols-1 gap-6">
                                <Card className="border border-slate-200/60">
                                    <CardHeader>
                                        <CardTitle className="text-lg">Daily Amounts</CardTitle>
                                    </CardHeader>
                                    <CardContent className="h-72">
                                        <ResponsiveContainer width="100%" height="100%">
                                            <BarChart data={daily} margin={{ top: 8, right: 8, left: 0, bottom: 8 }}>
                                                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                                                <XAxis dataKey="effective_date" tick={{ fontSize: 12 }} interval={Math.ceil(daily.length / 7)} />
                                                <YAxis tick={{ fontSize: 12 }} tickFormatter={(v) => `$${Number(v).toLocaleString()}`} />
                                                <Tooltip formatter={(v) => [`$${Number(v).toLocaleString(undefined, { maximumFractionDigits: 2 })}`, "Sum Amount"]} labelFormatter={(l) => `Date: ${l}`} />
                                                <Bar dataKey="sum_amount" fill={CAROLINA} radius={[4, 4, 0, 0]}>
                                                </Bar>
                                            </BarChart>
                                        </ResponsiveContainer>
                                    </CardContent>
                                </Card>

                                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                    <Card className="border border-slate-200/60">
                                        <CardHeader>
                                            <CardTitle className="text-lg">By Originator</CardTitle>
                                        </CardHeader>
                                        <CardContent className="h-72">
                                            <ResponsiveContainer width="100%" height="100%">
                                                <PieChart>
                                                    <Tooltip formatter={(v, n, e) => [`$${Number(v).toLocaleString(undefined, { maximumFractionDigits: 2 })}`, e?.payload?.originator || ""]} />
                                                    <Legend verticalAlign="bottom" height={24} wrapperStyle={{ fontSize: 12 }} />
                                                    <Pie data={byOriginator} dataKey="sum_amount" nameKey="originator" cx="50%" cy="50%" outerRadius={88} minAngle={5} paddingAngle={2} labelLine={{ stroke: "#cbd5e1" }} label={renderExternalLabel}>
                                                        {byOriginator.map((_, idx) => (
                                                            <Cell key={`org-slice-${idx}`} fill={ACCENTS[idx % ACCENTS.length]} stroke="#ffffff" strokeWidth={1} />
                                                        ))}
                                                    </Pie>
                                                </PieChart>
                                            </ResponsiveContainer>
                                        </CardContent>
                                    </Card>

                                    <Card className="border border-slate-200/60">
                                        <CardHeader>
                                            <CardTitle className="text-lg">By Receiver</CardTitle>
                                        </CardHeader>
                                        <CardContent className="h-72">
                                            <ResponsiveContainer width="100%" height="100%">
                                                <PieChart>
                                                    <Tooltip formatter={(v, n, e) => [`$${Number(v).toLocaleString(undefined, { maximumFractionDigits: 2 })}`, e?.payload?.receiver || ""]} />
                                                    <Legend verticalAlign="bottom" height={24} wrapperStyle={{ fontSize: 12 }} />
                                                    <Pie data={byReceiver} dataKey="sum_amount" nameKey="receiver" cx="50%" cy="50%" outerRadius={88} minAngle={5} paddingAngle={2} labelLine={{ stroke: "#cbd5e1" }} label={renderExternalLabel}>
                                                        {byReceiver.map((_, idx) => (
                                                            <Cell key={`rcv-slice-${idx}`} fill={ACCENTS[idx % ACCENTS.length]} stroke="#ffffff" strokeWidth={1} />
                                                        ))}
                                                    </Pie>
                                                </PieChart>
                                            </ResponsiveContainer>
                                        </CardContent>
                                    </Card>
                                </div>
                            </div>
                        );
                    })()}
                    {/* KPI cards */}


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

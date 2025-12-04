"use client";
import { useEffect, useState } from "react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, AreaChart, Area } from 'recharts';

interface BetResult {
  date: string;
  tournament: string;
  bet_on: string;
  odds: number;
  result: string;
  profit: number;
}

export default function ResultsPage() {
  const [history, setHistory] = useState<BetResult[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("http://127.0.0.1:8000/history")
      .then(res => res.json())
      .then(data => {
        // Calculate cumulative profit for the chart
        let runningTotal = 0;
        const chartData = data.map((item: BetResult) => {
          runningTotal += item.profit;
          return { ...item, cumulative: runningTotal };
        }).reverse(); // API gives newest first, chart needs oldest first
        
        setHistory(chartData.reverse()); // Set table to newest first
        setLoading(false);
      })
      .catch(err => console.error(err));
  }, []);

  // Stats
  const totalBets = history.length;
  const netProfit = history.reduce((sum, item) => sum + item.profit, 0);
  const wins = history.filter(h => h.result === 'WIN').length;
  const winRate = totalBets > 0 ? (wins / totalBets) * 100 : 0;
  const roi = totalBets > 0 ? (netProfit / totalBets) * 100 : 0; // Assuming 1 unit stakes

  // Chart Data (Need oldest to newest)
  const chartData = [...history].reverse().map((h: any) => ({
    date: h.date,
    profit: h.cumulative
  }));

  return (
    <main className="animate-fade-in space-y-8">
      {/* HERO STATS */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <StatCard label="Net Profit" value={`${netProfit > 0 ? '+' : ''}${netProfit.toFixed(2)}u`} color={netProfit >= 0 ? "text-green-400" : "text-red-400"} />
        <StatCard label="Win Rate" value={`${winRate.toFixed(1)}%`} />
        <StatCard label="ROI" value={`${roi.toFixed(1)}%`} color={roi >= 0 ? "text-green-400" : "text-red-400"} />
        <StatCard label="Total Bets" value={totalBets.toString()} />
      </div>

      {/* PROFIT CHART */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 h-80">
        <h3 className="text-gray-400 text-sm font-bold mb-4 uppercase tracking-wider">Profit Growth</h3>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={chartData}>
            <defs>
              <linearGradient id="colorProfit" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#22c55e" stopOpacity={0.3}/>
                <stop offset="95%" stopColor="#22c55e" stopOpacity={0}/>
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#333" vertical={false} />
            <XAxis dataKey="date" stroke="#666" fontSize={12} tickLine={false} axisLine={false} />
            <YAxis stroke="#666" fontSize={12} tickLine={false} axisLine={false} />
            <Tooltip 
              contentStyle={{ backgroundColor: '#111', borderColor: '#333', borderRadius: '8px' }}
              itemStyle={{ color: '#fff' }}
            />
            <Area type="monotone" dataKey="profit" stroke="#22c55e" strokeWidth={3} fillOpacity={1} fill="url(#colorProfit)" />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* HISTORY TABLE */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
        <table className="w-full text-sm text-left">
          <thead className="bg-gray-950 text-gray-400 font-medium">
            <tr>
              <th className="px-6 py-4">Date</th>
              <th className="px-6 py-4">Tournament</th>
              <th className="px-6 py-4">Pick</th>
              <th className="px-6 py-4">Odds</th>
              <th className="px-6 py-4">Result</th>
              <th className="px-6 py-4 text-right">Profit</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800">
            {history.map((row, i) => (
              <tr key={i} className="hover:bg-gray-800/50 transition">
                <td className="px-6 py-4 text-gray-500">{row.date}</td>
                <td className="px-6 py-4 text-gray-300">{row.tournament}</td>
                <td className="px-6 py-4 font-bold text-white">{row.bet_on}</td>
                <td className="px-6 py-4 text-blue-400">@{row.odds.toFixed(2)}</td>
                <td className="px-6 py-4">
                  <span className={`px-2 py-1 rounded text-xs font-bold ${row.result === 'WIN' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'}`}>
                    {row.result}
                  </span>
                </td>
                <td className={`px-6 py-4 text-right font-mono font-bold ${row.profit > 0 ? 'text-green-400' : 'text-red-400'}`}>
                  {row.profit > 0 ? '+' : ''}{row.profit.toFixed(2)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </main>
  );
}

function StatCard({ label, value, color = "text-white" }: { label: string, value: string, color?: string }) {
  return (
    <div className="bg-gray-900 border border-gray-800 p-6 rounded-xl">
      <div className="text-gray-500 text-xs font-bold uppercase tracking-wider mb-1">{label}</div>
      <div className={`text-3xl font-bold ${color}`}>{value}</div>
    </div>
  );
}